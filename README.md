# RiverGuard

Measuring riverbank erosion on satellite imagery, comparing independent sensors,
and publishing a chronic-risk ranking with honest uncertainty.

Built as a final-year solo project. Three reaches, 37 years of Landsat, 8 years
of Sentinel-2 at 10 m, and 37 complete years of real GloFAS river discharge.

---

## Read this first: there is no forecast, and that is the finding

The original aim was to predict next year's bank movement. **That does not work
on this data, and the project says so rather than shipping a number that looks
like a prediction.**

Tested against the only benchmark that matters — the trivial "predict the
average" (83.9 m/yr on the Jamuna):

| predictor | MAE (m/yr) | |
|---|---|---|
| **predict the average** | **83.9** | the baseline to beat |
| this transect's own past average | 87.1 | worse |
| same transect, previous pair | 133.7 | much worse |
| 37 years of real river discharge | r = **+0.049** | nothing |

On the Arial Khan, a completely different river:

| predictor | MAE (m/yr) |
|---|---|
| **predict the average** | **2.92** |
| repeat the previous pair | 4.06 (lag correlation **−0.073**) |

Erosion hotspots on a braided river **migrate rather than persist**, and a
catchment-scale discharge value cannot say *where* along the reach the water
attacks the bank. See `reports/DECISIONS.md` D44.

### What this project does claim

- **Measured history** — bank change per year since 1989, from two independent
  instruments that agree (ratio 0.98×, correlation +0.98 on the Jamuna)
- **Chronic risk** — which stretches of river are the persistent eroders
- **Uncertainty** — honestly reported, including that only 3 of 64 eligible
  Arial Khan records are statistically distinguishable from zero

Everything numeric here is reproducible by re-running `ml/`. The write-up should
not assert anything that a script cannot regenerate.

---

## Quickstart

```bash
cd ~/Projects/riverguard

# 1. guard checks — run these FIRST, before anything else
.venv/bin/python ml/09_checks.py

# 2. point the pipeline at a reach
export RIVERGUARD_REACH=arial_khan

# 3. run the measurement chain
cd ml
../.venv/bin/python 01_prepare.py s2        # GEE GeoTIFF -> aligned rasters
../.venv/bin/python 02_banklines.py s2      # rasters -> traced river edge
../.venv/bin/python 04_erosion.py s2        # -> bank erosion rate per transect
../.venv/bin/python 05_features.py s2       # -> modelling table
../.venv/bin/python 13_risk_and_forecast.py # -> risk table + map
../.venv/bin/python 06_predict_geojson.py   # -> long-run trend geometry
../.venv/bin/python 07_validate.py          # -> reports/VALIDATION.md
../.venv/bin/python 08_crosssensor.py       # -> two-sensor comparison
```

### Run the website

```bash
cd ~/Projects/riverguard/backend
../.venv/bin/python manage.py runserver 8010 --noreload

# second terminal
cd ~/Projects/riverguard/frontend
npm run dev          # http://127.0.0.1:5173
```

---

## The three reaches

The pipeline is reach-agnostic. Switch with `RIVERGUARD_REACH=<name>`.

| reach | width | centreline | transects | data |
|---|---|---|---|---|
| `jamuna` | 9 km braided belt | 38.8 km | 58 | Landsat 1989–2026, S2 2019–2026, GloFAS — **archived, see below** |
| `ganges` | 1–4 km single-thread | — | — | registered, no data yet |
| `arial_khan` | 300 m single-thread | 8.1 km | 32 (0 dropped) | S2 v2 2019–2026 ready; **Landsat in progress** |

### Why the Arial Khan

The switch is a test of a hypothesis, not a search for a river that cooperates.

The Jamuna's belt is 9 km wide, so one GloFAS cell (~5.5 km) cannot resolve
*where* the water attacks the bank — that is the specific reason discharge showed
no signal. The Arial Khan is 300 m wide and single-threaded, so the reach fits
inside one cell and outer-bank erosion should persist.

**The hypothesis is currently unsupported.** Seven annual Sentinel-2 pairs show
no skill. The Landsat record at 5-year blocks is the real test (D44, D60).

### Why the Jamuna data is archived, not deleted

`data/unused_data/jamuna/` holds 599 MB. Three reasons, all still valid:

1. It is the **evidence** for the project's central negative result (D44).
2. It is the **control**. A 9 km braided reach against a 300 m single-thread
   reach *is* the experiment. Keeping only the river chosen after the first one
   failed would be cherry-picking.
3. The 37 Landsat files cost about an hour of Earth Engine time to produce.

It remains fully runnable: `RIVERGUARD_REACH=jamuna`. Space was never the reason
to archive it — there is 431 GB free.

---

## Data provenance

| data | source | how |
|---|---|---|
| Landsat 1989–2026 | USGS via Earth Engine | `gee/landsat_export_arial_khan.js` |
| Sentinel-2 2019–2026 | ESA via Earth Engine | `gee/s2_export_arial_khan.js` |
| GloFAS discharge 1989–2025 | Copernicus CEMS Early Warning Data Store | `ml/12_glofas_discharge.py` |

**Imagery is not in this repository.** All rasters (`*.tif`), plus `data/raw/` and
`data/unused_data/` where raw downloads and the archived Jamuna live, are
gitignored — they are regenerable from the scripts above.
The small CSV and GeoJSON evidence tables that back the reports *are* committed.

Both export scripts share **identical water-detection logic**. They must: they
overlap 2019–2026, and if their rules differed the cross-sensor comparison would
measure the difference between two scripts rather than between two instruments,
producing a fabricated step in the river-width record at 2019 (D59). A standing
check enforces this.

The Copernicus token lives in `~/.cdsapirc`, outside the repository.

---

## Repository layout

```
ml/          measurement pipeline, numbered in run order
gee/         Earth Engine export scripts (data acquisition, needs your account)
backend/     Django read-only API over the processed outputs
frontend/    React + MapLibre map
notebooks/   Colab notebook - confirms the no-signal finding with a real model
reports/     DECISIONS.md, VALIDATION.md, RISK.md - the evidence
context/     CURRENT, DONE, TODO, OWNER_ACTIONS - working state
docs/        HOW_IT_WORKS.md - method in detail
```

---

## Documentation

| file | what it is |
|---|---|
| `reports/DECISIONS.md` | **the decision dictionary.** 60 numbered entries: what was chosen, why, what was rejected. Append-only. |
| `reports/VALIDATION.md` | Cross-sensor agreement, cross-method check, predictability testing |
| `reports/RISK.md` | Chronic risk per transect, uncertainty, limitations |
| `docs/HOW_IT_WORKS.md` | The measurement method end to end |
| `context/CURRENT.md` | Current state and the blocking item |
| `AGENTS.md` | Conventions for coding agents working on this repo |

---

## Known issues, stated plainly

1. **EPR signs were inverted project-wide** until D58. Magnitudes were always
   right; direction was not. The Jamuna risk ranking is inverted and must be
   regenerated before use.
2. **GloFAS may not be usable on the Arial Khan.** At Madaripur a 5.5 km cell
   contains both the Padma and the distributary, so the cell's dominant discharge
   may be the Padma's. Must be tested before any discharge feature is trusted.
3. **The MNDWI/AWEI thresholds were tuned on the Jamuna** and are unverified on a
   300 m river.
4. **Most Arial Khan geometry constants are unverified guesses** scaled down for
   a narrow river, pending the Landsat record.
5. **No ground truth.** Confidence comes from two sensors agreeing and from
   literature plausibility, not from absolute accuracy.
6. **`backend/config/settings.py` uses Django's `django-insecure-` dev key.**
   Must be replaced by an environment variable before any deployment.