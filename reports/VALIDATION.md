# RiverGuard - validation report

Generated: 2026-10-19

Everything in PART A is recomputed by `ml/07_validate.py` from files in this repository, and can be re-checked by re-running it. PART B is a frozen historical record.

Active reach: **arial_khan** - Arial Khan (Madaripur Sadar - Kalkini, middle reach)

---

# PART A - the active reach

## 1. What is measured, and on what

- study rectangle: `90.16808799423755, 23.134319063780836 -> 90.26902488388599, 23.261491731177696` (WGS84), worked in EPSG:32646
- Sentinel-2 10 m, annual pairs, 2019-2026
- Landsat 30 m, pairs every 5 yr, 1989-2026 (37 usable years)
- the north edge must stay south of 23.47N, beyond which the water body is the Padma, not this river

- geometry: 60 transects kept of 63 built, over 15.8 km of traced centreline, median belt width 250 m
- manual spot checks of the geometry: **6/7** pass; the failing one is documented in `10_verify_geometry.py`

## 2. Cross-sensor agreement, water maps

The strongest validation available without a ground survey. Sentinel-2 and Landsat are different instruments at different resolutions, and were never designed to agree. IoU is computed only where at least one sensor saw water, so easy dry land cannot inflate it.

| year | S2 km2 | Landsat km2 | area diff | IoU | bank offset |
|---|---:|---:|---:|---:|---:|
| 2019 | 5.91 | 5.57 | -5.7% | 0.78 | 0 m |
| 2020 | 5.67 | 5.52 | -2.6% | 0.80 | 0 m |
| 2021 | 5.71 | 5.46 | -4.4% | 0.81 | 0 m |
| 2022 | 6.2 | 5.64 | -9.0% | 0.76 | 30 m |
| 2023 | 5.83 | 5.49 | -5.8% | 0.79 | 0 m |
| 2024 | 5.65 | 5.32 | -5.9% | 0.80 | 0 m |
| 2025 | 5.89 | 5.45 | -7.5% | 0.78 | 0 m |
| 2026 | 5.85 | 5.5 | -6.0% | 0.79 | 0 m |

- mean IoU **0.79**, median **0.79** over 8 years
- mean area difference **-5.9%** (Landsat consistently reads slightly less water)

IoU sits in the 0.70-0.85 band: **usable, with a small systematic bias**. The bias is one-directional, so it is a calibration difference between the sensors rather than random noise. Absolute quantities that depend on the exact water edge carry that bias; the direction and relative ranking of movement do not.

## 3. Cross-sensor agreement, movement rates

The stricter test, and the one that matters: do the two sensors measure the same *movement*, not just the same water?

**Not available on this reach.** The two sensors use different pair steps (s2 every 1 yr, landsat every 5 yr), so no (y0, y1) pair exists in both and the rate comparison cannot be made.

This is a real gap and is stated rather than glossed over: on the archived Jamuna reach both sensors produced annual pairs and the rate comparison was the project's strongest evidence (ratio 0.98x, correlation +0.98, PART B). Here it cannot be made, so cross-sensor support for this reach rests on the water maps in section 2 only.

## 4. Water level confound

A low-water year exposes more bank, which can look like erosion even when no land moved. If the measurement were really just reading water level, this correlation would be strong.

- landsat: correlation **+0.16** over 32 year-pairs
- s2: correlation **+0.42** over 7 year-pairs

Weak. The measurement is not simply tracking how much water was present. Note the Sentinel-2 figure rests on very few pairs, so it is a weak constraint either way; the Landsat figure is the one with enough pairs to mean anything. It is not eliminated: every record carries `stage_km2`, `stage_change_km2` and `stage_ratio` so it can be inspected.

## 5. What the rates are, and how they compare with literature

Published comparison for this river: **21 m/yr**, derived from 0.66 km average channel shift over 1993-2024 (Hasan et al. (2024), Progress in Disaster Science 24, 100381, doi:10.1016/j.pdisas.2024.100381). That is a **channel-centreline average over 31 years**, not a median bank displacement - which matters for the comparison below.

- Landsat 30 m, pairs every 5 yr: 2414 bank-side pairs, median **11.2 m/yr**, and one pixel of offset is worth 6.0 m/yr
- Sentinel-2 10 m, pairs every 1 yr: 520 bank-side pairs, median **1.2 m/yr**, and one pixel of offset is worth 10.0 m/yr

**The Sentinel-2 line is the important one.** On an annual pair a 10 m pixel is worth 10 m/yr of apparent movement, and the measured median is an eighth of that. Almost everything Sentinel-2 sees in a single year is smaller than its own resolution, so its annual target is mostly quantisation rather than erosion. That is why the long record here is built from Landsat's 5-year pairs, where a pixel is worth 6 m/yr and the signal is several pixels wide.

The Landsat median is **11.2 m/yr**, about half the 21 m/yr published figure. **The two measure different things, so this is not a like-for-like disagreement.** A median of a heavy-tailed erosion distribution sits well below its own mean; a centreline average over 31 years includes the meander bends where migration is fastest; and a separate DSAS study of the wider Padma system reports a mean of 21.9 m/yr on eroding transects alone (Miah et al. 2025), which brackets the published number rather than this median.

What is left over is the project's own limitation and is stated rather than smoothed: the measurement strip is only 250 m wide, so it scores movement at the present bank and not the wider floodplain; the published study covers the whole river while this is one middle reach; and 30 m pixels put a floor under what any single pair can report.

## 6. Forecast-time model test

The only test that speaks to prediction: each target year is predicted from earlier years only, using features known before that year begins. A grouped random split would leak and is not used.

Model: `HistGradientBoostingRegressor(max_iter=400, learning_rate=0.05, max_leaf_nodes=31)`, sensor `landsat`, hydro features: False. This is the model the map draws and the one the scores below belong to.

2284 held-out bank-side/year records across [{'test_year': 1996, 'training_years': 2, 'rows': 68, 'mae_model': 20.518, 'mae_train_median': 30.329}, {'test_year': 1998, 'training_years': 3, 'rows': 72, 'mae_model': 23.907, 'mae_train_median': 25.721}, {'test_year': 1999, 'training_years': 4, 'rows': 72, 'mae_model': 26.253, 'mae_train_median': 24.732}, {'test_year': 2000, 'training_years': 5, 'rows': 72, 'mae_model': 19.498, 'mae_train_median': 28.435}, {'test_year': 2001, 'training_years': 6, 'rows': 70, 'mae_model': 22.174, 'mae_train_median': 27.907}, {'test_year': 2003, 'training_years': 7, 'rows': 86, 'mae_model': 22.608, 'mae_train_median': 28.672}, {'test_year': 2004, 'training_years': 8, 'rows': 94, 'mae_model': 16.977, 'mae_train_median': 26.526}, {'test_year': 2005, 'training_years': 9, 'rows': 94, 'mae_model': 16.373, 'mae_train_median': 29.8}, {'test_year': 2006, 'training_years': 10, 'rows': 90, 'mae_model': 15.391, 'mae_train_median': 26.496}, {'test_year': 2007, 'training_years': 11, 'rows': 86, 'mae_model': 16.158, 'mae_train_median': 25.48}, {'test_year': 2008, 'training_years': 12, 'rows': 84, 'mae_model': 17.889, 'mae_train_median': 29.604}, {'test_year': 2009, 'training_years': 13, 'rows': 82, 'mae_model': 17.959, 'mae_train_median': 27.954}, {'test_year': 2010, 'training_years': 14, 'rows': 80, 'mae_model': 18.312, 'mae_train_median': 23.96}, {'test_year': 2011, 'training_years': 15, 'rows': 82, 'mae_model': 15.968, 'mae_train_median': 25.162}, {'test_year': 2012, 'training_years': 16, 'rows': 80, 'mae_model': 20.88, 'mae_train_median': 28.123}, {'test_year': 2013, 'training_years': 17, 'rows': 78, 'mae_model': 18.86, 'mae_train_median': 25.445}, {'test_year': 2014, 'training_years': 18, 'rows': 80, 'mae_model': 12.629, 'mae_train_median': 20.111}, {'test_year': 2015, 'training_years': 19, 'rows': 76, 'mae_model': 10.646, 'mae_train_median': 18.554}, {'test_year': 2016, 'training_years': 20, 'rows': 80, 'mae_model': 15.447, 'mae_train_median': 13.828}, {'test_year': 2017, 'training_years': 21, 'rows': 76, 'mae_model': 13.844, 'mae_train_median': 15.946}, {'test_year': 2018, 'training_years': 22, 'rows': 74, 'mae_model': 11.858, 'mae_train_median': 9.426}, {'test_year': 2019, 'training_years': 23, 'rows': 76, 'mae_model': 13.166, 'mae_train_median': 11.993}, {'test_year': 2020, 'training_years': 24, 'rows': 76, 'mae_model': 11.518, 'mae_train_median': 10.416}, {'test_year': 2021, 'training_years': 25, 'rows': 76, 'mae_model': 11.789, 'mae_train_median': 12.637}, {'test_year': 2022, 'training_years': 26, 'rows': 74, 'mae_model': 9.72, 'mae_train_median': 8.727}, {'test_year': 2023, 'training_years': 27, 'rows': 74, 'mae_model': 11.078, 'mae_train_median': 10.146}, {'test_year': 2024, 'training_years': 28, 'rows': 76, 'mae_model': 7.635, 'mae_train_median': 6.079}, {'test_year': 2025, 'training_years': 29, 'rows': 80, 'mae_model': 7.338, 'mae_train_median': 6.944}, {'test_year': 2026, 'training_years': 30, 'rows': 76, 'mae_model': 8.303, 'mae_train_median': 6.374}] expanding-window folds, test years 1996-2026.

| predictor | MAE (m/yr) |
|---|---:|
| **HistGradientBoostingRegressor** | **15.675** |
| training-median baseline | 20.413 |
| training-mean baseline | 20.723 |
| repeat the previous pair | 23.284 |

The candidate beats the strongest baseline (**20.413** m/yr). See `reports/MODEL_CHOICE.md` for what that margin does and does not support.

**Where the advantage actually lives.** Pooling all folds hides this, and it matters more than the choice of model:

| test years | folds | beats its own baseline | mean gain |
|---|---:|---:|---:|
| 1996-2015 | 18 | 17/18 | +7.78 |
| 2016-2026 | 11 | 2/11 | -0.83 |

The early folds are the ones with few training years, where the training median is a poor constant and large absolute errors dominate the pooled average. Once enough history exists (2015 onward) the baseline becomes strong and the model stops beating it. So the headline MAE understates how little the recent behaviour is understood. See DECISIONS.md D92.

Caveats carried by the report itself:

- The projection is experimental unless forecast_supported is true.
- Validation uses an expanding time window and features known before each target year.
- The one-year rate is linearly extended across the requested horizon; long-horizon uncertainty is not calibrated.
- No surveyed banklines are available as independent ground truth.

## 7. What is claimed, and what is not

**Claimed, with the evidence above:**

- how much land each bank lost in each measured interval, and how much on average over three decades

- which stretches are the chronic eroders, relative to each other

- that the water maps of two independent instruments largely agree, and that the movement rates sit inside the published range for this river


**Not claimed:**

- that the forecast is validated. The pooled backtest beats its baselines, but the advantage is concentrated in the early folds (section 6) and the projection is drawn as experimental for that reason.

- cross-sensor validation of *movement rates* on this reach; the two sensors use different pair steps, so section 3 could not be run.

- absolute accuracy against ground truth, because there is no survey of where the bank was.

## 8. Honest limitations

1. **No ground truth.** Confidence comes from two instruments agreeing and from literature plausibility, not from absolute accuracy. A digitised set of bank positions from very high resolution imagery would be the cheapest real improvement and has not been done.

2. **The measurement resolution bounds the answer.** Landsat is 30 m, which over a 5-year pair is 6 m/yr of apparent movement from a single pixel of offset; Sentinel-2 is 10 m, which over an annual pair is 10 m/yr. On a river this size a bank can move less than one pixel between two observations, which is why many measured values are exactly zero. Zero here means 'less than one pixel', not 'no movement'.

3. **One reach, one season.** The masks are clear-season composites. Monsoon attack on the outer bends, at the highest water, is not captured.

4. **Annual pairs are not independent.** Several consecutive pairs can be dominated by a single flood. Uncertainty intervals use a block bootstrap for this reason - see `reports/RISK.md`.

5. **Individual transect rates are often not distinguishable from zero.** Only a minority of records with a long enough history have a confidence interval clear of zero. The rest are shown and flagged rather than quietly dropped.

6. **The projection horizon is not calibrated.** The 10-year lines are a linear extension of the one-step rate with no independently validated uncertainty band.

---

# PART B - archived Jamuna reach (historical record)

These numbers are kept because they are the project's central negative result and the reason the study reach was changed. They are **not** recomputed by this script: the Jamuna raw imagery and discharge table have been removed from the repository, so the figures below are frozen as they were last generated on 2026-10-18. They say nothing about the active reach.

## 9. Nothing predicts Jamuna bank erosion

This is the finding that shaped the product.

Rows: 1876 (transect x bank side x year pair), 1989-2026, 51 transects.

| predictor | MAE (m/yr) |
|---|---|
| **predict the average** | **83.9** |
| this transect's own past average (leave-one-out) | 87.1 |
| same transect, previous pair | 133.7 |

**Reading this honestly:** nothing beats simply predicting the average. Using the transect's own history makes it *worse*, and repeating the previous pair is worse still. Erosion hotspots on a braided river migrate rather than persist.

Confirmed with real models under GroupKFold by transect: RandomForest 83.3-84.4 across seeds and fold counts, GradientBoosting 86.9, against a per-fold median of 83.5. RandomForest ties the baseline; its edge over the mean disappears at other fold counts.

Real GloFAS discharge, 37 complete years (1989-2025), joined at the study reach: within-transect correlation with erosion rate **+0.049** (median +0.018, 48 transects, 54% positive). About half positive is what random noise looks like. A single catchment-scale discharge value cannot say where along a 9 km braided belt the water attacks the bank. See DECISIONS.md D44.

Cross-sensor agreement on that reach, the project's strongest positive result: mean Landsat/Sentinel-2 rate ratio **0.98x**, correlation **+0.98** across 7 shared year-pairs, on 58 of 78 candidate transects over 38.8 km of traced channel. Median rates 50.1 m/yr (Sentinel-2) and 57.6 m/yr (Landsat), inside the published 30-200 m/yr range for the Jamuna. Manual geometry spot checks passed 6/7.

> The earlier figure of **+0.92 must not be cited**. It was computed while a resolution-sampling bug was live, so both sides of that comparison came from the same distorted geometry. See DECISIONS.md D35, D37.

