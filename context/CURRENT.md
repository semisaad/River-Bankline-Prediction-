# CURRENT STATE

**Date:** 2026-10-18 · **Branch:** master, committed locally, **not yet pushed**

## Active reach: Arial Khan (Madaripur Sadar – Kalkini, middle reach)

Box `90.1927, 23.1638 → 90.2384, 23.2450` (42 km², measured from the export),
EPSG:32646, Sentinel-2 primary at 10 m.

Chosen 2026-10-18 (D49–D52). The pipeline was already reach-agnostic, so this
was a config change, not a rebuild.

> **The northern edge must stay south of 23.47N** — the bifurcation from the
> Padma. North of that line the water body *is* the Padma. An earlier box reached
> 23.60N and the preview came back mostly Padma (D51). Hard constraint, recorded
> in `config.py` and both export scripts.

## The headline result: no forecast, and that is the finding

Year-to-year bank erosion is not predictable from this data. Tested against the
trivial baseline of predicting the average.

**Jamuna** (1876 rows, 1989–2026, 37 yr GloFAS):

| predictor | MAE (m/yr) |
|---|---|
| **predict the average** | **83.9** ← the baseline |
| this transect's own past average | 87.1 |
| same transect, previous pair | 133.7 |
| real GloFAS discharge, within-transect | r = **+0.049** |

**Arial Khan** (432 rows, S2 2019–2026):

| predictor | MAE (m/yr) |
|---|---|
| **predict the average** | **2.92** |
| repeat the previous pair | 4.06 (lag corr **−0.073**) |

Hypothesis for the switch — that a 300 m single-thread meander erodes
persistently at its outer banks — is **currently unsupported**. The Landsat
record at 5-year blocks is the real test (D44).

## Status

| item | state |
|---|---|
| S2 masks, Arial Khan | ✅ v2, 8 years, verified |
| S2 geometry | ✅ 32 transects, 0 dropped, median width 350 m |
| S2 EPR + features | ✅ 7 pairs |
| Landsat masks, Arial Khan | ⛔ 19 files present but built with **superseded detection constants** — must be re-exported |
| GloFAS, Jamuna | ✅ 37 complete years |
| GloFAS, Arial Khan | ❌ existing download does not cover the reach |
| Cross-sensor check | ❌ needs Landsat 2019–2023 |
| Jamuna risk table | ⚠️ **inverted** — predates the EPR sign fix (D58) |
| Website | ✅ chronic-risk + long-run-trend layers |
| Guard checks | ✅ all pass, both reaches |

## Blocking item

**Re-export Landsat for the Arial Khan** with the current script. See
`context/OWNER_ACTIONS.md`.

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

- Cross-sensor, Jamuna: ratio 0.98×, correlation +0.98, mean IoU 0.85
- Arial Khan geometry: 8.1 km centreline, 32 transects, 0 dropped, median width
  335–370 m (published ~300 m)
- GloFAS: 37 complete years, cell 24.525N 89.725E, 2004 flood at the 97th
  percentile — independent evidence the hydrology is right
- Risk: 64 eligible records, **3** statistically significant

## Do not

- Do not cite **+0.92** anywhere. Withdrawn in D37, restated in VALIDATION.md.
- Do not call anything a forecast. The UI and the GeoJSON both carry
  `is_forecast: false`.
- Do not resample Landsat to 10 m.
- Do not commit or push unless explicitly asked.