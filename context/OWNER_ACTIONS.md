# OWNER ACTIONS

**Nothing is waiting on you right now.** All data is processed, all blocking
checks pass, and every remaining task is either development work or a decision
listed below.

---

## Decisions only you can make

### 1. How to state the recent-fold decay (D92) — most important

The model's pooled MAE (15.675) beats its strongest baseline (20.413) by 23%.
That advantage is **not spread over time**:

| test years | folds | beats its own baseline | mean gain |
|---|---:|---:|---:|
| 1996–2015 | 18 | 18/18 | +7.53 m/yr |
| 2016–2026 | 11 | 2/11 | −0.82 m/yr |

Your 2036 lines are extrapolated from the recent regime — the one where the
model loses to a trivial predictor. Three ways to say it:

- (a) pooled backtest as the headline, with the split shown as a caveat
- (b) recent-window backtest as the headline
- (c) withdraw `forecast_supported` and describe the output as an experimental
      extrapolation **← most defensible**

Nothing in the UI should state a forecast claim until this is chosen.

### 2. ~~RandomForest or gradient boosting (D91)~~ — settled

**Done, no action needed.** You said precision matters and even 1.3% counts as an
improvement, so the switch was made (D94). Gradient boosting now serves the map
at 15.675 vs the forest's 15.886. The forest is still reproducible as
`model_report_rf.json` if you want to show the comparison.

---

## Running the site

Two servers are needed. Django does **not** serve the frontend.

```
# backend
cd ~/Projects/riverguard/backend
../.venv/bin/python manage.py runserver 127.0.0.1:8010 --noreload

# frontend (second terminal)
cd ~/Projects/riverguard/frontend
npm run dev
```

Then open http://127.0.0.1:5173

---

## If you ever rebuild the pipeline

```
cd ~/Projects/riverguard/ml
RIVERGUARD_REACH=arial_khan ../.venv/bin/python 09_checks.py         # run FIRST
RIVERGUARD_REACH=arial_khan ../.venv/bin/python 01_prepare.py
RIVERGUARD_REACH=arial_khan ../.venv/bin/python 02_banklines.py
RIVERGUARD_REACH=arial_khan ../.venv/bin/python 04_erosion.py s2
RIVERGUARD_REACH=arial_khan ../.venv/bin/python 05_features.py s2
RIVERGUARD_REACH=arial_khan ../.venv/bin/python 01b_prepare_landsat.py
RIVERGUARD_REACH=arial_khan ../.venv/bin/python 04_erosion.py landsat
RIVERGUARD_REACH=arial_khan ../.venv/bin/python 05_features.py landsat
RIVERGUARD_REACH=arial_khan ../.venv/bin/python 08_crosssensor.py     # writes the JSON 07 reads
RIVERGUARD_REACH=arial_khan ../.venv/bin/python 14_model_train.py
RIVERGUARD_REACH=arial_khan ../.venv/bin/python 07_validate.py
RIVERGUARD_REACH=arial_khan ../.venv/bin/python 06_predict_geojson.py
RIVERGUARD_REACH=arial_khan ../.venv/bin/python 10_verify_geometry.py
RIVERGUARD_REACH=arial_khan ../.venv/bin/python 13_risk_and_forecast.py
```

`07_validate.py` reads what `08_crosssensor.py`, `10_verify_geometry.py` and
`14_model_train.py` wrote, so run those first or the report will say the inputs
are missing.

---

## If you ever need new imagery

`gee/hydro_export.js` — only if you want to revisit hydrology. It will not help
the model (D90); the header says so.

The two mask exporters are `gee/s2_export_arial_khan.js` and
`gee/landsat_export_arial_khan.js`. Draw the study rectangle exactly, confirm
the console prints the bounds you expect, and check the preview shows one river
and not the Padma.
