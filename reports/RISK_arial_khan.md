# RiverGuard - historical erosion risk: Arial Khan (Madaripur Sadar - Kalkini, middle reach)

Generated: 2026-10-18

## What this is

For each transect and bank side: how many metres per year that bank has actually lost, averaged over 32 years of Landsat imagery, with an honest confidence interval.

Positive means land was **lost** (erosion). Negative means the bank built outward (accretion).

## What this is not

This historical ranking does not predict a future bankline. For the active Arial Khan candidate model and its time-forward test, see `reports/VALIDATION.md` and `ml/artifacts/model_report.json`.

## The numbers

- 96 transect-side records, of which **92 have at least 10 usable year-pairs** and are eligible for ranking
- 4 are shorter than 10 years. They are kept in the CSV, flagged `sufficient = False`, and excluded from the ranking. Without that rule a single lucky year of erosion outranks thirty years of measured behaviour, which would rank noise as long-term exposure.
- 32 of the 92 eligible records (35%) have a confidence interval that does not straddle zero, i.e. a long-run rate confidently different from no change
- 32 have a positive long-run median (net erosion)
- long-run median rate across eligible records: +0.0 m/yr
- worst: +41.2 m/yr, best: -56.2 m/yr

### Risk tiers

Eligible records only (>= 10 years).

| tier | records | definition (long-run median) |
|---|---|---|
| high | 1 | 40 to 80 m/yr |
| moderate | 18 | 15 to 40 m/yr |
| low | 45 | 0 to 15 m/yr |
| accreting | 28 | below 0 (accreting) |

## Chronic hotspots - top 10 by long-run median

| rank | transect | side | arc (km) | median m/yr | 95% CI | years | eroding % | tier |
|---|---|---|---|---|---|---|---|---|
| 1 | 31 | right | 8.7 | +41.2 | +4 to +49 | 31 | 74 | high |
| 2 | 32 | right | 8.9 | +33.8 | +0 to +45 | 31 | 68 | moderate |
| 3 | 12 | right | 3.1 | +26.2 | +4 to +45 | 31 | 77 | moderate |
| 3 | 15 | right | 3.9 | +26.2 | +0 to +45 | 31 | 74 | moderate |
| 3 | 30 | right | 8.4 | +26.2 | +8 to +38 | 25 | 84 | moderate |
| 6 | 13 | right | 3.4 | +22.5 | +8 to +41 | 31 | 77 | moderate |
| 6 | 27 | left | 7.7 | +22.5 | +9 to +30 | 10 | 80 | moderate |
| 6 | 36 | left | 9.9 | +22.5 | -11 to +30 | 13 | 69 | moderate |
| 6 | 37 | left | 10.2 | +22.5 | -15 to +26 | 10 | 70 | moderate |
| 10 | 7 | right | 1.9 | +18.8 | +8 to +49 | 29 | 100 | moderate |

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

5. **60 eligible records are not statistically distinguishable from no change.** They are kept in the CSV and flagged, rather than quietly dropped, so the map shows what was actually measured.

