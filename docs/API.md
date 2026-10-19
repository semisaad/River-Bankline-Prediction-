# RiverGuard API reference

Base URL: `http://127.0.0.1:8010/api/`

The frontend runs on Vite at `http://127.0.0.1:5173` and **proxies `/api` to
:8010**, so frontend code can call `/api/...` directly with no CORS setup.

Two servers are required. **Django does not serve the frontend.** If the page
loads but every panel is empty, Django is usually the one that is down.

All responses are JSON. Everything below was captured from the running server,
not written from memory. Field counts and example values are real.

---

## Before you build anything: three rules

**1. Never hardcode wording about the forecast.** Read it from the payload.
`/api/predictions/` carries `forecast_supported`, `is_forecast`,
`projection_status`, `horizon_validated`, `warning` and the model scores. The
project's own history says to follow them: a hand-typed sentence in the map
metadata once survived the model improving and shipped a claim contradicting the
numbers beside it (D89). If the UI retypes a claim, the same thing happens.

**2. `forecast_supported: true` is NOT a licence to say "forecast".** It compares
the one-year rate model against trivial baselines *pooled over 29 folds*. That
advantage is **18/18 folds in 1996–2015 and 2/11 in 2016–2026** (D92), and the
projection is extrapolated from the recent regime. `is_forecast` is `false` and
must stay visibly false in the UI until the owner settles D92.

**3. Two sensors, two different jobs — do not blend them silently.** The
banklines, erosion and risk layers are **Sentinel-2 (10 m, 2019–2026)**. The
model and its projection are **Landsat (30 m, 1989–2026)**. Drawing both without
labelling invents a step change in the river at 2019 — the D59/D60 error.

---

## `GET /api/health/`

Liveness. Use it to show "API up".

```json
{ "status": "ok", "years": [2019, 2020, 2021, 2022, 2023, 2024, 2025, 2026] }
```

---

## `GET /api/years/`

The years that have a measured bankline (Sentinel-2 only).

```json
{ "years": [2019, 2020, 2021, 2022, 2023, 2024, 2025, 2026] }
```

---

## `GET /api/banklines/`

**8 features**, one per year. Plain GeoJSON `FeatureCollection`. Properties are
just `{"year": 2019, "kind": "bankline"}` — everything else is geometry.
253 KB, so fetch it once and switch years client-side rather than refetching.

---

## `GET /api/erosion/`

Erosion-accretion between two years. 38 features (one per transect).

```json
{
  "type": "FeatureCollection",
  "name": "epr_2025_2026",
  "features": [ { "type": "Feature", "properties": { ... }, "geometry": {...} } ]
}
```

The `name` field tells you which year-pair this is. Per-feature properties:

| field | meaning |
|---|---|
| `id` | transect id, joins to `/api/risk/` and `/api/predictions/` |
| `arc_m` | distance along the river centreline, metres |
| `left_rate`, `right_rate` | m/yr. **Positive = land LOST (erosion)** |
| `left_lost_m2`, `left_gained_m2`, `right_lost_m2`, `right_gained_m2` | areas |
| `width0_m` | channel width at the start year |
| `water_frac` | fraction of the transect that was water |
| `stage0_km2`, `stage1_km2` | water area at each year |
| `mag` | magnitude class |

**The sign convention is the single easiest thing to get wrong.** Positive is
erosion everywhere in this API. It was inverted once project-wide (D58).

---

## `GET /api/erosion/pairs/`

```json
{ "pairs": ["2019_2020", "2020_2021", "...", "2025_2026"] }
```

Build the pair selector from this, not from arithmetic on `/api/years/`.

---

## `GET /api/predictions/`

The experimental projection to 2036. 148 features, 68 KB. **This is the one
endpoint with rules attached.**

`metadata` (read this first — it is the model's own statement about itself):

```json
{
  "n_records": 76,
  "horizon_years": 10,
  "base_year": 2026,
  "method": "HistGradientBoostingRegressor, expanding-window backtest",
  "model_name": "HistGradientBoostingRegressor",
  "projection_status": "experimental",
  "horizon_validated": false,
  "forecast_supported": true,
  "is_forecast": false,
  "mae_model_m_per_yr": 15.675,
  "median_baseline_mae_m_per_yr": 20.413,
  "best_baseline_mae_m_per_yr": 20.413,
  "warning": "Experimental model projection. The one-year model beats the ..."
}
```

**Display `warning` verbatim.** It is generated from the numbers in the same
payload, so it cannot drift from them. `09_checks.py` fails the build if it does.

Features come in **two kinds**, distinguished by `properties.kind`:

**`kind: "current_bank"`** — the measured 2026 bankline, for reference.
Properties: `transect_id`, `side`, `year`.

**`kind: "experimental_projection"`** — the drawn line. Properties:

| field | meaning |
|---|---|
| `transect_id`, `side` | joins to the other endpoints |
| `horizon_years` | 10 |
| `rate_m_per_yr` | predicted rate, positive = erosion |
| `projected_offset_m` | total movement over the horizon |
| `offset_low_m`, `offset_high_m` | the uncertainty range |
| `n_years` | how much history this bank side has |
| `significant` | whether its own long-run rate is distinguishable from zero |
| `method` | names the model that produced it |
| `projection_status` | `"experimental"` |
| `horizon_validated` | `false` — the 10-year band is a heuristic, not calibrated |
| `forecast_supported` | see rule 2 above |
| `is_forecast` | `false` |
| `mae_model_m_per_yr` / `best_baseline_mae_m_per_yr` | 15.675 vs 20.413 |
| `basis` | human-readable provenance |

**Show the range, not just the line.** `offset_low_m` / `offset_high_m` frequently
straddle zero. Drawing only the midpoint implies precision the model does not
have.

**And show what it loses to.** The model beats trivial baselines on *rate*, but for
absolute *bank position* it loses to assuming the bank never moved — 30.8 m mean
error against 13.8 m on the 2023→2026 window. That comparison is in
`reports/validation_bankline_2026*.png`. A UI that shows the projection without
that is overclaiming by omission.

---

## `GET /api/risk/`

Historical long-run risk. 96 features, 64 KB.

`risk.summary` note: *"Historical long-run erosion rates; not future bankline
predictions."*

Per-feature properties (all 23):

| field | meaning |
|---|---|
| `transect_id`, `side` | identity |
| `arc_m` | centreline position, metres |
| `n_years` | years of record |
| `n_eff` | **effective** independent years — far smaller than `n_years`, because consecutive years are correlated |
| `rate_mean`, `rate_median`, `rate_sd` | m/yr; positive = erosion |
| `ci95_lo`, `ci95_hi` | 95% block-bootstrap interval for the **median** |
| `mean_ci95_lo`, `mean_ci95_hi` | interval for the **mean** |
| `rate_p10`, `rate_p90` | percentiles |
| `yrs_eroding_pct` | share of years the bank eroded |
| `min_rate`, `max_rate` | extremes |
| `significant` | **CI excludes zero.** Only 32 of 96 — the rest are not distinguishable from "not moving" |
| `sufficient` | at least 10 years of record (92 of 96) |
| `tier` | `high` (1) / `moderate` (18) / `low` (45) / `accreting` (28) / `insufficient record` (4) |
| `risk_rank` | 1 = fastest-eroding |
| `risk_share_pct` | relative to the worst transect |
| `risk_label` | display string |

**`significant` is the honest flag and it is usually `false`.** Render the
non-significant records differently rather than hiding them — hiding them implies
the rest were measured and found normal, which is a different claim.

---

## `GET /api/risk/summary/`

Counts for a legend or dashboard tile, so the UI does not have to compute them.

```json
{
  "records_total": 96,
  "records_eligible": 92,
  "records_insufficient": 4,
  "records_significant": 32,
  "tiers": { "high": 1, "moderate": 18, "low": 45, "accreting": 28 },
  "note": "Historical long-run erosion rates; not future bankline predictions."
}
```

---

## `GET /api/status/`

One call to decide what to draw, so the UI never shows an empty panel without
saying why.

```json
{
  "years": [2019, "...", 2026],
  "erosion_pairs": ["2019_2020", "..."],
  "landsat_years": ["1989", "...", "2026"],
  "features_ready": true,
  "hydro_ready": true,
  "risk_ready": true,
  "trend_ready": true,
  "model_trained": true,
  "predictions_ready": true
}
```

- `landsat_years` is **37 years** — 1997 is genuinely missing from the archive.
- `hydro_ready` means the ERA5-Land **data exists**, *not* that the model uses it.
  It does not — hydrology made the model slightly worse and was rejected (D90).
  **Do not show it as a model input.**
- `model_trained` is true only when `model_report.json` names this reach, so it
  detects a stale report rather than just a file existing.

---

## Adding an endpoint

1. Add the view in `backend/core/views.py` and a `path()` in
   `backend/core/urls.py`. Keep the trailing slash — the frontend proxy expects it.
2. Read data through `REACH_DIRS[REACH]`, never with an absolute path. The reach
   is a registry (`arial_khan` is currently the only entry) and hardcoded paths
   are how the wrong river got exported before (D88).
3. If the response carries a claim about the model, generate that text from the
   numbers in the same payload, and add or extend a check in `ml/09_checks.py`.
   **A guard that has never been seen to fail is not known to work** — verify it
   by breaking the data on purpose.
4. Restart Django: it runs with `--noreload`, so view changes need a restart.
   Data files are re-read per request and do not.
