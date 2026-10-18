"""14 - Can any model beat "predict the average"? (the colab_train test, run locally)

The question notebooks/colab_train.md asks, answered on this laptop because the
table is small (1.9k rows). Three feature sets, all under GroupKFold by transect:

  forecast   only information available at the START of the target year: the
             bank's own history, start-of-year width, static bend geometry,
             and PREVIOUS-year discharge/stage (derived as q_x - q_x_chg)
  forcing    forecast + same-year discharge and stage. Physically causal
             (erosion responds to this year's flow) but not knowable before
             the year begins, so a win here is not an operational forecast.
  as_written what the pre-fix notebook actually fed the models: forcing plus
             same-interval OUTCOMES - the other bank's rate for the same pair,
             end-of-year width, width change. Width change is approximately
             the sum of both banks' movements, i.e. the answer wearing a mask.

Run: ../.venv/bin/python 14_model_test.py
"""

import numpy as np
import pandas as pd
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.metrics import mean_absolute_error
from sklearn.model_selection import GroupKFold, cross_val_predict

import config as C


def load():
    d = C.DATA_PROC / "features" / "landsat"
    p = d / "features_hydro.csv"
    if not p.exists():
        p = d / "features.csv"  # second-reach trial: no hydro features yet
    print(f"table: {p.relative_to(C.ROOT)}")
    df = pd.read_csv(p)
    df = df.dropna(subset=["target_rate"]).copy()

    # previous-year values derived from the (year1 value, year1-year0 change) pairs
    for base in ["q_mean", "q_min", "q_max", "q_std", "q_cv",
                 "q_dry_season_mean", "q_monsoon_mean", "q_monsoon_max"]:
        if base in df.columns and f"{base}_chg" in df.columns:
            df[f"{base}_prev"] = df[base] - df[f"{base}_chg"]
    if "stage_km2" in df.columns and "stage_change_km2" in df.columns:
        df["stage_prev"] = df["stage_km2"] - df["stage_change_km2"]
    return df


def evaluate(df, features, gkf, models):
    X = df[features]
    Xc = X.fillna(X.median(numeric_only=True))
    y = df["target_rate"]
    groups = df["transect_id"]

    dummy = cross_val_predict(DummyRegressor(strategy="mean"),
                              Xc, y, cv=gkf, groups=groups)
    fold_mean_mae = mean_absolute_error(y, dummy)
    print(f"    honest baseline (per-fold train mean): MAE {fold_mean_mae:7.2f}")

    for name, model in models:
        pred = cross_val_predict(model, Xc, y, cv=gkf, groups=groups, n_jobs=1)
        mae = mean_absolute_error(y, pred)
        r = np.corrcoef(y, pred)[0, 1]
        verdict = "BEATS baseline" if mae < fold_mean_mae else "worse than baseline"
        print(f"    {name:<18} MAE {mae:7.2f}   r {r:+.3f}   -> {verdict}")
    return fold_mean_mae


def main():
    df = load()
    y = df["target_rate"]
    print(f"rows {len(df)}  transects {df.transect_id.nunique()}  "
          f"years {int(df.year0.min())}-{int(df.year1.max())}")
    global_mae = float(np.abs(y - y.mean()).mean())
    print(f"global-mean baseline (the 83.9 number): MAE {global_mae:.2f} m/yr")

    print("\ncorrelation of same-interval columns with the label "
          "(why they must be excluded):")
    for c in ["other_side_rate", "width_m", "width_change_pct", "width_ratio"]:
        s = df[[c, "target_rate"]].dropna()
        print(f"    {c:<18} r {s[c].corr(s.target_rate):+.3f}  (n={len(s)})")

    forecast = [c for c in ["rate_lag1", "rate_lag2", "rate_roll3", "rate_std3",
                            "n_prior", "width_lag1", "curvature_k",
                            "meander_off_m", "arc_norm",
                            "q_mean_prev", "q_min_prev", "q_max_prev",
                            "q_std_prev", "q_cv_prev", "q_dry_season_mean_prev",
                            "q_monsoon_mean_prev", "q_monsoon_max_prev",
                            "stage_prev"] if c in df.columns]
    q_now = [c for c in df.columns if c.startswith("q_") and not c.endswith("_prev")]
    stage_now = [c for c in ["stage_km2", "stage_change_km2",
                             "stage_ratio", "stage_change_ratio"]
                 if c in df.columns]
    forcing = forecast + q_now + stage_now
    as_written = forcing + ["other_side_rate", "width_m",
                            "width_change_pct", "width_ratio"]

    models = [
        ("RandomForest", RandomForestRegressor(
            n_estimators=500, min_samples_leaf=5, random_state=0, n_jobs=-1)),
        ("GradientBoosting", GradientBoostingRegressor(
            n_estimators=300, max_depth=3, learning_rate=0.05,
            subsample=0.8, random_state=0)),
    ]
    gkf = GroupKFold(n_splits=5)

    for label, feats in [("FORECAST-ONLY (honest)", forecast),
                         ("+ SAME-YEAR FORCING", forcing),
                         ("AS WRITTEN (leaky)", as_written)]:
        print(f"\n=== {label}: {len(feats)} features ===")
        evaluate(df, feats, gkf, models)


if __name__ == "__main__":
    main()
