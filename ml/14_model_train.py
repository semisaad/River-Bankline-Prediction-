"""Train and evaluate an experimental future bank-movement model.

Only features available before the target year are allowed. Evaluation moves
forward in time: each held-out year is predicted using earlier years only. The
model is not considered supported unless it beats both the training-median and
previous-year baselines. A multi-year bankline extension remains experimental
even if its one-year rate passes these checks.
"""

import argparse
import json
from datetime import date

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error

import config as C

ARTIFACTS = __import__("pathlib").Path(__file__).resolve().parent / "artifacts"
PRED_DIR = C.DATA_PROC / "predictions"

FORECAST_FEATURES = [
    "rate_lag1", "rate_lag2", "rate_roll3", "rate_std3", "n_prior",
    "width_lag1", "curvature_k", "meander_off_m", "arc_norm",
    "stage_km2_prev",
]

# Columns measured over the SAME interval as the target, so they cannot be known
# when the prediction has to be made. They stay in the feature table because
# other analyses use them, but using them for forecasting was the leakage that
# made the first reported score (MAE 2.843 m/yr) meaningless - see D63, where the
# corrected prior-year test gave 3.175 against a 2.507 median baseline.
#
# Listing them here turns that finding into a check instead of a memory: if one
# is ever added to FORECAST_FEATURES the run stops rather than quietly
# reproducing the same mistake.
LEAKY_COLUMNS = {
    "other_side_rate", "width_m", "width_change_pct", "width_ratio",
    "stage_km2", "stage_change_km2", "stage_ratio", "stage_change_ratio",
}

# ONE definition for the forest, used by both the backtest and the final fit.
#
# They previously differed - the backtest used min_samples_leaf=5 and the
# projection was built with 3 - while the saved artefact described only the
# first. So the reported MAE did not describe the model that drew the map. Same
# settings in both places means the number and the output agree by construction.
RF_PARAMS = dict(n_estimators=500, min_samples_leaf=5, random_state=0, n_jobs=-1)


def load(reach, sensor):
    p = C.DATA_PROC / "features" / sensor / "features.csv"
    if not p.exists():
        raise SystemExit(f"no features at {p}\n"
                         f"run: RIVERGUARD_REACH={reach} ../.venv/bin/python "
                         f"05_features.py {sensor}")
    df = pd.read_csv(p).dropna(subset=["target_rate"])
    return df


def features(df):
    if "stage_km2" in df and "stage_change_km2" in df:
        df["stage_km2_prev"] = df["stage_km2"] - df["stage_change_km2"]
    cols = [c for c in FORECAST_FEATURES if c in df.columns]
    leaked = sorted(set(cols) & LEAKY_COLUMNS)
    if leaked:
        raise SystemExit(
            f"{leaked} measure the SAME interval as the target, so they are not "
            f"known at prediction time. Using them is the leakage D63 removed. "
            f"Move them out of FORECAST_FEATURES.")
    return cols


def evaluate(df, cols):
    """Expanding-window evaluation; never train on a year after the test year."""
    yearly = sorted(df["year1"].unique())
    actual, predicted = [], []
    median_baseline, mean_baseline, lag_baseline = [], [], []
    folds = []

    for year in yearly[2:]:
        train = df[df["year1"] < year]
        test = df[df["year1"] == year]
        if train.empty or test.empty:
            continue

        train_medians = train[cols].median().fillna(0)
        X_train = train[cols].fillna(train_medians)
        X_test = test[cols].fillna(train_medians)
        model = RandomForestRegressor(**RF_PARAMS)
        model.fit(X_train, train["target_rate"])
        fold_pred = model.predict(X_test)
        train_median = float(train["target_rate"].median())
        train_mean = float(train["target_rate"].mean())
        fold_lag = test["rate_lag1"].fillna(train_median).to_numpy()

        actual.extend(test["target_rate"].to_numpy())
        predicted.extend(fold_pred)
        median_baseline.extend([train_median] * len(test))
        mean_baseline.extend([train_mean] * len(test))
        lag_baseline.extend(fold_lag)
        folds.append({
            "test_year": int(year),
            "training_years": int(train["year1"].nunique()),
            "rows": int(len(test)),
            "mae_model": round(mean_absolute_error(test["target_rate"], fold_pred), 3),
            "mae_train_median": round(mean_absolute_error(
                test["target_rate"], [train_median] * len(test)), 3),
        })

    model_mae = float(mean_absolute_error(actual, predicted))
    median_mae = float(mean_absolute_error(actual, median_baseline))
    mean_mae = float(mean_absolute_error(actual, mean_baseline))
    lag_mae = float(mean_absolute_error(actual, lag_baseline))

    # The model must beat EVERY trivial predictor, not just the ones listed in
    # the docstring. Comparing against the median and the previous pair alone
    # would let the flag say "supported" while a flat "predict the mean" beat it,
    # which is the one claim this project cannot afford to get wrong. The mean
    # baseline is computed anyway, so the comparison is free.
    best_baseline = min(median_mae, mean_mae, lag_mae)
    beating = [name for name, mae in (("training median", median_mae),
                                      ("training mean", mean_mae),
                                      ("repeat previous pair", lag_mae))
               if model_mae >= mae]

    return {
        "method": "expanding-window by target year; prior-year features only",
        "test_years": [fold["test_year"] for fold in folds],
        "rows": len(actual),
        "folds": folds,
        "mae_model": round(model_mae, 3),
        "mae_train_median": round(median_mae, 3),
        "mae_train_mean": round(mean_mae, 3),
        "mae_repeat_previous_pair": round(lag_mae, 3),
        "best_baseline": round(best_baseline, 3),
        "beaten_by": beating,
        "forecast_supported": model_mae < best_baseline,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--horizon", type=int, default=10,
                    help="years ahead to project (default 10)")
    args = ap.parse_args()
    reach = C.REACH

    print("=" * 68)
    print(f"RiverGuard model training - {C.REACH_LABEL}")
    print(f"reach {reach} | horizon {args.horizon} yr")
    print("=" * 68 + "\n")

    df = load(reach, "s2")
    cols = features(df)
    if not cols:
        raise SystemExit("no prior-year forecast features found")
    print(f"rows {len(df)} | transects {df.transect_id.nunique()} | "
          f"pairs {sorted(df.year0.unique())}")

    skill = evaluate(df, cols)
    print("\nSKILL (expanding-window, prior-year features only)")
    print(f"  RandomForest               MAE {skill['mae_model']:7.3f} m/yr")
    print(f"  training median baseline   MAE {skill['mae_train_median']:7.3f} m/yr")
    print(f"  training mean baseline     MAE {skill['mae_train_mean']:7.3f} m/yr")
    print(f"  repeat previous pair       MAE {skill['mae_repeat_previous_pair']:7.3f} m/yr")
    print(f"  forecast supported: {skill['forecast_supported']}")
    if skill["beaten_by"]:
        print(f"  -> a trivial predictor still beats it: {', '.join(skill['beaten_by'])}")

    # Refit on the full record to produce a clearly experimental projection,
    # using the SAME settings the backtest just scored (RF_PARAMS).
    train_medians = df[cols].median().fillna(0)
    X = df[cols].fillna(train_medians)
    model = RandomForestRegressor(**RF_PARAMS)
    model.fit(X, df["target_rate"])

    imp = (pd.Series(model.feature_importances_, index=cols)
             .sort_values(ascending=False))
    print("\nWHAT THE MODEL USES")
    for k, v in imp.head(8).items():
        print(f"  {k:<22} {v:.3f}")

    # ---- project forward, one row per (transect, bank side) ----------------
    last = df[df.year1 == df.year1.max()]
    latest_year = int(df.year1.max())
    proj = model.predict(last[cols].fillna(train_medians))

    # This heuristic is not a calibrated multi-year prediction interval.
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
            "n_years_history": int(
                ((df.transect_id == r.transect_id) & (df.side == r.side)).sum()),
            "projection_status": "experimental",
            "forecast_supported": skill["forecast_supported"],
            "model_mae_m_per_yr": skill["mae_model"],
            "median_baseline_mae_m_per_yr": skill["mae_train_median"],
        })

    PRED_DIR.mkdir(parents=True, exist_ok=True)
    out = PRED_DIR / "model_predictions.csv"
    pd.DataFrame(rows).to_csv(out, index=False)

    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    (ARTIFACTS / "model_report.json").write_text(json.dumps(
        {"generated": date.today().isoformat(),
         "reach": reach, "sensor": "s2",
         "model": (f"RandomForestRegressor(n_estimators={RF_PARAMS['n_estimators']}, "
                   f"min_samples_leaf={RF_PARAMS['min_samples_leaf']})"),
         "feature_importance": {k: round(float(v), 4) for k, v in imp.items()},
         "features_used": cols,
         "skill": skill,
         "horizon_years": args.horizon,
         "caveats": [
             "The projection is experimental unless forecast_supported is true.",
             "Validation uses an expanding time window and features known before each target year.",
             "The one-year rate is linearly extended across the requested horizon; long-horizon uncertainty is not calibrated.",
             "No surveyed banklines are available as independent ground truth.",
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