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

# Which sensor's prediction file to draw. Set from --sensor in main(); defaults
# to Landsat because it is the record long enough to support a forecast (D81).
_SENSOR = "landsat"


def sensor():
    return _SENSOR


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

    # One prediction file per sensor. Prefer the requested one, otherwise the
    # first that exists, and SAY which was used - the two differ in whether the
    # forecast is supported at all (D81), so silently picking one would put an
    # unsupported projection on the map without saying so.
    model_csv = C.DATA_PROC / "predictions" / f"model_predictions_{sensor()}.csv"
    if not model_csv.exists():
        cands = sorted((C.DATA_PROC / "predictions").glob("model_predictions_*.csv"))
        if cands:
            model_csv = cands[0]

    if model_csv.exists():
        src = model_csv
        print(f"using MODEL predictions from {model_csv}")
        print(f"  sensor: {model_csv.stem.replace('model_predictions_', '')}")
    elif RISK_CSV.exists():
        src = RISK_CSV
        print(f"no model yet - falling back to LONG-RUN RATES from {RISK_CSV}")
        print("(run 14_model_train.py for a trained projection)")
    else:
        print(f"Missing both {model_csv} and {RISK_CSV}")
        print("Run 14_model_train.py (model) or 13_risk_and_forecast.py (rates).")
        return

    using_model = src != RISK_CSV
    risk = pd.read_csv(src)
    forecast_supported = (bool(risk["forecast_supported"].iloc[0])
                          if using_model else False)
    model_mae = (float(risk["model_mae_m_per_yr"].iloc[0])
                 if using_model else None)
    median_mae = (float(risk["median_baseline_mae_m_per_yr"].iloc[0])
                  if using_model else None)
    # forecast_supported is decided against the STRONGEST of the three trivial
    # baselines, not the median one. That is the number any claim about beating
    # the baselines rests on, so it is the one reported. Older prediction files
    # predate the column; falling back to the median keeps them drawable.
    if not using_model:
        best_mae = None
    elif "best_baseline_mae_m_per_yr" in risk.columns:
        best_mae = float(risk["best_baseline_mae_m_per_yr"].iloc[0])
    else:
        best_mae = median_mae
    # The estimator's name travels with the rows (14_model_train.py writes it) so
    # this file cannot name the wrong model. It used to hardcode "RandomForest",
    # which became a lie the moment the default changed.
    if not using_model:
        model_name = None
    else:
        model_name = str(risk["model_name"].iloc[0]) \
            if "model_name" in risk.columns else "model"
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
        print(f"experimental {model_name} MAE {model_mae} vs median baseline "
              f"{median_mae}; forecast supported: {forecast_supported}\n")
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
                "method": (f"{model_name}, expanding-window backtest"
                           if using_model else "long-run rate"),
                "projection_status": "experimental" if using_model
                                     else "historical_trend",
                "horizon_validated": False,
                "forecast_supported": forecast_supported,
                "is_forecast": False,
                "mae_model_m_per_yr": model_mae,
                "median_baseline_mae_m_per_yr": median_mae,
                "best_baseline_mae_m_per_yr": best_mae,
                "basis": (f"Experimental {model_name} projection"
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
            "method": (f"{model_name}, expanding-window backtest"
                       if using_model else "long-run rate"),
            "projection_status": "experimental" if using_model
                                 else "historical_trend",
            "horizon_validated": False,
            "forecast_supported": forecast_supported,
            "is_forecast": False,
            "mae_model_m_per_yr": model_mae,
            "median_baseline_mae_m_per_yr": median_mae,
            "best_baseline_mae_m_per_yr": best_mae,
            "model_name": model_name,
        })

    if not feats:
        print("No usable rows matched the measured transects.")
        return

    # COMPOSED FROM THE NUMBERS IN THIS SAME PAYLOAD, not written out by hand.
    #
    # This text used to be hardcoded to "the one-year model does not beat both
    # baselines" and stayed there after the model started beating all three of
    # them, so the map shipped a sentence contradicting the MAE figures sitting
    # in the same file (15.886 against a best baseline of 20.413). A warning that
    # is typed once and never re-read is a warning that will be wrong later.
    if not using_model:
        warning = ("Historical long-run rate extended linearly; not a forecast.")
    elif forecast_supported:
        warning = (f"Experimental model projection. The one-year model beats the "
                   f"baselines it was tested against: {model_mae:.1f} m/yr against "
                   f"{best_mae:.1f} m/yr for the strongest trivial predictor. The "
                   f"multi-year extension drawn here is a linear extrapolation of "
                   f"that one-year rate and is NOT independently validated.")
    else:
        warning = (f"Experimental model projection. The one-year model does NOT "
                   f"beat the baselines it was tested against: {model_mae:.1f} "
                   f"m/yr against {best_mae:.1f} m/yr for the strongest trivial "
                   f"predictor. Its multi-year linear extension is not "
                   f"independently validated either.")

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
            "method": (f"{model_name}, expanding-window backtest"
                       if using_model else "long-run rate"),
            "projection_status": "experimental" if using_model
                                 else "historical_trend",
            "horizon_validated": False,
            "forecast_supported": forecast_supported,
            "is_forecast": False,
            "mae_model_m_per_yr": model_mae,
            "median_baseline_mae_m_per_yr": median_mae,
            "best_baseline_mae_m_per_yr": best_mae,
            "model_name": model_name,
            "warning": warning,
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
    # Same reasoning as the map warning above: state the measured result instead
    # of a fixed sentence about what the result would have to be.
    if not using_model:
        print("\nNOTE: no model was used - these are historical long-run rates "
              "extended linearly, not a forecast.")
    elif forecast_supported:
        print(f"\nNOTE: the chronological backtest beats every trivial predictor "
              f"it was scored against ({model_mae:.1f} vs {best_mae:.1f} m/yr for "
              f"the best of them). The multi-year extension is still "
              f"experimental - see ml/artifacts/model_report.json.")
    else:
        print(f"\nNOTE: model projections are EXPERIMENTAL - the chronological "
              f"backtest does NOT beat every baseline ({model_mae:.1f} vs "
              f"{best_mae:.1f} m/yr for the best of them). See "
              f"ml/artifacts/model_report.json.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--horizon", type=int, default=DEFAULT_HORIZON,
                    help="years to carry the long-run rate forward")
    ap.add_argument("--sensor", default="landsat", choices=sorted(C.SENSORS),
                    help="which sensor's predictions to draw (default landsat, "
                         "the record long enough to support a forecast)")
    args = ap.parse_args()
    global _SENSOR
    _SENSOR = args.sensor
    build(args.horizon)


if __name__ == "__main__":
    main()