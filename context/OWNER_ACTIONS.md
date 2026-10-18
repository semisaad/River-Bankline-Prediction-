# OWNER ACTIONS

## Coordinate the re-download

The raw Sentinel-2 and Landsat exports were deleted on 2026-10-18 and are being
re-fetched by a third party.

**Hand them `docs/DATA_HANDOVER.md`.** It is written for someone with no access to
this conversation and covers:

- which script to use, and which four to ignore
- the exact box, and why it must not be drawn by hand
- what the Earth Engine console table should say
- how to verify the download reproduces the processed measurement inputs

**The two things most likely to go wrong, both of which fail silently:**

1. **Using an older script.** Earlier versions used a blob threshold of 300
   against Sentinel-2's 1000, which keeps ponds the other sensor removes — Landsat
   would then measure a systematically wider river (D60).
2. **Drawing a different box.** Sentinel-2 and Landsat must cover identical
   ground or the cross-sensor comparison measures the scripts rather than the
   instruments (D59).

---

## What is available

The raw `.tif` downloads are gone, but **everything derived from them survived**:

| | |
|---|---|
| Candidate output | 62 transect-sides extended to 2036, labelled experimental |
| Processed masks, features, EPR | intact |
| Geometry | 32 transects, 0 dropped, median width 350 m |

`14_model_train.py` now evaluates only prior-year features using an expanding
time window. Its candidate MAE is **3.175 m/yr**, worse than the training-median
baseline (**2.507**). The 10-year overlay is a development output, not a
validated future bankline. D63 records why the old 2.843 score is withdrawn as
forecast evidence.

---

## Archived Jamuna result

Do not lose this. It is in `reports/RISK.md`, `reports/VALIDATION.md` and
`reports/DECISIONS.md`: 37 years of imagery plus real river discharge, and on the
**Jamuna** year-to-year erosion still could not be predicted (correlation +0.049,
nothing beat the average).

The Jamuna result is historical context only. It does not establish prediction
skill on the active Arial Khan reach.

---

## Running the site

```
# backend
cd ~/Projects/riverguard/backend
../.venv/bin/python manage.py runserver 8010 --noreload

# frontend (second terminal)
cd ~/Projects/riverguard/frontend
npm run dev
```

Then open http://127.0.0.1:5173

---

## Full rebuild after imagery returns

```
cd ~/Projects/riverguard/ml
RIVERGUARD_REACH=arial_khan ../.venv/bin/python 09_checks.py    # run FIRST
RIVERGUARD_REACH=arial_khan ../.venv/bin/python 01_prepare.py s2
RIVERGUARD_REACH=arial_khan ../.venv/bin/python 02_banklines.py s2
RIVERGUARD_REACH=arial_khan ../.venv/bin/python 04_erosion.py s2
RIVERGUARD_REACH=arial_khan ../.venv/bin/python 05_features.py s2
RIVERGUARD_REACH=arial_khan ../.venv/bin/python 14_model_train.py
RIVERGUARD_REACH=arial_khan ../.venv/bin/python 06_predict_geojson.py
RIVERGUARD_REACH=arial_khan ../.venv/bin/python 07_validate.py
RIVERGUARD_REACH=arial_khan ../.venv/bin/python 08_crosssensor.py
```

**Expected: 32 transects, 0 dropped, median width 335–370 m.** Anything different
means the imagery is not equivalent and the model needs retraining.