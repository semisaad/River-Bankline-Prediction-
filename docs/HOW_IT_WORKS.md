# How RiverGuard Works — A Plain-Language Guide

This guide explains your own system from top to bottom, in everyday words.
No prior background assumed. Read it top to bottom once; then use it as a map.

---

## 1. The big picture: what are we actually building?

Imagine a river that slowly eats into the land on its sides. That is the
**Jamuna river** in Bangladesh, and it is one of the fastest-moving rivers in
the world — huge areas of farmland and villages disappear into it every year.

We are building a tool that answers one question:

> **"Where along this river is the bank most likely to eat into the land next,
> and by roughly how much?"**

To answer that, we use **satellite photos** taken over many years, teach a
computer to **trace the river's edge** in each photo, **measure how far the edge
moved** year to year, and finally learn the **pattern** so we can **predict**
where it moves next. Then we show it all on a **map in a web browser**.

Why it matters: if people can see *where* erosion is coming, they can protect
the right spots, move families in time, and spend money where it counts.

---

## 2. The cast of characters (words you'll see, defined)

- **Satellite image / scene** — a photo of the ground taken from space. Stored
  as a grid of tiny squares ("pixels"), each with a number.
- **Pixel** — one tiny square of an image. In our main data, one pixel covers
  10 metres × 10 metres on the ground.
- **Band** — one "layer" of an image. Like how a photo has red, green, blue
  layers, some images also have invisible layers we can use to detect water.
- **Water index (we call it MNDWI)** — a math recipe applied to image layers
  that makes water stand out from land. Big number = likely water.
- **Mask** — a simplified version of an image where each pixel is just two
  choices: *water* or *not water*. (In our files, water = 255, land = 0.)
- **Bankline** — the edge of the river, i.e. where water meets land.
- **Channel belt** — the whole braided "band" of the river, including sand
  bars and multiple channels. The Jamuna isn't one clean channel; it's a wide
  messy belt.
- **Transect** — a straight line drawn across the river. We measure how far the
  river's edge moved along each line.
- **Erosion** — bank moving *into* the land (land lost).
- **Accretion** — bank moving *away* (new land/bar gained).
- **CRS (coordinate system)** — how we put map positions into numbers. lat/lon
  (like GPS) uses degrees; a "projected" CRS uses metres so we can measure real
  distances. We measure in metres (see §3).
- **GeoJSON** — a simple text file format for map shapes (lines, points,
  areas). Our web app reads these.
- **API** — the "waiter" between the web page and the stored results. The page
  asks for something, the API fetches it and hands it over.
- **Raster** — an image grid (the masks, the photos). **Vector** — shapes like
  lines and polygons (the banklines, transects).

---

## 3. The five "rooms" of the system

Think of the whole thing as a factory with five rooms. Data walks through them
in order.

### Room 1 — The Photo Room (`ml/01_prepare.py`)
**Job:** make every year's image line up perfectly, and convert distances to metres.

Raw satellites send images in GPS-style coordinates (degrees of latitude and
longitude). Degrees are awkward for measuring: one degree of longitude is a
different number of metres depending on where you are. So this step:

- Picks one **common grid** for the whole study area, in **metres** (a
  "projected" system called UTM zone 45 North). We use 10 m pixels.
- Reshapes ("reprojects") every year's photo and mask onto that exact same grid.
- Result: every pixel in 2019 sits exactly on top of the same pixel in 2025.
  Now differences between years are real changes on the ground, not alignment
  errors.

**Output:** `data/processed/mask_YYYY.tif` (water/land) and `rgb_YYYY.tif`
(colour, for display).

**Why it matters:** if years are misaligned, you'd "measure" fake movement.

### Room 2 — The Tracing Room (`ml/02_banklines.py`)
**Job:** draw the river's edge for each year.

The mask says water/land for every pixel. But it's speckled — small gaps,
noise, little ponds. So we clean it up:

- **Closing**: bridge tiny gaps (fill narrow slivers so the belt looks solid).
- **Largest body only**: keep the single biggest connected blob of water (the
  main river belt) and throw away stray puddles.
- **Fill holes**: if there's a small island fully surrounded by water, treat it
  as part of the belt for the *outer* outline.

Then we trace the **outer outline** of that belt — the outermost edge of all the
water. That outline is the **bankline**.

**Rule we chose (important):** the line is the *outer edge of the whole active
belt*, not each little channel. Internal bars and channels are ignored. Why:
they wiggle constantly and would create noisy measurements; the outer belt edge
is the thing that actually threatens land.

**Output:** `data/processed/banklines/bankline_YYYY.geojson` (a line, one per year).

### Room 3 — The Measuring Room (`ml/03_transects.py` old, `ml/04_erosion.py` current)
**Job:** measure how far the bank moved between two years.

**The old way (`03_transects.py`) — now superseded.** It drew 20 straight lines
across the river, found the outermost water pixel on each side, and compared
those positions between two years. Simple, but it failed: filling in the
sandbars to find the "river edge" depends on how high the water is that year, so
the edge jumped around for no real reason. Its reported number moved ~40% just
from changing a cleanup setting, and it produced impossible 2900 m jumps.

**The current way (`04_erosion.py`) — measure change, not position.**
Instead of asking "where was the edge?", it asks "what actually changed?":

- Count pixels that were **water in year A and land in year B** = **erosion**
  (land lost). Count the reverse = **accretion** (land gained).
- Do this inside a 1 km-wide strip along the bank at each transect.
- Net area difference divided by the length of river frontage gives
  **metres of bank movement per year**. This is the standard **EPR
  (Erosion/Progradation Rate)** method used in river and coastal studies.
- Because it averages over a whole square kilometre, one noisy pixel is
  meaningless — which is exactly what broke the old method.

**Two things that had to be right:**
1. **Measure the two banks separately.** Averaging across the whole 9 km belt
   gives nearly zero, because while one side erodes the other is building. The
   threat to people is the *outer* bank, so that is what we isolate.
2. **Put the measuring strip on the real water edge**, taken from the water mask
   itself — not from the filled-in outline, which reaches out onto dry sandbar.

**Output:** `data/processed/transects/epr_YYYY_YYYY.geojson` for all seven
consecutive year-pairs, each carrying `left_rate` and `right_rate` in m/yr, plus
the water area in each year as a rough water-level check.

**Reading the numbers:** medians run about **38-75 m/yr** depending on the year,
with a worst hotspot near 340 m. That sits inside the range published for the
Jamuna. An independent check (measuring how far the drawn outline moved between
years) agreed with these results, with a **correlation of +0.85** — so the
method is measuring something real, not noise.

### Room 4 — The Waiter (`backend/`, Django)
**Job:** hand results to the web page on request.

Django is a web framework: a small program that listens for requests and
answers them. Ours has four doors ("endpoints"):

- `/api/health/` — "are you alive, and which years do you have?"
- `/api/years/` — list of available years.
- `/api/banklines/?year=2023` — the bankline for one year (as GeoJSON).
- `/api/transects/?pair=2022_2023` — the movement measurements.

It works by reading the GeoJSON files Rooms 2 and 3 produced. No database —
the files on disk are the truth for now.

**Why a separate room?** So the web page never touches your files directly. The
waiter is the single safe doorway; later we can swap what's behind it (e.g. a
trained model's predictions) without changing the page.

### Room 5 — The Window (`frontend/`, React + MapLibre)
**Job:** show it on a map you can click.

- **React** builds the visible page (title, slider, legend, controls).
- **MapLibre GL** draws the interactive map (the satellite background is from
  Esri).
- The page fetches from the Waiter:
  - the **bankline** (cyan line) for the chosen year, and
  - the **transects**, drawn as short lines coloured green → yellow → red by
    how far the bank moved.
- The **timeline slider** (2019–2026) reloads the bankline for that year; the
  ▶ button animates through all years.

**Why it matters:** this is the thing a non-expert actually looks at and uses.

---

## 4. How a single data point travels (the whole pipeline)

```
GEE export (you download)
        │  raw photos + water masks, in lat/lon
        ▼
01_prepare.py   → aligned metre-grid rasters        (data/processed/*.tif)
        ▼
02_banklines.py → river edge per year               (data/processed/banklines/*.geojson)
        ▼
03_transects.py → bank movement between 2 years     (data/processed/transects/*.geojson)
        ▼
Django API      → serves those files                (backend/, port 8010)
        ▼
React + MapLibre→ draws them on a map               (frontend/, port 5173)
```

---

## 5. What is REAL right now vs. what is still to come

**Real and working today:**
- 8 years of satellite water/land data (2019–2026), aligned and clean.
- A traced bankline for each year.
- Migration measurements between 2022 and 2023.
- A working website that shows the bankline and the movement on a map.

**Not built yet (the point of the project):**
- **Predictions.** Today we only *show history*. The model that forecasts
  *future* erosion is not built.
- More sensors (radar, older Landsat), more years, and discharge/rainfall
  inputs.

So the current system is the **skeleton**: the full path from raw satellite to
interactive map works end to end, but the "future" smart part is next.

---

## 6. Honest weak spots (so you know what to harden)

1. **Only ~5 usable training years.** Fine to *build* the pipeline on, too thin
   to *trust* a forecast. The fix: extend backward with the **Landsat archive**
   (images from ~1984 onward) — that turns 5 samples into ~35.
2. **No labels / no ground truth.** We can't say "the bank was exactly here."
   We rely on: agreement between different satellites, agreement with published
   Jamuna studies, and honest error bars. We report uncertainty, not false
   precision.
3. **Water level confuses "bank" with "water edge".** A low-water year exposes
   more bank, so the edge looks like it moved when the land didn't. We already
   fix part of this by always comparing the **same dry season** window. Full fix
   (normalising for water level) is on the list.
4. **The zone depth still sets the magnitude.** How wide a strip of land we
   consider "at risk" changes the answer (500 m to 2000 m moves the median from
   -38% to +53%). This is a *physical* choice, not a cleanup artefact, but it
   must be stated as an assumption and reported as a **range**.

---

## 7. Why the split "train up to 2023, test 2024–2026" matters

When we train a model, we must **never** let it see the years we'll test it on —
that's called **data leakage** and makes a model look smart when it's only
cheating. So: learn from the past, then check on a future it has never seen.
Even better, keep 2023 aside for tuning, and open the 2024–26 "locked box"
once, at the very end, for the headline result.

---

## 8. Mini-glossary (one-liners)

- **Erosion** — land lost to the river. **Accretion** — land gained.
- **Bankline** — the river's edge (water meets land).
- **Transect** — a measuring line across the river.
- **Mask** — a water/land map.
- **Raster** — grid image. **Vector** — line/shape.
- **Deep learning / ML** — a computer finding patterns in examples. **XGBoost**
  — a popular pattern-finder. **LSTM** — a pattern-finder for time sequences.
- **Baseline** — the dumb "assume nothing changes" guess we must beat to be
  useful.

---

## 9. Where everything lives

- Project root: `/media/saad/HDD/riverguard` (also reachable as
  `~/Projects/riverguard`, a shortcut).
- Raw data: `data/raw/` · Processed data: `data/processed/`
- Code: `ml/` (pipeline), `backend/` (API), `frontend/` (map)
- This guide: `docs/HOW_IT_WORKS.md`
