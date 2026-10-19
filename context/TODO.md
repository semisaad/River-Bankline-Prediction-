# TODO

Last updated 2026-10-19. See `context/CURRENT.md` for state and
`reports/DECISIONS.md` for why things are the way they are.

## DECISIONS WAITING ON THE OWNER

These change the numbers, the method, or the claim. Nothing else should be
treated as final until they are settled.

- [ ] **How to state the recent-fold decay (D92).** The pooled MAE beats its
      baseline by 23%, but that advantage is 18/18 folds in 1996–2015 and 2/11
      in 2016–2026. Options: (a) report the pooled backtest with a prominent
      caveat table, (b) make a recent-window backtest the headline, (c) withdraw
      `forecast_supported` as a future claim and describe the output as an
      experimental extrapolation. **(c) is the most defensible** if the
      supervisor is going to read the number as a forecast.
- [x] **RandomForest or HistGradientBoosting (D91).** Settled by **D94**:
      gradient boosting is served (15.675 vs 15.886, folds 16/13). The margin is
      1.3% and is reported as small, but the comparison is controlled, so the
      better-scoring model ships. RF retained as `model_report_rf.json`.
- [ ] **Arbitrary projection window.** The model scores well only through 2015.
      Restrict the training window to, say, 2005+ and the recent folds improve
      but the sample shrinks. Worth a measurement, not a guess.

## APP WORK (next, unblocked)

- [ ] Build out the remaining UI. All 9 endpoints return 200 and the data layer
      is current; nothing is waiting on data.
- [ ] **Do not let the UI state a forecast claim until D92 is settled.**
- [ ] Replace Django's `django-insecure-` dev key before any deployment.

## MEASUREMENT WORK (optional, ranked by value)

- [ ] **Independent ground truth.** Digitise ~20 bank positions from Google
      Earth (~0.5 m) and compare against our 30 m edge. Cheapest real
      improvement to the project; currently everything rests on cross-sensor
      agreement.
- [ ] **Restore the rate-level cross-sensor test.** It ran on the Jamuna
      (0.98x, +0.98) but cannot run here because S2 uses 1-year pairs and
      Landsat 5-year. Aggregating S2 pairs into 5-year blocks would make the two
      comparable and would restore the project's strongest validation.
- [ ] **Calibrated uncertainty band** for the projection horizon. The present
      linear extension has no validated interval.
- [ ] **Bankline position error in metres**, not just erosion-rate MAE.
- [ ] **Automatic check that a prior-year feature window never overlaps the
      target window** (the D80 bug class). Still only checked by hand.
- [x] **Explain the 11.2 vs 21 m/yr gap.** Largely **definitional** and now
      written up as such (D95): the published figure is a derived *channel
      centreline average* (0.66 km ÷ 31 yr, Hasan et al. 2024), not a median bank
      displacement. The 250 m strip and single-reach scope remain real
      limitations and are stated in `VALIDATION.md` section 5.

## BEST THEORY FOR THE RECENT-FOLD DECAY (untested)

The erosion values are quantised to 30 m, and 63% of recent bank-sides read
exactly 0. A model with continuous features cannot beat "predict the median" on
a target that is mostly a spike at zero — the median baseline is *already* the
optimal predictor there. If true, the fix is a different target (probability of
movement exceeding one pixel, or a hurdle/zero-inflated model), not more
features. **This is an assumption. It has not been measured.**

## HIGHEST-VALUE REMAINING ACTION

- [ ] **Request water-level data from BWDB** (http://www.hydrology.bwdb.gov.bd).
      Water level is the one known confound the project can only state, not
      control: Landsat +0.16 and S2 +0.42 correlation between stage and measured
      rate. Observed stage would turn that caveat into a control variable. It is
      the only outstanding item that needs someone outside this repository.

## OPTIONAL / STRETCH

- [ ] Sentinel-1 SAR water masks — works through cloud, useful as a cross-check
- [ ] Denser transects near chronic hotspots
- [ ] More Landsat years in the 5-year pairing (currently 37 usable, 1997 missing)

## COMPLETED

- [x] Expanded-box rebuild: geometry, both sensors, model, risk, projection
- [x] Corrected time-forward evaluation (prior-year features, expanding window)
- [x] GloFAS tested and rejected; ERA5-Land hydrology tested and rejected
- [x] RandomForest vs HistGradientBoosting compared honestly; GBM adopted (D94)
- [x] Two bankline validation figures built (train ≤2021 vs ≤2023, both scored
      against 2026) — `reports/validation_bankline_2026*.png`
- [x] Learning curve: more data helps, and the gain is recency not quantity
- [x] Literature and evidence base written up — `reports/LITERATURE.md`
- [x] `reports/VALIDATION.md` regenerated from a generator that cannot go stale
- [x] Repository cleaned of dead scripts and dead reaches
- [x] Push the repository to GitHub. `main` tracks `origin/main`.
