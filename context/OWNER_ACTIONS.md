# WHAT SAAD NEEDS TO DO (2 things)

## ACTION 0 — Push the repository *(do this first, ~1 minute)*

The imagery re-download is being done by someone else, and they need the export
scripts from GitHub. **Four commits are still only on this machine** — including
the reopened forecast model, which is the project's headline result.

```
! gh auth login --hostname github.com --git-protocol https --web
```

Then tell me **"logged in"** and I will push immediately.

---

## ACTION 1 — Coordinate the re-download

The raw Sentinel-2 and Landsat exports were deleted on 2026-10-18 and are being
re-fetched by a third party.

**Hand them `docs/DATA_HANDOVER.md`.** It is written for someone with no access to
this conversation and covers:

- which script to use, and which four to ignore
- the exact box, and why it must not be drawn by hand
- what the Earth Engine console table should say
- how to verify the download is equivalent to what the model was trained on

**The two things most likely to go wrong, both of which fail silently:**

1. **Using an older script.** Earlier versions used a blob threshold of 300
   against Sentinel-2's 1000, which keeps ponds the other sensor removes — Landsat
   would then measure a systematically wider river (D60).
2. **Drawing a different box.** Sentinel-2 and Landsat must cover identical
   ground or the cross-sensor comparison measures the scripts rather than the
   instruments (D59).

---

## What is safe — nothing needs redoing

The raw `.tif` downloads are gone, but **everything derived from them survived**:

| | |
|---|---|
| Trained model | RandomForest, MAE **2.843** vs 2.919 baseline, r **+0.517** |
| Predictions | 62 transect-sides projected to 2036 |
| Processed masks, features, EPR | intact |
| Geometry | 32 transects, 0 dropped, median width 350 m |

`14_model_train.py` still runs and still returns MAE 2.843 from the processed
data. So there is **no rush** — but the model rests on 432 rows over 7 year-pairs,
and the Landsat 5-year-block record is what would make it defensible.

---

## The Jamuna result stands

Do not lose this. It is in `reports/RISK.md`, `reports/VALIDATION.md` and
`reports/DECISIONS.md`: 37 years of imagery plus real river discharge, and on the
**Jamuna** year-to-year erosion still could not be predicted (correlation +0.049,
nothing beat the average).

On the **Arial Khan** it does work — correlation +0.517, and a trained model
beats the baseline. That contrast is the project's scientific contribution, and
it is why the study moved rivers (D62).

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