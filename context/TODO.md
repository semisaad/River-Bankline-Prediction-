# TODO

Last updated 2026-10-18. See `context/CURRENT.md` for current state and
`reports/DECISIONS.md` for why things are the way they are.

## BLOCKED — the export scripts are not on GitHub yet

- [ ] **PUSH THE REPOSITORY.** A third party is re-downloading the imagery and
      needs `gee/*.js` to do it. Four commits are local-only. Until this is
      pushed, nobody else can run the exports.
- [ ] **`gh auth login`** in this session, then `git push -u origin main`.

## BLOCKED ON SAAD

- [ ] **Sentinel-2 and Landsat re-export for the Arial Khan**.
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

- [ ] **Nothing outstanding on the active reach.** The EPR sign fix (D58) landed
      before the model was trained, and everything downstream was rebuilt from it.
- [ ] **Regenerate `reports/VALIDATION.md` for the active reach.** Its
      cross-sensor section still describes the archived river, so it is not yet
      evidence for anything this project currently claims.
- [ ] Check `docs/HOW_IT_WORKS.md` against the current code — it predates the
      sign fix and the model.

**Deliberately not done:** the archived reach's risk table predates the sign fix
and is therefore inverted. It is unused and stays archived. Regenerating it would
mean spending time on a river the project has left, so it is recorded here as a
known state rather than as a task.

## NEXT (after Landsat)

- [ ] Add rainfall (CHIRPS) as a covariate and re-test skill
- [ ] Widen the record. 432 rows over 7 year-pairs is the binding constraint on
      how much the model can be trusted. Landsat 5-year blocks is the fix.
- [ ] Sediment load, if a source is found. It is the physically correct missing
      variable: bank erosion is driven by shear stress and sediment supply, not
      discharge alone.

## OPTIONAL / STRETCH

- [ ] Sentinel-1 SAR water masks — works through cloud, useful as a cross-check
- [ ] Denser transects near chronic hotspots
- [ ] Replace Django's `django-insecure-` dev key before any deployment

## HOUSEKEEPING

- [ ] **Push to GitHub** — commits are local only, and the export scripts are
      needed by whoever re-downloads the imagery
- [ ] Decide whether the forecast branch stays closed for good