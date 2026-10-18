# RiverGuard - validation report

Generated: 2026-10-18

Every number below is produced by a script in `ml/` and can be re-checked by re-running it.

## 1. Two independent sensors agree

This is the central check. Sentinel-2 (10 m, 2019-2026) and Landsat (30 m, 1989-2026) measure the same river with different instruments. They were not built to agree.

| pair | S2 median m/yr | Landsat median m/yr | ratio |
|---|---|---|---|
| 2019->2020 | 110.2 | 108.9 | 0.99x |
| 2020->2021 | 135.6 | 136.8 | 1.01x |
| 2021->2022 | 50.1 | 67.5 | 1.35x |
| 2022->2023 | 55.3 | 57.6 | 1.04x |
| 2023->2024 | 47.2 | 52.2 | 1.11x |
| 2024->2025 | 30.0 | 21.6 | 0.72x |
| 2025->2026 | 33.4 | 21.6 | 0.65x |

- mean Landsat/Sentinel-2 ratio: **0.98x**
- correlation across pairs: **+0.98**
- Sentinel-2 overall median: **50.1 m/yr** over 7 pairs
- Landsat overall median: **57.6 m/yr** over 35 pairs

A ratio near 1 with a high correlation means both instruments are seeing the same movement. The remaining scatter pair by pair is real: individual years differ between sensors, which is why no single year should be trusted alone.

- transects placed: 58 of 78 candidates, over 38.8 km of traced channel
- manual geometry spot checks passed: **6/7**

## 2. Cross-check against an independent method

Method A: EPR net-area change (above).

Method B: how far the traced river outline physically moved between the same two years (75th percentile of nearest-outline distance).

Method B shares almost no machinery with EPR, so agreement means both are seeing real movement rather than one shared artefact.

| pair | EPR median | outline distance p75 |
|---|---|---|
| 2019->2020 | 110.2 m | 340.5 m |
| 2020->2021 | 135.6 m | 422.2 m |
| 2021->2022 | 50.1 m | 250.4 m |
| 2022->2023 | 55.3 m | 413.5 m |
| 2023->2024 | 47.2 m | 386.0 m |
| 2024->2025 | 30.0 m | 450.6 m |
| 2025->2026 | 33.4 m | 202.4 m |

**Correlation +0.26** across 7 year pairs.

> The earlier figure of **+0.92 is withdrawn and must not be cited**. It was computed while a resolution-sampling bug was live, so both sides of that comparison came from the same distorted geometry. Re-measured now, with the corrected geometry, the figure is +0.26 over 7 pairs. See DECISIONS.md D35, D37.

## 3. Plausibility against literature

Published Jamuna bank-change rates for comparable reaches sit broadly in the **30-200 m/yr** range, with local hotspots higher. The medians here (50 m/yr for Sentinel-2, 58 m/yr for Landsat) sit inside that range.

## 4. Water level confound

A low-water year exposes more bank, which can look like erosion even when no land moved. If the measurement were really just reading water level, this correlation would be strong.

- correlation between water-area change and median bank change: **+0.10**
- A weak relationship is reassuring: the measurement is not simply tracking how much water was present.
- It is not eliminated. Each record carries `stage_km2`, `stage_change_km2` and `stage_ratio` so this can be inspected.

## 5. Is there any learnable signal?

This is the finding that shapes the product.

Rows: 1876 (transect x bank side x year pair), 1989-2026, 51 transects.

| predictor | MAE (m/yr) |
|---|---|
| **predict the average** | **83.9** |
| this transect's own past average (leave-one-out) | 87.1 |
| same transect, previous pair | 133.7 |

**Reading this honestly:** nothing beats simply predicting the average. Using the transect's own history makes it *worse*, and repeating the previous year is worse still. Erosion hotspots on a braided river migrate rather than persist.

Real GloFAS discharge, 37 complete years (1989-2025), joined at the study reach. Within-transect correlation with erosion rate: **+0.049** (median +0.018, 48 transects, 54% positive).

About half positive is what random noise looks like. The physically correct forcing does not resolve the signal, because a single catchment-scale discharge value cannot say where along a braided reach the water attacks the bank. See DECISIONS.md D44.

**Confirmed with real models (2026-10-18, DECISIONS.md D47).** RandomForest and GradientBoosting under GroupKFold by transect, using only information available at the start of the target year:

| predictor | MAE (m/yr) |
|---|---|
| predict the average (per-fold mean) | 84.0 |
| predict the median (per-fold) | **83.5** (the correct bar for MAE) |
| RandomForest | 83.3-84.4 across seeds and fold counts |
| GradientBoosting | 86.9 |

For MAE the optimal constant predictor is the median, and this label is heavy-tailed, so the median dummy is the harder baseline. RandomForest ties it and its edge over the mean baseline (under 1%) disappears at other fold counts. Prediction-observation correlation reaches r = +0.28 (about 8% of variance) - a faint, reproducible trace, nowhere near enough to forecast with. The test is reproducible via `ml/14_model_test.py` and `notebooks/colab_train.md`.

## 6. What is claimed, and what is not

**Claimed, with the evidence above:**

- how much land this bank lost in each year since 1989, and how much it lost on average over three decades

- which stretches are the chronic eroders, relative to each other

- that two independent instruments agree, and that the result sits inside the published range for this river


**Not claimed:**

- a prediction of next year's erosion. This was tested and it does not work; see section 5.

- absolute accuracy against ground truth, because there is no survey of where the bank was.

## 7. Honest limitations

1. **No ground truth.** Confidence comes from two independent sensors agreeing and from literature plausibility, not from absolute accuracy.

2. **The measurement zone sets the magnitude.** A 1000 m strip defines 'at risk'. That is a stated physical assumption, not a fitted parameter; a wider zone dilutes the same land loss over more frontage.

3. **One reach, one season.** About 30 km, sampled January-February at low water. Monsoon attacks on the outer bends are not captured.

4. **Annual pairs are not independent.** Several consecutive pairs can be dominated by one flood. Uncertainty intervals use a block bootstrap for this reason - see RISK.md.

5. **Individual transect rates are often not distinguishable from zero.** Of the records with a long enough history, only a small minority have a confidence interval clear of zero. The rest are shown, and flagged, rather than quietly dropped.

6. **Landsat misses part of the traced river.** The export stops at 24.35N, excluding about 12% of the traced channel. Cross-sensor work uses the shared bbox.

