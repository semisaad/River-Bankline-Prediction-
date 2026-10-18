"""
14 - Train the erosion model and predict future banklines.

WHAT THIS DOES
    Takes the measured history and learns how a bank behaves, then projects that
    bank forward. This is the project's original aim and it is now supported by
    evidence (see reports/DECISIONS.md D62).

THE RESULT THAT LICENSED THIS
    Arial Khan, Sentinel-2, 432 rows, 31 transects, GroupKFold grouped BY
    TRANSECT so no part of a bank is ever in both training and test:

        predict the average        MAE 2.919 m/yr
        repeat the previous pair   MAE 4.060
        RandomForest               MAE 2.835   r +0.520   <- beats baseline

    On the Jamuna the equivalent correlation was +0.049 and nothing beat the
    baseline. That contrast is the whole reason the study moved rivers.

WHY GroupKFold AND NOT A RANDOM SPLIT
    A random split puts part of a bank in training and another part of the SAME
    bank in the test set. The model then scores highly by memorising where that
    particular bank tends to erode, which tells you nothing about a bank it has
    never seen. That leak is what makes erosion models look excellent and
    generalise to nothing. Grouping by transect removes it, which is why the
    honest number (2.835) is only marginally better than the baseline rather than
    dramatically better.

HONEST LIMITS, IN PLAIN TEXT
    - The margin over "predict the average" is 2.9%. Real, not large.
    - 432 rows over 7 year-pairs is thin. The Landsat record at 5-year blocks is
      what would make this defensible rather than merely promising.
    - The strongest predictors are how the channel is ALREADY changing
      (width_change_pct, other_side_rate, rate_roll3). That is plausible for a
      single-thread meander, but it means the model partly reads the bank's
      current state. Applying it forward assumes that state persists, which is
      the hypothesis under test.
    - Every number below is cross-validated. The exported model is refit on all
      data, so its in-sample fit will look better than 2.835. The 2.835 is the
      number to quote.

WHAT IT WRITES
    data/processed/predictions/predictions.csv
        one row per (transect, bank side): predicted rate, projected position,
        and the interval, for the horizon given on the command line.
    ml/artifacts/model_report.json
        the full skill table, so the claim is reproducible.

Run:
    cd ~/Projects/riverguard/ml
    ../.venv/bin/python 14_model_train.py
    ../.venv/bin/python 14_model_train.py --reach arial_khan --horizon 10
"""

import argparse
import json
from datetime import date

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import GroupKFold, cross_val_predict
from sklearn.metrics import mean_absolute_error

import config as C

ARTIFACTS = __import__("pathlib").Path(__file__).resolve().parent / "artifacts"
PRED_DIR = C.DATA_PROC / "predictions"

# Things that must never be features.
#   transect_id / side  - identifiers; the model would memorise the bank
#   year0 / year1       - the measurement window itself
#   target_rate         - the answer
#   stage_km2           - total water area of the year; a proxy for the label's
#                         own year, and the stage confound is handled explicitly
#                         in reports/VALIDATION.md rather than learned here
LEAKY = {"transect_id", "side", "year0", "year1", "sensor", "res_m",
         "target_rate", "stage_km2"}


def load(reach, sensor):
    p = C.DATA_PROC / "features" / sensor / "features.csv"
    if not p.exists():
        raise SystemExit(f"no features at {p}\n"
                         f"run: RIVERGUARD_REACH={reach} ../.venv/bin/python "
                         f"05_features.py {sensor}")
    df = pd.read_csv(p).dropna(subset=["target_rate"])
    return df


def features(df):
    cols = [c for c in df.columns
            if c not in LEAKY and np.issubdtype(df[c].dtype, np.number)]
    return cols


def evaluate(df, cols, folds=5, seed=0):
    """Cross-validated skill, grouped by transect."""
    X = df[cols].fillna(df[cols].median())
    y = df["target_rate"]
    groups = df["transect_id"]
    gkf = GroupKFold(n_splits=folds)

    model = RandomForestRegressor(n_estimators=500, min_samples_leaf=3,
                                  random_state=seed, n_jobs=-1)
    pred = cross_val_predict(model, X, y, cv=gkf, groups=groups, n_jobs=1)

    base = float(np.mean(np.abs(y - y.mean())))
    lag = df.dropna(subset=["rate_lag1"])
    lag_mae = (float(np.mean(np.abs(lag.target_rate - lag.rate_lag1)))
               if len(lag) else float("nan"))

    out = {
        "rows": int(len(df)),
        "transects": int(groups.nunique()),
        "features": len(cols),
        "cv": f"GroupKFold({folds}) grouped by transect_id",
        "mae_predict_average": round(base, 3),
        "mae_repeat_previous_pair": round(lag_mae, 3),
        "mae_model": round(float(mean_absolute_error(y, pred)), 3),
        "model_beats_baseline": bool(mean_absolute_error(y, pred) < base),
        "correlation_model": round(float(np.corrcoef(y, pred)[0, 1]), 3),
        "correlation_lag1": (round(float(lag.target_rate.corr(lag.rate_lag1)), 3)
                             if len(lag) else None),
    }
    out["improvement_pct"] = round(
        100 * (1 - out["mae_model"] / out["mae_predict_average"]), 1)
    return out, pred


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--horizon", type=int, default=10,
                    help="years ahead to project (default 10)")
    ap.add_argument("--reach", default=C.REACH)
    args = ap.parse_args()

    print("=" * 68)
    print(f"RiverGuard model training - {C.REACH_LABEL}")
    print(f"reach {args.reach} | horizon {args.horizon} yr")
    print("=" * 68 + "\n")

    df = load(args.reach, "s2")
    cols = features(df)
    print(f"rows {len(df)} | transects {df.transect_id.nunique()} | "
          f"pairs {sorted(df.year0.unique())}")

    skill, pred = evaluate(df, cols)
    print("\nSKILL (cross-validated, grouped by transect)")
    print(f"  predict the average        MAE {skill['mae_predict_average']:7.3f} m/yr")
    print(f"  repeat the previous pair   MAE {skill['mae_repeat_previous_pair']:7.3f} m/yr")
    print(f"  RandomForest               MAE {skill['mae_model']:7.3f} m/yr   "
          f"r {skill['correlation_model']:+.3f}")
    verdict = "BEATS" if skill["model_beats_baseline"] else "LOSES TO"
    print(f"\n  {verdict} the baseline by {skill['improvement_pct']}%")

    # refit on everything, for deployment
    X = df[cols].fillna(df[cols].median())
    model = RandomForestRegressor(n_estimators=500, min_samples_leaf=3,
                                  random_state=0, n_jobs=-1)
    model.fit(X, df["target_rate"])

    imp = (pd.Series(model.feature_importances_, index=cols)
             .sort_values(ascending=False))
    print("\nWHAT THE MODEL USES")
    for k, v in imp.head(8).items():
        print(f"  {k:<22} {v:.3f}")

    # ---- project forward, one row per (transect, bank side) ----------------
    last = df[df.year1 == df.year1.max()]
    latest_year = int(df.year1.max())
    proj = model.predict(last[cols].fillna(X.median()))

    # spread of predictions gives a rough interval. Not a calibrated confidence
    # interval - the honest one is the CV MAE, carried forward as +/- that value.
    band = skill["mae_model"]

    rows = []
    for (_, r), p in zip(last.iterrows(), proj):
        rows.append({
            "transect_id": int(r.transect_id),
            "side": r.side,
            "base_year": latest_year,
            "horizon_years": args.horizon,
            "predicted_year": latest_year + args.horizon,
            "predicted_rate": round(float(p), 2),
            "projected_offset_m": round(float(p) * args.horizon, 1),
            "offset_low_m": round(float(p - band) * args.horizon, 1),
            "offset_high_m": round(float(p + band) * args.horizon, 1),
            "n_years_history": int((df.transect_id == r.transect_id).sum()),
        })

    PRED_DIR.mkdir(parents=True, exist_ok=True)
    out = PRED_DIR / "predictions.csv"
    pd.DataFrame(rows).to_csv(out, index=False)

    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    (ARTIFACTS / "model_report.json").write_text(json.dumps(
        {"generated": date.today().isoformat(),
         "reach": args.reach, "sensor": "s2",
         "model": "RandomForestRegressor(n_estimators=500, min_samples_leaf=3)",
         "feature_importance": {k: round(float(v), 4) for k, v in imp.items()},
         "skill": skill,
         "horizon_years": args.horizon,
         "caveats": [
             "Margin over baseline is small; quote the cross-validated MAE, "
             "never the in-sample fit.",
             "432 rows over 7 year-pairs is thin. The Landsat 5-year-block "
             "record is needed before this is defensible.",
             "Strongest features describe how the channel is already changing, "
             "so the model partly reads the bank's current state. Applying it "
             "forward assumes that state persists - which is the hypothesis.",
             "No ground truth; skill is measured only against our own baselines.",
         ]}, indent=2))

    print(f"\nprojected {len(rows)} transect-sides to {latest_year + args.horizon}")
    biggest = sorted(rows, key=lambda z: -abs(z["projected_offset_m"]))[:8]
    print(f"\n{'transect':>9} {'side':<6} {'m/yr':>7} {'offset':>9}  range")
    for r in biggest:
        print(f"{r['transect_id']:>9} {r['side']:<6} {r['predicted_rate']:>7.1f} "
              f"{r['projected_offset_m']:>8.0f}m  "
              f"{r['offset_low_m']:+.0f} to {r['offset_high_m']:+.0f}")
    print(f"\n-> {out}")
    print(f"-> {ARTIFACTS / 'model_report.json'}")
    print("\nNext: 06_predict_geojson.py draws these onto the map.")


if __name__ == "__main__":
    main()