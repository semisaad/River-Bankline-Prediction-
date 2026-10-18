# TODO

Last updated 2026-10-18. See `context/CURRENT.md` for current state and
`reports/DECISIONS.md` for why things are the way they are.

## DATA RESTORATION — owner / Earth Engine account

- [x] **Select and synchronize the expanded rectangle.** Bounds:
      `90.16808799423755, 23.134319063780836, 90.26902488388599, 23.261491731177696`.
      Both GEE scripts and `ml/config.py` now use these bounds; the north edge
      remains south of 23.47N.
- [ ] **Export Sentinel-2 and Landsat using that exact same rectangle.**
      Scripts: `gee/s2_export_arial_khan.js` and
      `gee/landsat_export_arial_khan.js`. Start GEE Tasks only after the bounds
      are synchronized; previews must show only the Arial Khan.
      Download folder `riverguard_arial_khan` →
      `data/reaches/arial_khan/raw/landsat/`

      **Both raw exports were deleted on 2026-10-18** and are being re-fetched by
      a third party. Handover instructions: `docs/DATA_HANDOVER.md`.

      Processed S2 masks, features and EPR survive for the old box only. They
      cannot be reused for the expanded area. The current candidate model is not
      supported by chronological validation; more data alone does not guarantee
      forecast skill.

      Priority years: **2019–2023**, for the cross-sensor overlap. One year is not
      a validation.

## READY THE MOMENT DATA ARRIVES

- [ ] After `config.py` and both GEE reference boxes match the new rectangle,
      run `09_checks.py` before processing either sensor.
- [ ] Prepare Sentinel-2: `01_prepare.py`, then `02_banklines.py`
- [ ] Train candidate from S2: `04_erosion.py s2`, `05_features.py s2`,
      `14_model_train.py`, then `06_predict_geojson.py`
- [ ] Prepare Landsat: `01b_prepare_landsat.py` (not `01_prepare.py landsat`)
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