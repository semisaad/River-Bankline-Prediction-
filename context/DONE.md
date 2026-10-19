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

---

## Documentation rebuilt for collaborators (Oct 18, 2026)

The repo had no README, and the existing docs predated the reach switch, the
sign fix and the negative result. Anything a new collaborator read would have
been wrong.

- [x] **README.md** (new) — the front door. Headline finding stated first, then
      quickstart, the three reaches, data provenance, and six known issues.
- [x] **AGENTS.md** (rewritten) — orientation, reach-agnosticism, the standing
      checks and which bugs they caught, and the hard-won constraints
      (env-var chaining, bulk find-and-replace, sensor resolution, GEE async).
- [x] **context/TODO.md** (rewritten) — current blockers, plus a "correctness
      debt" section that did not previously exist: the Jamuna risk table is
      inverted and the feature tables need rebuilding after the D58 sign fix.
- [x] **context/CURRENT.md** (rewritten) — current state, blocking item, key
      numbers, and a do-not list.
- [x] **docs/HOW_IT_WORKS.md** (rewritten) — it still promised a forecasting
      model, cited the withdrawn +0.92 as +0.85, and described a 1 km measuring
      strip for a river that now uses 300 m.
- [x] **context/OWNER_ACTIONS.md**, **notebooks/colab_train.md** — updated
      earlier in the session.

**Decision:** documentation is part of the deliverable, not an afterthought. A
final-year project is assessed partly on whether its claims are traceable, and a
document that overstates what was achieved is worse than no document.

## Raw imagery deleted; handover written (Oct 18, 2026)

- [x] Verified what survived: processed masks, features, EPR, geometry, the
      trained model and its projections are all intact. Only the raw `.tif`
      downloads are gone.
- [x] Re-ran `14_model_train.py` on the surviving processed data: still
      MAE 2.843, then reported as beating the 2.919 baseline. D63 later
      withdrew that score as forecast evidence because same-interval features
      were present; see the corrected time-forward test in CURRENT.md.
- [x] `docs/DATA_HANDOVER.md` (new) — written for a third party with no access to
      this conversation. Which script to use and which four to ignore, the exact
      box, why it must not be drawn, what the console table should say, how to
      verify, and the full rebuild sequence.
- [x] Flagged that the export scripts were not yet on GitHub; the later push to
      `origin/main` resolved that blocker.

---

## Hydrology export repaired, tested, and rejected (Oct 19, 2026) — D88, D90

### The export was measuring the wrong river
- [x] `gee/hydro_export.js` carried the retired **Jamuna** box as its REGION
      (`[88.5, 23.5, 91.0, 25.5]`). The active reach is at latitude 23.134–23.261.
      The two rectangles **did not overlap at all.** `11_hydro_features.py` clips
      every raster to the study box, so it would have written a table of NaNs and
      raised no error anywhere.
- [x] Region now `[89.95, 22.90, 90.50, 23.45]`
- [x] Dry season (1 Jan – 28 Feb) → **full calendar year**. The old window is the
      lowest-flow part of the year: it described drought, not the monsoon that
      actually moves a bank.
- [x] `filterDate` end is **exclusive**, so each year now ends at the following
      1 January; ending on `12-31` silently drops 31 December
- [x] Years `1985–2026` → **`1983–2025`** (1983 because the oldest pair needs
      y0−step = 1984; 2025 because 2026 is part-complete and biased high)
- [x] Docstring no longer claims "catchment-scale" — it is a weather proxy over
      the reach, roughly one ERA5-Land cell
- [x] **New standing check 7b** in `09_checks.py`: the hydrology box must
      *cover* the study box (a superset is fine here, unlike the imagery
      exporters). Tested both ways — it fails on the old box, passes on the new.

### The data arrived and the hypothesis lost
- [x] 43 `Hydro_<year>.tif` downloaded, verified (8 bands, correct descriptions,
      EPSG:4326, 0% NaN, precip ~2.4 m/yr, solar ~16 MJ/m²/day — both plausible
      for Bangladesh) and moved to `data/reaches/arial_khan/raw/hydro/`
- [x] **Bug found:** `11_hydro_features.py` passed `densify_pts=21` to
      `rasterio.warp.transform_geom`. That is a **pyproj** argument; rasterio
      rejects it outright. The line had never executed because no data existed
      before, so the wrong keyword sat there harmlessly.
- [x] Result: 24 hydrology columns, 2414 rows, correlations ≤ 0.056. Rain and
      runoff point the physically correct way (+0.056, +0.045).
- [x] `14_model_train.py --hydro` → **16.562, worse by 0.676 (+4.3%)**. Every
      column reaches the forest; the strongest gets 1.2% importance.
- [x] Kept as evidence rather than deleted; the export script header now says
      the reasoning was tested and did not hold

## GloFAS route abandoned (Oct 19, 2026) — D88

- [x] At this reach the nearest GloFAS cell reads a maximum of **13 m³/s for an
      entire year** — a 5 km grid cannot see a 300 m distributary, so it models a
      small local catchment instead. A perfect 38-year download would still have
      been the wrong river.
- [x] Leftover partial outputs archived to `data/archive/glofas_arial_khan_*`
- [x] `*.nc` added to `.gitignore`
- [x] `MIN_GLOFAS_YEARS = 10` guard added — the 2-row remnant would have produced
      `q_*` columns that are neither empty nor constant, so **both** guards in the
      trainer would have kept them
- [x] Later removed entirely along with its downloader, so a stale
      `glofas_annual.csv` can no longer be read by anything

## Two bugs in our own honesty machinery (Oct 19, 2026) — D89

- [x] `06_predict_geojson.py` printed **"the one-year model does not beat both
      baselines"** while the same payload carried MAE 15.886 vs 20.413 and
      `forecast_supported: True`
- [x] Root cause: the payload never carried the number the claim rests on.
      `forecast_supported` is gated on `best_baseline` (the min of the three),
      but only the *median* was written out.
- [x] `14_model_train.py` now emits `best_baseline_mae_m_per_yr`; the warning and
      the console note are generated from the payload's own values in both
      directions
- [x] Frontend now quotes the strongest baseline, not the median
- [x] **New check 10 guard:** the warning must agree with `forecast_supported`.
      Worth recording that **the first version of this check searched for
      "NOT beat" while the real text says "does not beat" — it passed the exact
      bug it was written to catch.** Rewritten case-insensitively and tested
      against the old text in both directions.

## Model comparison corrected (Oct 19, 2026) — D91, D92

- [x] `--model gbm` now scores **15.675**, beating RandomForest's 15.886 by 0.211
      (1.3%), with folds split 16/13 — a tie
- [x] D82's "RandomForest beats GradientBoosting (17.330 vs 17.468)" was measured
      **before `curv_outer` was added** and is superseded explicitly, not deleted
- [x] RF kept on tie-break grounds only: built-in `feature_importances_`, fewer
      hyperparameters, continuity of published numbers
- [x] **Per-fold analysis:** the model beats its own baseline in 20/29 folds.
      **1996–2015: 18/18, mean gain +7.53. 2016–2026: 2/11, mean gain −0.82.**
      The pooled 22% advantage is concentrated in the folds with fewest training
      years.
- [x] Per-fold results were already stored in `model_report.json`, so D92 is now
      reproducible rather than a hand calculation
- [x] `reports/MODEL_CHOICE.md` written: why RF and by how much, the tie with
      GBM, feature importance, the recent-fold caveat, why hydrology hurt

## Validation report made honest and regenerable (Oct 19, 2026)

- [x] `reports/VALIDATION.md` section 7 was **stale**: it quoted 3.175 vs 2.507,
      numbers belonging to the **previous box**, and its limitations described
      the retired Jamuna box ("export stops at 24.35N", "about 30 km")
- [x] Root cause: the report had drifted from its generator, and the generator
      would have **deleted** the hand-written section rather than correct it.
      Nothing recomputed it, so nothing caught the drift.
- [x] `07_validate.py` rewritten: **PART A** is recomputed from files on every
      run and cannot go stale; **PART B** is a clearly-marked frozen record of
      the Jamuna negative result, which this script does not pretend to recompute
      (the Jamuna data is gone)
- [x] `08_crosssensor.py` now writes `reports/crosssensor_check.json` so the
      report quotes real numbers instead of restating them by hand
- [x] Fixed a hardcoded `EPSG:32645` (the Jamuna's zone) in the generator
- [x] **Proved idempotent:** running it twice produces a byte-identical report
- [x] New honest findings it surfaced:
      - Sentinel-2's annual median is **1.2 m/yr** — an eighth of its own 10 m
        pixel. Its annual target is mostly quantisation, not erosion.
      - Landsat's median is **11.2 m/yr**, roughly **half** the published 21 m/yr
        for this river. The old report claimed to sit inside the published range;
        it does not, and now says so.
      - The **rate-level cross-sensor test cannot run on this reach** — S2 uses
        1-year pairs, Landsat 5-year, so no shared pair exists. On the Jamuna
        this was the project's strongest evidence; here it is simply absent.

## Repository cleaned (Oct 19, 2026) — D93

- [x] Removed dead scripts: `12_glofas_discharge.py` (rejected path),
      `14_model_test.py` (superseded diagnostic), `00_collect_landsat.py`
      (targeted the pre-reach-aware layout), `gee/landsat_export.js` and
      `gee/landsat_export_ganges.js` (a retired reach and a never-run trial —
      both would have exported the **wrong river** if run today)
- [x] Removed `notebooks/colab_train.md` (training runs locally; Colab not needed)
- [x] Removed `data/unused_data/` (50 MB: Jamuna raw masks and stale v1 masks)
      and the `jamuna`/`ganges` reach entries from `config.py` and `views.py`
- [x] **Caught in the process:** check 2 in `09_checks.py` tested only the first
      line mentioning `LE07` in the deleted Jamuna script. Pointed at the live
      exporter — where `LE07` appears once, in a collection id — it **passed
      vacuously**. Rewritten to verify the actual band mapping for TM/ETM+
      (green = SR_B2) and OLI (green = SR_B3), then tested against a deliberately
      swapped band list to prove it now fails when it should.
- [x] Context files, README, docs and prompts reconciled with reality

**Not recoverable:** `data/unused_data/jamuna/` was gitignored and held the raw
Jamuna GloFAS discharge table, which `config.py` recorded as impossible to
derive from the masks. The *finding* survives in full (D44, `reports/RISK.md`,
PART B of `VALIDATION.md`) with its numbers, cell coordinates and plausibility
checks, but the raw CSV is gone.

---

## Gradient boosting adopted as the served model; the report can no longer name the wrong estimator (D94)

**Date:** 2026-10-19

- `DEFAULT_MODEL = "gbm"` and `DEFAULT_SENSOR = "landsat"` now key the artefact
  filenames in `14_model_train.py`. The default writes `model_report.json` and
  `model_predictions_landsat.csv`; everything else writes a suffixed variant.
- Gradient boosting scores **15.675** against the forest's **15.886** on the
  identical expanding-window backtest — 0.211 m/yr, **1.3%**, folds split 16/13.
  Adopted on the owner's position that a small, reproducible, out-of-sample
  margin is still a margin.
- **Bug fixed:** the report's `"model"` field was a hardcoded RandomForest string
  written regardless of `--model`, so a GBM run produced an artefact naming the
  wrong estimator while carrying its score. Now built by `model_label()`, and a
  short `model_name` travels in the prediction rows so `06_predict_geojson.py`
  names the model in the GeoJSON instead of typing it.
- **Bug fixed (2):** `--sensor` defaulted to `s2` while `model_report.json` has no
  sensor in its name and `views.py` reads it as the served model — so a bare
  re-run, exactly what `README.md` documents, would have described the landsat
  map with S2 numbers. Default is now `landsat`.
- Deleted the now-orphaned `_gbm` artefacts, since no command produces that
  suffix any more.
- `MODEL_CHOICE.md` rewritten around the new default, including the honest cost:
  permutation importance does not rank features the same way the forest's
  built-in importance did, so **both** tables are now shown.

## Two bankline validation figures, and the learning curve behind them

**Date:** 2026-10-19

- `reports/validation_bankline_2026.png` — model trained only through **2021**,
  asked to draw 2026 (5-year horizon).
- `reports/validation_bankline_2026_from2023.png` — trained through **2021** vs
  **2023**, both predicting the *same* 2023→2026 window (3-year horizon), so only
  the amount of history differs. Includes the full learning curve.
- Both now name the estimator on the figure itself.
- **The result is honest and uncomfortable: the model loses to "the bank never
  moved" for absolute position** (2021→2026 mean error 50.6 m vs 18.2 m;
  2023→2026 30.8 m vs 13.8 m). At 30 m resolution over a 3–5 year step, many bank
  sides genuinely do not move a whole pixel, so do-nothing is not an assumption
  for them — it is the measurement.
- **More data does help**: MAE falls monotonically from 29.75 (through 1999) to
  11.02 (through 2023) on a fixed target. A count-matched test shows the gain is
  **recency, not quantity** — the newest 8 pairs score 8.87 against the oldest
  16 at 21.02.

## Literature and evidence base written (D95)

**Date:** 2026-10-19

- `reports/LITERATURE.md` created: every claim the project makes, plus the
  published work behind it, with DOIs resolved and confidence marks.
- **D95 — the 21 m/yr gap is largely definitional, not a measurement failure.**
  The published figure is *derived*: Hasan et al. (2024) report the channel
  "shifted an average of 0.66 km" over 1993–2024 = 21.3 m/yr, measured as a
  **channel-centreline average** over a 2 km buffer. This project reports the
  **median of individual bank-side displacements** at fixed transects. A median
  of a heavy-tailed distribution sits below its own mean, and a centreline
  average follows the fastest bends. Both numbers can be right.
- The 250 m measurement strip and single-reach scope are **not** explained away
  and remain stated limitations.
- Section 4 of `LITERATURE.md` reframes the negative result: Langhorst &
  Pavelsky (2023) put the minimum detectable change from 30 m imagery at ~0.35
  pixel (≈10 m), which is the same order as the model's error. The conclusion is
  "not predictable beyond persistence at this resolution", which is a finding
  rather than a failure.
- Section 6 records that **no published bankline-prediction paper found runs a
  persistence baseline** — so this project fills a gap rather than contradicting
  prior work.
