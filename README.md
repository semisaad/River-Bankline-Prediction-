# RiverGuard

Measuring riverbank erosion on satellite imagery, comparing independent sensors,
and publishing a chronic-risk ranking with honest uncertainty.

Built as a final-year solo project on the **Arial Khan** (Madaripur Sadar –
Kalkini reach, Bangladesh): 8 years of Sentinel-2 at 10 m, a trained erosion
model cross-validated against it, and banklines projected forward to 2036.

The project moved here from an earlier reach on the Jamuna, where year-to-year
erosion turned out to be unpredictable. That negative result is what motivated
the switch and is preserved in `reports/DECISIONS.md`; the Jamuna data itself is
archived and no longer part of the work.

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

The project works on **one river**, the Arial Khan. The pipeline still accepts a
reach name so the earlier work stays reachable, but the analysis, the model and
the reported results are all Arial Khan.

| | |
|---|---|
| Reach | 300 m wide, single-thread, 8.1 km centreline |
| Geometry | 32 transects, **0 dropped**, median width 335–370 m |
| Model | RandomForest, `GroupKFold(5)` **grouped by transect** |
| Skill | MAE **2.843** m/yr vs 2.919 for predict-the-average, r **+0.517** |
| Projection | 62 transect-sides to 2036 |

### The model works — on the Arial Khan

| | MAE (m/yr) | correlation |
|---|---|---|
| predict the average | 2.919 | — |
| repeat the previous pair | 4.060 | −0.073 |
| **RandomForest** | **2.843** | **+0.517** |

Cross-validated with `GroupKFold` grouped **by transect**, so no part of a bank is
ever in both training and test. The equivalent test on the Jamuna gave +0.049 and
nothing beat the baseline — that contrast is why the study moved rivers (D62).

The margin is 2.6%: real, not large, and the record behind it is 432 rows over 7
year-pairs. The Landsat 5-year-block record is what would make it defensible.

### Why this river

The previous reach was a 9 km braided belt where erosion hotspots *migrate*
rather than persist, and nothing beat predicting the average. That negative result
is preserved in `reports/DECISIONS.md` (D44, D62) and is the reason for the
switch — it is not part of the current analysis.

The Arial Khan is 300 m wide and single-threaded, so outer-bank erosion is
expected to persist. That expectation holds: a trained model beats the baseline
here, at correlation +0.517, where the braided reach gave +0.049.

Archived Jamuna data remains at `data/unused_data/jamuna/` and is reachable with
`RIVERGUARD_REACH=jamuna`, but it is no longer maintained.

---

## Data provenance

| data | source | how |
|---|---|---|
| Landsat 1989–2026 | USGS via Earth Engine | `gee/landsat_export_arial_khan.js` |
| Sentinel-2 2019–2026 | ESA via Earth Engine | `gee/s2_export_arial_khan.js` |
| GloFAS discharge 1989–2025 | Copernicus CEMS Early Warning Data Store | `ml/12_glofas_discharge.py` |

**Imagery is not in this repository.** All rasters (`*.tif`), plus `data/raw/` and
`data/unused_data/` where raw downloads and the archived earlier reach live, are
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
   right; direction was not. Everything on the active reach was rebuilt after the
   fix.
2. **The model is trained on 432 rows over 7 year-pairs.** That is the binding
   constraint on how much the 2.6% margin can be trusted. A longer record is the
   single highest-value improvement available.
3. **Water-detection thresholds carry over from the earlier reach** and are
   unverified on a 300 m river.
4. **Most geometry constants are unverified guesses** scaled for a narrow river,
   pending the longer record.
5. **No ground truth.** Confidence comes from two sensors agreeing and from
   literature plausibility, not from absolute accuracy.
6. **`backend/config/settings.py` uses Django's `django-insecure-` dev key.**
   Must be replaced by an environment variable before any deployment.