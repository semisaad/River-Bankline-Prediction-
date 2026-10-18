# CURRENT STATE

**Date:** 2026-10-18 · **Branch:** main, synchronized with origin/main

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

## Goal and current model status

The goal is a system that predicts future bankline positions and makes
uncertainty visible. The current implementation is a research prototype, not a
validated forecasting system.

The former 2.843 m/yr score (D62) used a transect-grouped split but included
same-interval measurements, such as end-of-year width and the opposite bank's
movement. Those values are unavailable before predicting that year. D63 records
the correction; the old score is not forecasting evidence.

The corrected RandomForest uses prior-year features and expanding time windows:

| test years | held-out records | model MAE | training-median MAE | previous-year MAE |
|---|---:|---:|---:|---:|
| 2022–2026 | 310 | 3.175 m/yr | 2.507 m/yr | 3.977 m/yr |

The model loses to the median baseline. Its 62 current bank-side rates are still
drawn as **experimental** 10-year extensions to 2036; the extension is linear
and has no independently validated 10-year uncertainty interval.

## Status

| item | state |
|---|---|
| Active reach | Arial Khan, Madaripur Sadar–Kalkini |
| Processed Sentinel-2 | 2019–2026 masks, banklines, EPR and features available |
| Geometry | 32 transects; 0 dropped; median width about 350 m |
| Candidate model | Runs with prior-year features; fails chronological median baseline |
| Experimental projection | 62 bank sides to 2036; explicitly not a validated forecast |
| Raw S2/Landsat exports | Missing; processed S2 outputs survive |
| Arial Khan Landsat | Not yet exported; needed for longer-record and cross-sensor tests |
| Ground-truth survey | Not available |
| Website | Serves selected reach; default is Arial Khan |
| Guard checks | Blocking checks pass; Landsat/GloFAS checks warn while data is absent |

## Next work

1. Re-export the raw Sentinel-2 and Landsat imagery using `docs/DATA_HANDOVER.md`.
2. Rebuild the Landsat record and run cross-sensor validation before using it as
  training evidence.
3. Test forecast-time features with walk-forward evaluation and compare against
  training median and previous-year baselines. Keep a later year untouched for
  a final test.
4. Improve bankline-position evaluation and uncertainty; rate MAE alone does
  not measure the spatial error of a future shoreline.

Push blocker is resolved: `main` is synchronized with `origin/main`.

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
- Archived Jamuna GloFAS: 37 complete years; not Arial Khan evidence
- Archived Jamuna risk table: 64 eligible records, **3** statistically significant

## Do not

- Do not cite the withdrawn **+0.92**. Withdrawn in D37.
- Do not quote **2.843** or **2.835** as forecast skill; they used same-interval
  features. Current time-forward rate MAE is 3.175 vs 2.507 median baseline.
- Do not call the current 2036 geometry a validated forecast. The UI and GeoJSON
  mark it experimental and carry `is_forecast: false`.
- Do not resample Landsat to 10 m.
- Do not commit or push unless explicitly asked.