# RiverGuard - archived Jamuna long-run erosion risk

> Historical report for the archived Jamuna reach. These risk rankings are not
> current Arial Khan results and must not be served as such. The active reach's
> Landsat record and risk analysis are still outstanding.

Generated: 2026-10-18

## What this is

For each transect and bank side: how many metres per year that bank has actually lost, averaged over 36 years of Landsat imagery, with an honest confidence interval.

Positive means land was **lost** (erosion). Negative means the bank built outward (accretion).

## What this is not

This is **not** a forecast for next year. It was tested and it does not work. Measured against the trivial baseline of predicting the average:

| predictor | MAE (m/yr) |
|---|---|
| predict the average | **83.9** |
| this transect's own past average | 87.1 |
| same transect, previous pair | 133.7 |
| river discharge (best case, within transect) | correlation +0.05 |

37 years of imagery and the physically correct forcing still produce no usable year-to-year signal. On a braided river the erosion hotspots migrate instead of persisting. Publishing a yearly forecast would be presenting noise as skill.

## The numbers

- 102 transect-side records, of which **64 have at least 10 usable year-pairs** and are eligible for ranking
- 38 are shorter than 10 years. They are kept in the CSV, flagged `sufficient = False`, and excluded from the ranking. Without that rule a single lucky year of erosion outranks thirty years of measured behaviour, which would rank noise as long-term exposure.
- 3 of the 64 eligible records (5%) have a confidence interval that does not straddle zero, i.e. a long-run rate confidently different from no change
- 20 have a positive long-run median (net erosion)
- long-run median rate across eligible records: +0.0 m/yr
- worst: +102.6 m/yr, best: -39.6 m/yr

### Risk tiers

Eligible records only (>= 10 years).

| tier | records | definition (long-run median) |
|---|---|---|
| very high | 1 | >= 80 m/yr |
| high | 3 | 40 to 80 m/yr |
| moderate | 3 | 15 to 40 m/yr |
| low | 39 | 0 to 15 m/yr |
| accreting | 18 | below 0 (accreting) |

## Chronic hotspots - top 10 by long-run median

| rank | transect | side | arc (km) | median m/yr | 95% CI | years | eroding % | tier |
|---|---|---|---|---|---|---|---|---|
| 1 | 28 | left | 17.7 | +102.6 | -216 to +117 | 10 | 60 | very high |
| 2 | 20 | right | 13.7 | +58.5 | -47 to +146 | 20 | 65 | high |
| 3 | 21 | right | 14.2 | +57.6 | -135 to +255 | 18 | 56 | high |
| 4 | 22 | left | 14.7 | +48.6 | -68 to +128 | 19 | 58 | high |
| 5 | 23 | right | 15.2 | +37.8 | +16 to +85 | 17 | 71 | moderate |
| 6 | 24 | left | 15.7 | +28.8 | +0 to +167 | 15 | 53 | moderate |
| 7 | 28 | right | 17.7 | +18.0 | -9 to +110 | 10 | 60 | moderate |
| 8 | 19 | right | 13.2 | +14.4 | -9 to +95 | 16 | 56 | low |
| 8 | 26 | right | 16.7 | +14.4 | +0 to +47 | 15 | 60 | low |
| 10 | 1 | right | 4.2 | +10.8 | -16 to +40 | 32 | 56 | low |

## How the uncertainty is calculated

Consecutive years are **not** independent - a bank eroding this year is usually still eroding next year. Counting 35 consecutive years as 35 independent samples would shrink the interval far too much and make the result look more certain than it is.

So each series is reduced to an **effective sample size**

```
n_eff = n * (1 - r1) / (1 + r1)
```

where `r1` is that transect's own lag-1 autocorrelation, and the interval is built from `n_eff` rather than `n`. Series too short to estimate `r1` fall back to `n_eff = n`, which never overstates the evidence.

The ranking uses the **median**, not the mean. A few transect-years swing past 300 m/yr, and one extreme year should not be able to reorder the whole river.

The interval is a **block bootstrap percentile interval for that same median**, resampling in blocks of 3 consecutive years so the serial dependence survives the resampling. An interval belonging to the mean would be answering a different question from the one the ranking poses. Both are in the CSV (`ci95_lo/hi` for the median, `mean_ci95_lo/hi` for the mean); they are usually far apart, which is itself informative.

## Honest limitations

1. **No ground truth.** There is no survey of where the bank actually was. Confidence comes from two independent sensors agreeing (Sentinel-2 vs Landsat: ratio 0.98x, correlation +0.96) and from the rates falling inside the published Jamuna range, not from absolute accuracy.

2. **A 1000 m measurement zone sets the magnitude.** How wide a strip counts as 'at risk' is a stated physical assumption, not a fitted parameter. A wider zone dilutes the same area of land loss over more frontage and lowers the rate.

3. **Annual pairs overstate independence in the other direction.** A single dramatic flood can dominate several consecutive pairs, which the autocorrelation adjustment only partly handles.

4. **One reach, one season.** A 30 km stretch sampled in January-February (low water). Monsoon attacks on the outer bends are not captured.

5. **61 eligible records are not statistically distinguishable from no change.** They are kept in the CSV and flagged, rather than quietly dropped, so the map shows what was actually measured.

