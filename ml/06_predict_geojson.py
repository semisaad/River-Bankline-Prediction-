"""
06 - Draw experimental model projections or historical-rate trends.

Model output is always experimental until its chronological rate test passes
and the requested spatial horizon is independently validated. Multi-year
offsets are currently a linear extension of a one-year rate.

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
    data/reaches/<reach>/processed/predictions/longrun_trend_<horizon>yr.geojson
    data/reaches/<reach>/processed/predictions/predictions.csv
    data/reaches/<reach>/processed/predictions/model_predictions.csv

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
from pyproj import Transformer
from shapely.geometry import LineString, mapping

import config as C
import transects as T

OUT_DIR = C.DATA_PROC / "predictions"
RISK_CSV = C.DATA_PROC / "risk" / "transect_risk.csv"
# Candidate model output from 14_model_train.py, kept separate from the
# rendered map CSV so generating the GeoJSON never overwrites its input.
MODEL_CSV = C.DATA_PROC / "predictions" / "model_predictions.csv"

# Historical-rate fallback requires this many years; candidate model rows are
# retained but always labelled experimental.
MIN_YEARS = 10
DEFAULT_HORIZON = 10


def wgs84_line(points, transformer):
    eastings, northings = zip(*points)
    longitudes, latitudes = transformer.transform(eastings, northings)
    return mapping(LineString(zip(longitudes, latitudes)))


def build(horizon_years):
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    import pandas as pd

    if MODEL_CSV.exists():
        src = MODEL_CSV
        print(f"using MODEL predictions from {MODEL_CSV}")
    elif RISK_CSV.exists():
        src = RISK_CSV
        print(f"no model yet - falling back to LONG-RUN RATES from {RISK_CSV}")
        print("(run 14_model_train.py for a trained projection)")
    else:
        print(f"Missing both {MODEL_CSV} and {RISK_CSV}")
        print("Run 14_model_train.py (model) or 13_risk_and_forecast.py (rates).")
        return

    using_model = src == MODEL_CSV
    risk = pd.read_csv(src)
    forecast_supported = (bool(risk["forecast_supported"].iloc[0])
                          if using_model else False)
    model_mae = (float(risk["model_mae_m_per_yr"].iloc[0])
                 if using_model else None)
    median_mae = (float(risk["median_baseline_mae_m_per_yr"].iloc[0])
                  if using_model else None)
    # Every record with a long enough history is drawn, not only the statistically
    # significant ones. Significance is carried as a property so the map can show
    # it - hiding the other 60 would imply they were measured and found normal,
    # which is a different claim. Only 3 of 64 clear the bar, and saying so
    # openly is part of the result.
    if "significant" not in risk.columns:
        risk["significant"] = False
        risk["tier"] = "model"
    if "n_years" not in risk.columns:
        # model output: rename onto the long-run-rate schema this script expects
        risk = risk.rename(columns={"n_years_history": "n_years"})
        print(f"  {len(risk)} model projections")

    usable = (risk if using_model else risk[risk["n_years"] >= MIN_YEARS])
    if usable.empty:
        print(f"No record has at least {MIN_YEARS} years of history.")
        print(f"See reports/RISK_{C.REACH}.md.")
        return

    # latest year we actually measured, on the geometry sensor
    years = C.sensor_years(T.GEOM_SENSOR)
    if not years:
        print(f"No processed masks for {T.GEOM_SENSOR}")
        return
    latest = max(years)
    print(f"geometry sensor {T.GEOM_SENSOR}, latest year {latest}")
    print(f"horizon: {horizon_years} yr")
    n_sig = int(usable["significant"].sum()) if not using_model else None
    if using_model:
        print(f"model rows: {len(usable)}, bank-side history: "
              f"{int(usable['n_years'].min())}-{int(usable['n_years'].max())} years")
        print(f"experimental model MAE {model_mae} vs median baseline {median_mae}; "
              f"forecast supported: {forecast_supported}\n")
    else:
        print(f"records with >= {MIN_YEARS} yr history: {len(usable)}")
        print(f"{n_sig} statistically distinguishable from zero\n")

    ts = T.build_transects(sensor_geom=T.GEOM_SENSOR, quiet=True)
    to_wgs84 = Transformer.from_crs(
        C.CRS_WORK, "EPSG:4326", always_xy=True)
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
        if "predicted_rate" in r:
            # already projected at its own horizon; rescale to the requested one
            own = float(r["horizon_years"])
            k = horizon_years / own
            rate = float(r["predicted_rate"]) * k
            offset = float(r["projected_offset_m"]) * k
            lo = float(r["offset_low_m"]) * k
            hi = float(r["offset_high_m"]) * k
        else:
            rate = float(r["rate_median"])      # m/yr, positive = land lost
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
            "geometry": wgs84_line([tuple(a), tuple(c)], to_wgs84),
            "properties": {
                "kind": "current_bank",
                "transect_id": tid,
                "side": side,
                "year": latest,
            },
        })
        feats.append({
            "type": "Feature",
            "geometry": wgs84_line([tuple(e), tuple(g)], to_wgs84),
            "properties": {
                "kind": ("experimental_projection" if using_model
                         else "long_run_trend"),
                "transect_id": tid,
                "side": side,
                "horizon_years": horizon_years,
                "rate_m_per_yr": round(rate, 1),
                "projected_offset_m": round(offset, 1),
                "offset_low_m": round(min(lo, hi), 1),
                "offset_high_m": round(max(lo, hi), 1),
                "n_years": int(r["n_years"]),
                "tier": r.get("tier", "model"),
                "significant": bool(r.get("significant", False)),
                "method": ("RandomForest, expanding-window backtest"
                           if using_model else "long-run rate"),
                "projection_status": "experimental" if using_model
                                     else "historical_trend",
                "horizon_validated": False,
                "forecast_supported": forecast_supported,
                "is_forecast": False,
                "mae_model_m_per_yr": model_mae,
                "median_baseline_mae_m_per_yr": median_mae,
                "basis": ("Experimental RandomForest projection"
                          if "predicted_rate" in r else
                          "long-run median rate over the full Landsat record"),
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
            "significant": bool(r.get("significant", False)),
            "predicted_year": latest + horizon_years,
            "predicted_rate": round(rate, 1),
            "method": ("RandomForest, expanding-window backtest"
                       if using_model else "long-run rate"),
            "projection_status": "experimental" if using_model
                                 else "historical_trend",
            "horizon_validated": False,
            "forecast_supported": forecast_supported,
            "is_forecast": False,
            "mae_model_m_per_yr": model_mae,
            "median_baseline_mae_m_per_yr": median_mae,
        })

    if not feats:
        print("No usable rows matched the measured transects.")
        return

    fc = {
        "type": "FeatureCollection",
        "name": "bankline_projection",
        "crs": {"type": "name",
            "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"}},
        "metadata": {
            "n_records": len(rows),
            "n_significant": n_sig,
            "horizon_years": horizon_years,
            "base_year": latest,
            "min_years_history": None if using_model else MIN_YEARS,
            "method": ("RandomForest, expanding-window backtest"
                       if using_model else "long-run rate"),
            "projection_status": "experimental" if using_model
                                 else "historical_trend",
            "horizon_validated": False,
            "forecast_supported": forecast_supported,
            "is_forecast": False,
            "mae_model_m_per_yr": model_mae,
            "median_baseline_mae_m_per_yr": median_mae,
            "warning": ("Experimental model projection; the one-year model "
                        "does not beat both baselines and its multi-year linear "
                        "extension is not independently validated."
                        if using_model else
                        "Historical long-run rate extended linearly; not a forecast."),
        },
        "features": feats,
    }

    gj = OUT_DIR / f"longrun_trend_{horizon_years}yr.geojson"
    with open(gj, "w") as f:
        json.dump(fc, f, indent=1)

    csv_path = OUT_DIR / "predictions.csv"
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)

    print(f"drawn {len(rows)} transect-side projections")
    for row in sorted(rows, key=lambda z: -abs(z["projected_offset_m"]))[:10]:
        print(f"   transect {row['transect_id']:>3} {row['side']:<5} "
              f"{row['rate_m_per_yr']:+7.1f} m/yr  ->  "
              f"{row['projected_offset_m']:+8.1f} m over {horizon_years} yr "
              f"(range {row['offset_low_m']:+.0f} to {row['offset_high_m']:+.0f})")

    print(f"\n-> {gj}")
    print(f"-> {csv_path}")
    print("\nNOTE: model projections are experimental unless the chronological "
          "backtest beats both baselines; see ml/artifacts/model_report.json.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--horizon", type=int, default=DEFAULT_HORIZON,
                    help="years to carry the long-run rate forward")
    args = ap.parse_args()
    build(args.horizon)


if __name__ == "__main__":
    main()