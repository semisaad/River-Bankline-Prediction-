# How RiverGuard works

The measurement method, end to end, in plain language.

> **Status note (2026-10-18).** An earlier version of this document described a
> system that would forecast next year's erosion. That was tested and it does not
> work — see `reports/DECISIONS.md` D44. This version describes what the project
> actually measures and what it actually claims.

---

## 1. The short version

Satellites photograph this river every few days. We turn those photographs into a
simple yes/no picture of where the water was, once per year, for many years. Then
we ask a very specific question about a small number of places along the bank:

> *Between year A and year B, how many square metres of land turned into water,
> and how many turned back into land?*

Divide by the length of riverbank involved and you get **metres of bank movement
per year**, separately for each bank. Do that 35 times and you have a history.

That is the whole measurement. Everything else in this project exists to make
that one number trustworthy.

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
reprojects every year onto it. Result: the same patch of ground lands on the same
pixel in 1989 and in 2026. Without this, you would "measure" alignment error as
movement.

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
transects took the reach from **23 to 32 transects**, a 39% gain.

### Room 5 — Assess (`ml/13_risk_and_forecast.py`)

Turns the measurements into a risk ranking **with honest uncertainty**.

- Requires **at least 10 years** before a transect may be ranked. Without that, a
  single lucky year of +165 m/yr outranked thirty years of measured behaviour.
- Uses the **median**, not the mean, so one extreme year cannot reorder the river.
- The confidence interval is a **block bootstrap** for that median, resampling in
  blocks of three consecutive years so the serial dependence survives. Consecutive
  years are not independent measurements — a bank eroding this year usually still
  erodes next year.

Result: of 64 eligible records, **only 3** are statistically distinguishable from
zero. That is reported, not smoothed over.

### Room 6 — Serve (`backend/` Django, `frontend/` React + MapLibre)

The API reads the processed GeoJSON files — no database, the files are the truth.
The map draws the bankline, transects coloured by movement, and two optional
layers: **chronic risk** and a **long-run trend**. The word "forecast" was
removed from the interface entirely, because a button labelled "forecast"
invites a reader to accept a claim the evidence does not support.

---

## 4. What the numbers actually say

**The central result is negative.** Measured against "predict the average"
(83.9 m/yr on the Jamuna):

| predictor | MAE (m/yr) |
|---|---|
| **predict the average** | **83.9** |
| this transect's own past average | 87.1 |
| same transect, previous pair | 133.7 |
| 37 years of real GloFAS discharge | r = +0.049 |

Nothing beats the baseline. On the Arial Khan, a completely different river, the
same is true (2.92 vs 4.06 m/yr).

**Why, physically:** on a braided river, erosion hotspots **migrate rather than
persist**. And a catchment-scale discharge number — one value for a ~5 km cell —
cannot say *where* along a 9 km reach the water attacks the bank.

**What survives:** the measured record, cross-sensor agreement, and the relative
ranking of which stretches are chronic eroders. Those are defensible. A
year-by-year forecast is not.

---

## 5. Honest weak spots

1. **No ground truth.** No survey says where the bank was. Confidence comes from
   two independent sensors agreeing and from published rates, not from absolute
   accuracy.
2. **The measuring strip sets the magnitude.** 1000 m on the Jamuna, 300 m on the
   Arial Khan. A wider strip dilutes the same land loss over more frontage. It is
   a stated assumption, not a fitted parameter.
3. **Dry season only.** January–February at low water. Monsoon attacks on the
   outer bends are not captured — and on a 21 m/yr river, that is likely a large
   part of the annual story.
4. **Annual pairs are not independent**, and several consecutive pairs can be
   dominated by one flood. The bootstrap intervals only partly handle this.
5. **Most individual transect rates are not distinguishable from zero.** Shown and
   flagged rather than quietly dropped.
6. **Thresholds were tuned on the Jamuna** and are unverified on a 300 m river.
7. **The measured 1.7 m/yr on the Arial Khan sits far below the published
   ~21 m/yr.** Part is definitional — published figures are channel *shift*, we
   measure net land change in a bank strip — and part may be real. It must not be
   "corrected" by rescaling to match the literature.

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