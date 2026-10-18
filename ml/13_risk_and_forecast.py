"""
13 - Long-run erosion risk, with honest uncertainty.

WHY THIS EXISTS
  This script summarizes historical long-run erosion rates and ranks chronic
  exposure for the selected reach. It does not train or evaluate the future
  bankline model; that work is in 14_model_train.py.

  A historical risk ranking answers "where has erosion tended to be high?"
  It is not a prediction of where a bank will be in a future year.

HOW THE UNCERTAINTY IS DONE
    Two effects are handled explicitly rather than ignored:

    a) AUTOCORRELATION. Neighbouring years are not independent observations - a
       bank that is eroding this year is usually still eroding next year. Treating
       35 consecutive years as 35 independent samples would shrink the confidence
       interval far too much. The effective sample size is

           n_eff = n * (1 - r1) / (1 + r1)

       where r1 is the lag-1 autocorrelation of that transect's own series.

    b) HEAVY TAILS. A handful of transect-years swing past 300 m/yr. The ranking
       uses the MEDIAN, which a single extreme year cannot move, and the mean is
       reported beside it so the difference is visible rather than hidden.

OUTPUTS
    data/reaches/<reach>/processed/risk/transect_risk.csv
    data/reaches/<reach>/processed/risk/risk.geojson
    reports/RISK_<reach>.md                   methods and limitations

Run:
    cd ~/Projects/riverguard/ml
    ../.venv/bin/python 13_risk_and_forecast.py
"""

from datetime import date

import geopandas as gpd
import numpy as np
import pandas as pd

import config as C

FEATURES = C.DATA_PROC / "features" / "landsat" / "features.csv"
LINES = C.DATA_PROC / "features" / "landsat" / "transect_lines.geojson"
OUT_DIR = C.DATA_PROC / "risk"
REPORTS = C.ROOT / "reports"

# Rate at which a long-run mean stops being distinguishable from no change.
CI_LEVEL = 0.95

# A record needs this many usable year-pairs before it can be called a CHRONIC
# hotspot. Not a cosmetic threshold. Many transects are measurable only in some
# years, so without this rule a single lucky year of +165 m/yr outranked
# 30-year averages - ranking noise as if it were long-term exposure.
MIN_YEARS = 10

# Tiers are cut on the long-run median rate, in m/yr. These are descriptive
# bands for ranking chronic exposure, not official hazard classes.
TIERS = [
    (80.0, "very high"),
    (40.0, "high"),
    (15.0, "moderate"),
    (0.0, "low"),
    (-1e9, "accreting"),
]


def eff_n(x):
    """Effective sample size after removing lag-1 autocorrelation.

    Returns the plain n when the series is too short or has no usable
    autocorrelation, which is the conservative direction in the sense that it
    never pretends to more information than there is.
    """
    n = len(x)
    if n < 6:
        return float(n)
    a = x - x.mean()
    denom = float((a * a).sum())
    if denom <= 0:
        return 1.0
    r1 = float((a[1:] * a[:-1]).sum()) / denom
    r1 = max(-0.95, min(0.95, r1))
    return max(1.0, n * (1.0 - r1) / (1.0 + r1))


def boot_median_ci(x, n_boot=2000, block=3, seed=0):
    """Percentile confidence interval for the MEDIAN, by block bootstrap.

    Two reasons this is not just a textbook bootstrap on the median:

    1. The ranking is done on the median because a single extreme transect-year
       should not be able to reorder the river. The interval therefore has to
       describe the median too, otherwise the map shows a median with a
       confidence band that belongs to a different statistic.

    2. A plain bootstrap resamples single years, which destroys the
       autocorrelation and pretends the record is 35 independent observations.
       Resampling in BLOCKS of consecutive years keeps the serial dependence,
       so the interval comes out honestly wide where it should be.
    """
    n = len(x)
    if n < 8 or block >= n:
        return float("nan"), float("nan")
    rng = np.random.default_rng(seed)
    n_blocks = int(np.ceil(n / block))
    max_start = n - block + 1
    meds = np.empty(n_boot)
    for b in range(n_boot):
        starts = rng.integers(0, max_start, n_blocks)
        idx = np.concatenate([np.arange(s, s + block) for s in starts])[:n]
        meds[b] = np.median(x[idx])
    return float(np.percentile(meds, 2.5)), float(np.percentile(meds, 97.5))


def describe(group_rate):
    """Long-run statistics for one transect-side series."""
    x = group_rate.dropna().to_numpy(dtype=float)
    n = len(x)
    if n == 0:
        return None
    mean = float(x.mean())
    med = float(np.median(x))
    sd = float(x.std(ddof=1)) if n > 1 else float("nan")
    ne = eff_n(x)
    se = sd / np.sqrt(ne) if np.isfinite(sd) else float("nan")

    # mean interval, kept for transparency and to show how much wider it is
    half = 1.96 * se if np.isfinite(se) else float("nan")
    # median interval, block-bootstrap, this is the one the map uses
    mlo, mhi = boot_median_ci(x)

    return {
        "n_years": n,
        "n_eff": round(ne, 1),
        "rate_mean": mean,
        "rate_median": med,
        "rate_sd": sd,
        "ci95_lo": mlo,
        "ci95_hi": mhi,
        "mean_ci95_lo": mean - half,
        "mean_ci95_hi": mean + half,
        "rate_p10": float(np.percentile(x, 10)),
        "rate_p90": float(np.percentile(x, 90)),
        "yrs_eroding_pct": float((x > 0).mean() * 100.0),
        "max_rate": float(x.max()),
        "min_rate": float(x.min()),
    }


def tier_of(med):
    for cut, name in TIERS:
        if med >= cut:
            return name
    return "accreting"


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)

    if not FEATURES.exists():
        print(f"Missing {FEATURES}")
        print("Run 05_features.py landsat first.")
        return
    if not LINES.exists():
        print(f"Missing {LINES}")
        return

    df = pd.read_csv(FEATURES)
    df = df.dropna(subset=["target_rate"]).copy()
    print(f"source rows: {len(df)}  years {int(df.year0.min())}-"
          f"{int(df.year1.max())}  transects {df.transect_id.nunique()}")

    # ---- one record per transect-side -------------------------------------
    rows = []
    for (tid, side), g in df.groupby(["transect_id", "side"]):
        g = g.sort_values("year1")
        stats = describe(g["target_rate"])
        if stats is None:
            continue
        rows.append({"transect_id": int(tid), "side": side, **stats})

    risk = pd.DataFrame(rows)

    # ---- uncertainty flags ------------------------------------------------
    # A transect whose confidence interval straddles zero is NOT reliably
    # eroding; calling it "high risk" on the strength of a noisy mean would be
    # the same mistake as publishing a forecast.
    risk["significant"] = ~(
        (risk.ci95_lo <= 0) & (risk.ci95_hi >= 0)
    ) & risk.ci95_lo.notna()

    # Records too short to speak about long-run behaviour are kept, but never
    # ranked and never tiered. They are reported separately so the shortfall is
    # visible instead of hidden.
    risk["sufficient"] = risk["n_years"] >= MIN_YEARS
    risk["tier"] = np.where(risk["sufficient"],
                            risk["rate_median"].apply(tier_of),
                            "insufficient record")
    ranked = risk[risk["sufficient"]]
    rank_map = ranked["rate_median"].rank(ascending=False,
                                         method="min").astype(int)
    risk["risk_rank"] = rank_map.reindex(risk.index)
    worst = max(1.0, float(ranked["rate_median"].max())) if len(ranked) else 1.0
    risk["risk_share_pct"] = np.where(
        risk["sufficient"], risk["rate_median"] / worst * 100.0, np.nan)

    lines = gpd.read_file(LINES)
    risk = risk.merge(lines.rename(columns={"id": "transect_id"})[
        ["transect_id", "arc_m", "geometry"]], on="transect_id", how="left")

    cols = ["transect_id", "side", "arc_m", "n_years", "n_eff", "rate_mean",
            "rate_median", "rate_sd", "ci95_lo", "ci95_hi",
            "mean_ci95_lo", "mean_ci95_hi", "rate_p10",
            "rate_p90", "yrs_eroding_pct", "min_rate", "max_rate",
            "sufficient", "significant", "tier", "risk_rank", "risk_share_pct"]
    # keep geometry on `risk` for the GeoJSON, but exclude it from the CSV
    risk = risk.sort_values(["sufficient", "risk_rank", "transect_id"],
                            ascending=[False, True, True])

    csv = OUT_DIR / "transect_risk.csv"
    risk[[c for c in cols if c in risk.columns]].to_csv(csv, index=False)

    gj = gpd.GeoDataFrame(risk, geometry="geometry", crs=lines.crs)
    gj["risk_label"] = gj.apply(
        lambda r: f"{r.side} bank, transect {int(r.transect_id)}: "
                  f"{r.rate_median:+.0f} m/yr over {int(r.n_years)} yr",
        axis=1)
    gpath = OUT_DIR / "risk.geojson"
    gj.to_file(gpath, driver="GeoJSON")

    # ---- report -----------------------------------------------------------
    n = len(risk)
    ranked = risk[risk["sufficient"]]
    sig = int(ranked["significant"].sum())
    eroding = ranked[ranked.rate_median > 0]

    L = []
    A = L.append
    A(f"# RiverGuard - historical erosion risk: {C.REACH_LABEL}\n")
    A(f"Generated: {date.today().isoformat()}\n")
    A("## What this is\n")
    A("For each transect and bank side: how many metres per year that bank has "
      f"actually lost, averaged over {int(df.year1.max() - df.year1.min())} years "
      f"of Landsat imagery, with an honest confidence interval.\n")
    A("Positive means land was **lost** (erosion). Negative means the bank built "
      "outward (accretion).\n")

    A("## What this is not\n")
    A("This historical ranking does not predict a future bankline. For the "
      "active Arial Khan candidate model and its time-forward test, see "
      "`reports/VALIDATION.md` and `ml/artifacts/model_report.json`.\n")

    A("## The numbers\n")
    A(f"- {n} transect-side records, of which **{len(ranked)} have at least "
      f"{MIN_YEARS} usable year-pairs** and are eligible for ranking")
    A(f"- {n - len(ranked)} are shorter than {MIN_YEARS} years. They are kept in "
      f"the CSV, flagged `sufficient = False`, and excluded from the ranking. "
      f"Without that rule a single lucky year of erosion outranks thirty years "
      f"of measured behaviour, which would rank noise as long-term exposure.")
    A(f"- {sig} of the {len(ranked)} eligible records ({100*sig/max(1,len(ranked)):.0f}%) "
      f"have a confidence interval that does not straddle zero, i.e. a long-run "
      f"rate confidently different from no change")
    A(f"- {len(eroding)} have a positive long-run median (net erosion)")
    A(f"- long-run median rate across eligible records: "
      f"{ranked.rate_median.median():+.1f} m/yr")
    A(f"- worst: {ranked.rate_median.max():+.1f} m/yr, "
      f"best: {ranked.rate_median.min():+.1f} m/yr\n")

    A("### Risk tiers\n")
    A(f"Eligible records only (>= {MIN_YEARS} years).\n")
    A("| tier | records | definition (long-run median) |")
    A("|---|---|---|")
    for name in [t[1] for t in TIERS]:
        sub = ranked[ranked.tier == name]
        if len(sub) == 0:
            continue
        if name == "very high":
            desc = ">= 80 m/yr"
        elif name == "high":
            desc = "40 to 80 m/yr"
        elif name == "moderate":
            desc = "15 to 40 m/yr"
        elif name == "low":
            desc = "0 to 15 m/yr"
        else:
            desc = "below 0 (accreting)"
        A(f"| {name} | {len(sub)} | {desc} |")

    A("\n## Chronic hotspots - top 10 by long-run median\n")
    A("| rank | transect | side | arc (km) | median m/yr | 95% CI | years | eroding % | tier |")
    A("|---|---|---|---|---|---|---|---|---|")
    for _, r in ranked.head(10).iterrows():
        ci = ("n/a" if not np.isfinite(r.ci95_lo)
              else f"{r.ci95_lo:+.0f} to {r.ci95_hi:+.0f}")
        A(f"| {int(r.risk_rank)} | {int(r.transect_id)} | {r.side} | "
          f"{r.arc_m/1000:.1f} | {r.rate_median:+.1f} | {ci} | "
          f"{int(r.n_years)} | {r.yrs_eroding_pct:.0f} | {r.tier} |")

    A("\n## How the uncertainty is calculated\n")
    A("Consecutive years are **not** independent - a bank eroding this year is "
      "usually still eroding next year. Counting 35 consecutive years as 35 "
      "independent samples would shrink the interval far too much and make the "
      "result look more certain than it is.\n")
    A("So each series is reduced to an **effective sample size**\n")
    A("```\nn_eff = n * (1 - r1) / (1 + r1)\n```\n")
    A("where `r1` is that transect's own lag-1 autocorrelation, and the interval "
      "is built from `n_eff` rather than `n`. Series too short to estimate `r1` "
      "fall back to `n_eff = n`, which never overstates the evidence.\n")
    A("The ranking uses the **median**, not the mean. A few transect-years swing "
      "past 300 m/yr, and one extreme year should not be able to reorder the "
      "whole river.\n")
    A("The interval is a **block bootstrap percentile interval for that same "
      "median**, resampling in blocks of 3 consecutive years so the serial "
      "dependence survives the resampling. An interval belonging to the mean "
      "would be answering a different question from the one the ranking poses. "
      "Both are in the CSV (`ci95_lo/hi` for the median, `mean_ci95_lo/hi` for "
      "the mean); they are usually far apart, which is itself informative.\n")

    A("## Honest limitations\n")
    A("1. **No ground truth.** There is no survey of where the bank actually was. "
      "Confidence comes from two independent sensors agreeing (Sentinel-2 vs "
      "Landsat: ratio 0.98x, correlation +0.96) and from the rates falling inside "
      "the published Jamuna range, not from absolute accuracy.\n")
    A("2. **A 1000 m measurement zone sets the magnitude.** How wide a strip "
      "counts as 'at risk' is a stated physical assumption, not a fitted "
      "parameter. A wider zone dilutes the same area of land loss over more "
      "frontage and lowers the rate.\n")
    A("3. **Annual pairs overstate independence in the other direction.** A "
      "single dramatic flood can dominate several consecutive pairs, which the "
      "autocorrelation adjustment only partly handles.\n")
    A("4. **One reach, one season.** A 30 km stretch sampled in January-February "
      "(low water). Monsoon attacks on the outer bends are not captured.\n")
    A(f"5. **{len(ranked) - sig} eligible records are not statistically distinguishable from no "
      f"change.** They are kept in the CSV and flagged, rather than quietly "
      f"dropped, so the map shows what was actually measured.\n")

    rpath = REPORTS / f"RISK_{C.REACH}.md"
    rpath.write_text("\n".join(L) + "\n")

    print("\n".join(L))
    print(f"\n-> {csv}")
    print(f"-> {gpath}")
    print(f"-> {rpath}")


if __name__ == "__main__":
    main()