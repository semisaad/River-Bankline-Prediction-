"""
06 - Draw the long-run erosion trend on the map.

WHAT CHANGED AND WHY
    This script used to turn a machine-learning forecast into a predicted
    bankline. It was rewritten because the forecast was not defensible.

    After 37 years of Landsat imagery and a full record of real river discharge,
    every predictor was tested against the trivial baseline of "predict the
    average" (83.9 m/yr MAE):

        this transect's own past average      87.1 m/yr   (worse)
        same transect, previous pair         133.7 m/yr   (much worse)
        river discharge, best case            r = +0.05   (nothing)

    There is no learnable year-to-year signal. Drawing a confident predicted
    bankline would have been drawing noise and labelling it skill.

    So this script now draws what the evidence does support: a LONG-RUN TREND.
    For each bank, its measured erosion rate over three decades of imagery is
    carried forward over a stated horizon, with the uncertainty band attached.
    This is standard practice for chronic-exposure mapping and it is honest,
    because it is labelled a trend and it carries its own error bars.

    It is still NOT a forecast. A trend says "this bank has been losing about
    40 m/yr and has been for 30 years". It does not say "next year it will lose
    40 m".

HOW THE GEOMETRY WORKS
    The transect cast is rebuilt with the current river-following geometry
    (see transects.py), which places every transect perpendicular to the LOCAL
    direction of the channel. For a given year the two water edges are measured
    along that cast: vmin on one bank, vmax on the other.

    An eroding bank moves OUTWARD, away from the water and into the land, so the
    left bank (at vmin) moves towards lower v and the right bank (at vmax)
    towards higher v. Positive rate means land is lost. Getting this sign wrong
    would draw erosion happening in the wrong direction, so the convention is
    stated here once and used consistently.

OUTPUTS
    data/processed/predictions/longrun_trend_<horizon>yr.geojson
    data/processed/predictions/predictions.csv     (kept for compatibility)

Run:
    cd ~/Projects/riverguard/ml
    ../.venv/bin/python 06_predict_geojson.py            # default 10-year horizon
    ../.venv/bin/python 06_predict_geojson.py --horizon 20
"""

import argparse
import csv
import json
from pathlib import Path

import numpy as np
from shapely.geometry import LineString, mapping

import config as C
import transects as T

OUT_DIR = C.DATA_PROC / "predictions"
RISK_CSV = C.DATA_PROC / "risk" / "transect_risk.csv"

# Records shorter than this are excluded: one lucky year is not a trend.
MIN_YEARS = 10
DEFAULT_HORIZON = 10


def build(horizon_years):
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    if not RISK_CSV.exists():
        print(f"Missing {RISK_CSV}")
        print("Run 13_risk_and_forecast.py first - it holds the long-run rates "
              "and their confidence intervals.")
        return

    import pandas as pd
    risk = pd.read_csv(RISK_CSV)
    # Every record with a long enough history is drawn, not only the statistically
    # significant ones. Significance is carried as a property so the map can show
    # it - hiding the other 60 would imply they were measured and found normal,
    # which is a different claim. Only 3 of 64 clear the bar, and saying so
    # openly is part of the result.
    usable = risk[risk["n_years"] >= MIN_YEARS]
    if usable.empty:
        print(f"No record has at least {MIN_YEARS} years of history.")
        print("See reports/RISK.md.")
        return

    # latest year we actually measured, on the geometry sensor
    years = C.sensor_years(T.GEOM_SENSOR)
    if not years:
        print(f"No processed masks for {T.GEOM_SENSOR}")
        return
    latest = max(years)
    print(f"geometry sensor {T.GEOM_SENSOR}, latest year {latest}")
    print(f"horizon: {horizon_years} yr")
    n_sig = int(usable["significant"].sum())
    print(f"records with >= {MIN_YEARS} yr history: {len(usable)} "
          f"({n_sig} statistically distinguishable from zero)\n")

    ts = T.build_transects(sensor_geom=T.GEOM_SENSOR, quiet=True)
    pos, _ = T.bank_positions(ts, latest, sensor=T.GEOM_SENSOR, quiet=True)
    by_id = {t.i: t for t in pos}
    print(f"bank edges measured for {len(by_id)} transects in {latest}\n")

    feats = []
    rows = []

    for _, r in usable.iterrows():
        tid = int(r["transect_id"])
        t = by_id.get(tid)
        if t is None:
            continue

        side = str(r["side"])
        rate = float(r["rate_median"])          # m/yr, positive = land lost
        offset = rate * horizon_years
        # scale the confidence band by the same horizon
        lo = float(r["ci95_lo"]) * horizon_years
        hi = float(r["ci95_hi"]) * horizon_years

        if side == "left":
            v_now = t.vmin
            v_out = v_now - offset             # outward = lower v
            v_lo = v_now - lo
            v_hi = v_now - hi
        else:
            v_now = t.vmax
            v_out = v_now + offset             # outward = higher v
            v_lo = v_now + lo
            v_hi = v_now + hi

        pad = min(T.BUFFER_M, t.half_max)
        a = t.center + (t.arc_m * 0 - pad) * t.tangent + v_now * t.normal
        c = t.center + pad * t.tangent + v_now * t.normal
        e = t.center - pad * t.tangent + v_out * t.normal
        g = t.center + pad * t.tangent + v_out * t.normal

        feats.append({
            "type": "Feature",
            "geometry": mapping(LineString([tuple(a), tuple(c)])),
            "properties": {
                "kind": "current_bank",
                "transect_id": tid,
                "side": side,
                "year": latest,
            },
        })
        feats.append({
            "type": "Feature",
            "geometry": mapping(LineString([tuple(e), tuple(g)])),
            "properties": {
                "kind": "long_run_trend",
                "transect_id": tid,
                "side": side,
                "horizon_years": horizon_years,
                "rate_m_per_yr": round(rate, 1),
                "projected_offset_m": round(offset, 1),
                "offset_low_m": round(min(lo, hi), 1),
                "offset_high_m": round(max(lo, hi), 1),
                "n_years": int(r["n_years"]),
                "tier": r["tier"],
                "significant": bool(r["significant"]),
                "is_forecast": False,
                "basis": "long-run median rate over the full Landsat record",
            },
        })

        rows.append({
            "transect_id": tid,
            "side": side,
            "base_year": latest,
            "horizon_years": horizon_years,
            "rate_m_per_yr": round(rate, 1),
            "projected_offset_m": round(offset, 1),
            "offset_low_m": round(min(lo, hi), 1),
            "offset_high_m": round(max(lo, hi), 1),
            "n_years": int(r["n_years"]),
            "significant": bool(r["significant"]),
            "predicted_year": latest + horizon_years,
            "predicted_rate": round(rate, 1),
            "is_forecast": False,
        })

    if not feats:
        print("No usable rows matched the measured transects.")
        return

    fc = {
        "type": "FeatureCollection",
        "name": "longrun_trend",
        "crs": {"type": "name",
                "properties": {"name": C.CRS_WORK}},
        "metadata": {
            "n_records": len(rows),
            "n_significant": n_sig,
            "horizon_years": horizon_years,
            "base_year": latest,
            "min_years_history": MIN_YEARS,
            "is_forecast": False,
            "warning": ("Long-run trend, not a forecast. Projected year-to-year "
                        "erosion was tested and found unpredictable; see "
                        "reports/RISK.md."),
        },
        "features": feats,
    }

    gj = OUT_DIR / f"longrun_trend_{horizon_years}yr.geojson"
    with open(gj, "w") as f:
        json.dump(fc, f, indent=1)

    csv_path = OUT_DIR / "predictions.csv"
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    print(f"drawn {len(rows)} transect-side trends")
    for row in sorted(rows, key=lambda z: -abs(z["projected_offset_m"]))[:10]:
        print(f"   transect {row['transect_id']:>3} {row['side']:<5} "
              f"{row['rate_m_per_yr']:+7.1f} m/yr  ->  "
              f"{row['projected_offset_m']:+8.1f} m over {horizon_years} yr "
              f"(range {row['offset_low_m']:+.0f} to {row['offset_high_m']:+.0f})")

    print(f"\n-> {gj}")
    print(f"-> {csv_path}")
    print("\nNOTE: these are long-run trends with error bars, not forecasts.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--horizon", type=int, default=DEFAULT_HORIZON,
                    help="years to carry the long-run rate forward")
    args = ap.parse_args()
    build(args.horizon)


if __name__ == "__main__":
    main()