# RiverGuard — notes for coding agents

Read `README.md` first. It has the headline finding, the quickstart, and the
known issues. This file covers conventions.

## The one rule that matters most

**Do not present an assumption as a finding.**

This project's goal is to predict future bankline positions. The current Arial
Khan model is experimental and does not beat the chronological training-median
baseline; do not describe its projected lines as validated forecasts. Every
number must be traceable to a script and every limitation written down.

If a change affects the numbers, the method, or a claim, append to
`reports/DECISIONS.md`. It is **append-only**: never edit an old entry to make it
look better. Supersede it with a new entry that says so.

## The project

**One river: the Arial Khan**, Madaripur Sadar – Kalkini reach, Bangladesh. The
expanded rectangle is fully processed for both sensors; nothing is waiting on an
export. The Jamuna is archived and the Ganges trial was never run — both have
been **removed from the reach registry** (D93), so `RIVERGUARD_REACH=jamuna`
fails fast instead of half-working.

The served model is **HistGradientBoostingRegressor** (D94), scored with only
prior-year features and an expanding time window: MAE **15.675 m/yr** versus
**20.413** for the strongest trivial baseline (2414 held-out records, 29 folds).
The RandomForest it replaced scores 15.886 on the identical test. **That pooled margin is
misleading on its own** — it is 18/18 folds in 1996–2015 and 2/11 in 2016–2026,
so the model does not beat the baseline in the recent regime that the projection
is drawn from (D92). Quote the split, never the pooled number alone.

Older figures are dead and must not be cited: **2.843 / 2.835** used same-interval
features (D63), and **3.175 / 2.507** describe the previous, smaller box.

## Orientation — read these before touching anything

| file | why |
|---|---|
| `context/CURRENT.md` | current state, the one blocking item, key numbers |
| `reports/DECISIONS.md` | why anything is the way it is. Read the entries your area touches. |
| `reports/VALIDATION.md` | what has actually been verified. **Generated** — edit `ml/07_validate.py`, not the report |
| `reports/MODEL_CHOICE.md` | why this model, by how much, and what the margin does not support |
| `reports/RISK.md` | the product and its uncertainty |
| `docs/HOW_IT_WORKS.md` | the measurement method |
| `docs/API.md` | every endpoint's real response shape, and the rules for the UI |

## Where the code is

- Project root: `/media/saad/HDD/riverguard` (`~/Projects/riverguard` is a symlink)
- **The HDD is not in `/etc/fstab`.** If paths vanish, check the mount first.
- Python: `.venv/bin/python` from the root, `../.venv/bin/python` from `ml/`
- Prediction path: `01_prepare` → `02_banklines` → `04_erosion` → `05_features` →
  `14_model_train` → `06_predict_geojson`, then `07_validate` for the report.
  `01b_prepare_landsat` → `04_erosion landsat` → `05_features landsat` builds the
  long record. `08_crosssensor` and `10_verify_geometry` write JSON that
  `07_validate` reads, so they must run first. `11_hydro_features` is optional and
  produced no gain (D90). `13_risk_and_forecast` is a separate Landsat-based
  historical-risk analysis, not the model-prediction step.

## Reach-agnostic by design

Every path and constant comes from `config.py`, selected by:

```bash
RIVERGUARD_REACH=arial_khan ../.venv/bin/python 04_erosion.py s2
```

Active reach: `arial_khan`, and **it is now the only reach in the registry**
(D93). The multi-reach regression discipline below existed because a fix aimed at
one reach twice silently changed the archived one (a build clamp that raised
transects from 58 to 70; a sign fix needing re-validation of both). That specific
hazard is gone, but the underlying one is not: `config.py` and `transects.py` are
shared by everything, so after changing either, re-run `04_erosion.py` and compare
some rates against the values in `context/CURRENT.md` before trusting anything
downstream.

## Standing checks

```bash
.venv/bin/python ml/09_checks.py            # run FIRST, always
```

Sections that have caught real bugs, so do not weaken them:

- **2** — Landsat band mapping. TM/ETM+ green is `SR_B2`; OLI green is `SR_B3`.
  A swap silently computes the wrong water index, in the wrong places
- **7** — export scripts must agree with `config.py` on bbox and CRS
- **7b** — the hydrology export must *cover* the study box. It went out carrying
  the retired Jamuna box, which did not overlap the reach at all (D88)
- **8** — the two Earth Engine export scripts must share identical
  water-detection constants, or the cross-sensor comparison measures the scripts
  instead of the sensors
- **9** — no stale pre-rewrite artefacts are being served
- **10** — the map's warning text must agree with `forecast_supported` in the
  payload it ships with. It did not, for months (D89)
- **11** — hydrology files are present, complete, and actually usable

**A check that has never been seen to fail is not known to work.** Section 8 was
verified by breaking a constant. Section 2 was verified by swapping a band list.
But note the counter-example: the first version of check 10 searched for
`"NOT beat"` while the real stale text said `"does not beat"`, so it **passed the
exact bug it was written to catch**. When you write a guard, test it against the
broken state, not just the fixed one.

## Hard-won constraints — do not rediscover these

| rule | why |
|---|---|
| Never chain `RIVERGUARD_REACH=x cmd && cmd2` | the variable is lost for the second command and it silently runs on the wrong reach |
| No bulk find-and-replace without reading the result | three times it silently no-matched or corrupted its target; every time only a follow-up check caught it |
| Editors that fail loudly beat scripts that silently do nothing | a `sed`/`.replace()` that does not match reports success |
| Landmask sampling must use the **measured** sensor's resolution | using the geometry sensor's resolution compressed Landsat casts to a third of their length and produced 3.3× wrong rates (D35) |
| Never resample Landsat to 10 m | the sensor has no 10 m detail; GEE would interpolate and invent it |
| Evaluate Earth Engine statistics with one synchronous `getInfo()` per batch | nested `.evaluate()` calls race, and reported 0% valid for years holding 15 scenes (D61) |
| Delete `__pycache__/` after restoring or rapidly re-editing a module | Python validates cached bytecode by comparing the source mtime **to the second**, so a restore landing in the same second as the edit it undoes leaves the stale `.pyc` looking valid — a guard check then runs the OLD logic and reports PASS for code that no longer exists |

## Sign conventions

- `target_rate`, `left_rate`, `right_rate`: **positive = land LOST = erosion**
- Transect `v` axis: `vmin` bank is negative side, `vmax` bank positive
- Eroding left bank moves toward **lower** v; right bank toward **higher** v

These were inverted once, project-wide (D58). Check them if you touch
`04_erosion.py`.

## Earth Engine exports need the owner's account

Two things cannot be automated here:

1. **Earth Engine exports** — imagery comes from scripts in `gee/`. The owner runs
   them at code.earthengine.google.com and drops `.tif` files into
   `data/reaches/<reach>/raw/<sensor>/`.
2. **Heavy model training** — planned for Colab, but the local dataset turned out
   small enough that `14_model_train.py` runs in about a minute. No Colab needed.

Do not try to fetch imagery from this machine; there is no reliable outbound
network.

## Before you commit

- Never commit imagery: `*.tif` is gitignored for a reason. 600 MB of GeoTIFF
  does not belong in history.
- Never commit secrets. `data/` holds no credentials; the old Copernicus token
  location (`~/.cdsapirc`) is no longer used by anything.
- Do not commit or push unless the owner explicitly asks.
- Update `context/CURRENT.md` and append to `reports/DECISIONS.md`.

## Communication

The owner is the sole developer and is learning this system as it is built.

- Plain language, no jargon. Define any unavoidable technical term in the same
  sentence, in everyday words.
- Explain **what** you changed and **why**. Never change something silently.
- Short answers by default; go long only when asked.
- Never inflate expectations. The project has one headline negative result and
  several unverified assumptions; say which is which.