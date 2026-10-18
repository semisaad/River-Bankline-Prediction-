# CURRENT STATE

> **ACTIVE REACH: Arial Khan, MIDDLE reach (Madaripur Sadar - Kalkini)**, chosen
> 2026-10-18 (D49-D52). Box 90.1927-23.1638 to 90.2384-23.2450 (42 km2, measured from the export), EPSG:32646,
> Sentinel-2 v2 (owner multi-index, verified: 32 transects, 0 dropped, median width 350 m), Landsat still needed. The pipeline already supported multiple reaches, so this was a config
> change, not a rebuild. Jamuna results are preserved as the negative result
> that motivated the switch.
> Run everything for the new reach with `RIVERGUARD_REACH=arial_khan`.
>
> **BLOCKED on the owner:** the study box. Both scripts now use a rectangle the
> owner DRAGS on the Earth Engine map, after two computed boxes were wrong.
> Aim for 8-15 km with 4-5 meander loops. Then imagery. TWO scripts have not been run:
> `gee/s2_export_arial_khan.js` (2019-2026, 8 files) and
> `gee/landsat_export_arial_khan.js` (1989-2026, ~38 files).
> **The preview must show exactly ONE thin river. If two rivers appear, the box
> has caught the Padma and the pipeline would measure the wrong river.** Nothing downstream can be verified until it is. See
> `context/OWNER_ACTIONS.md`.


**Date:** 2026-10-18
**Project:** RiverGuard - Jamuna riverbank erosion, retrospective + chronic risk

## THE HEADLINE RESULT

Year-to-year bank erosion **cannot be predicted** from this data. Tested against
the trivial baseline of predicting the average (83.9 m/yr MAE):

| predictor | MAE (m/yr) |
|---|---|
| predict the average | **83.9** (best) |
| transect's own past average | 87.1 |
| same transect, previous pair | 133.7 |
| real GloFAS discharge, within-transect | r = +0.049 |
| RandomForest (GroupKFold by transect, D47) | 83.3-84.4, ties the median dummy |
| GradientBoosting (D47) | 86.9 |

37 years of Landsat, 16 of Sentinel-2, and 37 complete years of real river
discharge still produce no usable year-to-year signal. On a braided river,
erosion hotspots migrate rather than persist. See DECISIONS.md D44; confirmed
with real models in D47 (2026-10-18, run locally via `ml/14_model_test.py`).

## WHAT WE SHIP INSTEAD

Three things the evidence does support:

1. **Measured history** - per-pair bank change since 1989, two independent
   sensors agreeing (ratio 0.98x, r +0.98), rates inside the published range
2. **Chronic risk ranking** - 102 transect-side records, 64 eligible (>=10 years),
   with block-bootstrap median confidence intervals. Only **3 of 64** are
   distinguishable from zero, which is reported rather than smoothed over.
3. **Long-run trend** - each bank carried forward over 10 years at its measured
   rate, with wide honest error bars. Labelled `is_forecast: false` everywhere.

## CURRENT STATUS

| Item | State |
|---|---|
| Sentinel-2 masks | done, 16 years |
| Landsat masks | done, 37 years (1992 absent) |
| GloFAS discharge | done, 37 complete years + 1 flagged incomplete |
| Transect geometry | done, 58 transects over 38.8 km, 6/7 spot checks pass |
| EPR rates | done, both sensors |
| Risk table + map | done |
| Long-run trend geometry | done, 44 trends |
| Validation report | regenerated, +0.92 explicitly withdrawn, model test in section 5 |
| Model test (RF/GB vs baseline) | done locally, D47; no useful win |
| API | risk, risk/summary, predictions, status all live |
| Frontend | chronic-risk + trend layers, "forecast" wording removed |
| Guard checks | 09_checks.py sections 1-9 all pass |

## WAITING ON SAAD - NOTHING

The Colab model test is no longer blocking: it was run locally on 2026-10-18
(`ml/14_model_test.py`, D47) and confirmed the no-signal finding. Running
`notebooks/colab_train.md` on Colab is now optional independent reproduction,
not a required step.

## RUNNING

```
cd ~/Projects/riverguard/backend && ../.venv/bin/python manage.py runserver 8010 --noreload
cd ~/Projects/riverguard/frontend && npm run dev
```

## KEY NUMBERS

- Cross-sensor agreement: ratio 0.98x, correlation +0.98, mean IoU 0.85
- Risk: 64 eligible records, 3 significant, 1 very high / 3 high / 3 moderate
- GloFAS: 37 complete years, cell 24.525N 89.725E, 2004 flood at 97th percentile
- Incomplete: 2026 has 181 days only, excluded and flagged

## DO NOT

- Do not cite +0.92 anywhere; withdrawn in D37, restated in VALIDATION.md
- Do not call anything a forecast; the UI and GeoJSON both say `is_forecast: false`
- Do not commit or push unless explicitly asked
