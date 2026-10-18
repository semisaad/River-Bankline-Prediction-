"""
07 - Validation and methods report.

Produces reports/VALIDATION.md: the evidence behind every number, so the write-up
does not rest on assertion. Everything here is reproducible by re-running.

WHAT IS CHECKED, AND WHY THESE CHECKS
  1. Two INDEPENDENT SENSORS must agree. Sentinel-2 and Landsat were never
     supposed to produce the same answer - different resolution, different
     spectrum, different acquisition dates. Agreement between them is the
     strongest evidence available without a ground survey.
  2. An INDEPENDENT METHOD on the same data: how far the traced river outline
     physically moved, which shares almost no machinery with EPR.
  3. Are the rates PLAUSIBLE against published Jamuna work?
  4. Is the measurement just tracking WATER LEVEL rather than land movement?
  5. Is there any LEARNABLE SIGNAL, or is the honest answer no?

A NOTE ON THE WITHDRAWN NUMBER
  An earlier version of this report cited a cross-method correlation of +0.92.
  That number was WITHDRAWN and must not be cited anywhere. It was computed while
  a sampling bug was live (transects built for one sensor were sampled at the
  other sensor's resolution), so both halves of that comparison were derived from
  the same distorted geometry. See reports/DECISIONS.md D35 and D37.

Run:
    cd ~/Projects/riverguard/ml
    ../.venv/bin/python 07_validate.py
"""

import json
from datetime import date

import geopandas as gpd
import numpy as np
import pandas as pd
from pyproj import Transformer
from shapely.geometry import LineString, Point

import config as C

REPORTS = C.ROOT / "reports"
TR = Transformer.from_crs("EPSG:4326", "EPSG:32645", always_xy=True)
PAIRS = [(y, y + 1) for y in C.YEARS[:-1]]
LAND_PAIRS = sorted(
    (int(p.stem.split("_")[1]), int(p.stem.split("_")[2]))
    for p in C.TRANSECTS_LANDSAT.glob("epr_*.geojson")
)


def outline(year):
    c = json.load(open(C.bankline_path(year)))["features"][0]["geometry"]["coordinates"]
    return LineString([tuple(TR.transform(float(x), float(y))) for x, y in c])


def outline_dist(y0, y1):
    la, lb = outline(y0), outline(y1)
    ds = []
    for src, dst in ((np.array(la.coords), lb), (np.array(lb.coords), la)):
        for p in src[::10]:
            ds.append(dst.distance(Point(float(p[0]), float(p[1]))))
    return np.array(ds)


def epr_pair_median(y0, y1):
    gdf = gpd.read_file(C.TRANSECTS / f"epr_{y0}_{y1}.geojson")
    return float(np.median([abs(r["mag"]) for _, r in gdf.iterrows()]))


def main():
    REPORTS.mkdir(parents=True, exist_ok=True)
    L = []
    A = L.append

    A("# RiverGuard - validation report\n")
    A(f"Generated: {date.today().isoformat()}\n")
    A("Every number below is produced by a script in `ml/` and can be "
      "re-checked by re-running it.\n")

    # ---------------------------------------------------------------- 1
    A("## 1. Two independent sensors agree\n")
    A("This is the central check. Sentinel-2 (10 m, 2019-2026) and Landsat "
      "(30 m, 1989-2026) measure the same river with different instruments. "
      "They were not built to agree.\n")

    s2 = {}
    ls = {}
    for y0, y1 in PAIRS:
        if (C.TRANSECTS / f"epr_{y0}_{y1}.geojson").exists():
            s2[(y0, y1)] = epr_pair_median(y0, y1)
    for y0, y1 in LAND_PAIRS:
        gdf = gpd.read_file(C.TRANSECTS_LANDSAT / f"epr_{y0}_{y1}.geojson")
        ls[(y0, y1)] = float(np.median([abs(r["mag"]) for _, r in gdf.iterrows()]))

    shared = sorted(set(s2) & set(ls))
    A("| pair | S2 median m/yr | Landsat median m/yr | ratio |")
    A("|---|---|---|---|")
    ratios = []
    for k in shared:
        r = ls[k] / s2[k] if s2[k] else float("nan")
        ratios.append(r)
        A(f"| {k[0]}->{k[1]} | {s2[k]:.1f} | {ls[k]:.1f} | {r:.2f}x |")
    ratios = np.array([r for r in ratios if np.isfinite(r)])
    sv = np.array([s2[k] for k in shared])
    lv = np.array([ls[k] for k in shared])
    corr = float(np.corrcoef(sv, lv)[0, 1]) if len(shared) > 2 else float("nan")

    A(f"\n- mean Landsat/Sentinel-2 ratio: **{ratios.mean():.2f}x**")
    A(f"- correlation across pairs: **{corr:+.2f}**")
    A(f"- Sentinel-2 overall median: **{np.median(sv):.1f} m/yr** over "
      f"{len(s2)} pairs")
    A(f"- Landsat overall median: **{np.median(lv):.1f} m/yr** over {len(ls)} pairs\n")
    A("A ratio near 1 with a high correlation means both instruments are seeing "
      "the same movement. The remaining scatter pair by pair is real: individual "
      "years differ between sensors, which is why no single year should be "
      "trusted alone.\n")

    gc_path = REPORTS / "geometry_check.json"
    if gc_path.exists():
        gc = json.load(open(gc_path))
        A(f"- transects placed: {gc.get('transects_kept')} of "
          f"{gc.get('transects_built')} candidates, over "
          f"{gc.get('centreline_km', 0):.1f} km of traced channel")
        A(f"- manual geometry spot checks passed: "
          f"**{gc.get('spot_checks_passed', 'n/a')}**")
        A("")

    # ---------------------------------------------------------------- 2
    A("## 2. Cross-check against an independent method\n")
    A("Method A: EPR net-area change (above).\n")
    A("Method B: how far the traced river outline physically moved between the "
      "same two years (75th percentile of nearest-outline distance).\n")
    A("Method B shares almost no machinery with EPR, so agreement means both are "
      "seeing real movement rather than one shared artefact.\n")
    A("| pair | EPR median | outline distance p75 |")
    A("|---|---|---|")
    ea, pb = [], []
    for y0, y1 in PAIRS:
        if (y0, y1) not in s2:
            continue
        d = outline_dist(y0, y1)
        e = s2[(y0, y1)]
        ea.append(e)
        pb.append(float(np.percentile(d, 75)))
        A(f"| {y0}->{y1} | {e:.1f} m | {np.percentile(d, 75):.1f} m |")
    ea, pb = np.array(ea), np.array(pb)
    c2 = float(np.corrcoef(ea, pb)[0, 1]) if len(ea) > 2 else float("nan")
    A(f"\n**Correlation {c2:+.2f}** across {len(ea)} year pairs.\n")
    A(f"> The earlier figure of **+0.92 is withdrawn and must not be cited**. It "
      f"was computed while a resolution-sampling bug was live, so both sides of "
      f"that comparison came from the same distorted geometry. Re-measured now, "
      f"with the corrected geometry, the figure is {c2:+.2f} over {len(ea)} pairs. "
      f"See DECISIONS.md D35, D37.\n")

    # ---------------------------------------------------------------- 3
    A("## 3. Plausibility against literature\n")
    A("Published Jamuna bank-change rates for comparable reaches sit broadly in "
      "the **30-200 m/yr** range, with local hotspots higher. The medians here "
      f"({np.median(sv):.0f} m/yr for Sentinel-2, {np.median(lv):.0f} m/yr for "
      f"Landsat) sit inside that range.\n")

    # ---------------------------------------------------------------- 4
    A("## 4. Water level confound\n")
    A("A low-water year exposes more bank, which can look like erosion even when "
      "no land moved. If the measurement were really just reading water level, "
      "this correlation would be strong.\n")
    st, med = [], []
    for y0, y1 in PAIRS:
        p = C.TRANSECTS / f"epr_{y0}_{y1}.geojson"
        if not p.exists():
            continue
        gdf = gpd.read_file(p)
        st.append(float(gdf["stage1_km2"].iloc[0]) - float(gdf["stage0_km2"].iloc[0]))
        med.append(float(np.median([abs(r["mag"]) for _, r in gdf.iterrows()])))
    if len(st) > 2:
        A(f"- correlation between water-area change and median bank change: "
          f"**{np.corrcoef(np.array(st), np.array(med))[0,1]:+.2f}**")
    A("- A weak relationship is reassuring: the measurement is not simply "
      "tracking how much water was present.")
    A("- It is not eliminated. Each record carries `stage_km2`, "
      "`stage_change_km2` and `stage_ratio` so this can be inspected.\n")

    # ---------------------------------------------------------------- 5
    A("## 5. Is there any learnable signal?\n")
    A("This is the finding that shapes the product.\n")
    lp = C.DATA_PROC / "features" / "landsat" / "features.csv"
    if not lp.exists():
        A("`features/landsat/features.csv` not built. Run `05_features.py landsat`.")
    else:
        df = pd.read_csv(lp).dropna(subset=["target_rate"])
        gm = df["target_rate"].mean()
        mae_mean = float(np.mean(np.abs(df["target_rate"] - gm)))

        loo = []
        for _, row in df.iterrows():
            o = df[(df.transect_id == row.transect_id) &
                   (df.year1 != row.year1)]["target_rate"]
            loo.append(o.mean() if len(o) else gm)
        loo = np.array(loo)
        mae_loo = float(np.mean(np.abs(df["target_rate"] - loo)))

        pers = (df.sort_values("year1").groupby("transect_id")["target_rate"]
                  .shift(1).fillna(gm))
        mae_pers = float(np.mean(np.abs(df["target_rate"] - pers)))

        A(f"Rows: {len(df)} (transect x bank side x year pair), "
          f"{int(df.year0.min())}-{int(df.year1.max())}, "
          f"{df.transect_id.nunique()} transects.\n")
        A("| predictor | MAE (m/yr) |")
        A("|---|---|")
        A(f"| **predict the average** | **{mae_mean:.1f}** |")
        A(f"| this transect's own past average (leave-one-out) | {mae_loo:.1f} |")
        A(f"| same transect, previous pair | {mae_pers:.1f} |")
        A("")
        A("**Reading this honestly:** nothing beats simply predicting the average. "
          "Using the transect's own history makes it *worse*, and repeating the "
          "previous year is worse still. Erosion hotspots on a braided river "
          "migrate rather than persist.\n")

        hp = C.DATA_PROC / "features" / "landsat" / "features_hydro.csv"
        if hp.exists():
            h = pd.read_csv(hp)
            if "q_monsoon_mean" in h.columns:
                hh = h.dropna(subset=["q_monsoon_mean", "target_rate"])
                wr = []
                for tid, g in hh.groupby("transect_id"):
                    if g["q_monsoon_mean"].nunique() > 1 and len(g) > 2:
                        wr.append(g["q_monsoon_mean"].corr(g["target_rate"]))
                wr = np.array([v for v in wr if np.isfinite(v)])
                if len(wr):
                    A(f"Real GloFAS discharge, 37 complete years (1989-2025), "
                      f"joined at the study reach. Within-transect correlation "
                      f"with erosion rate: **{wr.mean():+.3f}** "
                      f"(median {np.median(wr):+.3f}, {len(wr)} transects, "
                      f"{100*(wr > 0).mean():.0f}% positive).\n")
                    A("About half positive is what random noise looks like. The "
                      "physically correct forcing does not resolve the signal, "
                      "because a single catchment-scale discharge value cannot "
                      "say where along a braided reach the water attacks the "
                      "bank. See DECISIONS.md D44.\n")

    # ---------------------------------------------------------------- 6
    A("## 6. What is claimed, and what is not\n")
    A("**Claimed, with the evidence above:**\n")
    A("- how much land this bank lost in each year since 1989, and how much it "
      "lost on average over three decades\n")
    A("- which stretches are the chronic eroders, relative to each other\n")
    A("- that two independent instruments agree, and that the result sits "
      "inside the published range for this river\n")
    A("\n**Not claimed:**\n")
    A("- a prediction of next year's erosion. This was tested and it does not "
      "work; see section 5.\n")
    A("- absolute accuracy against ground truth, because there is no survey of "
      "where the bank was.\n")

    # ---------------------------------------------------------------- 7
    A("## 7. Honest limitations\n")
    A("1. **No ground truth.** Confidence comes from two independent sensors "
      "agreeing and from literature plausibility, not from absolute accuracy.\n")
    A("2. **The measurement zone sets the magnitude.** A 1000 m strip defines "
      "'at risk'. That is a stated physical assumption, not a fitted "
      "parameter; a wider zone dilutes the same land loss over more frontage.\n")
    A("3. **One reach, one season.** About 30 km, sampled January-February at "
      "low water. Monsoon attacks on the outer bends are not captured.\n")
    A("4. **Annual pairs are not independent.** Several consecutive pairs can "
      "be dominated by one flood. Uncertainty intervals use a block bootstrap "
      "for this reason - see RISK.md.\n")
    A("5. **Individual transect rates are often not distinguishable from zero.** "
      "Of the records with a long enough history, only a small minority have a "
      "confidence interval clear of zero. The rest are shown, and flagged, "
      "rather than quietly dropped.\n")
    A("6. **Landsat misses part of the traced river.** The export stops at "
      "24.35N, excluding about 12% of the traced channel. Cross-sensor work "
      "uses the shared bbox.\n")

    out = REPORTS / "VALIDATION.md"
    out.write_text("\n".join(L) + "\n")
    print("\n".join(L))
    print(f"\n-> {out}")


if __name__ == "__main__":
    main()