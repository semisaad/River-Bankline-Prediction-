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
    "rate_lag1", "rate_lag2", "rate_lag3", "rate_roll3", "rate_std3",
    "rate_mean_all", "rate_std_all", "n_prior",
    "width_lag1", "curvature_k", "curv_outer", "meander_off_m", "arc_norm",
    "stage_km2_prev",
]

# Columns measured over the SAME interval as the target, so they cannot be known
# when the prediction has to be made. They stay in the feature table because
# other analyses use them, but using them for forecasting was the leakage that
# made the first reported score (MAE 2.843 m/yr) meaningless - see D63.
#
# THOSE NUMBERS ARE HISTORICAL. D63's corrected test gave 3.175 against a 2.507
# baseline, but that was before the bankline correction (D77-D84) rescaled the
# target. The current figures are 15.886 against 20.413. What survives is the
# lesson, not the arithmetic - and D92 shows the "beats the baseline" verdict
# only holds for 1996-2015.
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

# Gradient boosting, kept here so the two can be scored through the SAME
# backtest rather than compared on different code paths. On tabular data of this
# shape it usually edges out a forest, but "usually" is not a reason to assume
# it - the expanding-window backtest below decides, and either can lose.
#
# early_stopping is OFF and the iteration count is fixed, because the internal
# validation split that early stopping uses is drawn from the training rows, and
# this project's whole discipline is that the scored model and the saved model
# are identical.
GBM_PARAMS = dict(max_iter=400, learning_rate=0.05, max_leaf_nodes=31,
                  min_samples_leaf=20, l2_regularization=1.0,
                  early_stopping=False, random_state=0)

# The configuration the map, the API and reports/VALIDATION.md actually serve.
# Exactly one model and one sensor hold these defaults, because the artefact
# names are keyed off them: the default writes model_report.json and
# model_predictions_landsat.csv, and anything else writes a suffixed variant.
#
# Gradient boosting took the default in D94. It won by 0.211 m/yr - 1.3% - which
# is small, and the project's stated position is that a small, reproducible,
# out-of-sample margin is still a margin. See reports/MODEL_CHOICE.md.
#
# D94 also moved DEFAULT_SENSOR to landsat. The trainer previously defaulted to
# s2 while model_report.json is written with no sensor in its name and
# backend/core/views.py reads it as the served model - so a bare re-run, which
# is what README.md tells you to type, would have described the map with the
# wrong sensor's numbers. Same failure shape as D81.
DEFAULT_MODEL = "gbm"
DEFAULT_SENSOR = "landsat"

MODEL_NAMES = {"rf": "RandomForestRegressor",
               "gbm": "HistGradientBoostingRegressor"}


def model_label(kind):
    """Human-readable description of the model that actually ran.

    The report used to hardcode a RandomForest string regardless of --model, so
    a --model gbm run produced an artefact that named the wrong estimator while
    carrying that estimator's score.
    """
    if kind == "gbm":
        return (f"HistGradientBoostingRegressor(max_iter={GBM_PARAMS['max_iter']}, "
                f"learning_rate={GBM_PARAMS['learning_rate']}, "
                f"max_leaf_nodes={GBM_PARAMS['max_leaf_nodes']})")
    return (f"RandomForestRegressor(n_estimators={RF_PARAMS['n_estimators']}, "
            f"min_samples_leaf={RF_PARAMS['min_samples_leaf']})")


def make_model(kind):
    if kind == "gbm":
        from sklearn.ensemble import HistGradientBoostingRegressor
        return HistGradientBoostingRegressor(**GBM_PARAMS)
    return RandomForestRegressor(**RF_PARAMS)


def load(reach, sensor, hydro=False):
    # Hydro forcing lands in a separate table (11_hydro_features.py) rather than
    # being merged into features.csv. That separation is deliberate - it means
    # the hydro model can be scored against the identical backtest as the base
    # one, instead of the two differing in code as well as in inputs.
    name = "features_hydro.csv" if hydro else "features.csv"
    p = C.DATA_PROC / "features" / sensor / name
    if not p.exists():
        if hydro:
            raise SystemExit(
                f"no hydro feature table at {p}\n"
                f"run: RIVERGUARD_REACH={reach} ../.venv/bin/python "
                f"11_hydro_features.py {sensor}")
        raise SystemExit(f"no features at {p}\n"
                         f"run: RIVERGUARD_REACH={reach} ../.venv/bin/python "
                         f"05_features.py {sensor}")
    df = pd.read_csv(p).dropna(subset=["target_rate"])
    return df


def hydro_columns(df):
    """Hydro forcing columns: GloFAS discharge (q_) and ERA5-Land climate (clim_).

    All of them are attached at year0 by 11_hydro_features.py, so none may appear
    in LEAKY_COLUMNS - the guard in features() re-checks that rather than trusting
    this comment. Columns that are entirely empty are dropped: the median fill
    would turn them into a constant, which is a feature that looks present and
    carries nothing.

    Constant columns are dropped for the same reason, and they are a live risk
    rather than a hypothetical one: the GloFAS table carries the chosen cell's
    latitude and longitude, so a column like q_lat is the same number on every
    row. 11_hydro_features.py strips those before prefixing, but a guard that
    depends on another script remembering to strip them is not a guard. A
    constant cannot inform any prediction, and leaving the check here means the
    failure mode is a missing feature rather than a silent one.
    """
    cols = []
    for c in df.columns:
        if not (c.startswith("q_") or c.startswith("clim_")):
            continue
        if not pd.api.types.is_numeric_dtype(df[c]):
            continue
        if df[c].notna().sum() == 0:
            continue
        if df[c].nunique(dropna=True) <= 1:
            continue
        cols.append(c)
    return sorted(cols)


def features(df, hydro=False):
    if "stage_km2" in df and "stage_change_km2" in df:
        df["stage_km2_prev"] = df["stage_km2"] - df["stage_change_km2"]
    cols = [c for c in FORECAST_FEATURES if c in df.columns]
    if hydro:
        cols += [c for c in hydro_columns(df) if c not in cols]
    leaked = sorted(set(cols) & LEAKY_COLUMNS)
    if leaked:
        raise SystemExit(
            f"{leaked} measure the SAME interval as the target, so they are not "
            f"known at prediction time. Using them is the leakage D63 removed. "
            f"Move them out of FORECAST_FEATURES.")
    return cols


def evaluate(df, cols, model_kind=DEFAULT_MODEL):
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
        model = make_model(model_kind)
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
    ap.add_argument("--sensor", default=DEFAULT_SENSOR, choices=sorted(C.SENSORS),
                    help=f"which feature table to train on "
                         f"(default {DEFAULT_SENSOR}, the served one)")
    ap.add_argument("--model", default=DEFAULT_MODEL, choices=["rf", "gbm"],
                    help=f"gbm = gradient boosting (default {DEFAULT_MODEL}), "
                         f"rf = RandomForest")
    ap.add_argument("--hydro", action="store_true",
                    help="add GloFAS discharge and ERA5-Land climate forcing "
                         "(from features_hydro.csv, built by "
                         "11_hydro_features.py). Run with and without it and "
                         "compare the two scores: the extra columns are only "
                         "worth keeping if they move the backtest.")
    args = ap.parse_args()
    reach = C.REACH

    print("=" * 68)
    print(f"RiverGuard model training - {C.REACH_LABEL}")
    print(f"reach {reach} | sensor {args.sensor} | model {args.model} | "
          f"horizon {args.horizon} yr | hydro {args.hydro}")
    print("=" * 68 + "\n")

    df = load(reach, args.sensor, args.hydro)
    cols = features(df, args.hydro)
    if not cols:
        raise SystemExit("no prior-year forecast features found")
    print(f"rows {len(df)} | transects {df.transect_id.nunique()} | "
          f"pairs {sorted(int(y) for y in df.year0.unique())}")
    if args.hydro:
        hcols = [c for c in cols if c.startswith(("q_", "clim_"))]
        print(f"hydro columns {len(hcols)}")
        for c in hcols:
            print(f"  {c:<34} filled {df[c].notna().mean()*100:5.1f}%")

    skill = evaluate(df, cols, args.model)
    print("\nSKILL (expanding-window, prior-year features only)")
    label = {"rf": "RandomForest", "gbm": "GradientBoosting"}[args.model]
    print(f"  {label:<26} MAE {skill['mae_model']:7.3f} m/yr")
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
    model = make_model(args.model)
    model.fit(X, df["target_rate"])

    # Not every estimator exposes feature_importances_; gradient boosting does
    # not, and asking it for one crashed the run after the score was printed.
    if hasattr(model, "feature_importances_"):
        imp = (pd.Series(model.feature_importances_, index=cols)
                 .sort_values(ascending=False))
    else:
        from sklearn.inspection import permutation_importance
        r = permutation_importance(model, X, df["target_rate"], n_repeats=10,
                                   random_state=0)
        imp = (pd.Series(r.importances_mean, index=cols)
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
            # forecast_supported is decided against best_baseline - the STRONGEST
            # of the three trivial predictors, not the median one. The map quotes
            # the number this gate actually used, so it has to travel with the
            # rows; quoting the median instead would overstate the margin in any
            # year where the median is not the strongest.
            "best_baseline_mae_m_per_yr": skill["best_baseline"],
            # Travels with the rows so the map can name the estimator that
            # actually produced them, instead of a string typed here once.
            "model_name": MODEL_NAMES[args.model],
        })

    PRED_DIR.mkdir(parents=True, exist_ok=True)
    # Per sensor. Both sensors once wrote the same filename, so training the
    # second silently overwrote the first - and the one that overwrote it was
    # the sensor whose forecast is NOT supported (D81).
    #
    # The same guard now covers model variants: a --hydro or --model gbm run is
    # for comparison and must not replace the file the map is built from. The
    # default configuration keeps its plain name so 06_predict_geojson.py and the
    # API keep working untouched.
    # Keyed off the SERVED defaults, not off "rf": now that gbm is the default,
    # testing rf must not overwrite the file the map is built from.
    variant = "" if (args.model == DEFAULT_MODEL and not args.hydro) else \
        "_" + args.model + ("_hydro" if args.hydro else "")
    out = PRED_DIR / f"model_predictions_{args.sensor}{variant}.csv"
    pd.DataFrame(rows).to_csv(out, index=False)

    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    report = ARTIFACTS / (f"model_report{variant}.json" if variant
                          else "model_report.json")
    report.write_text(json.dumps(
        {"generated": date.today().isoformat(),
         "reach": reach, "sensor": args.sensor, "hydro": args.hydro,
         "model": model_label(args.model),
         "model_name": MODEL_NAMES[args.model],
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
    print(f"-> {report}")
    print("\nNext: 06_predict_geojson.py draws these onto the map.")


if __name__ == "__main__":
    main()