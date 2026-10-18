# OWNER ACTIONS

## Export the selected larger rectangle

The larger bounds have been selected and synchronized in both GEE scripts and
`ml/config.py`:

`90.16808799423755, 23.134319063780836, 90.26902488388599, 23.261491731177696`

Follow `docs/DATA_HANDOVER.md`. The GEE scripts now require one drawn rectangle
and print its exact bounds. Before starting export Tasks:

1. Draw this same rectangle in both scripts and verify the printed bounds.
2. Confirm the previews contain the Arial Khan only, with no Padma.
3. Run `09_checks.py`; then export/download the masks and rebuild all products.

**The two things most likely to go wrong, both of which fail silently:**

1. **Using an older script.** Earlier versions used a blob threshold of 300
   against Sentinel-2's 1000, which keeps ponds the other sensor removes — Landsat
   would then measure a systematically wider river (D60).
2. **Different sensor extents.** Sentinel-2 and Landsat must cover identical
   ground or the cross-sensor comparison measures the scripts rather than the
   instruments (D59).

---

## What is available

The raw `.tif` downloads are gone. The files below survive for the previous box
only and must be rebuilt for the expanded area:

| | |
|---|---|
| Candidate output | 62 transect-sides extended to 2036, labelled experimental |
| Processed masks, features, EPR | intact |
| Previous-box geometry | 32 transects, 0 dropped, median width 350 m |

`14_model_train.py` now evaluates only prior-year features using an expanding
time window. Its candidate MAE is **3.175 m/yr**, worse than the training-median
baseline (**2.507**) on the previous box. The 10-year overlay is experimental,
not a validated future bankline. D63 withdraws the old 2.843 score as forecast
evidence; D65 records that none of these results transfer automatically to the
larger extent.

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
RIVERGUARD_REACH=arial_khan ../.venv/bin/python 01_prepare.py
RIVERGUARD_REACH=arial_khan ../.venv/bin/python 02_banklines.py
RIVERGUARD_REACH=arial_khan ../.venv/bin/python 04_erosion.py s2
RIVERGUARD_REACH=arial_khan ../.venv/bin/python 05_features.py s2
RIVERGUARD_REACH=arial_khan ../.venv/bin/python 14_model_train.py
RIVERGUARD_REACH=arial_khan ../.venv/bin/python 06_predict_geojson.py
RIVERGUARD_REACH=arial_khan ../.venv/bin/python 01b_prepare_landsat.py
RIVERGUARD_REACH=arial_khan ../.venv/bin/python 04_erosion.py landsat
RIVERGUARD_REACH=arial_khan ../.venv/bin/python 05_features.py landsat
RIVERGUARD_REACH=arial_khan ../.venv/bin/python 08_crosssensor.py
```

The expanded transect count and width have not been measured yet. Inspect the
new geometry and masks before trusting model results; the model must be retrained
and re-evaluated on the expanded features.