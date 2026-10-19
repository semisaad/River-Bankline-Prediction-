# RiverGuard

RiverGuard is a research prototype that measures how a riverbank has moved from
satellite observations and estimates where it may move next. Its study site is
the **Arial Khan**, Madaripur Sadar–Kalkini reach, Bangladesh.

The measurement side works: two independent instruments largely agree on the
water, and the geometry has been checked by hand. The **prediction** side is
where the project is honest about its limits — see below.

---

## Goal and current evidence

The goal is to say where each bank may move over a stated horizon, show the
uncertainty, and tell the user when the data does not support a useful answer.
A model that only reproduces the average is not a forecasting system.

The measurement uses Landsat (30 m, 1989–2026) in 5-year pairs and Sentinel-2
(10 m, 2019–2026) annually. The model is a gradient-boosted tree ensemble
(`HistGradientBoostingRegressor`) trained on prior-year features only and scored
with an **expanding time window**: each target year is predicted from earlier
years alone, so nothing from the interval being predicted can leak in.

| method | MAE (m/yr) |
|---|---:|
| gradient-boosted trees (served model) | **15.675** |
| RandomForest (retained for comparison) | 15.886 |
| training-median baseline (the bar) | 20.413 |
| training-mean baseline | 20.723 |
| repeat the previous pair | 23.284 |

Gradient boosting leads the forest by 0.211 m/yr — **1.3%**. That is small, and
it is reported as small; but the comparison is controlled (same folds, same rows,
same features, both seeded), so the better-scoring model is the one that ships.
Recorded as **D94**.

**That 22% margin is not spread evenly over time, and this is the most important
caveat in the project:**

| test years | folds | beats its own baseline | mean gain |
|---|---:|---:|---:|
| 1996–2015 | 18 | 18/18 | +7.53 m/yr |
| 2016–2026 | 11 | 2/11 | −0.82 m/yr |

The early folds have only a few training years, so the baseline is weak and the
model wins easily. From 2016 the baseline is strong and the model stops beating
it. The 2036 lines are extrapolated from **that** recent regime, which is why the
map labels them `experimental` and carries `is_forecast: false`.

**The prediction system is not validated.** See D92 in `reports/DECISIONS.md`
and `reports/MODEL_CHOICE.md`.

### What was tried and did not work

- **Real river discharge (GloFAS).** At this reach the nearest cell reads a
  maximum of 13 m³/s for a whole year — a 5 km grid cannot see a 300 m
  distributary, so it models a small local catchment instead. Recorded as D88.
- **ERA5-Land weather over the reach.** It made the model slightly *worse*
  (15.886 → 16.562). Every column reached the forest; the strongest earned 1.2%
  importance. Recorded as D90.
- **RandomForest.** The previous served model. Scored 15.886, losing to gradient
  boosting by 0.211 m/yr with the folds split 13/16. Kept in the tree because it
  reproduces on demand, but no longer the one the map draws. Recorded as D91
  (comparison) and D94 (the switch).

### What the model does *not* do

It does **not** beat simply assuming the bank stayed where it was. For absolute
bank position the do-nothing baseline wins, and both validation figures say so
on their face:

| held-out interval | horizon | model mean error | do-nothing mean error |
|---|---:|---:|---:|
| 2021 → 2026 | 5 yr | 50.6 m | **18.2 m** |
| 2023 → 2026 | 3 yr | 30.8 m | **13.8 m** |

That is not a bug and it is not being hidden. A 30 m Landsat pixel over a 5-year
pair is worth 6 m/yr of apparent movement, and many bank sides genuinely do not
move a whole pixel in that time — so for more than half of them, "no movement" is
not an assumption, it is the measurement. The published minimum detectable change
from 30 m imagery is about 0.35 of a pixel, which puts the model's error in the
same range as the noise of its own target. See `reports/LITERATURE.md` section 4.

**Useful with more data.** A learning-curve experiment shows the model improving
steadily as training years are added (MAE 29.75 trained through 1999 → 11.02
through 2023), and a count-matched test shows the gain comes from **recency, not
quantity** — the newest 8 pairs beat the oldest 16 at equal-or-better error.

The archived Jamuna reach, where 37 years of imagery and real discharge still
could not predict erosion, is the negative result that motivated the move to a
narrower single-thread river. It is preserved in `reports/VALIDATION.md` PART B.

Everything numeric is reproducible from a script. No assumption or experimental
output is described as a finding.

---

## Quickstart

```bash
cd ~/Projects/riverguard

# 1. Select the active reach and run guard checks (always do this first)
RIVERGUARD_REACH=arial_khan .venv/bin/python ml/09_checks.py

# 2. Build the measurement, then the model
cd ml
RIVERGUARD_REACH=arial_khan ../.venv/bin/python 01_prepare.py
RIVERGUARD_REACH=arial_khan ../.venv/bin/python 02_banklines.py
RIVERGUARD_REACH=arial_khan ../.venv/bin/python 04_erosion.py s2
RIVERGUARD_REACH=arial_khan ../.venv/bin/python 05_features.py s2
RIVERGUARD_REACH=arial_khan ../.venv/bin/python 01b_prepare_landsat.py
RIVERGUARD_REACH=arial_khan ../.venv/bin/python 04_erosion.py landsat
RIVERGUARD_REACH=arial_khan ../.venv/bin/python 05_features.py landsat
RIVERGUARD_REACH=arial_khan ../.venv/bin/python 08_crosssensor.py
RIVERGUARD_REACH=arial_khan ../.venv/bin/python 14_model_train.py
RIVERGUARD_REACH=arial_khan ../.venv/bin/python 07_validate.py
RIVERGUARD_REACH=arial_khan ../.venv/bin/python 06_predict_geojson.py
RIVERGUARD_REACH=arial_khan ../.venv/bin/python 10_verify_geometry.py
RIVERGUARD_REACH=arial_khan ../.venv/bin/python 13_risk_and_forecast.py
```

The masked rasters are not in this repository, so a full rebuild needs the Earth
Engine exports first — see `docs/DATA_HANDOVER.md`.

### Run the website

Two servers. Django does **not** serve the frontend.

```bash
cd ~/Projects/riverguard/backend
../.venv/bin/python manage.py runserver 127.0.0.1:8010 --noreload

# second terminal
cd ~/Projects/riverguard/frontend
npm run dev          # http://127.0.0.1:5173
```

---

## Active study

One reach: the **Arial Khan**, middle reach. The Jamuna is archived and the
Ganges trial was never run; both have been removed from the reach registry so no
command can silently run against a reach whose data is gone.

Study rectangle
`90.16808799423755, 23.134319063780836 → 90.26902488388599, 23.261491731177696`,
worked in EPSG:32646.

> The north edge must stay south of **23.47N**. Beyond that line the water body
> is the Padma, a different and much larger river. A box that crossed it would
> silently measure the Padma instead. Enforced in both exporters, and verified by
> standing checks.

| item | state |
|---|---|
| Sentinel-2 | 2019–2026, annual pairs, 520 feature rows |
| Landsat | 1989–2026, 37 usable years (1997 missing), 5-year pairs, 2414 feature rows |
| Geometry | 63 transects built, 60 kept, 15.8 km centreline, 250 m belt, 6/7 spot checks |
| Served model | MAE 15.675 vs 20.413 baseline (see the time split above) |
| Projection | 74 bank-sides to 2036, experimental, `is_forecast: false` |
| Chronic risk | 96 records, 92 eligible for ranking, 4 flagged insufficient |
| Independent ground truth | None |

---

## Data provenance

| data | source | script |
|---|---|---|
| Sentinel-2 masks, 2019–2026 | ESA via Earth Engine | `gee/s2_export_arial_khan.js` |
| Landsat masks, 1989–2026 | USGS via Earth Engine | `gee/landsat_export_arial_khan.js` |
| ERA5-Land weather over the reach | ECMWF via Earth Engine | `gee/hydro_export.js` |
| Real discharge | — | tested and rejected, D88 |

**Imagery is not in this repository.** Rasters (`*.tif`, `*.tiff`) and per-reach
raw download folders under `data/reaches/<reach>/raw/` are gitignored. The small
CSV and GeoJSON evidence tables that back the reports *are* committed.

Both mask exporters share **identical water-detection logic**. They have to: they
overlap 2019–2026, and if their rules differed the cross-sensor comparison would
measure the difference between two scripts rather than between two instruments.
A standing check enforces this.

---

## Repository layout

```
ml/          measurement pipeline, numbered in run order
gee/         Earth Engine export scripts (data acquisition, needs your account)
backend/     Django read-only API over the processed outputs
frontend/    React + MapLibre map
reports/     DECISIONS.md, VALIDATION.md, RISK*.md, MODEL_CHOICE.md - the evidence
context/     CURRENT, DONE, TODO, OWNER_ACTIONS - working state
docs/        HOW_IT_WORKS.md (method), DATA_HANDOVER.md (rebuild instructions)
```

---

## Documentation

| file | what it is |
|---|---|
| `reports/DECISIONS.md` | **the decision dictionary.** Append-only record of choices, evidence, and corrections. |
| `reports/MODEL_CHOICE.md` | Why this model, by how much, and what the margin does not support |
| `reports/VALIDATION.md` | Generated by `ml/07_validate.py`. PART A is current and regenerable; PART B is frozen Jamuna history. |
| `reports/RISK.md`, `reports/RISK_arial_khan.md` | Chronic-risk analysis and its limitations |
| `docs/HOW_IT_WORKS.md` | The measurement method end to end |
| `context/CURRENT.md` | Current state and what is undecided |
| `AGENTS.md` | Conventions for coding agents working on this repo |

---

## Known issues, stated plainly

1. **The model's advantage is concentrated in 1996–2015** and disappears in
   2016–2026. The projection is drawn from the recent regime. This is the
   project's central open question (D92).
2. **Sentinel-2's annual target is mostly quantisation.** Its median movement of
   1.2 m/yr is an eighth of one 10 m pixel. The long record is therefore built
   from Landsat's 5-year pairs, where a pixel is worth 6 m/yr.
3. **Landsat's median rate (11.2 m/yr) is about half** the published 21 m/yr for
   this river. Not explained; stated rather than smoothed over.
4. **The rate-level cross-sensor test cannot be run here.** Sentinel-2 uses
   1-year pairs and Landsat 5-year, so no shared pair exists. On the Jamuna this
   was the project's strongest evidence; on this reach it is simply absent.
5. **No ground truth.** Confidence rests on two instruments agreeing and on
   literature plausibility, not on surveyed banklines.
6. **EPR signs were inverted project-wide** until D58. Magnitudes were always
   right; direction was not. Everything on the active reach was rebuilt.
7. **`backend/config/settings.py` uses Django's `django-insecure-` dev key.**
   Must be replaced by an environment variable before any deployment.
