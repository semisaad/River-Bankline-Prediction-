# TODO

Last updated 2026-10-18. See `context/CURRENT.md` for current state and
`reports/DECISIONS.md` for why things are the way they are.

## DATA RESTORATION — owner / Earth Engine account

- [ ] **Sentinel-2 and Landsat re-export for the Arial Khan**.
      Script: `gee/landsat_export_arial_khan.js`. Press Run, do **not** draw — the
      fallback box is the measured S2 extent and must match.
      Download folder `riverguard_arial_khan` →
      `data/reaches/arial_khan/raw/landsat/`

      **Both raw exports were deleted on 2026-10-18** and are being re-fetched by
      a third party. Handover instructions: `docs/DATA_HANDOVER.md`.

      Processed S2 masks, features and EPR survive. The current candidate model
      is not supported by chronological validation; more data is needed but is
      not by itself a guarantee of forecast skill.

      Priority years: **2019–2023**, for the cross-sensor overlap. One year is not
      a validation.

## READY THE MOMENT DATA ARRIVES

- [ ] Prepare Landsat: `01_prepare.py landsat`
- [ ] Build the long record: `04_erosion.py landsat`, `05_features.py landsat`
- [ ] **Cross-sensor check** — do S2 and Landsat measure the same reach the
      same way over 2019–2026? This is the strongest validation available without
      ground truth, and it is the check that proves the D59 logic alignment worked
- [ ] **Test GloFAS on the Arial Khan.** At Madaripur a 5.5 km cell contains both
      the Padma and the distributary; the cell's dominant discharge may be the
      Padma's. Pick the cell by proximity to the reach, check its magnitude, and
      decide whether discharge is usable at all. **Do not assume the reach switch
      fixed the discharge problem — it fixed the scale mismatch only.**
- [ ] Verify the geometry gates against the Landsat record — the current values
      are unverified guesses scaled for a 300 m river (D50)

## PREDICTION SYSTEM — development work

- [ ] Keep evaluating with expanding time windows and forecast-time-only
      features; always compare with the training median and previous-year rate.
- [ ] Reserve a later year as a final untouched test after model choices are
      fixed.
- [ ] Evaluate bankline position error in metres, not only erosion-rate MAE.
- [ ] Develop a calibrated uncertainty interval for the full prediction
      horizon; the present linear extension is experimental and not calibrated.
- [ ] Once Landsat is available, test longer temporal blocks without mixing
      future information into features or validation.
- [ ] Explore rainfall or sediment covariates only when they are available at
      prediction time and can be independently validated.

## OPTIONAL / STRETCH

- [ ] Sentinel-1 SAR water masks — works through cloud, useful as a cross-check
- [ ] Denser transects near chronic hotspots
- [ ] Replace Django's `django-insecure-` dev key before any deployment

## COMPLETED

- [x] Push the repository to GitHub. `main` tracks `origin/main`.
- [x] Replace the unsupported random-row model score with a prior-year-only,
      expanding-window evaluation. Current candidate fails the median baseline.