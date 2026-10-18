# RiverGuard

RiverGuard is a research prototype being built to predict future riverbank
positions from satellite observations. Its active study site is the **Arial
Khan**, Madaripur Sadar–Kalkini reach, Bangladesh.

The project currently measures bankline history from Sentinel-2 (2019–2026),
trains a candidate erosion-rate model, and draws an experimental 10-year
bankline projection. **The prediction system is not validated yet.** The current
model does not beat a simple historical-median benchmark in a time-forward test.
The map labels its projected lines experimental for that reason.

## Goal and current evidence

The goal is to estimate where each bank may move over a stated future horizon,
show the uncertainty, and tell users when the data does not support a useful
prediction. A model that only reproduces the average is not a successful
forecasting system.

The previous headline score (MAE 2.843 m/yr) came from a test that grouped rows
by transect but included measurements from the same year as the target. End-of-
year width and the opposite bank's same-year movement are not available when
predicting that year. That score does not validate future prediction and is
withdrawn as forecasting evidence (see D63 in `reports/DECISIONS.md`).

The corrected test uses only prior-year features and predicts later years from
earlier years. Across 310 held-out bank-side/year records for 2022–2026:

| method | MAE (m/yr) |
|---|---:|
| RandomForest candidate | 3.175 |
| historical median, using training years only | **2.507** |
| repeat the previous year | 3.977 |

The candidate loses to the median baseline. The displayed 2036 lines are a
linear extension of that candidate's rates, not a validated 10-year forecast.
The archived Jamuna study remains useful context, but its negative result is not
evidence about the active Arial Khan reach.

Everything numeric should be reproducible from a script. No assumption or
experimental output should be described as a finding.

---

## Quickstart

```bash
cd ~/Projects/riverguard

# 1. Export masks from Earth Engine and copy them into data/reaches/.
#    Follow docs/DATA_HANDOVER.md; Earth Engine creates Google Drive Tasks.

# 2. Select the active reach and run guard checks
export RIVERGUARD_REACH=arial_khan
.venv/bin/python ml/09_checks.py

# 3. Build the Sentinel-2 history, train the candidate, and draw its experimental projection
cd ml
../.venv/bin/python 01_prepare.py            # GEE GeoTIFF -> aligned rasters
../.venv/bin/python 02_banklines.py          # rasters -> traced river edge
../.venv/bin/python 04_erosion.py s2        # -> bank erosion rate per transect
../.venv/bin/python 05_features.py s2       # -> modelling table
../.venv/bin/python 14_model_train.py      # -> time-forward evaluation + experimental rates
../.venv/bin/python 06_predict_geojson.py   # -> experimental bankline projection
```

The current trainer uses Sentinel-2 only. For Landsat history, cross-sensor
validation, and chronic risk, see the optional Landsat commands in
`docs/DATA_HANDOVER.md`. The 2036 overlay remains experimental until it beats
the baseline and its future bankline positions are validated.

### Run the website

```bash
cd ~/Projects/riverguard/backend
../.venv/bin/python manage.py runserver 8010 --noreload

# second terminal
cd ~/Projects/riverguard/frontend
npm run dev          # http://127.0.0.1:5173
```

---

## Active study

The active study site is the **Arial Khan**. The pipeline can still select
archived reaches with `RIVERGUARD_REACH=<name>`; they are not the active study.

The selected expanded rectangle is
`90.16808799423755, 23.134319063780836 → 90.26902488388599, 23.261491731177696`
and is synchronized in `ml/config.py` and both GEE scripts. Exports and
processing for it are still pending. The 8.1 km centreline, 32 transects, table,
and model scores below describe only the previous, smaller box; rebuild and
re-evaluate before applying them to the expanded area.

| item | current state |
|---|---|
| Existing processed S2 history (previous box only) | 2019–2026 |
| Existing model inputs (previous box) | 432 rows, 31 transects, 7 year-pairs |
| Previous-box evaluation | Expanding time window, prior-year features, 2022–2026 |
| Previous-box candidate / median MAE | 3.175 / 2.507 m/yr |
| Previous-box projection | 62 bank sides extended to 2036, experimental only |
| Expanded-box exports and validation | Bounds selected; exports and rebuild pending |
| Independent ground truth | Not available |

The model currently loses to the median baseline, so the 2036 overlay is a
development output, not a validated forecast. The archived Jamuna result
(37-year record, discharge correlation +0.049) is historical context, not
evidence for Arial Khan prediction skill.

---

## Data provenance

| data | source | how |
|---|---|---|
| Landsat, Arial Khan | Planned; not yet exported | `gee/landsat_export_arial_khan.js` |
| Sentinel-2 2019–2026, previous box | ESA via Earth Engine | `gee/s2_export_arial_khan.js` |
| GloFAS discharge, Arial Khan | Not available for this reach | `ml/12_glofas_discharge.py` |

**Imagery is not in this repository.** All rasters (`*.tif`) and per-reach raw
download folders under `data/reaches/<reach>/raw/` are gitignored. The archived
Jamuna raw downloads under `data/unused_data/` are also excluded.
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
notebooks/   Colab notebook - archived Jamuna model test
reports/     DECISIONS.md, VALIDATION.md, RISK.md - the evidence
context/     CURRENT, DONE, TODO, OWNER_ACTIONS - working state
docs/        HOW_IT_WORKS.md - method in detail
```

---

## Documentation

| file | what it is |
|---|---|
| `reports/DECISIONS.md` | **the decision dictionary.** Append-only record of choices, evidence, and corrections. |
| `reports/VALIDATION.md` | Historical checks and the current time-forward model evaluation |
| `reports/RISK.md` | Archived Jamuna chronic-risk analysis and its limitations |
| `docs/HOW_IT_WORKS.md` | The measurement method end to end |
| `context/CURRENT.md` | Current state and the blocking item |
| `AGENTS.md` | Conventions for coding agents working on this repo |

---

## Known issues, stated plainly

1. **EPR signs were inverted project-wide** until D58. Magnitudes were always
   right; direction was not. Everything on the active reach was rebuilt after the
   fix.
2. **The current model does not beat the historical-median baseline** in the
   chronological test. More data and better forecast-time features are needed
   before treating a projected bankline as a forecast.
3. **Water-detection thresholds carry over from the earlier reach** and are
   unverified on a 300 m river.
4. **Most geometry constants are unverified guesses** scaled for a narrow river,
   pending the longer record.
5. **No ground truth or active-reach cross-sensor validation.** Prediction
   accuracy cannot yet be checked against surveyed banklines, and the Arial
   Khan Landsat comparison is still outstanding.
6. **`backend/config/settings.py` uses Django's `django-insecure-` dev key.**
   Must be replaced by an environment variable before any deployment.