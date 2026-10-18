# Colab: prove the no-signal finding with a real model

## Why this notebook exists, and why it is NOT a forecasting notebook

An earlier version of this file trained an XGBoost model to predict next year's
bank erosion and write a predicted bankline. **That has been abandoned**, and this
file now does something more useful.

On the laptop we established with simple statistics that year-to-year erosion
cannot be predicted:

| predictor | MAE (m/yr) |
|---|---|
| predict the average | **83.9** |
| this transect's own past average | 87.1 |
| same transect, previous pair | 133.7 |
| real GloFAS discharge (within transect) | r = +0.049 |

Simple correlations can be misleading though. A nonlinear model with many
features might still find something the pairwise correlations missed. So we
test that properly, here, with a real model and proper cross-validation.

**This test has already been run** — locally, on 2026-10-18, because 1.9k rows
turns out to be a laptop-sized job (~80 s, no GPU). The result is recorded in
DECISIONS.md **D47** and reports/VALIDATION.md section 5: nothing usefully
beats the baseline. This notebook remains so the result can be reproduced
independently on Colab.

## What you need

Nothing heavy. The data is already prepared on the laptop:

```
data/processed/features/landsat/features_hydro.csv  1876 rows, 1989-2026
```

## Step 1 - on your laptop, check the file is there

```
ls -la ~/Projects/riverguard/data/processed/features/landsat/
```

## Step 2 - upload `features_hydro.csv` to Colab, then run this one cell

There is only one cell and it is the correct one. (An older version of this
file opened with a deliberately broken cell as a paste-the-right-block trap;
that was deleted - a notebook that errors on purpose teaches the wrong habit.)

```python
# RiverGuard: does ANY model beat the trivial baselines?
import pandas as pd, numpy as np
from sklearn.model_selection import GroupKFold, cross_val_predict
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.metrics import mean_absolute_error

df = pd.read_csv("features_hydro.csv")
print("rows", len(df), "cols", len(df.columns))

TARGET = "target_rate"
df = df.dropna(subset=[TARGET]).copy()

# previous-year hydrology, derived from the (year1 value, year1-year0 change)
# pairs the CSV already carries, so every feature below is knowable BEFORE the
# target year begins
for base in ["q_mean", "q_min", "q_max", "q_std", "q_cv",
             "q_dry_season_mean", "q_monsoon_mean", "q_monsoon_max"]:
    df[f"{base}_prev"] = df[base] - df[f"{base}_chg"]
df["stage_prev"] = df["stage_km2"] - df["stage_change_km2"]

# FORECAST-ONLY: nothing measured during the target interval. The bank's own
# history, start-of-year width, static bend geometry, previous-year forcing.
FORECAST = ["rate_lag1", "rate_lag2", "rate_roll3", "rate_std3", "n_prior",
            "width_lag1", "curvature_k", "meander_off_m", "arc_norm",
            "q_mean_prev", "q_min_prev", "q_max_prev", "q_std_prev",
            "q_cv_prev", "q_dry_season_mean_prev", "q_monsoon_mean_prev",
            "q_monsoon_max_prev", "stage_prev"]

# FORCING adds same-year discharge and stage: physically causal, but not
# knowable before the year starts, so a win here is not an operational forecast.
Q_NOW = [c for c in df.columns if c.startswith("q_") and not c.endswith("_prev")]
FORCING = FORECAST + Q_NOW + ["stage_km2", "stage_change_km2",
                              "stage_ratio", "stage_change_ratio"]

# AS-FIRST-WRITTEN keeps the old notebook's extra columns: other bank's rate
# for the same pair, end-of-year width, width change. These are outcomes of
# the same interval as the label, so they are excluded from the real test;
# the set is kept only to show they add nothing (measured r with the label:
# -0.05..+0.01). See D47.
AS_FIRST_WRITTEN = FORCING + ["other_side_rate", "width_m",
                              "width_change_pct", "width_ratio"]

y = df[TARGET]
groups = df["transect_id"]          # keep a transect entirely in one fold

# GroupKFold by transect: the model must never see one part of a bank in
# training and another part of the SAME bank in testing, or it just memorises
# where that bank tends to erode. That is the leak that makes erosion models
# look brilliant and generalise to nothing.
gkf = GroupKFold(n_splits=5)

MODELS = [
    ("RandomForest", RandomForestRegressor(
        n_estimators=500, min_samples_leaf=5, random_state=0, n_jobs=-1)),
    ("GradientBoosting", GradientBoostingRegressor(
        n_estimators=300, max_depth=3, learning_rate=0.05,
        subsample=0.8, random_state=0)),
]

print(f"\nglobal mean-baseline (the published 83.9): "
      f"MAE {np.abs(y - y.mean()).mean():.2f} m/yr")

for label, feats in [("FORECAST-ONLY (honest)", FORECAST),
                     ("+ SAME-YEAR FORCING", FORCING),
                     ("AS-FIRST-WRITTEN (kept as demonstration)", AS_FIRST_WRITTEN)]:
    print(f"\n=== {label}: {len(feats)} features ===")
    X = df[feats]
    Xc = X.fillna(X.median(numeric_only=True))

    # two bars, both leak-free: the per-fold train mean (the published 83.9)
    # and the per-fold train MEDIAN - for MAE the median constant is the
    # stronger baseline, and the one a model must beat to be interesting
    for strat in ("mean", "median"):
        p = cross_val_predict(DummyRegressor(strategy=strat), Xc, y,
                              cv=gkf, groups=groups)
        print(f"  {strat:6s} dummy baseline: MAE {mean_absolute_error(y, p):7.2f}")
    med = cross_val_predict(DummyRegressor(strategy="median"), Xc, y,
                            cv=gkf, groups=groups)
    bar = mean_absolute_error(y, med)

    for name, model in MODELS:
        pred = cross_val_predict(model, Xc, y, cv=gkf, groups=groups, n_jobs=1)
        mae = mean_absolute_error(y, pred)
        r = np.corrcoef(y, pred)[0, 1]
        verdict = ("BEATS median baseline" if mae < bar - 1.0 else
                   "no useful win (within ~1 m/yr of the median baseline)")
        print(f"  {name:<18} MAE {mae:7.2f}   r {r:+.3f}   -> {verdict}")

print("""
WHAT THIS MEANS
--------------
Beating the MEAN baseline by a hair (under ~1 m/yr out of 84) is not a finding:
the median constant already scores ~83.5, and a model that only learns
"predict something near the median" gets there for free. A model that wins
by a hair on one cross-validation split will usually lose on the next
(this one flips between 83.3 and 84.4 depending on seed and fold count - D47).

If neither model beats the MEDIAN baseline by a clear margin, the conclusion
stands: the data cannot forecast year-to-year bank movement, and the project
should say so plainly. Report the chronic-risk ranking instead - reports/RISK.md.

If a model DOES beat the median baseline by a clear margin, that is genuinely
interesting: report the honest cross-validated number, check it holds across
seeds and fold counts, and bring it back before changing anything.
""")
```

## Step 3 - bring the numbers back

Paste the printed MAE values into `reports/DECISIONS.md` as a new numbered
entry, and update `reports/VALIDATION.md` section 5. Both are append-only
records of what was actually measured, so they must reflect the real output
rather than a guess.

The same test also runs locally, no Colab needed:

```
cd ml && ../.venv/bin/python 14_model_test.py
```

## A note on honesty

Whatever this prints, the numbers that go in the write-up must be the ones that
actually came out. The published numbers (D47) came from the local run with
scikit-learn 1.9.1; Colab's version may differ in the second decimal, which
changes nothing.
