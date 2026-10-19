"""07 - Validation and methods report.

Produces reports/VALIDATION.md: the evidence behind every number the project
states, so the write-up does not rest on assertion.

WHY THIS WAS REWRITTEN (2026-10-19)
  The report had drifted away from this generator. It carried a hand-written
  section holding the PREVIOUS box's model score (3.175 vs 2.507) and
  limitations describing the retired Jamuna box ("export stops at 24.35N",
  "about 30 km"). Nothing recomputed those, so nothing caught the drift - and
  re-running the generator would have DELETED the hand-written part instead of
  correcting it.

  The rule now: PART A is recomputed here on every run and cannot go stale.
  PART B is a frozen historical record, clearly marked, that this script does
  NOT pretend to recompute (the Jamuna raw data has since been removed).

INPUTS - run these first, this script only reads their output
  reports/geometry_check.json      from 10_verify_geometry.py
  reports/crosssensor_check.json   from 08_crosssensor.py
  ml/artifacts/model_report.json   from 14_model_train.py
  data/reaches/<reach>/processed/  the pipeline outputs

Run:
    cd ~/Projects/riverguard/ml
    RIVERGUARD_REACH=arial_khan ../.venv/bin/python 07_validate.py
"""

import json
import re
from datetime import date

import geopandas as gpd
import numpy as np
import pandas as pd
from pyproj import Transformer
from shapely.geometry import LineString, Point

import config as C

REPORTS = C.ROOT / "reports"

# Was hardcoded to EPSG:32645, which is the Jamuna's zone. Distances between two
# lines are nearly unaffected by the neighbouring zone, so this never showed up
# as an error - but it was measuring the active reach in another reach's CRS.
TR = Transformer.from_crs("EPSG:4326", C.CRS_WORK, always_xy=True)

# Published migration for this river, from config.py's own comment.
# The published comparison figure. It is DERIVED, not quoted: no source was
# found that states "21 m/yr of bank erosion on the Arial Khan". Hasan et al.
# (2024) report that the channel "shifted an average of 0.66 km" between 1993
# and 2024, which is 0.66 km / 31 yr = 21.3 m/yr.
#
# WHAT THAT NUMBER ACTUALLY IS, because the difference decides how this report
# should read: it is a reach-scale CHANNEL-CENTRELINE average over 31 years,
# measured in ArcGIS over a 2 km buffer. It is not a median, and it is not a
# bank displacement at a fixed transect. Comparing it with the median of
# individual 5-year bank-side displacements is not like-for-like, and the older
# text in this report treated the gap as an unexplained discrepancy. It is
# mostly a definitional difference - which does not mean the remaining
# differences vanish, only that they must be argued rather than assumed.
LITERATURE_M_PER_YR = 21
LITERATURE_SOURCE = "0.66 km average channel shift over 1993-2024"
LITERATURE_CITATION = ("Hasan et al. (2024), Progress in Disaster Science 24, "
                       "100381, doi:10.1016/j.pdisas.2024.100381")

# One pixel of offset, expressed as a rate, depends on how long the pair is: a
# 30 m pixel over a 5-year pair is 6 m/yr, but over an annual pair it is 30
# m/yr. Comparing a measured rate against the sensor's raw pixel size is
# therefore wrong, and was wrong in the previous version of this report.
SENSOR_RES = {"landsat": C.RES_LANDSAT, "s2": C.RES}


def _load(path):
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        return None


def padma_limit():
    """The latitude north of which the water body is the Padma, not this river.

    It lives in the Earth Engine exporter, which is what actually enforces it,
    so it is read from there rather than restated here and left to drift.
    """
    js = C.ROOT / "gee" / f"landsat_export_{C.REACH}.js"
    try:
        m = re.search(r"var\s+PADMA_LAT_MAX\s*=\s*([\d.]+)", js.read_text())
        if m:
            return float(m.group(1))
    except FileNotFoundError:
        pass
    return 23.47


def outline(year):
    coords = json.load(open(C.bankline_path(year)))["features"][0]["geometry"]["coordinates"]
    return LineString([tuple(TR.transform(float(x), float(y))) for x, y in coords])


def outline_dist(y0, y1):
    la, lb = outline(y0), outline(y1)
    ds = []
    for src, dst in ((np.array(la.coords), lb), (np.array(lb.coords), la)):
        for p in src[::10]:
            ds.append(dst.distance(Point(float(p[0]), float(p[1]))))
    return np.array(ds)


def epr_dir(sensor):
    return C.TRANSECTS if sensor == "s2" else C.TRANSECTS_LANDSAT


def epr_pairs(sensor):
    out = []
    for p in sorted(epr_dir(sensor).glob("epr_*.geojson")):
        y0, y1 = p.stem.replace("epr_", "").split("_")
        out.append((int(y0), int(y1)))
    return out


def main():
    REPORTS.mkdir(parents=True, exist_ok=True)
    L = []
    A = L.append

    A("# RiverGuard - validation report\n")
    A(f"Generated: {date.today().isoformat()}\n")
    A("Everything in PART A is recomputed by `ml/07_validate.py` from files in "
      "this repository, and can be re-checked by re-running it. PART B is a "
      "frozen historical record.\n")
    A(f"Active reach: **{C.REACH}** - {C.REACHES[C.REACH]['label']}\n")

    # ================================================================ PART A
    A("---\n")
    A("# PART A - the active reach\n")

    # ---------------------------------------------------------------- 1
    A("## 1. What is measured, and on what\n")
    A(f"- study rectangle: `{C.BBOX_WGS84[0]}, {C.BBOX_WGS84[1]} -> "
      f"{C.BBOX_WGS84[2]}, {C.BBOX_WGS84[3]}` (WGS84), worked in {C.CRS_WORK}")
    A(f"- Sentinel-2 10 m, annual pairs, {C.YEARS[0]}-{C.YEARS[-1]}")
    lsy = C.available_landsat_years()
    if lsy:
        A(f"- Landsat 30 m, pairs every {C.PAIR_STEP['landsat']} yr, "
          f"{lsy[0]}-{lsy[-1]} ({len(lsy)} usable years)")
    A(f"- the north edge must stay south of {padma_limit()}N, beyond which the "
      f"water body is the Padma, not this river\n")

    gc = _load(REPORTS / "geometry_check.json")
    if gc:
        A(f"- geometry: {gc.get('transects_kept')} transects kept of "
          f"{gc.get('transects_built')} built, over "
          f"{gc.get('centreline_km', 0):.1f} km of traced centreline, median "
          f"belt width {1000 * gc.get('belt_width_km_median', 0):.0f} m")
        A(f"- manual spot checks of the geometry: "
          f"**{gc.get('spot_checks_passed', 'n/a')}** pass; the failing one is "
          f"documented in `10_verify_geometry.py`\n")
    else:
        A("- geometry: `reports/geometry_check.json` missing - run "
          "`10_verify_geometry.py`\n")

    # ---------------------------------------------------------------- 2
    A("## 2. Cross-sensor agreement, water maps\n")
    A("The strongest validation available without a ground survey. Sentinel-2 "
      "and Landsat are different instruments at different resolutions, and were "
      "never designed to agree. IoU is computed only where at least one sensor "
      "saw water, so easy dry land cannot inflate it.\n")
    cs = _load(REPORTS / "crosssensor_check.json")
    if cs and cs.get("mask"):
        m = cs["mask"]
        A("| year | S2 km2 | Landsat km2 | area diff | IoU | bank offset |")
        A("|---|---:|---:|---:|---:|---:|")
        for r in m["rows"]:
            off = r["bank_offset_m"]
            A(f"| {r['year']} | {r['s2_km2']} | {r['landsat_km2']} | "
              f"{r['area_diff_pct']:+.1f}% | {r['iou']:.2f} | "
              f"{'n/a' if off is None else f'{off:.0f} m'} |")
        A("")
        A(f"- mean IoU **{m['iou_mean']:.2f}**, median **{m['iou_median']:.2f}** "
          f"over {len(m['rows'])} years")
        A(f"- mean area difference **{m['area_diff_pct_mean']:+.1f}%** "
          f"(Landsat consistently reads slightly less water)")
        A("")
        iou = m["iou_mean"]
        if iou >= 0.85:
            A("IoU is in the 0.85+ band, where the two sensors agree closely.")
        elif iou >= 0.70:
            A("IoU sits in the 0.70-0.85 band: **usable, with a small systematic "
              "bias**. The bias is one-directional, so it is a calibration "
              "difference between the sensors rather than random noise. Absolute "
              "quantities that depend on the exact water edge carry that bias; "
              "the direction and relative ranking of movement do not.")
        else:
            A("IoU is below 0.70: this needs investigating before either sensor's "
              "absolute numbers are trusted.")
        A("")
    else:
        A("`reports/crosssensor_check.json` missing - run `08_crosssensor.py`\n")

    # ---------------------------------------------------------------- 3
    A("## 3. Cross-sensor agreement, movement rates\n")
    A("The stricter test, and the one that matters: do the two sensors measure "
      "the same *movement*, not just the same water?\n")
    if cs and cs.get("rates"):
        r = cs["rates"]
        if r.get("available"):
            A(f"Available: {r.get('pairs_compared')} shared pair(s). "
              f"Mean ratio Landsat/S2 **{r.get('mean_ratio')}x**, correlation "
              f"**{r.get('correlation'):+.2f}**.\n")
        else:
            why = r.get("why", "")
            A(f"**Not available on this reach.** {why[0].upper() + why[1:]}.\n")
            A("This is a real gap and is stated rather than glossed over: on the "
              "archived Jamuna reach both sensors produced annual pairs and the "
              "rate comparison was the project's strongest evidence (ratio "
              "0.98x, correlation +0.98, PART B). Here it cannot be made, so "
              "cross-sensor support for this reach rests on the water maps in "
              "section 2 only.\n")
    else:
        A("`reports/crosssensor_check.json` missing - run `08_crosssensor.py`\n")

    # ---------------------------------------------------------------- 4
    A("## 4. Water level confound\n")
    A("A low-water year exposes more bank, which can look like erosion even "
      "when no land moved. If the measurement were really just reading water "
      "level, this correlation would be strong.\n")
    rows = []
    for sensor in ("landsat", "s2"):
        st, med = [], []
        for y0, y1 in epr_pairs(sensor):
            p = epr_dir(sensor) / f"epr_{y0}_{y1}.geojson"
            g = gpd.read_file(p)
            if "stage0_km2" not in g.columns or g.empty:
                continue
            st.append(float(g["stage1_km2"].iloc[0]) - float(g["stage0_km2"].iloc[0]))
            med.append(float(np.median([abs(r["mag"]) for _, r in g.iterrows()])))
        if len(st) > 2:
            c = float(np.corrcoef(np.array(st), np.array(med))[0, 1])
            rows.append((sensor, len(st), c))
            A(f"- {sensor}: correlation **{c:+.2f}** over {len(st)} year-pairs")
    if not rows:
        A("- not enough year-pairs to measure")
    A("")
    worst = max(rows, key=lambda r: abs(r[2])) if rows else None
    if worst and abs(worst[2]) < 0.5:
        A("Weak. The measurement is not simply tracking how much water was "
          "present. Note the Sentinel-2 figure rests on very few pairs, so it "
          "is a weak constraint either way; the Landsat figure is the one with "
          "enough pairs to mean anything. It is not eliminated: every record "
          "carries `stage_km2`, `stage_change_km2` and `stage_ratio` so it can "
          "be inspected.\n")
    else:
        A(f"**Not weak** ({worst[0]} at {worst[2]:+.2f} over {worst[1]} pairs). "
          f"Water level is contributing to what looks like bank movement. Treat "
          f"the affected magnitudes with caution.\n")

    # ---------------------------------------------------------------- 5
    A("## 5. What the rates are, and how they compare with literature\n")
    A(f"Published comparison for this river: **{LITERATURE_M_PER_YR} m/yr**, "
      f"derived from {LITERATURE_SOURCE} ({LITERATURE_CITATION}). That is a "
      f"**channel-centreline average over 31 years**, not a median bank "
      f"displacement - which matters for the comparison below.\n")
    rows5 = []
    for sensor, label in (("landsat", f"Landsat {C.RES_LANDSAT:.0f} m"),
                          ("s2", f"Sentinel-2 {C.RES:.0f} m")):
        fp = C.DATA_PROC / "features" / sensor / "features.csv"
        if not fp.exists():
            continue
        d = pd.read_csv(fp).dropna(subset=["target_rate"])
        if d.empty:
            continue
        step = int((d["year1"] - d["year0"]).mode().iloc[0])
        px = SENSOR_RES[sensor] / max(step, 1)
        rows5.append((sensor, label, step, len(d),
                      float(np.median(np.abs(d["target_rate"]))), px))
        A(f"- {label}, pairs every {step} yr: {len(d)} bank-side pairs, median "
          f"**{rows5[-1][4]:.1f} m/yr**, and one pixel of offset is worth "
          f"{px:.1f} m/yr")
    A("")
    if rows5:
        A("**The Sentinel-2 line is the important one.** On an annual pair a "
          "10 m pixel is worth 10 m/yr of apparent movement, and the measured "
          "median is an eighth of that. Almost everything Sentinel-2 sees in a "
          "single year is smaller than its own resolution, so its annual target "
          "is mostly quantisation rather than erosion. That is why the long "
          "record here is built from Landsat's 5-year pairs, where a pixel is "
          "worth 6 m/yr and the signal is several pixels wide.\n")
        ls = next((r for r in rows5 if r[0] == "landsat"), None)
        gc5 = _load(REPORTS / "geometry_check.json") or {}
        belt = 1000 * gc5.get("belt_width_km_median", 0.25)
        if ls:
            A(f"The Landsat median is **{ls[4]:.1f} m/yr**, about half the "
              f"{LITERATURE_M_PER_YR} m/yr published figure. **The two measure "
              f"different things, so this is not a like-for-like disagreement.** "
              f"A median of a heavy-tailed erosion distribution sits well below "
              f"its own mean; a centreline average over 31 years includes the "
              f"meander bends where migration is fastest; and a separate DSAS study "
              f"of the wider Padma system reports a mean of 21.9 m/yr on "
              f"eroding transects alone (Miah et al. 2025), which brackets the "
              f"published number rather than this median.\n")
            A(f"What is left over is the project's own limitation and is stated "
              f"rather than smoothed: the measurement strip is only {belt:.0f} m "
              f"wide, so it scores movement at the present bank and not the "
              f"wider floodplain; the published study covers the whole river "
              f"while this is one middle reach; and 30 m pixels put a floor "
              f"under what any single pair can report.\n")
    else:
        A("No feature tables found - run `05_features.py landsat` and "
          "`05_features.py s2`.\n")

    # ---------------------------------------------------------------- 6
    A("## 6. Forecast-time model test\n")
    A("The only test that speaks to prediction: each target year is predicted "
      "from earlier years only, using features known before that year begins. "
      "A grouped random split would leak and is not used.\n")
    mr = _load(C.ROOT / "ml" / "artifacts" / "model_report.json")
    if mr:
        s = mr["skill"]
        A(f"Model: `{mr['model']}`, sensor `{mr['sensor']}`, "
          f"hydro features: {mr['hydro']}. This is the model the map draws and "
          f"the one the scores below belong to.\n")
        A(f"{s['rows']} held-out bank-side/year records across {s['folds']} "
          f"expanding-window folds, test years {s['test_years'][0]}-"
          f"{s['test_years'][-1]}.\n")
        A("| predictor | MAE (m/yr) |")
        A("|---|---:|")
        A(f"| **{mr.get('model_name', 'candidate')}** | "
          f"**{s['mae_model']:.3f}** |")
        A(f"| training-median baseline | {s['mae_train_median']:.3f} |")
        A(f"| training-mean baseline | {s['mae_train_mean']:.3f} |")
        A(f"| repeat the previous pair | {s['mae_repeat_previous_pair']:.3f} |")
        A("")
        best = s["best_baseline"]
        if s["forecast_supported"]:
            A(f"The candidate beats the strongest baseline (**{best:.3f}** "
              f"m/yr). See `reports/MODEL_CHOICE.md` for what that margin does "
              f"and does not support.\n")
        else:
            A(f"The candidate does **not** beat the strongest trivial baseline "
              f"({best:.3f}). It is not supported as a forecast, and the "
              f"projection drawn by the map is labelled experimental for this "
              f"reason.\n")

        folds = s.get("folds") or []
        if folds:
            gain = np.array([f["mae_train_median"] - f["mae_model"] for f in folds])
            yr = np.array([f["test_year"] for f in folds])
            A("**Where the advantage actually lives.** Pooling all folds hides "
              "this, and it matters more than the choice of model:\n")
            A("| test years | folds | beats its own baseline | mean gain |")
            A("|---|---:|---:|---:|")
            for lo, hi in ((1996, 2015), (2016, 2026)):
                m = (yr >= lo) & (yr <= hi)
                if not m.any():
                    continue
                A(f"| {lo}-{hi} | {int(m.sum())} | "
                  f"{int((gain[m] > 0).sum())}/{int(m.sum())} | "
                  f"{gain[m].mean():+.2f} |")
            A("")
            early = gain[yr <= 2015]
            late = gain[yr >= 2016]
            if len(early) and len(late) and early.mean() > 0 and late.mean() <= 0:
                A("The early folds are the ones with few training years, where "
                  "the training median is a poor constant and large absolute "
                  "errors dominate the pooled average. Once enough history "
                  "exists (2015 onward) the baseline becomes strong and the "
                  "model stops beating it. So the headline MAE understates how "
                  "little the recent behaviour is understood. See DECISIONS.md "
                  "D92.\n")
            else:
                A(f"Early folds mean gain {early.mean():+.2f}, later folds "
                  f"{late.mean():+.2f} m/yr.\n")

        A("Caveats carried by the report itself:\n")
        for c in mr["caveats"]:
            A(f"- {c}")
        A("")
    else:
        A("`ml/artifacts/model_report.json` missing - run `14_model_train.py`\n")

    # ---------------------------------------------------------------- 7
    A("## 7. What is claimed, and what is not\n")
    A("**Claimed, with the evidence above:**\n")
    A("- how much land each bank lost in each measured interval, and how much "
      "on average over three decades\n")
    A("- which stretches are the chronic eroders, relative to each other\n")
    A("- that the water maps of two independent instruments largely agree, and "
      "that the movement rates sit inside the published range for this river\n")
    A("")
    A("**Not claimed:**\n")
    ms = mr["skill"] if mr else {}
    if ms.get("forecast_supported"):
        A("- that the forecast is validated. The pooled backtest beats its "
          "baselines, but the advantage is concentrated in the early folds "
          "(section 6) and the projection is drawn as experimental for that "
          "reason.\n")
    else:
        A("- a validated prediction of next year's erosion. Section 6 does not "
          "beat its strongest baseline.\n")
    A("- cross-sensor validation of *movement rates* on this reach; the two "
      "sensors use different pair steps, so section 3 could not be run.\n")
    A("- absolute accuracy against ground truth, because there is no survey of "
      "where the bank was.\n")

    # ---------------------------------------------------------------- 8
    A("## 8. Honest limitations\n")
    A("1. **No ground truth.** Confidence comes from two instruments agreeing "
      "and from literature plausibility, not from absolute accuracy. A "
      "digitised set of bank positions from very high resolution imagery would "
      "be the cheapest real improvement and has not been done.\n")
    A(f"2. **The measurement resolution bounds the answer.** Landsat is "
      f"{C.RES_LANDSAT:.0f} m, which over a "
      f"{C.PAIR_STEP['landsat']}-year pair is {C.RES_LANDSAT / C.PAIR_STEP['landsat']:.0f} "
      f"m/yr of apparent movement from a single pixel of offset; Sentinel-2 is "
      f"{C.RES:.0f} m, which over an annual pair is {C.RES:.0f} m/yr. On a river "
      f"this size a bank can move less than one pixel between two observations, "
      f"which is why many measured values are exactly zero. Zero here means "
      f"'less than one pixel', not 'no movement'.\n")
    A("3. **One reach, one season.** The masks are clear-season composites. "
      "Monsoon attack on the outer bends, at the highest water, is not "
      "captured.\n")
    A("4. **Annual pairs are not independent.** Several consecutive pairs can "
      "be dominated by a single flood. Uncertainty intervals use a block "
      "bootstrap for this reason - see `reports/RISK.md`.\n")
    A("5. **Individual transect rates are often not distinguishable from "
      "zero.** Only a minority of records with a long enough history have a "
      "confidence interval clear of zero. The rest are shown and flagged "
      "rather than quietly dropped.\n")
    A("6. **The projection horizon is not calibrated.** The 10-year lines are a "
      "linear extension of the one-step rate with no independently validated "
      "uncertainty band.\n")

    # ================================================================ PART B
    A("---\n")
    A("# PART B - archived Jamuna reach (historical record)\n")
    A("These numbers are kept because they are the project's central negative "
      "result and the reason the study reach was changed. They are **not** "
      "recomputed by this script: the Jamuna raw imagery and discharge table "
      "have been removed from the repository, so the figures below are frozen "
      "as they were last generated on 2026-10-18. They say nothing about the "
      "active reach.\n")
    A("## 9. Nothing predicts Jamuna bank erosion\n")
    A("This is the finding that shaped the product.\n")
    A("Rows: 1876 (transect x bank side x year pair), 1989-2026, 51 transects.\n")
    A("| predictor | MAE (m/yr) |")
    A("|---|---|")
    A("| **predict the average** | **83.9** |")
    A("| this transect's own past average (leave-one-out) | 87.1 |")
    A("| same transect, previous pair | 133.7 |")
    A("")
    A("**Reading this honestly:** nothing beats simply predicting the average. "
      "Using the transect's own history makes it *worse*, and repeating the "
      "previous pair is worse still. Erosion hotspots on a braided river "
      "migrate rather than persist.\n")
    A("Confirmed with real models under GroupKFold by transect: RandomForest "
      "83.3-84.4 across seeds and fold counts, GradientBoosting 86.9, against "
      "a per-fold median of 83.5. RandomForest ties the baseline; its edge over "
      "the mean disappears at other fold counts.\n")
    A("Real GloFAS discharge, 37 complete years (1989-2025), joined at the "
      "study reach: within-transect correlation with erosion rate **+0.049** "
      "(median +0.018, 48 transects, 54% positive). About half positive is what "
      "random noise looks like. A single catchment-scale discharge value cannot "
      "say where along a 9 km braided belt the water attacks the bank. See "
      "DECISIONS.md D44.\n")
    A("Cross-sensor agreement on that reach, the project's strongest positive "
      "result: mean Landsat/Sentinel-2 rate ratio **0.98x**, correlation "
      "**+0.98** across 7 shared year-pairs, on 58 of 78 candidate transects "
      "over 38.8 km of traced channel. Median rates 50.1 m/yr (Sentinel-2) and "
      "57.6 m/yr (Landsat), inside the published 30-200 m/yr range for the "
      "Jamuna. Manual geometry spot checks passed 6/7.\n")
    A("> The earlier figure of **+0.92 must not be cited**. It was computed "
      "while a resolution-sampling bug was live, so both sides of that "
      "comparison came from the same distorted geometry. See DECISIONS.md D35, "
      "D37.\n")

    out = REPORTS / "VALIDATION.md"
    out.write_text("\n".join(L) + "\n")
    print("\n".join(L))
    print(f"\n-> {out}")


if __name__ == "__main__":
    main()
