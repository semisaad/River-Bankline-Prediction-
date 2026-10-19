# CURRENT STATE

**Date:** 2026-10-19 · **Branch:** main, synchronized with origin/main at `4c45af3`.
Everything after that commit is **uncommitted working-tree changes**.

## THE PROJECT: Arial Khan (Madaripur Sadar – Kalkini, middle reach)

One river, one reach. The Jamuna is archived and out of scope; the Ganges trial
was never run. Both have been **removed from the reach registry** so no command
can silently run against a reach whose data is gone.

Study box `90.16808799423755, 23.134319063780836 → 90.26902488388599,
23.261491731177696`, worked in EPSG:32646. Sentinel-2 is 10 m, Landsat 30 m.

> **The northern edge must stay south of 23.47N**, the Padma bifurcation. North
> of that line the water body *is* the Padma. Enforced in both exporters and
> verified by `09_checks.py` check 8 and check 7b (hydrology).

## What exists now

Both sensors are fully processed for the selected box. Nothing is waiting on an
export.

| item | state |
|---|---|
| Sentinel-2 | 2019–2026, annual pairs, 520 feature rows |
| Landsat | 1989–2026, **37 usable years** (1997 missing), 5-year pairs, 2414 feature rows |
| Geometry | 63 transects built, **60 kept**, 15.8 km centreline, 250 m belt, **6/7** spot checks |
| Model | **HistGradientBoostingRegressor** (served), MAE **15.675 m/yr** on 29 expanding-window folds |
| Weakest baseline | median **20.413 m/yr**; also mean 20.723, repeat-previous 23.284 |
| Projection | 76 bank-sides to 2036, `status: experimental`, `is_forecast: false` |
| Risk | 96 records, 92 eligible for ranking, 4 flagged insufficient |
| Hydrology | 43 ERA5-Land years (1983–2025) present; **tested and it did not help** (D90) |
| Website | Django `:8010` + Vite `:5173`; 9 endpoints; headless test 0 errors |
| Guard checks | all blocking checks pass |

## The single most important thing to understand about the model

The pooled MAE of 15.675 against a 20.413 baseline looks like a solid 23% win.
**It is not evenly earned.**

| test years | folds | beats its own baseline | mean gain |
|---|---:|---:|---:|
| 1996–2015 | 18 | **18/18** | **+7.53 m/yr** |
| 2016–2026 | 11 | **2/11** | **−0.82 m/yr** |

The early folds have only 2–5 training years, so the training median is a poor
constant and large absolute errors inflate the pooled average. Once enough
history exists (2016 onward) the baseline is strong and the model stops beating
it. **The headline number overstates how well the recent regime is understood.**
See D92, and `reports/MODEL_CHOICE.md`.

The 2036 lines are extrapolations from the recent regime — the one where the
model does not beat a trivial predictor. They are marked experimental for this
reason.

## What was tested and rejected

| tried | result | decision |
|---|---|---|
| Real GloFAS discharge | within-transect correlation +0.049, i.e. noise. And at this reach the nearest cell models a local catchment (max 13 m³/s for a year), not the river | D88 — route abandoned, downloader and reader deleted |
| ERA5-Land hydrology | 15.886 → **16.562 (+0.676 worse)**. All 24 columns reach the model; strongest importance 1.2%, rain/runoff ≤0.5% | D90 — not in the model |
| RandomForest | 15.886, losing to GBM by 0.211 (1.3%); folds split 13/16 | D94 — superseded as the served model; kept as `model_report_rf.json` |

D82's claim that RF beat GBM was measured **before** `curv_outer` existed and is
superseded. D91 recorded the pair as tied and left the choice open; **D94 closed
it in favour of boosting**, on the grounds that the comparison is controlled and
a small reproducible out-of-sample margin is still a margin.

**What the switch does not fix.** The recent-fold decay above is unchanged — the
model is very slightly better on the metric and still not better in the regime
the projection is drawn from.

## Where the model still loses

Neither validation figure flatters the model, and both should be looked at
before quoting any MAE:

| held-out interval | horizon | model mean error | do-nothing mean error |
|---|---:|---:|---:|
| 2021 → 2026 | 5 yr | 50.6 m | **18.2 m** |
| 2023 → 2026 | 3 yr | 30.8 m | **13.8 m** |

`reports/validation_bankline_2026.png` and
`reports/validation_bankline_2026_from2023.png`. The reason is resolution, not
effort: 30 m pixels put a floor under what any pair can resolve, and many bank
sides genuinely move less than one pixel in 5 years. See `reports/LITERATURE.md`
section 4 for the published ~0.35-pixel detection limit.

## Key numbers

- Landsat median `|rate|` **11.2 m/yr** (one pixel over a 5-year pair = 6.0 m/yr)
- Sentinel-2 median `|rate|` **1.2 m/yr** (one pixel over an annual pair = 10.0 m/yr)
  — **an eighth of a pixel**, so S2's annual target is mostly quantisation. This
  is why the long record is built from Landsat 5-year pairs.
- Published migration for this river: **21 m/yr** (0.66 km over 1993–2024). Ours
  is roughly half that, and the report says so rather than claiming a match.
- Cross-sensor water maps: mean IoU **0.79**, area difference **−5.9%**
- Cross-sensor *rates*: **not available** — S2 uses 1-year pairs, Landsat 5-year,
  so no shared pair exists. A real gap; the Jamuna had this and it was the
  project's strongest evidence.
- 63% of Landsat bank-sides read exactly 0 over 2021→2026; all offsets are
  multiples of 30 m

## Hard-won constraints

- Never chain `RIVERGUARD_REACH=x cmd && cmd2` — the variable is lost for the
  second command and it silently runs on the wrong reach
- No bulk find-and-replace without reading the result
- Landmask sampling must use the **measured** sensor's resolution (D35)
- Never resample Landsat to 10 m — it invents detail the sensor never captured
- Keep `pkill` and the matching `setsid` start in **separate** commands; a
  bracketed pattern still matches if the same command line also contains the
  unbracketed string
- Delete `__pycache__/` after restoring a module, or a stale `.pyc` reports PASS
  using the old logic

## Do not

- Do not cite the withdrawn **+0.92** (D37).
- Do not quote **2.843** or **2.835** as forecast skill — same-interval features
  (D63). **3.175 / 2.507 are equally dead** — they describe the previous box.
- Do not call the 2036 geometry a validated forecast. It carries
  `is_forecast: false` and `status: experimental`.
- Do not present the pooled 22% as uniform skill; quote the 1996–2015 vs
  2016–2026 split (D92).
- Do not add hydrology back to the model without a new measurement (D90).
- Do not commit or push unless explicitly asked.
