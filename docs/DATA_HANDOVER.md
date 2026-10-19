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

Both files are in `gee/` in this repository, and they are now the **only** mask
exporters — the retired-reach and never-run trial scripts were deleted in D93,
because each carried a hardcoded box for a different river and would have
exported the wrong place while looking runnable.

---

## Selected larger rectangle

The selected bounds are:

```text
90.16808799423755, 23.134319063780836 → 90.26902488388599, 23.261491731177696
```

They are synchronized in both GEE scripts and `ml/config.py`.

> ### Draw NOTHING. Just press Run.
>
> The scripts carry these bounds as `REFERENCE_BOX` and **always** use them.
> Shapes on the map are ignored — the script prints a note if it sees any.
>
> This is deliberate. An earlier version required a drawn rectangle to match the
> bounds to within `1e-6` degrees (about 10 cm), which no hand-drawn shape can
> achieve, so it failed every time.
>
> **To change the study area**, edit the four numbers in `REFERENCE_BOX` in
> *both* export scripts and `bbox` / `bbox_landsat` in `ml/config.py`, then run
> `ml/09_checks.py` and confirm section 7 passes. Do not do it by drawing.

- The scripts print `EXPORT RECTANGLE [west, south, east, north]`. Confirm those
  numbers are the four above.
- Both scripts now **throw** if the northern edge reaches 23.47N, so the Padma
  cannot be exported even by a mistake in the bounds.

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
2. Open `gee/s2_export_arial_khan.js`, copy the whole file into the editor, and
   **leave the map empty** — do not draw anything. Clear old drawings if present.
3. Press **Run**. Confirm the console prints the four bounds above and that the
   water preview looks like the Arial Khan.
4. Run `ml/09_checks.py`; section 7 must pass before starting Tasks.
5. Open `gee/landsat_export_arial_khan.js`, leave the map empty again, and press
   **Run**. Confirm its printed bounds match Sentinel-2 exactly and inspect its
   preview.
6. Only after both previews and bounds are correct, open **Tasks** and start the
   exports. Earth Engine writes them to Google Drive; it does not download files
   directly to this computer.
7. Download and unzip the Drive folders:
   `riverguard_arial_khan_s2` for Sentinel-2 and `riverguard_arial_khan` for
   Landsat. Copy the `MNDWI_Mask_<year>.tif` files to the folders below.

### Read this in the table

| field | Sentinel-2 | Landsat |
|---|---|---|
| printed bounds | the four numbers above | must match Sentinel-2 exactly |
| `No shape drawn; using the synchronized REFERENCE_BOX.` | expected | expected |
| `scenes` | usable scenes that year | same |
| `status` | `QUEUED`, or `SKIP (too few scenes)` | same |

Start about **5 Tasks at a time** and do not rename files.

**The Run is quick by design.** The scene count for every year is fetched in a
single call, so the script returns in seconds. It no longer evaluates the
water/valid statistics year by year — that ran the whole detection chain once
per year, which froze the Code Editor and could exceed Earth Engine's memory
limit. Do not add it back.

> **Quality is verified after download, not before.** `ml/01_prepare.py` reports
> water area and `valid` coverage per year once the files are copied, measured on
> the actual GeoTIFFs rather than a server-side preview of them. That is the
> stronger check. If a year looks wrong there — no water, a wildly different
> area, or a `valid` below the gate — report it instead of feeding it to the
> pipeline.

**To spot-check a few years before exporting**, set `SURVEY = true` and narrow
`YEAR_FROM` / `YEAR_TO` to about four years near the top of either script. That
restores the `valid` and `water` columns for just those years. Keep the range
small; the freeze came from evaluating too many years at once.

**If Tasks come back empty**, set `YEAR_FROM` / `YEAR_TO` to export a slice and
run again. Each Run only creates Tasks for its own range, and Tasks already
created are unaffected.

---

## Before you trust it

Open the map preview at the bottom of the script. The box now covers a **longer
stretch** of the river than before, so expect a longer ribbon, not a wider one.
You should see:

- **one** meandering ribbon, roughly 300 m wide, running through the box
- **not** a wider belt — the river does not get broader downstream
- **not** a second, larger river — that would be the Padma

If you see either of the wrong things, **stop and report it** rather than
exporting. There is no error in that case; the bounds would simply be wrong.

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

The expanded reach is now fully built: **60 transects kept of 63**, 15.8 km
centreline, **6/7** manual spot checks pass. The old 32-transect figures describe
the previous, smaller box and no longer apply. After a rebuild, inspect the masks
and transects before training, then re-evaluate — more river coverage does not
automatically improve forecast skill.

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

- Served model output: **76 transect-sides** extended to 2036, marked
  experimental. Gradient boosting (D94) gives MAE **15.675 m/yr** against a
  strongest-baseline **20.413** — but that margin is 18/18 folds in 1996–2015 and
  **2/11** in 2016–2026 (D92). The projection is drawn from the recent regime.
  The model also loses to a plain "the bank never moved" baseline for absolute
  bank position; both validation figures show this.
- Outputs: `data/reaches/arial_khan/processed/predictions/`, `ml/artifacts/`

The 2.843 and 3.175 scores are both dead: 2.843 used same-interval features (D63)
and 3.175 describes the previous, smaller box. Do not cite either. The rebuilt
reach has new measurements and a new time-forward evaluation against simple
baselines. Do not infer that more river coverage automatically improves forecast
skill — the recent-fold split is the evidence that it did not.