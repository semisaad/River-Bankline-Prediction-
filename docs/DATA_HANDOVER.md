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

## Selected larger rectangle

The selected bounds are:

```text
90.16808799423755, 23.134319063780836 → 90.26902488388599, 23.261491731177696
```

They are synchronized in both GEE scripts and `ml/config.py`. Draw this exact
rectangle for both sensors; do not approximate or change its extent.

- Extend along the Arial Khan to capture more of the river, rather than widening
  across unrelated floodplain water.
- Keep the northern edge south of **23.47°N** and exclude the Padma. If the
  preview contains another river or the Padma, stop and redraw.
- Clear old drawings and leave exactly one rectangle. Both scripts now refuse to
  export when a drawing is missing or multiple drawings remain.
- The scripts print `DRAWN RECTANGLE [west, south, east, north]`. Record these
  exact numbers; Landsat's printed bounds must match Sentinel-2 exactly.

The S2 script prints the selected bounds. Verify them against the box above;
Landsat's printed bounds must match. The wider area changes transect placement
and counts, so review the geometry settings and validate new transects before
training. The old 32-transect geometry and old evaluation scores do not apply.

### The one hard constraint

> **The box must stay SOUTH of 23.47°N.**

That is where the Arial Khan splits from the **Padma**. North of that line the
water body is the Padma — a completely different, much bigger river. An earlier
box reached 23.60°N and the preview came back mostly Padma
(`reports/DECISIONS.md` D51).

The selected box's northern edge is 23.26149°N, south of the Padma limit.

---

## How to run

1. Open **https://code.earthengine.google.com** and sign in to the project
  owner's Earth Engine account.
2. Open `gee/s2_export_arial_khan.js`, clear old drawings, and draw the selected
  rectangle above.
3. Press **Run**. Confirm the printed coordinates match the selected bounds and
  inspect the water preview.
4. Run `ml/09_checks.py`; section 7 must pass before starting Tasks. Review
  transect geometry settings for the longer reach before processing.
5. Open `gee/landsat_export_arial_khan.js`, clear old drawings, draw the same
  rectangle, and press **Run**. Confirm its printed bounds match S2 exactly and
  inspect its preview.
6. Only after both previews and bounds are correct, open **Tasks** and start the
  exports. Earth Engine writes them to Google Drive; it does not download files
  directly to this computer.
7. Download and unzip the Drive folders:
  `riverguard_arial_khan_s2` for Sentinel-2 and `riverguard_arial_khan` for
  Landsat. Copy the `MNDWI_Mask_<year>.tif` files to the folders below.

### Read this in the table

| field | Sentinel-2 | Landsat |
|---|---|---|
| drawn geometry | record printed bounds | must match Sentinel-2 exactly |
| `valid` | at least **90%** | at least **70%** (scan-line gaps are expected) |
| `water` | must pass the script's quality gate | must pass the script's quality gate |
| `status` | `EXPORT` for usable years | `EXPORT` for usable years |

Start about **5 Tasks at a time**. Some Landsat years may be skipped by the
quality gates; keep the console output and do not rename files.

---

## Before you trust it

Open the map preview at the bottom of the script. You should see:

- **one** thin meandering ribbon, roughly 300 m wide
- **not** a wide braided belt — that would be the wrong river
- **not** a second river — that would be the Padma

If you see either of the wrong things, **stop and report it** rather than
exporting. There is no error in that case; the box is simply wrong.

---

## Copy exports and run the project

After extracting both Google Drive downloads under `~/Downloads/`, run these
from the repository root. Confirm the files were exported over the same bounds
now recorded in `ml/config.py` and both GEE scripts.

```bash
mkdir -p data/reaches/arial_khan/raw/landsat
cp ~/Downloads/riverguard_arial_khan_s2/MNDWI_Mask_*.tif data/reaches/arial_khan/raw/
cp ~/Downloads/riverguard_arial_khan/MNDWI_Mask_*.tif data/reaches/arial_khan/raw/landsat/
export RIVERGUARD_REACH=arial_khan
.venv/bin/python ml/09_checks.py
```

Section 7 checks the box and CRS; section 8 checks that the two scripts share
the same water-detection rules. Both must pass before processing.

### Train and create the current experimental projection

The current trainer uses **Sentinel-2 features only**. Landsat is prepared
separately for the longer historical record and cross-sensor checks; the current
model does not combine the two sensors.

```bash
.venv/bin/python ml/01_prepare.py
.venv/bin/python ml/02_banklines.py
.venv/bin/python ml/04_erosion.py s2
.venv/bin/python ml/05_features.py s2
.venv/bin/python ml/14_model_train.py --horizon 10
.venv/bin/python ml/06_predict_geojson.py --horizon 10
```

This trains and evaluates the candidate, then draws its 10-year extension.
It does **not** make that extension a validated forecast: the current model
loses to its historical-median baseline, so inspect `ml/artifacts/model_report.json`.

### Process Landsat for additional history and validation

```bash
.venv/bin/python ml/01b_prepare_landsat.py
.venv/bin/python ml/04_erosion.py landsat
.venv/bin/python ml/05_features.py landsat
.venv/bin/python ml/08_crosssensor.py
.venv/bin/python ml/13_risk_and_forecast.py
```

The expanded reach will have a different transect count and width summary; do
not expect the old **32 transects**. Inspect the masks and new transects before
training. All previous model scores and projected lines apply only to the old
extent; retrain and re-evaluate from the rebuilt features.

---

## Why the two scripts look almost identical

They run the **same water-detection logic on purpose**: same six bands, same
25th-percentile composite, same five indices at the same thresholds, same 20 m
morphological close, and same nominal ~90-hectare filter (connected at 60 m).
The coarser filter reduces memory for the expanded AOI but can change small edge
details. Inspect both previews, especially narrow meanders and tips, before
starting Tasks.

Sentinel-2 and Landsat overlap 2019–2026. If their rules differed, comparing them
across that overlap would measure the difference between two *scripts* rather
than between two *instruments*, producing a fabricated step in the river-width
record at 2019 (D59, D60).

**Do not "improve" one script independently.** The constants are guarded by
`09_checks.py` section 8, which will fail.

---

## Existing outputs apply only to the previous extent

- Candidate model output: 62 transect-sides extended to 2036, marked
  experimental. The corrected chronological test gives MAE **3.175 m/yr**,
  worse than its training-median baseline (**2.507**).
- Outputs: `data/reaches/arial_khan/processed/predictions/`, `ml/artifacts/`

The listed files and the current 3.175 m/yr time-forward score describe the
previous box only. The earlier 2.843 m/yr score used same-interval features and
is withdrawn as forecast evidence (D63). The expanded area needs new measurements
and a new time-forward evaluation against simple baselines; do not infer that
more river coverage automatically improves forecast skill.