# TODO

Last updated 2026-10-18. See `context/CURRENT.md` for current state and
`reports/DECISIONS.md` for why things are the way they are.

## BLOCKED — the export scripts are not on GitHub yet

- [ ] **PUSH THE REPOSITORY.** A third party is re-downloading the imagery and
      needs `gee/*.js` to do it. Four commits are local-only. Until this is
      pushed, nobody else can run the exports.
- [ ] **`gh auth login`** in this session, then `git push -u origin main`.

## BLOCKED ON SAAD

- [ ] **Landsat export for the Arial Khan**, 1989–2026.
      Script: `gee/landsat_export_arial_khan.js`. Press Run, do **not** draw — the
      fallback box is the measured S2 extent and must match.
      Download folder `riverguard_arial_khan` →
      `data/reaches/arial_khan/raw/landsat/`

      **Both raw exports were deleted on 2026-10-18** and are being re-fetched by
      a third party. Handover instructions: `docs/DATA_HANDOVER.md`.

      Everything derived survives (processed masks, features, EPR, the trained
      model), so there is no rush to rebuild — but the model is trained on 432
      rows of 7 year-pairs, and the Landsat 5-year-block record is what would
      make it defensible.

      Priority years: **2019–2023**, for the cross-sensor overlap. One year is not
      a validation.

- [ ] **Colab model test** — confirm the no-signal finding with a real model
      (RandomForest + GradientBoosting vs the 83.9 baseline, GroupKFold by
      transect). ~10 min, no GPU. Instructions: `notebooks/colab_train.md`.
      Note: a local version of this already ran for the Jamuna (`ml/14_model_test.py`,
      D47) and reproduced the same negative result; the Colab run is for
      reproducibility and for the Arial Khan.

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

## MUST DO — correctness debt

- [ ] **Regenerate the Jamuna risk table.** `reports/RISK.md` and
      `data/unused_data/jamuna/processed/risk/` predate the EPR sign fix (D58), so the ranking is
      **inverted** — it ranks accretion as top erosion risk. Run
      `RIVERGUARD_REACH=jamuna 13_risk_and_forecast.py` and re-check
      `reports/RISK.md`.
- [ ] **Rebuild the Jamuna feature tables** for the same reason (`target_rate`
      sign). Magnitudes were unaffected, so `VALIDATION.md`'s cross-sensor
      numbers stand.
- [ ] Check `docs/HOW_IT_WORKS.md` against the current code — it predates the
      reach switch and the sign fix.

## NEXT (after Landsat)

- [ ] Decide the honest product. Options, in descending order of defensibility:
      measured record + chronic risk + uncertainty (current), or a long-run trend
      with error bars. **Not** a year-by-year forecast — that was tested and does
      not work (D44).
- [ ] Add rainfall (CHIRPS) as a covariate; discharge alone showed nothing
- [ ] Consider adding the **Ganges** reach as a third point on a scale gradient —
      9 km braided vs 1–4 km vs 300 m single-thread. Elegant, but triples the
      export and processing work.
- [ ] Sediment load, if a source is found. It is the physically correct missing
      variable: bank erosion is driven by shear stress and sediment supply, not
      discharge alone.

## OPTIONAL / STRETCH

- [ ] Sentinel-1 SAR water masks — works through cloud, useful as a cross-check
- [ ] Denser transects near chronic hotspots
- [ ] Replace Django's `django-insecure-` dev key before any deployment

## HOUSEKEEPING

- [ ] Create the GitHub remote and push (committed locally, not yet pushed)
- [ ] Decide whether the forecast branch stays closed for good