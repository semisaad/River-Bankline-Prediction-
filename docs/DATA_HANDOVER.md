# Data handover — for whoever downloads the imagery

This project needs two satellite datasets re-exported from Google Earth Engine.
The raw downloads were deleted and are being re-fetched by someone who may not
have been in the conversation.

**Read this before running anything.** Using the wrong script, or drawing a
different box, produces data that silently does not match everything already
computed. Nothing will error. The numbers will just quietly be wrong.

---

## What is needed

| dataset | years | script | destination |
|---|---|---|---|
| Sentinel-2 | 2019–2026 (8 files) | `gee/s2_export_arial_khan.js` | `data/reaches/arial_khan/raw/` |
| Landsat | 1989–2026 (~30 files) | `gee/landsat_export_arial_khan.js` | `data/reaches/arial_khan/raw/landsat/` |

Both files are in `gee/` in this repository. Nothing else in `gee/` should be
used — `landsat_export.js` and `landsat_export_ganges.js` are for other reaches
and produce data for the wrong place entirely.

---

## The study box — do not draw it

```
90.1927, 23.1638  →  90.2384, 23.2450
```

This is 4.7 × 9.0 km and it was **measured from the previous export's GeoTIFF**,
not typed in by hand. Both scripts carry it as `FALLBACK_BOX` and use it
automatically when nothing is drawn on the map.

**Just press Run. Do not draw a rectangle or polygon.**

Drawing is *permitted* — both scripts honour a drawn shape — but it must match
these numbers exactly. The Sentinel-2 and Landsat exports have to cover identical
ground, or the cross-sensor comparison measures the difference between two
exports rather than between two instruments.

### The one hard constraint

> **The box must stay SOUTH of 23.47°N.**

That is where the Arial Khan splits from the **Padma**. North of that line the
water body is the Padma — a completely different, much bigger river. An earlier
box reached 23.60°N and the preview came back mostly Padma
(`reports/DECISIONS.md` D51).

The current box's northern edge is 23.245°N, comfortably clear.

---

## How to run

1. Open **https://code.earthengine.google.com**
2. Open the script file, copy the whole thing, paste into the editor.
3. Press **Run**. Read the console table before exporting anything.

### Read this in the table

| field | expect |
|---|---|
| first line | `No shape drawn - using the fallback box` — correct |
| `valid` | **~99%** for Sentinel-2, **~70%** for Landsat |
| `water` | **5–10%** |
| `status` | `EXPORT` for most years |

Then open the **Tasks** tab, right-click → **Run**, about **5 at a time**.
Download the folders and drop the `.tif` files into the destinations above.
**No renaming needed** — filenames already match.

---

## Before you trust it

Open the map preview at the bottom of the script. You should see:

- **one** thin meandering ribbon, roughly 300 m wide
- **not** a wide braided belt — that would be the wrong river
- **not** a second river — that would be the Padma

If you see either of the wrong things, **stop and report it** rather than
exporting. There is no error in that case; the box is simply wrong.

---

## How to check it worked

From the project root:

```bash
cd ml
RIVERGUARD_REACH=arial_khan ../.venv/bin/python 09_checks.py
```

`09_checks.py` **section 7** verifies that the export scripts and `config.py`
agree on the box, and **section 8** verifies the two scripts still share
identical water-detection constants. Both must pass.

Then, to rebuild everything from the new imagery:

```bash
RIVERGUARD_REACH=arial_khan ../.venv/bin/python 01_prepare.py s2
RIVERGUARD_REACH=arial_khan ../.venv/bin/python 02_banklines.py s2
RIVERGUARD_REACH=arial_khan ../.venv/bin/python 04_erosion.py s2
RIVERGUARD_REACH=arial_khan ../.venv/bin/python 05_features.py s2
RIVERGUARD_REACH=arial_khan ../.venv/bin/python 14_model_train.py
RIVERGUARD_REACH=arial_khan ../.venv/bin/python 06_predict_geojson.py
```

Expected: **32 transects, 0 dropped**, median width 335–370 m. If that comes out
different, the imagery is not equivalent to what the model was trained on.

---

## Why the two scripts look almost identical

They run the **same water-detection logic on purpose**: same six bands, same
25th-percentile composite, same five indices at the same thresholds, same 20 m
morphological close, same ~92-hectare main-channel filter.

Sentinel-2 and Landsat overlap 2019–2026. If their rules differed, comparing them
across that overlap would measure the difference between two *scripts* rather
than between two *instruments*, producing a fabricated step in the river-width
record at 2019 (D59, D60).

**Do not "improve" one script independently.** The constants are guarded by
`09_checks.py` section 8, which will fail.

---

## What is already done, and must not need redoing

- Candidate model output: 62 transect-sides extended to 2036, marked
  experimental. The corrected chronological test gives MAE **3.175 m/yr**,
  worse than its training-median baseline (**2.507**).
- Outputs: `data/reaches/arial_khan/processed/predictions/`, `ml/artifacts/`

If the re-exported imagery reproduces the box and the scripts are unchanged,
the measurements can be rebuilt. The model must still pass time-forward tests
against simple baselines, and prediction skill must not be inferred from the
earlier 2.843 m/yr score: it used same-interval features and is withdrawn as
forecast evidence (D63).