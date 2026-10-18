# Done

## M0 — Walking Skeleton (complete)
- [x] Repo scaffolded: data, ml, backend, frontend, notebooks, reports, context
- [x] Extracted 16 GEE files (8 years of RGB + MNDWI masks, 2019–2026)
- [x] Python venv built with rasterio, geopandas, shapely, scikit-image, scipy, pyproj
- [x] `ml/config.py` — shared paths, CRS (EPSG:32645), pixel size (10 m), years
- [x] `ml/01_prepare.py` — reprojected all 8 years to one common metre-grid (2095 × 3365 px)
- [x] `ml/02_banklines.py` — traced river edge per year → GeoJSON per year
- [x] `ml/03_transects.py` — measured bank movement 2022→2023 via flow-aligned transects
- [x] Fixed PCA transect method (old horizontal version gave 582 m/yr nonsense; PCA gives 140 m/yr median — plausible)
- [x] Django 6.1 + DRF + CORS backend with 4 endpoints: health, years, banklines, transects
- [x] React + Vite + MapLibre GL frontend with year slider, play button, colour-coded transects
- [x] Vite proxies /api to Django (port 8010)
- [x] Production build passes (vite build)
- [x] **Fixed MapLibre v6 named-exports** (no default export)
- [x] **Fixed coordinate system bug** — banklines/transects were saved in UTM metres (EPSG:32645), MapLibre needs WGS84 degrees (EPSG:4326). Now reprojected to WGS84 before writing GeoJSON.
- [x] Moved project from `~/Projects/riverguard` → `/media/saad/HDD/riverguard` (HDD, 431 GB free)
- [x] Created symlink `~/Projects/riverguard` → `/media/saad/HDD/riverguard`
- [x] Rebuilt .venv and node_modules on HDD
- [x] Added `.gitignore` (excludes .venv, node_modules, __pycache__, data/raw)
- [x] Saved preferences: global `~/.config/opencode/AGENTS.md` + project `AGENTS.md`
- [x] Wrote plain-language guide: `docs/HOW_IT_WORKS.md`

## Validation (in progress)
- [x] Confirmed median bank movement 60–140 m/yr (plausible for Jamuna, matches literature)
- [x] Confirmed direct polygon-distance check: median 62–117 m between years
- [ ] Cross-sensor agreement (S2 ↔ S1 ↔ Landsat) — not started
- [ ] GSW comparison — not started

## M1 — Measurement fix (Oct 17, 2026)
- [x] Diagnosed the envelope method as the core scientific weakness
- [x] Built `ml/04_erosion.py` using EPR (Erosion/Progradation Rate)
- [x] Learned: whole-belt averaging nets to ~0; must isolate outer banks
- [x] Learned: zone must straddle the real water edge, not the filled belt
- [x] Generated all 7 consecutive year-pairs (2019->2020 ... 2025->2026)
- [x] Sensitivity test: speckle filter stable (+6%), zone depth documented
- [x] Cross-validated vs independent outline-distance measure: corr +0.85
- [x] Added `/api/erosion/` and `/api/erosion/pairs/` endpoints
- [x] Map now colours transects by erosion rate, with a stats readout
- [x] Removed the temporary debug panel
- [x] Closed a path-traversal hole in the `pair` query parameter
- [x] Fixed MapLibre worker 404 (copy worker to public/, set config.WORKER_URL)

## Full build-out (Oct 17, 2026, session 3)
- [x] `ml/transects.py` — shared transect geometry module
- [x] Refactored `04_erosion.py` onto it, numbers byte-identical
- [x] `ml/05_features.py` — leak-free ML feature table (280 rows, 25 columns)
      Includes water-level columns (stage_km2, stage_change_km2, stage_ratio)
      and bend geometry (curvature_k, meander_off, bank_asym_m, width_ratio)
- [x] `gee/landsat_export.js` — Earth Engine script for 1984-2026 (OWNER RUNS)
- [x] `ml/01b_prepare_landsat.py` + config additions — 30 m Landsat branch
- [x] `notebooks/colab_train.md` — full training notebook (OWNER RUNS)
- [x] `ml/06_predict_geojson.py` — offsets bank lines into predicted geometry
- [x] `ml/07_validate.py` — writes `reports/VALIDATION.md`
- [x] API: `/api/predictions/`, `/api/status/`, erosion endpoints
- [x] Map: erosion colouring by rate, forecast toggle, stats readout
- [x] Validation report: cross-method correlation +0.92
- [x] Honest finding recorded: no learnable signal with 8 years; persistence
      (MAE 74.2) is worse than predicting the mean (47.8)
- [x] `context/OWNER_ACTIONS.md` written for the owner

## Landsat export script rewritten (Oct 17, 2026)
- [x] Fixed **fatal bug**: header block comment was never closed (`*/` missing),
      so the entire file was one unterminated comment. Would have failed instantly
      in Earth Engine. Caught with `node --check`.
- [x] Fixed **wrong QA_PIXEL bit positions**. Previous version used
      `parseInt('11111',2)` for "shadow" and `parseInt('1',1)` for "dilated",
      which were the wrong bits. Now explicit: fill=1, dilated=2, cirrus=4,
      cloud=8, shadow=16.
- [x] Removed **Landsat 1-3 / MSS handling**, which cannot work: MSS is not in
      `LANDSAT/C02/T1_L2` at all. Landsat 4 (1982) covers our 1984+ window.
- [x] Removed the fragile `ee.Image(0).where(...)` sensor branching. Each sensor
      generation is now filtered separately and combined with `mosaic()`, which
      is how Earth Engine is meant to handle mixed sensors.
- [x] Automatic naming retained and verified: every task is `MNDWI_Mask_<year>.tif`
- [x] Verified with a stubbed Earth Engine: 43 tasks created, names/scale/CRS validated
- [x] Years with no imagery are skipped automatically and reported in the console

## Sentinel-2 data audit (Oct 17, 2026)
Checked all 16 raw files (8 masks + 8 RGB), 2019-2026:
- Metadata fully consistent: EPSG:4326, 2227x3340, uint8 masks / uint16 RGB
- **Nodata: 0.00% every year.** No gaps that could masquerade as land.
- **Cloud contamination: 0.0%** bright+flat pixels inside the water mask.
- Water pixels are dark and green-dominant (R<G>B pattern), which is CORRECT for
  the Jamuna: it is one of the most turbid rivers in the world, so suspended
  silt makes green reflectance exceed blue. Not a bug.
- Water area 83-104 km2/yr. 2020 is high (103.6), consistent with an unusually
  wet late-2019 monsoon leaving the floodplain fuller into Jan-Feb.
- Spatial structure is a single coherent diagonal band. Good.

### IMPORTANT: found an index mismatch, now fixed
The existing Sentinel-2 masks use **(B3 - B11)/(B3 + B11) > 0.2**, where B11 is
SWIR at 1.6 um. My Landsat script originally used a NIR-based index with the
opposite sign. Different measurements, so the two records would have disagreed
for reasons unrelated to the river.

Fixed: Landsat now uses the **identical** index (green - SWIR1)/(green + SWIR1)
with the **identical** 0.2 threshold. Landsat has SWIR1 at the same 1.6 um
wavelength in every generation (L4/5 = SR_B5, L7 = SR_B5, L8/9 = SR_B6).

Added `ml/08_crosssensor.py`: compares both sensors on the 8 overlapping years
at a common 30 m grid, reporting IoU, water-area difference and bankline offset.
This is the strongest validation available without ground truth. Runs once the
Landsat files arrive.

## Landsat dataset ID bug, fixed (Oct 17, 2026)
Saad hit: `ImageCollection asset 'LANDSAT/C02/T1_L2' not found`.

Root cause: **there is no merged Collection 2 collection.** Collection 1 had one
(`LANDSAT/C01/T1_L2`), but Collection 2 is published per sensor:
- LANDSAT/LT04/C02/T1_L2 (Landsat 4 TM)
- LANDSAT/LT05/C02/T1_L2 (Landsat 5 TM)
- LANDSAT/LE07/C02/T1_L2 (Landsat 7 ETM+)
- LANDSAT/LC08/C02/T1_L2 (Landsat 8 OLI)
- LANDSAT/LC09/C02/T1_L2 (Landsat 9 OLI-2)

Fixed: script loads each sensor's own collection, filters to region + dry season,
then merges them with `.merge()` before grouping by SENSOR_ID.

Verified against the official Earth Engine catalog:
- SR_B6 on LC08 is confirmed as "shortwave infrared 1", 1.566-1.651 um, which is
  the same wavelength as Sentinel-2 B11. Our matching-index choice is sound.
- QA_PIXEL bits confirmed: 0 Fill, 1 Dilated Cloud, 2 Cirrus, 3 Cloud,
  4 Cloud Shadow. Our mask uses 1/2/4/8/16. Correct.
- NEW FINDING: QA_PIXEL **Bit 7: Water** is CFMask's own water classification,
  an independent water map for free. Future work: use it to validate our
  threshold-derived mask rather than trusting the threshold blindly.

## Two more Earth Engine bugs, found by Saad running it (Oct 17, 2026)

### Bug A — `Date.fromYMD` got an undefined year
Symptom: `Required argument (year) missing to function: Date.fromYMD(...)`

I had written `.evaluate(function (n, year) {...}, year)`, assuming Earth Engine
passes a second "user data" argument to the callback. **It does not.** The
callback only ever receives the evaluated result, so `year` was `undefined`.

Fix: each year is now built inside its own `buildYear(year)` function, so every
callback closes over its own private copy of the year.

Proven with an isolated test using async callbacks:
- broken (shared loop variable): 1987,1987,1987  <- all three exports same year
- fixed  (own copy each):       1984,1985,1986  <- correct

This one mattered a lot: left unfixed, every task would have been filed under
the wrong year name.

### Bug B — an Earth Engine object is always truthy
`if (group.size().gt(0))` never evaluated to false, because `.size()` returns an
Earth Engine *object* and every JavaScript object is truthy. So the script
tried to build a median composite for all five sensors every year, including
sensors with zero scenes in that window - wasteful and potentially an error.

Fix: emptiness is now tested on the server with `ee.Algorithms.If`, returning a
fully masked image when a sensor has no scenes; `mosaic()` skips that
automatically. Both patterns are gone from the file (verified by grep).

Lesson worth remembering: in Earth Engine, never branch on a server-side value
with a plain JavaScript `if`. Use `ee.Algorithms.If`, or force evaluation first.

## Landsat record ingested (Oct 17, 2026)
- [x] 37 usable Landsat years (1989-2026, only 1992 dropped) at 100% coverage
- [x] Removed 10 stale empty masks + 37 duplicate files found mixed in
- [x] `01b_prepare_landsat.py` on its own bbox; coverage guard working
- [x] `08_crosssensor.py` result: **IoU 0.86, area diff +1.4%, bank offset 0-30 m**
- [x] Per-pair zone anchoring (D-earlier) - fixed zeros over the 36-year span
- [x] `09_checks.py` guard script added
- [x] **FOUND A REAL PROBLEM (D33): transect geometry is wrong.** Zones sit on
      dry land; belt width measures 18 km instead of ~9 km. Both sensors'
      erosion figures are untrustworthy until this is fixed.

## Transect geometry rebuilt (Oct 17, 2026) — D34
- [x] Centreline that follows the river (distance-transform ridge)
- [x] Transects perpendicular to local direction, 500 m spacing, fixed once
- [x] Length capped at belt width + margin; all drops reported with reasons
- [x] Edge = where smoothed water profile stops looking like river
- [x] Validated 6/7 spot checks pass; belt width 4.1-11.1 km (was 18 km)
- [x] Withdrew the old +0.92 correlation as validation of absolute values
- [x] Rates recomputed: S2 56.6 m/yr, Landsat 138.6 m/yr (35 pairs)
- [x] **OPEN (D35): cross-sensor rate disagreement 3.3x, corr -0.10**

## Cross-sensor disagreement SOLVED (Oct 17, 2026)
- [x] Root cause: masks sampled with the GEOMETRY sensor's resolution (10 m)
      instead of the measured sensor's (30 m) -> Landsat casts compressed to 1/3
- [x] Proved it was not the speckle filter (OPEN_M 0/20/40 all identical)
- [x] Proved the masks themselves were identical bin by bin
- [x] Belt width ratio now 1.00x (17/18 transects within 15%)
- [x] EPR rate ratio 0.98x, correlation +0.96 -> real cross-sensor validation
- [x] Recomputed: S2 56.6 m/yr (7 pairs), Landsat 109.8 m/yr (35 pairs)
- [x] Recorded that two RGB-based checks failed legitimately (D36)

## Hydrology features prepared (Oct 17, 2026) — D38
- [x] Discovered GloFAS is NOT in Earth Engine (CDS-only), unlike assumed
- [x] `gee/hydro_export.js` — ERA5-Land hydrology, 1985-2026, 8 bands, catchment box
- [x] `ml/11_hydro_features.py` — joins climate to features, leak-free
- [x] `ml/12_glofas_discharge.py` — real discharge via CDS, clear setup instructions
- [x] Both scripts pass the guard checks
- [x] Confirmed 35 years of imagery still gives no signal (D18)

## GloFAS route prepared (Oct 17, 2026) — D39
- [x] Verified the real dataset/API: `cems-glofas-historical` on
      `ewds.climate.copernicus.eu/api` (NOT the main CDS API, NOT Earth Engine)
- [x] Removed `upstream_area` from the request (separate ancillary dataset)
- [x] One request per year, resumable, rate-limited
- [x] Cell chosen by discharge magnitude; printed with a plausibility check
- [x] Installed cdsapi>=0.7.7 + xarray; verified Client(url=...) signature
- [x] `11_hydro_features.py` joins GloFAS or ERA5-Land, reporting each separately
- [x] One-year-per-request confirmed against the live form (D40)
- [x] `--from-files` mode reads hand-downloaded NetCDF, any filename, any
      coordinate naming; tested on a synthetic awkward-layout file, then cleaned up
- [x] First real GloFAS file (1989) inspected; 4 bugs fixed (D41): avg_dis name,
      netcdf4 backend, year-boundary leak, Ganges-instead-of-Jamuna cell
- [x] 1989 verified plausible: Jan 3.5k -> Jul 66k -> Dec 5.2k m3/s
- [x] netcdf4 installed; `--from-files` runs clean on the real file
- [x] API route verified end-to-end; 1989 API output md5-identical to form download (D42)
- [x] 403 on multi-year confirmed server-side cap; pinned to 1 yr/request (D43)
- [x] md5 duplicate-file guard so a year can't be counted twice
- [x] cdsapi retry tuned to survive intermittent DNS

## Product reframed after D44 (Oct 18, 2026) - D45
- [x] `13_risk_and_forecast.py`: 102 risk records, 64 eligible (>=10 yr), block-bootstrap median CI
- [x] `06_predict_geojson.py` rewritten for new transects API; emits long-run trend, is_forecast=false
- [x] `07_validate.py` rewritten: cross-sensor 0.98x / +0.98, +0.92 explicitly withdrawn
- [x] Stale 280-row features.csv archived to data/archive/, guard check added
- [x] API: /api/risk/, /api/risk/summary/, /api/predictions/?horizon=
- [x] 09_checks.py sections 7-9 added; all blocking checks pass

## Model test run, no-signal finding confirmed with real models (Oct 18, 2026) - D47
- [x] scikit-learn 1.9.1 installed into `.venv` (new project dependency)
- [x] `ml/14_model_test.py`: RandomForest/GradientBoosting vs mean+median dummies,
      GroupKFold by transect, three feature sets (forecast-only / +same-year
      forcing / as-first-written), runs in ~80 s locally
- [x] Robustness: seeds 0/1/2 x fold counts 5/10/20 — RandomForest 83.28-84.39,
      GradientBoosting ~87-89; median dummy 83.50 is the bar; no useful win
- [x] `notebooks/colab_train.md` fixed: broken canary cell deleted; feature set
      now honours its own "nothing from the target interval" comment (old set fed
      the models other_side_rate, width_m, width_change_pct, width_ratio +
      same-year forcing — measured harmless, r -0.05..+0.01, but wrong on principle)
- [x] Notebook cell verified end-to-end against the real CSV (extracted and run)
- [x] DECISIONS.md D47 appended; VALIDATION.md section 5 gains the model table;
      CURRENT/TODO/OWNER_ACTIONS updated — nothing is waiting on the owner anymore
