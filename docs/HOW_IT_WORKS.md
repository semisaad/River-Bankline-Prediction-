# How RiverGuard works

The measurement method, end to end, in plain language.

> **Status note (2026-10-18).** The goal is a system that predicts future bankline
> positions. The current Arial Khan model is experimental: when evaluated using
> only prior-year information, it does not beat the training-median baseline.
> Its 2036 lines are not validated forecasts; see D63 in
> `reports/DECISIONS.md`.
>
> **Area scope:** the larger Arial Khan rectangle is now selected and
> configured (D65), but its exports have not been processed. Geometry counts,
> maps, and model scores here describe the previous smaller box; rebuild and
> revalidate before applying these figures to the expanded area.

---

## 1. The short version

Satellites photograph this river every few days. We turn those photographs into a
simple yes/no picture of where the water was, once per year, for many years. Then
we ask a very specific question about a small number of places along the bank:

> *Between year A and year B, how many square metres of land turned into water,
> and how many turned back into land?*

Divide by the length of riverbank involved and you get **metres of bank movement
per year**, separately for each bank. Do that 35 times and you have a history.

Those measurements are the input to a prediction model. The model's job is to
estimate future movement using only information available before the prediction
period, then compare its results with simple baselines and later observed
banklines.

---

## 2. The words you will see

- **Pixel** — one tiny square of a satellite image. At 10 m it covers 10 × 10 m of
  ground; at 30 m, 30 × 30 m.
- **Band** — one layer of an image. Visible ones are blue, green, red; there are
  also invisible infrared layers we use to tell water from land.
- **Water index** — a formula combining bands so water stands out. Bigger number
  means more likely water. We use five of them and count a pixel as water if
  **any** fires, because each fails differently.
- **Mask** — a simplified image where every pixel is just *water* or *not water*
  (255 or 0 in our files).
- **Composite** — one image made from many. Each pixel takes the 25th percentile
  of its values across every pass that month. Cloud and haze are *bright*, water is
  *dark*, so pulling toward the lower quartile removes cloud without removing
  water.
- **Bankline** — where water meets land.
- **Channel belt** — the whole braided band of a river including sandbars. The
  Jamuna is a 9 km wide mess of it; the Arial Khan is a single 300 m channel.
- **Transect** — a short line drawn straight across the river. We measure
  movement along it.
- **Erosion** — bank moving into land. **Accretion** — bank building outward.
- **EPR (Erosion/Progradation Rate)** — the standard river-science method:
  net area change divided by river frontage, giving m/yr.
- **CRS** — how map positions become numbers. Degrees (like GPS) are awkward for
  measuring; we use a projected CRS in metres, UTM zone 45N for the Jamuna and
  46N for the Arial Khan.
- **GeoJSON** — a plain-text format for map shapes. The website reads these.

---

## 3. The pipeline, room by room

### Room 1 — Align (`ml/01_prepare.py`)

Satellites send images in degrees of latitude and longitude. One degree of
longitude is a different number of metres depending on where you are, so degrees
cannot be used to measure distance.

This room picks **one common grid in metres** for the whole study area and
reprojects every year onto it. For the active Arial Khan study, Sentinel-2
currently covers 2019–2026. The archived Jamuna Landsat record covers earlier
years. Without alignment, you would "measure" grid error as movement.

**Output:** `mask_YYYY.tif` (water/not water) and, if available, `rgb_YYYY.tif`
(colour, display only — nothing in the measurement reads it).

### Room 2 — Trace (`ml/02_banklines.py`)

Cleans the speckle, keeps only the largest connected body of water, fills holes,
and traces its **outer outline**. That is the bankline.

For a braided belt like the Jamuna we deliberately take the outer edge of the
whole belt rather than each small channel, because internal bars wiggle constantly
and would produce noise. The threat to people is the outer bank.

### Room 3 — Measure (`ml/04_erosion.py`)

This is the heart, and it asks a different question from the obvious one.

**The obvious question — "where was the edge?" — does not work.** Where the edge
*appears* to be depends on how much water there was that year, so it jumps around
for reasons that have nothing to do with land moving. An earlier version did
exactly this and its answer moved 40% purely from changing a cleanup setting.

**What we do instead:** count what *changed*.

- Pixels that were **land in year A and water in year B** → land **lost**
- Pixels that were **water in year A and land in year B** → land **gained**
- Both counted inside a **measuring strip** along each bank
- Net change ÷ length of riverbank = **m/yr**

This is EPR, the standard method in river science. Averaging over a whole strip
means one noisy pixel cannot swing the answer.

**Two details that had to be right:**

1. **Each bank measured separately.** Averaged across a whole braided belt the
   answer is nearly zero, because one side erodes while the other builds. The
   threat is the outer bank, so that is what we isolate.

2. **The measuring strip sits on the real water edge**, taken from the water mask
   itself — not from the filled-in outline, which reaches out onto dry sandbar.

> ⚠️ **Sign convention:** positive always means **land lost**. This was inverted
> across the whole project until D58 — magnitudes were always correct, direction
> was not. Check it if you touch this file.

### Room 4 — Geometry (`ml/transects.py`)

Where the transects go, and how the two banks of each one are found.

**Transects follow the river.** An earlier version drew 20 straight lines across
one global axis. The Jamuna runs diagonally, so "across the river" was wrong
almost everywhere: the measured belt came out 18 km wide instead of 9 km, and
many measuring zones sat on dry land, which can only ever report "no change".
Those wrong numbers looked plausible, which is the dangerous part.

Now: trace a centreline that follows the channel, place a transect every 250–500 m,
and draw each one **perpendicular to the local direction** of that centreline.
Same two points on the river are compared in every year, so a rate always means
the same thing.

**How the banks are found depends on the river** — this is not a detail, it was
worth 9 transects:

| | Jamuna (9 km braided) | Arial Khan (300 m single) |
|---|---|---|
| method | smoothed water fraction | **contiguous run** through the centre |
| why | mid-channel bars must be averaged out | a bar 3 km away is a pond, not a bank |

On the Arial Khan, ponds connected to the river by a breach made the profile read
a pond as the far bank — a "3.5 km river". Clamping instead of dropping those
transects took the reach from 23 to 32 transects when it was first measured; the
current expanded box yields **60 transects kept of 63 built**, over 15.8 km of
centreline.

### Room 5 — Historical risk (`ml/13_risk_and_forecast.py`)

Turns the measurements into a risk ranking **with honest uncertainty**.

- Requires **at least 10 years** before a transect may be ranked. Without that, a
  single lucky year of +165 m/yr outranked thirty years of measured behaviour.
- Uses the **median**, not the mean, so one extreme year cannot reorder the river.
- The confidence interval is a **block bootstrap** for that median, resampling in
  blocks of three consecutive years so the serial dependence survives. Consecutive
  years are not independent measurements — a bank eroding this year usually still
  erodes next year.

This step needs a long Landsat record. The active Arial Khan output is **96
records, 92 eligible for ranking, 4 flagged insufficient**. `reports/RISK.md`
describes the archived Jamuna analysis; `reports/RISK_arial_khan.md` is the
active reach.

### Room 6 — Test and project (`ml/14_model_train.py`, `ml/06_predict_geojson.py`)

The model uses only prior-year rates, prior-year width and static river geometry.
It is tested by predicting later years using earlier years only. Missing values
are filled using the training years, not the test years. The candidate is
compared with a training-median rate and the previous year's rate.

The walk-forward test covers **2414 bank-side/year records across 29 folds**.
Gradient-boosted trees score **15.675 m/yr**, against **20.413** for the strongest trivial
baseline. That pooled margin is real but **is not spread over time**: the model
beats its own baseline in 18/18 folds for 1996–2015 and only 2/11 for 2016–2026.
The pipeline draws a 10-year linear extension, but marks it **experimental** and
does not call it a validated forecast — and the recent folds are exactly the
regime that extension is drawn from. See D92 and `reports/MODEL_CHOICE.md`.
That extension's uncertainty band is not calibrated for ten years.

### Room 7 — Serve (`backend/` Django, `frontend/` React + MapLibre)

The API reads processed GeoJSON files for the selected reach. The map shows
observed banklines and can show chronic risk when data exists, plus the current
**experimental projection**. It displays the model-vs-baseline scores beside
that projection so users can see why it is not yet called a forecast.

---

## 4. What the numbers actually say

The archived Jamuna test was negative: its 37-year record did not produce a
model that beat the mean/median baselines (see `reports/VALIDATION.md`). That
result motivated the move to Arial Khan, but it is not the active-reach result.

On Arial Khan, the former MAE 2.843 m/yr score used same-interval measurements
and is withdrawn as forecast evidence. Under the corrected time-forward test:

| predictor | MAE (m/yr) |
|---|---|
| gradient-boosted trees (served) | **15.675** |
| RandomForest (retained) | 15.886 |
| training-median baseline | 20.413 |
| training-mean baseline | 20.723 |
| repeat previous pair | 23.284 |

The model beats the baselines pooled, but **loses to them in the recent regime**
(2/11 folds from 2016 on) — which is the regime the 2036 projection extends. The
goal remains to build and validate the future-bankline system; the map's current
projection is a development output, not evidence that the goal has been achieved.

---

## 5. Honest weak spots

1. **No ground truth.** No survey says where the bank was. Confidence comes from
   two independent sensors agreeing and from published rates, not from absolute
   accuracy.
2. **The measuring strip sets the magnitude.** 1000 m on the Jamuna, **250 m** on
   the Arial Khan. A wider strip dilutes the same land loss over more frontage. It
   is a stated assumption, not a fitted parameter.
3. **One clear-season composite per year.** Monsoon attack on the outer bends, at
   the highest water, is not captured — and on a 21 m/yr river, that is likely a
   large part of the annual story.
4. **Annual pairs are not independent**, and several consecutive pairs can be
   dominated by one flood. The bootstrap intervals only partly handle this.
5. **Most individual transect rates are not distinguishable from zero.** Shown and
   flagged rather than quietly dropped.
6. **Thresholds were tuned on the Jamuna** and are unverified on a 300 m river.
7. **Landsat's measured median of 11.2 m/yr sits about half the published ~21
   m/yr** for this river. Part is definitional — published figures are channel
   *shift*, we measure net land change in a bank strip — and part may be real. It
   must not be "corrected" by rescaling to match the literature.
8. **Sentinel-2 cannot resolve annual movement here.** Its median of 1.2 m/yr is
   an eighth of one 10 m pixel, so its annual target is mostly quantisation. This
   is why the long record is built from Landsat's 5-year pairs, where a pixel is
   worth 6 m/yr.
9. **The rate-level cross-sensor test cannot run on this reach.** Sentinel-2 uses
   1-year pairs and Landsat 5-year, so no shared pair exists. On the Jamuna this
   was the strongest validation available; here it is absent, and only the water
   maps can be compared (IoU 0.79).

---

## 6. Mini-glossary

| | |
|---|---|
| **raster** | an image grid (masks, satellite pictures) |
| **vector** | map shapes — lines, polygons (banklines, transects) |
| **API** | the waiter between the web page and the stored files |
| **UTM** | a projected coordinate system in metres, 6° zones; zone 45N covers 84–90°E |
| **GloFAS** | Copernicus global river discharge reanalysis, m³/s |
| **5-year block** | measuring Landsat between year Y and Y+5, because at 30 m a 21 m/yr river moves 0.7 pixel per year and annual pairs would measure noise |

---

## 7. Where everything lives

| | |
|---|---|
| Imagery comes from | `gee/*.js`, run by the owner in Earth Engine |
| Measurements | `ml/` |
| Reports | `reports/` |
| Working state | `context/` |
| Conventions for agents | `AGENTS.md` |

Rasters are **not** in git — all regenerable. The small CSV and GeoJSON evidence
tables behind the reports are committed.

**Start here if you are new:** `README.md`, then `reports/DECISIONS.md`.