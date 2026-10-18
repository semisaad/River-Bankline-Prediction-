# CURRENT STATE

**Date:** 2026-10-18 · **Branch:** master, committed locally, **not yet pushed**

## THE PROJECT: Arial Khan (Madaripur Sadar – Kalkini, middle reach)

One river. The earlier Jamuna reach is archived and out of scope; it is mentioned
only as the reason for the switch.

Box `90.1927, 23.1638 → 90.2384, 23.2450` (42 km², measured from the export),
EPSG:32646, Sentinel-2 primary at 10 m.

Chosen 2026-10-18 (D49–D52). The pipeline was already reach-agnostic, so this
was a config change, not a rebuild.

> **The northern edge must stay south of 23.47N** — the bifurcation from the
> Padma. North of that line the water body *is* the Padma. An earlier box reached
> 23.60N and the preview came back mostly Padma (D51). Hard constraint, recorded
> in `config.py` and both export scripts.

## The headline result: the model predicts

Arial Khan, Sentinel-2, 432 rows, 31 transects, 17 features,
`GroupKFold(5)` **grouped by transect** so no part of a bank is in both
training and test:

| | MAE (m/yr) | correlation |
|---|---|---|
| predict the average | 2.919 | — |
| repeat the previous pair | 4.060 | −0.073 |
| **RandomForest** | **2.843** | **+0.517** |
| GradientBoosting | 2.949 | +0.568 |

**A trained model beats the trivial baseline by 2.6%.** 62 transect-sides are
projected to 2036.

An earlier conclusion that no forecast was supportable was **wrong** — it was
drawn from baselines and correlations without training a model. D62 supersedes
it. The Jamuna result (nothing beat the average, r = +0.049) stands as the reason
the project moved rivers, but it is not a result of this one.

## Status

| item | state |
|---|---|
| **Model trained and validated** | ✅ RandomForest, MAE **2.843** vs 2.919 baseline, r **+0.517** (D62) |
| Predictions to 2036 | ✅ 62 transect-sides, `predictions.csv` + map geometry |
| S2 masks, Arial Khan | ⚠️ **raw exports DELETED.** Processed masks, features and predictions all survive |
| S2 geometry | ✅ 32 transects, 0 dropped, median width 350 m — still reproducible |
| S2 EPR + features | ✅ 7 pairs — still reproducible |
| Landsat masks, Arial Khan | ❌ not exported with the current script |
| GEE scripts on GitHub | ❌ **not pushed — 4 commits local only. BLOCKS the re-export.** |
| GloFAS discharge | ⛔ for this reach — existing download covers a different river |
| GloFAS, Arial Khan | ❌ existing download does not cover the reach |
| Cross-sensor check | ❌ needs Landsat 2019–2023 |

| Website | ✅ chronic-risk + long-run-trend layers |
| Guard checks | ✅ all pass, both reaches |

## Blocking item — two things

1. **Push the repository to GitHub.** A third party now needs the GEE export
   scripts in order to download anything, and they are only on this machine.
   This is now the critical path, not a housekeeping task.
2. **Re-export Sentinel-2 and Landsat** for the Arial Khan. Raw downloads were
   deleted and are being re-fetched. Instructions for whoever does it:
   **`docs/DATA_HANDOVER.md`** — written for a third party with no access to this
   conversation.

Everything downstream is intact: processed masks, features, EPR, the trained
model and its projections. `14_model_train.py` still runs and still returns MAE
2.843 from the processed data.

## Recently found and fixed

| | |
|---|---|
| **EPR signs inverted project-wide** | `lost`/`gained` were swapped, so every rate carried the wrong direction. Magnitudes survived (most reporting used `\|rate\|`); the Jamuna risk ranking is inverted (D58) |
| **Earth Engine script race** | nested `.evaluate()` calls reported 0% valid for years holding 15 scenes, and printed two different years as exactly 12.55% (D61) |
| **Memory limit on 38-year export** | `connectedPixelCount(1024)` is a ~31 km window; now batched 8 years per synchronous `getInfo()` (D61) |
| **Cross-sensor detection mismatch** | Landsat used `.gte(300)` where S2 used `.gte(1000)` — Landsat would have kept ponds S2 removes, measuring a systematically wider river (D60) |
| **Pond leak in transects** | connected ponds read as a 3.5 km river, losing 28% of the reach. Fixed by run-mode edges and clamping: 23 → 32 transects (D55) |
| **`data/reaches/` deleted** | recovered; v1 S2 masks had been backed up first, so nothing was lost (D57) |

## Hard-won constraints

- Never chain `RIVERGUARD_REACH=x cmd && cmd2` — the variable is lost for the
  second command and it silently runs on the wrong reach
- No bulk find-and-replace without reading the result — three times it silently
  no-matched or corrupted its target
- Landmask sampling must use the **measured** sensor's resolution (D35)
- Both GEE export scripts must share identical detection constants — enforced by
  `09_checks.py` section 8

## Key numbers

- Geometry: 8.1 km centreline, 32 transects, 0 dropped, median width
  335–370 m (published ~300 m)
- GloFAS: 37 complete years, cell 24.525N 89.725E, 2004 flood at the 97th
  percentile — independent evidence the hydrology is right
- Risk: 64 eligible records, **3** statistically significant

## Do not

- Do not cite the withdrawn **+0.92**. Withdrawn in D37.
- Do not quote an in-sample fit. The number is the cross-validated **2.843**.
- Do not call anything a forecast. The UI and the GeoJSON both carry
  `is_forecast: false`.
- Do not resample Landsat to 10 m.
- Do not commit or push unless explicitly asked.