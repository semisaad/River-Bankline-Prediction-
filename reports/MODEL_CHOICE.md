# RiverGuard - why gradient boosting, and why the hydrology features were rejected

Reach: `arial_khan`. Sensor: Landsat. Date: 2026-10-19.
Every number here is reproduced by the commands in section 7.

This report answers two questions honestly:

1. Why is HistGradientBoostingRegressor the model, and by how much does it beat
   the alternatives?
2. Why did adding hydrology make the result worse, and why is it not in the model?

A third section was added because the numbers demanded it: the model's advantage
is not evenly spread across time, and that matters more than the choice of model.

---

## 1. What is being predicted, and how it is scored

**Target.** `target_rate` - how fast one bank side moved over a pair of years, in
metres per year. **Positive means land was lost (erosion).** Each row is one bank
side of one transect over one pair of years.

**Size of the test.** 2,284 held-out bank-side/year records, 29 test years
(1996-2026, 1997 missing from the Landsat record), 76 bank sides, 14 features.

**Scoring method: expanding-window backtest.** For each test year, the model is
trained only on years *before* it and then predicts it. Every feature is
constrained to be known before the target window starts (D80). Missing-value
medians are fitted on training years only.

This is the only scoring used below. No model was scored on data it was trained
on, and no feature selection was done against the reported score.

**The three trivial baselines.** These are what the model has to beat to be worth
anything:

| baseline | what it does |
|---|---|
| median | predict the median rate seen in training years |
| mean | predict the mean rate seen in training years |
| repeat previous pair | predict that the next pair moves at the same rate as the last one |

`forecast_supported` is true only when the model's MAE is lower than **all three**.
The gate uses the *strongest* of them, not the median one - which is why the map
payload now carries `best_baseline_mae_m_per_yr` (D89).

---

## 2. Why gradient boosting - and by how much

### 2.1 Against the baselines: a wide, real margin

| predictor | MAE (m/yr) | gap to the model |
|---|---:|---:|
| **HistGradientBoostingRegressor** | **15.675** | - |
| median baseline (strongest) | 20.413 | **+4.527 (+22.2%)** |
| mean baseline | 20.723 | +4.837 (+23.3%) |
| repeat previous pair | 23.284 | +7.398 (+31.8%) |

So the model is **22.2% better than the strongest trivial predictor** and 31.8%
better than assuming the rate repeats. `beaten_by` is empty: no baseline beats it.

### 2.2 Against the forest: a small margin, and it was taken

| model | MAE (m/yr) |
|---|---:|
| **HistGradientBoostingRegressor** (400 iters, lr 0.05, 31 leaves, seed 0) | **15.675** |
| RandomForest (500 trees, `min_samples_leaf=5`, seed 0) | 15.886 |

**Gradient boosting is 0.211 m/yr (1.3%) better on the current feature table.**
Both are seeded and both reproduce exactly on a re-run.

Per year, the two split almost evenly: GBM is better in 16 of 29 folds, RandomForest
in 13. GBM's wins are larger (-2.75 m/yr at its best fold, 2015) and its losses are
smaller (-0.03 m/yr at its worst), which is where the 0.211 comes from. On 29 folds
and 2,284 rows, a 1.3% difference with a 16/13 split is within fold-to-fold noise.

**1.3% was still taken (D94).** An earlier draft of this report called the pair a
tie and kept the forest for continuity. That was the wrong call, and the reason is
the one thing that *is* unambiguous here: the comparison is controlled. Same folds,
same rows, same features, both seeded and reproducible. There is no principle on
which to prefer the model that scored worse on the identical test — and "we kept
the worse one because the gap looked small" is not a defensible sentence in a
methods chapter. A small, reproducible, out-of-sample margin is still a margin.

**A claim that must be withdrawn.** D82 recorded that RandomForest beat
`HistGradientBoostingRegressor` 17.330 to 17.468. That comparison was run on the
table **before `curv_outer` was added**. Both models improved substantially once
signed curvature was available, and they did not improve by the same amount. The
D82 result was true of the table it was measured on and is no longer true of the
current one. It is superseded here rather than quietly left standing.

### 2.3 What the switch costs, honestly

The three arguments for keeping the forest were real. Two of them are now paid for
in code, and the third was never an argument at all:

1. **Feature importance.** `RandomForestRegressor` exposes `feature_importances_`
   directly; gradient boosting does not, so the pipeline falls back to
   **permutation importance** (it crashed `--model gbm` once, after printing its
   score — D82). Paid for: `14_model_train.py` now detects which kind of model it
   has and uses the appropriate method. **But the two methods do not rank the
   features the same way**, and that is a real cost — see section 3.
2. **Fewer knobs.** A forest has two settings that matter here
   (`n_estimators`, `min_samples_leaf`); boosting has four or five that interact,
   so there are more ways to tune against the backtest and mistake that for skill.
   Mitigated, not solved: `GBM_PARAMS` is fixed, `early_stopping` is **off**, and
   the same settings are used for the scored model and the saved one. Nothing was
   tuned against the reported score.
3. **Continuity.** Originally the strongest argument — every number in `RISK.md`,
   `VALIDATION.md` and the map came from the forest, and switching changes all of
   them. Rejected as a *reason to keep the wrong model*: the whole pipeline is
   reproducible from `features.csv` in about a minute, so continuity is a
   re-run away. Continuity is a reason to be careful, not a reason to be wrong.

**Write it up as a small controlled margin, not a win.** 1.3% on one reach, with a
16/13 fold split, does not show that boosting is generally better for this
problem — only that it is very slightly better on this dataset, measured properly.

---

## 3. Where the model's accuracy actually comes from

**Read the next paragraph before the table.** The served model is gradient
boosting, which has no built-in importance, so the pipeline measures it by
**permutation importance**: shuffle one feature, watch how much the error grows.
Two consequences, both stated rather than hidden:

- The values are **in units of m/yr of added error**, not percentages, so they do
  **not sum to 100%**.
- Permutation importance ranks features differently from the forest's built-in
  importance. The two tables below are both presented, because the disagreement is
  informative rather than one of them being wrong.

Served model - `HistGradientBoostingRegressor`, permutation importance:

| feature | added error (m/yr) | what it is |
|---|---:|---|
| `curv_outer` | **0.411** | signed curvature: +1 when this bank is the OUTSIDE of a bend |
| `rate_lag1` | 0.275 | how fast this bank moved in the previous pair |
| `n_prior` | 0.274 | how many prior measurements this bank has |
| `arc_norm` | 0.231 | position along the reach |
| `meander_off_m` | 0.210 | distance of the channel from its long-run path |
| `rate_mean_all` | 0.147 | mean rate over the bank's whole history |
| `rate_std_all` | 0.137 | variability of this bank's rate over its history |
| `stage_km2_prev` | 0.120 | water area at the previous measurement |
| `width_lag1` | 0.110 | channel width at the previous measurement |
| `curvature_k` | 0.109 | unsigned curvature magnitude |

Previous model - `RandomForestRegressor`, built-in importance (sums to 100%):

| feature | importance | what it is |
|---|---:|---|
| `rate_lag1` | 19.1% | how fast this bank moved in the previous pair |
| `arc_norm` | 13.8% | position along the reach |
| `meander_off_m` | 11.8% | distance of the channel from its long-run path |
| `rate_mean_all` | 8.8% | mean rate over the bank's whole history |
| `curv_outer` | 8.4% | signed curvature: +1 when this bank is the OUTSIDE of a bend |
| `n_prior` | 7.7% | how many prior measurements this bank has |
| `stage_km2_prev` | 7.2% | water area at the previous measurement |

**What the two rankings agree on**, and this is the part worth putting in the
thesis: the model is not using one thing. Roughly **40% of the forest's importance
sits on the bank's own history** (the rate features) and **about 39% on bend
geometry** (`arc_norm`, `meander_off_m`, `curv_outer`, `curvature_k`). Two
independent views of the problem, both earning their place.

**Where they disagree**: permutation importance puts `curv_outer` first by a clear
margin, the forest's built-in importance puts it fifth. The reason is
methodological — built-in importance rewards a feature for being *used often*
across many trees, including as a tie-breaker in splits that barely matter, while
permutation importance measures the damage done when the feature is scrambled.
They answer different questions. Do not quote one as if it were the other.

Two things worth noting for the write-up, whichever table is cited:

- `curv_outer` was the single change that produced an **8.3% MAE gain**
  (17.330 -> 15.886, D82). That is the textbook result — outer banks erode, inner
  banks accrete — showing up in our own measurements.
- `n_prior` is not physics, it is *how much history a bank has*. It scores highly
  because banks with short records are harder to predict. That is a data-quality
  signal, not a geomorphic one, and it belongs in the limitations.

---

## 4. The caveat that matters more than the model choice

The headline "22.2% below the best baseline" is true of the whole backtest, but it
is **not true of the recent record**, and the projection is made from the recent
record.

| period | folds | model beats that fold's baseline | mean gain per fold |
|---|---:|---:|---:|
| 1996-2015 | 18 | **18 / 18** | **+7.53 m/yr** |
| 2016-2026 | 11 | **2 / 11** | **-0.82 m/yr** |

In the last ten folds, the model is slightly *worse* than simply predicting the
training median:

| test year | model MAE | baseline MAE | gain |
|---|---:|---:|---:|
| 2017 | 14.96 | 15.95 | +0.99 |
| 2018 | 11.54 | 9.43 | -2.11 |
| 2019 | 12.71 | 11.99 | -0.72 |
| 2020 | 10.88 | 10.42 | -0.47 |
| 2021 | 11.76 | 12.64 | +0.87 |
| 2022 | 10.29 | 8.73 | -1.57 |
| 2023 | 10.47 | 10.15 | -0.32 |
| 2024 | 7.57 | 6.08 | -1.49 |
| 2025 | 7.99 | 6.94 | -1.04 |
| 2026 | 8.76 | 6.37 | -2.39 |

**Why this happens.** In the early folds the model is trained on only 2-5 years,
so the training median is a poor estimate of the next year and the model wins
easily - and those years also have the largest absolute errors (rates were around
20-30 m/yr), so they dominate the pooled MAE. By 2016 the training set is large,
the median is a good predictor, and the rates are smaller and more stable, so the
baseline is hard to beat and the model adds noise.

**What this does and does not mean.**

- It does **not** invalidate the measurement chain. Mask agreement, cross-sensor
  IoU, and the literature comparison are separate and unaffected.
- It **does** limit the forecast claim. The 10-year lines drawn on the map are
  extended from the most recent regime, and in that regime the model has not been
  shown to beat a trivial baseline. "The aggregate backtest passes" is weaker than
  it sounds.
- `VALIDATION.md` section 7 still quotes the **pre-correction** numbers (3.175
  against a 2.507 baseline, verdict "not supported"). That section is stale: the
  bankline correction (D77-D84) rescaled the target. The substance of its warning
  has not gone away - see this section - but its numbers no longer match the
  pipeline and should be regenerated before they are quoted in a write-up.

---

## 5. Why the hydrology features made it worse

### 5.1 What was tried

`gee/hydro_export.js` exports ERA5-Land daily aggregates over the reach, averaged
per calendar year. `11_hydro_features.py` turned 8 bands into **24 columns** - for
each band, a value at year0, a change over the pair window, and an expanding-median
anomaly. `14_model_train.py --hydro` scored it through the **identical** backtest
and folds.

### 5.2 Result: worse

| | no hydro | + hydro | change |
|---|---:|---:|---:|
| **model MAE** | **15.886** | **16.562** | **+0.676 (+4.3% worse)** |
| median baseline | 20.413 | 20.413 | 0 |
| mean baseline | 20.723 | 20.723 | 0 |
| repeat previous pair | 23.284 | 23.284 | 0 |

Both still clear the baselines, but the hydrology version is strictly worse. It
does not reach the 16 m/yr threshold that was the point of trying it.

### 5.3 Why: the columns are near-noise

All 24 columns are passed to the forest - none were silently dropped - but their
importance is negligible:

| column | importance |
|---|---:|
| `clim_u_component_of_wind_10m_chg` (strongest) | 1.2% |
| `clim_v_component_of_wind_10m_chg` | 0.9% |
| any runoff or precipitation column | **<= 0.5%** |
| all 24 together | ~10% |

Raw correlation with the erosion label, over 2,414 rows:

| column | r |
|---|---:|
| `clim_total_precipitation_sum` | +0.056 |
| `clim_runoff_sum` | +0.045 |
| `clim_sub_surface_runoff_sum` | +0.045 |
| `clim_u_component_of_wind_10m` | +0.026 |
| `clim_surface_solar_radiation_downwards_sum` | -0.035 |
| `clim_v_component_of_wind_10m` | -0.041 |
| `clim_potential_evaporation_sum` | +0.042 |

The signs are not absurd - rain and runoff point the right way, more water and
more erosion - but nothing exceeds 0.056.

**Why adding weak features hurts.** Twenty-four columns that carry almost no
signal give the forest many more ways to fit the training folds. Those fits do
not generalise, so the error on unseen years rises. The +0.676 m/yr is the price
of the extra freedom, and it is the expected outcome of adding noise.

### 5.4 Why it is not in the model

Because it was measured and it made the result worse. It is not excluded on
principle, on cost, or because it was overlooked - it was tried with the exact
same backtest, it lost, and the loss is recorded (D90).

It is also not evidence that hydrology does not drive erosion. It plainly does.
What this says is that this **measurement** of it is useless as a feature:

- ERA5-Land is about 11 km per cell. The study box is about 10 x 14 km. So the
  "forcing" is roughly **one number per year for the whole reach.**
- The target is measured on 30 m Landsat pixels, and on a ~300 m river **63% of
  the rates are exactly 0 m** (D84) because the pixels cannot resolve the movement.
- A single annual weather figure has nothing to attach to in a target that coarse.

The constraint is the target, not the feature list. Adding predictors at the far
end of a long causal chain does not loosen it.

### 5.5 What was already tried before this

`GloFAS` was the first attempt, because it gives real discharge in m3/s. At this
reach its nearest cell reads a mean of 5.22 m3/s and a **maximum of 13.28 m3/s for
a whole year**, with the right seasonal shape but a magnitude orders of magnitude
too small: a ~5 km cell cannot see a 300 m distributary, so it models a small
local catchment, not the Arial Khan (D88). A perfect 38-year download would still
have been the wrong river.

---

## 6. What would change these conclusions

1. **A finer target.** Sentinel-2 is 10 m and would resolve more movement, but its
   annual signal is currently indistinguishable from noise - lag correlations are
   negative (-0.082 to -0.200) and the model does not beat its baseline. The limit
   there is record length, not model choice.
2. **Independent ground truth.** No surveyed banklines exist. Everything rests on
   our own mask edges. Digitising ~20 bankline points from Google Earth would test
   the measurement itself rather than the model.
3. **Discharge that resolves this river.** Neither ERA5-Land (too coarse) nor
   GloFAS (wrong cell) does. A gauged record at the reach, or a hydrodynamic model,
   would be a genuinely different input - but neither is available to this project.

---

## 7. How to reproduce every number

```bash
cd ~/Projects/riverguard/ml

# Gradient boosting - the served default (writes model_report.json)
RIVERGUARD_REACH=arial_khan ../.venv/bin/python 14_model_train.py --sensor landsat

# RandomForest, for comparison (writes model_report_rf.json)
RIVERGUARD_REACH=arial_khan ../.venv/bin/python 14_model_train.py --sensor landsat --model gbm

# RandomForest + hydrology (writes model_report_rf_hydro.json)
RIVERGUARD_REACH=arial_khan ../.venv/bin/python 11_hydro_features.py landsat
RIVERGUARD_REACH=arial_khan ../.venv/bin/python 14_model_train.py --sensor landsat --hydro

# All standing checks
RIVERGUARD_REACH=arial_khan ../.venv/bin/python 09_checks.py
```

Both models are seeded (`random_state=0`), so these reproduce exactly.

Decisions referenced: D63 (leakage), D80 (feature windows), D82 (`curv_outer`,
and the superseded GBM comparison), D84 (target quantisation), D88 (GloFAS),
D89 (the warning that contradicted itself), D90 (hydrology result).
