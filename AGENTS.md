# RiverGuard — notes for coding agents

Read `README.md` first. It has the headline finding, the quickstart, and the
known issues. This file covers conventions.

## The one rule that matters most

**Do not present an assumption as a finding.**

This project's central result is negative — year-to-year bank erosion could not
be predicted, and nothing beat "predict the average". That result is only
credible because every number is traceable to a script and every limitation is
written down. Adding an unsupported claim destroys the whole thing.

If a change affects the numbers, the method, or a claim, append to
`reports/DECISIONS.md`. It is **append-only**: never edit an old entry to make it
look better. Supersede it with a new entry that says so.

## Orientation — read these before touching anything

| file | why |
|---|---|
| `context/CURRENT.md` | current state, the one blocking item, key numbers |
| `reports/DECISIONS.md` | why anything is the way it is. 60 entries. Read the ones your area touches. |
| `reports/VALIDATION.md` | what has actually been verified |
| `reports/RISK.md` | the product and its uncertainty |
| `docs/HOW_IT_WORKS.md` | the measurement method |

## Where the code is

- Project root: `/media/saad/HDD/riverguard` (`~/Projects/riverguard` is a symlink)
- **The HDD is not in `/etc/fstab`.** If paths vanish, check the mount first.
- Python: `.venv/bin/python` from the root, `../.venv/bin/python` from `ml/`
- Pipeline runs in numeric order: `01_prepare` → `02_banklines` → `04_erosion` →
  `05_features` → `13_risk_and_forecast` → `06_predict_geojson` →
  `07_validate` → `08_crosssensor`

## Reach-agnostic by design

Every path and constant comes from `config.py`, selected by:

```bash
RIVERGUARD_REACH=arial_khan ../.venv/bin/python 04_erosion.py s2
```

Reaches: `jamuna` (archived), `ganges` (no data), `arial_khan` (active).

**A change meant for one reach must not alter the others.** Two times now a fix
targeted at `arial_khan` silently changed `jamuna` (a build clamp that raised
transects from 58 to 70; a sign fix that needed re-validating both). After any
change to `transects.py` or `config.py`, re-run both reaches and compare against
the known values — see the regression commands in `docs/HOW_IT_WORKS.md`.

## Standing checks

```bash
.venv/bin/python ml/09_checks.py            # run FIRST, always
```

Sections that have caught real bugs, so do not weaken them:

- **7** — export scripts must agree with `config.py` on bbox and CRS
- **8** — the two Earth Engine export scripts must share identical
  water-detection constants, or the cross-sensor comparison measures the scripts
  instead of the sensors
- **9** — no stale pre-rewrite artefacts are being served

A check that has never been seen to fail is not known to work. Section 8 was
verified by deliberately breaking a constant and watching it fail.

## Hard-won constraints — do not rediscover these

| rule | why |
|---|---|
| Never chain `RIVERGUARD_REACH=x cmd && cmd2` | the variable is lost for the second command and it silently runs on the wrong reach |
| No bulk find-and-replace without reading the result | three times it silently no-matched or corrupted its target; every time only a follow-up check caught it |
| Editers that fail loudly beat scripts that silently do nothing | a `sed`/`.replace()` that does not match reports success |
| Landmask sampling must use the **measured** sensor's resolution | using the geometry sensor's resolution compressed Landsat casts to a third of their length and produced 3.3× wrong rates (D35) |
| Never resample Landsat to 10 m | the sensor has no 10 m detail; GEE would interpolate and invent it |
| Evaluate Earth Engine statistics with one synchronous `getInfo()` per batch | nested `.evaluate()` calls race, and reported 0% valid for years holding 15 scenes (D61) |

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
2. **Copernicus GloFAS** — needs `~/.cdsapirc`, outside the repo.

Do not try to fetch imagery from this machine; there is no reliable outbound
network.

## Before you commit

- Never commit imagery: `*.tif` is gitignored for a reason. 600 MB of GeoTIFF
  does not belong in history.
- Never commit secrets. The token is in `~/.cdsapirc`.
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