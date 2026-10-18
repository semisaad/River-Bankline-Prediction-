# Decision Dictionary — RiverGuard

**Purpose.** This file is the record of *every significant decision* in this
project: what we chose, why we chose it, and what we rejected instead.

It exists for three reasons:
1. A final-year project is examined. "Why did you do it this way?" must have an
   answer that is better than "we tried it and it looked nice".
2. Decisions made on different days are made by different people-in-the-loop.
   Writing them down stops us contradicting ourselves six weeks later.
3. Some numbers in this project are *assumptions*, not facts. Those have to be
   written down, or we will accidentally present them as findings.

**Rule from now on:** any choice that affects the numbers, the method, or the
claims gets an entry here before we move on. Append-only — never rewrite an old
decision to look better. If a decision changes, add a new entry that supersedes
the old one and say so.

Format: numbered, dated, with **Reason** and **Rejected** so the alternatives
stay visible.

---

## D1 — Study area and period

**Date:** 2026-10-17
**Decision:** One reach of the Jamuna near Kazipur / Sirajganj,
bbox `89.65–89.85°E, 24.30–24.60°N`, analysed only for **1 January – 28
February** every year.

**Reason:** The dry-season window is the whole point of a *fixed* season. A
low-water year exposes more of the bank, so comparing a wet January against a
dry February manufactures movement that never happened. Holding the window
constant removes most of that artefact.

**Rejected:**
- Year-round / wet-season imagery — water level swings far too much between
  months; the "bank" would mostly be tracking the tide of the river, not erosion.
- Full river length — a single 20 km reach is already a large body of work for a
  solo final-year project. Generality is explicitly *not* claimed.

**Impact:** Limits the conclusions to one reach and one season. Stated in the
validation report.

---

## D2 — Map projections: measure in metres, not degrees

**Date:** 2026-10-17
**Decision:** All analysis in **EPSG:32645 (UTM 45 North)**. GeoJSON written to
the web in EPSG:4326 only for display.

**Reason:** One degree of longitude is a different number of metres depending
where you are on Earth. Erosion is measured in metres per year, so the maths
has to be done in metres. UTM 45N covers 84°E–90°E, which contains the study
area.

**Rejected:**
- Lat/lon throughout — distances would be wrong and unit-dependent.
- Web Mercator (EPSG:3857) — fine for drawing a web map, wrong for measuring.

**Impact:** Distance errors avoided. Cost: one reprojection step in
`01_prepare.py`, and forgetting to reproject was a real bug we hit (D14).

---

## D3 — Scene selection: Sentinel-2 (existing record, 2019–2026)

**Date:** 2026-10-17 (inherited from the original export script)
**Decision:**
- Collection: `COPERNICUS/S2_SR_HARMONIZED`
- Window: `YYYY-01-01` to `YYYY-02-28`
- Scene filter: `CLOUDY_PIXEL_PERCENTAGE < 10`
- One **median** composite per year (not a single scene, not a mean)
- **No per-pixel cloud mask** (see Rejected)

**Reason:** The median across all clear scenes in the window is deliberately
robust. It removes single-scene artefacts (cloud, haze, sun glint) because an
outlier affects a median far less than it affects a mean. One scene would be
at the mercy of one bad pixel; a mean lets a single bright cloud drag results.

**Rejected:**
- A single "best" scene per year — no robust measure of "best", and one cloud
  ruins the year.
- Mean instead of median — sensitive to outliers, which is exactly what we are
  trying to remove.
- Seasonal (June–September, as used elsewhere in this project for rainfall) —
  that is monsoon season; the river is at its most dynamic and least
  comparable between years.

**Known weakness, accepted:** filtering at *scene* level (10% cloud) is much
weaker than masking clouds *per pixel*. We did test this (audit, Oct 17):
measured cloud contamination inside the final water mask was **0.0%**, so for
these 8 years it did not cause a visible problem. It is still the weakest part
of the Sentinel-2 selection and is disclosed.

---

## D4 — Scene selection: Landsat (new record, 1984–2026)

**Date:** 2026-10-17
**Decision:**
- Collection: Collection 2 Level 2, **loaded per sensor**
  (`LT04`, `LT05`, `LE07`, `LC08`, `LC09` — there is no merged C2 collection)
- Window: `YYYY-01-01` to `YYYY-02-28`
- Scene filter: `CLOUD_COVER < 40` (scene level)
- **Per-pixel** cloud/shadow mask on `QA_PIXEL` bits 0,1,2,3,4
  (Fill, Dilated Cloud, Cirrus, Cloud, Cloud Shadow)
- Median composite **per sensor generation**, then `mosaic()`
- 30 m export, EPSG:4326

**Reason:** Two reasons for the difference from D3. (a) Landsat revisits every
16 days versus Sentinel-2's 5, so the dry-season window holds fewer scenes and a
40% scene-level cut still leaves enough for a median; the per-pixel QA mask
recovers the rest. (b) Landsat has a published per-pixel quality bitmask, and
using it is strictly better than not.

**Rejected:**
- `CLOUDY_PIXEL_PERCENTAGE`-style scene filtering only — no per-pixel mask,
  leaves cloud edges in.
- Merged `LANDSAT/C02/T1_L2` collection — **does not exist.** Only Collection 1
  had a merged collection. This caused a real failure.
- Landsat 1–3 (MSS) — not in Collection 2, and different enough to be its own
  problem. Landsat 4 (1982) already covers our 1984+ window.

**Known weakness:** Landsat 7 failed in May 2003 (SLC-off) and produces striped
gaps through 2013. Expect sparse or unusable years in that range. This is a
sensor fault, not an error in our work, and must be disclosed rather than
silently dropped.

---

## D5 — The water index, and making the two sensors comparable

**Date:** 2026-10-17
**Decision:** Use
`(green − SWIR) / (green + SWIR) > 0.2`
for **both** satellites, where SWIR is the ~1.6 µm band.

- Sentinel-2: `B3` (green) and `B11` (SWIR, 1.6 µm)
- Landsat 4/5: `SR_B2` / `SR_B5`
- Landsat 7: `SR_B3` / `SR_B5`
- Landsat 8/9: `SR_B3` / `SR_B6`

**Reason:** This is the most important decision in the whole data stage. Water
absorbs SWIR strongly, so `(green − SWIR)/(green + SWIR)` is positive over water.
Crucially, **Landsat's SWIR1 sits at 1.566–1.651 µm and Sentinel-2's B11 at
1.6 µm — the same wavelength.** So the two satellites can be measured with a
genuinely identical instrument definition.

This is why we did *not* use the more common NIR-based index for Landsat: it is a
different physical measurement, and mixing the two would make Sentinel-2 and
Landsat disagree for reasons that have nothing to do with the river. Every
cross-sensor comparison afterwards would then be worthless.

**Rejected:**
- NIR-based MNDWI/NDWI for Landsat — different index, opposite sign convention.
  This was our first attempt and it was wrong.
- Per-sensor tuned thresholds — the index matches, so the threshold should
  match. If it turns out it does not, we calibrate it **on the 2019–2026
  overlap years only, and say so explicitly.**

**Impact:** Makes `08_crosssensor.py` a meaningful validation rather than a
measurement of our own inconsistency.

---

## D6 — Small-blob removal (Sentinel-2 only)

**Date:** 2026-10-17 (inherited)
**Decision:** Drop connected regions smaller than 150 pixels (1.5 ha at 10 m).

**Reason:** Isolated single pixels and small speckles are noise, not river.
150 px is roughly the smallest feature that could be a real channel fragment.

**Impact:** Not applied to the Landsat record yet. For consistency it should
either be applied there too or dropped everywhere. **Currently inconsistent —
this needs resolving before we trust cross-sensor IoU.**

---

## D7 — What "the bankline" means

**Date:** 2026-10-17
**Decision:** The bankline is the **outer boundary of the active channel belt**:
all water, gap-bridged, largest connected body, interior holes filled.

**Reason:** The Jamuna is braided — a wide messy belt of many channels and
bars, not one clean river. The threat to people is the *outer* edge of that
belt. Tracing every individual channel would produce a line that flickers
wildly as bars appear and vanish, and would measure sandbar migration rather
than the thing that actually floods farmland.

**Rejected:**
- Every individual channel edge — measures bar migration, which is not the
  hazard and is very noisy.
- A single "thalweg" centreline — does not show where the land is being lost.

**Impact:** Internal bar migration is explicitly out of scope. Any claim must
say "active-channel-belt migration", not "bank migration" in general.

---

## D8 — How movement is measured: EPR, and why the first method was scrapped

**Date:** 2026-10-17
**Decision:** Measure **EPR (Erosion/Progradation Rate)** — the standard method
in river and coastal literature. Count pixels that were water in year A and land
in year B (erosion), and the reverse (accretion), inside a zone at each bank;
net them and divide by river frontage length to get metres per year.

**Reason (this replaced a whole method):** The first implementation traced the
bank *position* and compared it between years. That failed because filling in
sandbars depends on how high the water is, so the "edge" jumped for no real
reason. Evidence:

| symptom | old (position-based) | new (EPR) |
|---|---|---|
| median shift vs cleanup radius | 114 → 161 m (**+41%**) | stable |
| worst-case artefact | 2934 m | 339 m (a plausible hotspot) |
| "belt area" year to year | 113 → 177 km² while real water moved 1.5 km² | n/a |

Counting changed area over a large zone makes single-pixel noise irrelevant,
because one pixel out of a million contributes nothing.

**Rejected:**
- Outline position comparison — unstable, as above.
- Whole-belt averaging — see D9; it cancels to nearly zero.

**Impact:** This is the single biggest methodological change in the project and
must be explained in the write-up.

---

## D9 — Measure the two banks separately

**Date:** 2026-10-17
**Decision:** Left and right bank zones are measured independently and never
averaged together.

**Reason:** Our first EPR attempt averaged across the whole ~9 km belt and
returned **~0 m/yr**. That is physically correct, not a bug: while one side
erodes the other accretes, so the belt average cancels. The land-threatening
process is the *outer* bank.

**Impact:** Roughly doubles the usable training rows (2 banks × 20 transects ×
year). D10 follows directly from this.

---

## D10 — Where the measuring zone sits, and why the first attempt gave zero

**Date:** 2026-10-17
**Decision:** The measuring zones **straddle the real water edge**, taken from
the water mask's 1st/99th percentiles. They are defined once from the reference
year (2023) and reused for both years being compared.

**Reason:** Our second attempt also gave ~0 m/yr, because the zones were placed
using the *filled belt outline* — which reaches out onto dry sandbar, so we were
measuring bare land. Percentiles are also used instead of min/max because a
single stray pixel would otherwise set the "bank" hundreds of metres out.

Fixing the zones to the reference year prevents a subtler failure: if the zone
were allowed to slide with the bank each year, it would slide *with* the change
and hide it.

**Impact:** Zones are now anchored to real water, not to an artefact.

---

## D11 — Zone depth = 1000 m, and this is an assumption not a fact

**Date:** 2026-10-17
**Decision:** The measurement zone is 1000 m deep across flow.

**Reason:** It stands for "a 1 km-wide strip of land along the bank" — roughly
the scale of a village or a farm plot, i.e. the parcel size at which losing land
actually matters to someone.

**Sensitivity (measured):**

| zone depth | median change |
|---|---|
| 500 m | −38% |
| 1000 m | baseline |
| 1500 m | +30% |
| 2000 m | +53% |

Deeper zones start capturing interior sandbar motion, not just the bank.

**This is the largest remaining uncertainty in the numbers.** It must be reported
as a range, never as one number, and the chosen value must be stated as a
physical assumption. Unlike the old method, this is a *physical* choice about
what counts as at-risk land — not a hidden cleanup knob — but it still drives
the magnitude.

---

## D12 — The speckle filter is stable (checked, not assumed)

**Date:** 2026-10-17
**Decision:** Open (remove speckle) by 20 m before measuring. No hole filling.

**Reason:** Removing tiny noise is safe *provided* it does not change the
answer. Verified:

| speckle opening | median change |
|---|---|
| 10 m | +6% |
| 20 m | baseline |
| 30 m | +19% |

Hole filling is excluded because that is precisely what caused the instability in
D8.

---

## D13 — Transect frame and placement

**Date:** 2026-10-17
**Decision:** 20 transects, placed on a **PCA flow-aligned frame** (u = along
flow, v = across flow), reference year 2023.

**Reason:** The reach runs diagonally across the image. Horizontal rows scrape
*along* the bank instead of across it and produce nonsense distances (this gave
523 m/yr before the fix). PCA finds the river's own direction so the measuring
lines are genuinely perpendicular.

**Rejected:** Row-wise / axis-aligned transects — the original bug.

---

## D14 — GeoJSON is written in EPSG:4326

**Date:** 2026-10-17
**Decision:** Analysis in EPSG:32645, but every GeoJSON is reprojected to
EPSG:4326 before being written.

**Reason:** The web map (MapLibre) requires lon/lat degrees. It silently ignores
anything else, which produced a map with no data on it and no visible error.

**Lesson:** a silently-wrong-but-valid file is more dangerous than a crash.

---

## D15 — No manual labelling

**Date:** 2026-10-17
**Decision:** No hand-drawn or CVAT-labelled training data.

**Reason:** Not enough time to label well, and badly-labelled data is worse
than none. Validation is done by agreement between independent methods instead.

**Consequence (important):** we have **no ground truth**. Every accuracy claim
must be phrased as "agrees with an independent method" or "consistent with
published rates", never "is accurate to X metres".

---

## D16 — How we validate without ground truth

**Date:** 2026-10-17
**Decision:** Four independent lines of evidence:
1. **Cross-method agreement** — EPR vs a completely separate outline-distance
   measure. Result: **correlation +0.92** across 7 year-pairs.
2. **Cross-sensor agreement** — Sentinel-2 vs Landsat on the 8 overlapping
   years (IoU, area difference, bankline offset). Script: `08_crosssensor.py`.
3. **Literature** — published Jamuna rates (~30–200 m/yr). Our medians 38–76
   m/yr fall inside.
4. **Parameter sensitivity** — how much does the answer move when we change
   settings (D11, D12).

**Reason:** With no truth, confidence has to come from independent lines that do
not share the same failure mode.

---

## D17 — Water level is handled as a feature, not a correction

**Date:** 2026-10-17
**Decision:** Do not "correct" for water level with a hand-derived formula.
Instead give the model `stage_km2`, `stage_change_km2`, `stage_ratio` and
`stage_change_ratio` and let it learn.

**Reason:** A hand-tuned correction would be another arbitrary knob (the D11
trap). Giving the model the ingredients lets it discount stage-driven change if
that is what is happening.

**Measured so far:** correlation between stage change and measured bank change
is **−0.06**, i.e. the measurement is not simply tracking water volume. That is
reassuring but not proof.

**Known weakness:** total water area is a weak proxy for river stage. Real
discharge (GloFAS/GRDC) would be much better and is still missing.

---

## D18 — The honest headline: 8 years cannot train this model

**Date:** 2026-10-17
**Decision:** Do **not** train and publish a predictive model on the current
8-year record. Record the negative result and get more data first.

**Evidence:**

| test | result |
|---|---|
| correlation(last year → this year) | **−0.14** |
| persistence baseline (repeat last year) | MAE 74.2 m/yr |
| mean-only baseline (predict the average) | MAE **47.8 m/yr** |
| best single-feature correlation | \|r\| < 0.24 |

**Reason:** Persistence is *worse* than predicting the average, so no model can
currently beat a coin flip. Erosion hotspots on a braided river *move* rather
than persist, so lag features are the wrong predictors. The dataset is
**data-limited, not model-limited.**

**Rejected:** training anyway and reporting a flattering score. It would be
either leakage or luck, and undetectable by the reader — the worst outcome for a
final-year project.

**Impact:** This finding is what justifies the Landsat extension (D19).

---

## D19 — Extend the record with Landsat, and add discharge

**Date:** 2026-10-17
**Decision:** Add Landsat 1984+ (~35 years) and, next, real discharge data.

**Reason:** Landsat multiplies the training rows by roughly 4 and captures far
more of the natural variability. Discharge is the dominant *physical* driver of
bank erosion and we currently have none of it — no feature in the current table
is a genuine causal driver, which is precisely why D18 found no signal.

**Impact:** This is the single biggest remaining lever on project quality.

---

## D20 — Technical stack

**Date:** 2026-10-17
**Decision:** Backend Django + DRF serving plain GeoJSON. Frontend React + Vite +
MapLibre GL (2D). No PostGIS. Model training on Google Colab.

**Reason:** Plain GeoJSON needs no database and no spatial server, which keeps a
solo project inside reach. PostGIS is powerful but adds a service to install and
maintain for no benefit at this scale.

**Rejected:** PostGIS, Leaflet (heavier canvas, weaker with large GeoJSON),
Docker (extra moving parts on a laptop with 7.5 GB RAM).

---

## D21 — Project lives on the external HDD

**Date:** 2026-10-17
**Decision:** `/media/saad/HDD/riverguard`, with `~/Projects/riverguard` as a
symlink.

**Reason:** Internal disk was 84% full with ~20 GB free; the HDD has ~430 GB.

**Known risk:** the HDD is **not** in `/etc/fstab`, so it may not auto-mount
after a reboot. If commands suddenly report missing files, check
`ls /media/saad/HDD` first.

---

## D22 — Not committing without permission

**Date:** 2026-10-17
**Decision:** No git commits or pushes unless Saad explicitly asks.

**Reason:** Owner preference. Repo is initialised with a `.gitignore` covering
`.venv/`, `node_modules/`, `__pycache__/` and `data/raw/` so an accidental
commit cannot swallow gigabytes.

---

## D23 — MapLibre worker must be set explicitly

**Date:** 2026-10-17
**Decision:** Copy `maplibre-gl-worker.mjs` into `frontend/public/` and set
`config.WORKER_URL` before creating the map.

**Reason:** MapLibre guesses its worker URL from its own module path, which
Vite's bundler breaks. The symptom was a map with basemap tiles but **no vector
layers** — clouds and colours silently missing, no console error.

**General lesson:** when a web map renders partly, suspect asset URL resolution
before suspecting the data.

---

## D24 — Earth Engine gotchas (recorded so we stop re-hitting them)

**Date:** 2026-10-17
Three bugs that each cost a round of debugging. All fixed, all verified by
`node --check` plus a stubbed-Earth-Engine execution test.

1. **`LANDSAT/C02/T1_L2` does not exist.** Collection 2 is per-sensor
   (`LT04`, `LT05`, `LE07`, `LC08`, `LC09`). Only Collection 1 had a merged
   collection.
2. **`.evaluate(fn, data)` does not pass `data` to the callback.** It only passes
   the result. Combined with a `var` loop variable and an *asynchronous*
   callback, all 43 exports would have been filed under the same wrong year.
   Fix: give each year its own function scope.
3. **An Earth Engine object is always truthy.** `if (coll.size().gt(0))` is always
   true, so emptiness tests must use `ee.Algorithms.If` or force evaluation
   first.

**Rule:** never branch on a server-side value with a plain JavaScript `if`.

---

## D25 — Unresolved / must revisit

**Date:** 2026-10-17
Open inconsistencies that must not be forgotten:

- **D6 is unresolved.** Blob removal (150 px) applies to Sentinel-2 but not to
  Landsat. Cross-sensor IoU may be depressed purely by that. Decide: apply to
  both, or drop from both, before quoting an IoU number.
- **Landsat 7 SLC-off (2003–2013)** may make those years unusable. Decide and
  document how such years are excluded, rather than dropping them silently.
- **Discharge data** not yet obtained (D19).
- **Prediction horizon** undecided (1 year or 5).
- **Second reach** never tested, so generalisation is unproven (D1).

---

*Append new decisions below this line, numbered from D26.*
---

## D26 — Landsat export produced empty masks; threshold is wrong

**Date:** 2026-10-17
**Decision:** Do **not** ship the Landsat record until the water threshold is set
from measured data. Pause Landsat work and run a diagnostic export instead.

**What happened:** All 27 downloaded Landsat masks came back with **zero** water
pixels (every pixel 0). Grid geometry was verified correct: EPSG:4326, pixel
27.3 x 29.9 m, bbox 89.6498-89.8500 E / 24.2998-24.6000 N — matching the
Sentinel-2 study area. So the export geometry is right; only the
**classification** failed.

**Suspected cause, in order of likelihood:**
1. **Threshold 0.2 is too high for Landsat with this index.** The index
   `(green - SWIR)/(green + SWIR)` behaves differently between sensors.
   Over Landsat water it may commonly sit *below* 0.2, especially over turbid
   water where suspended sediment reflects in SWIR and pushes the index toward
   zero. Sentinel-2's 0.2 was never re-derived for Landsat - it was copied.
2. **`ee.Algorithms.If` in the composite builder broke the composite.** This was
   added to guard against empty collections. It is a known fragile construct for
   images and may have produced an empty composite for every year.

**Action taken:**
- Removed the `ee.Algorithms.If` guard entirely. All sensors for a year are now
  merged into one pool of already-renamed `green`/`swir` bands and given a single
  median. Within any Jan-Feb window there is effectively one satellite anyway, so
  the per-sensor mosaic was unnecessary complexity.
- Added a **diagnostic export** (`RUN_DIAGNOSTIC`) that exports the raw index
  scaled by 100 for three sample years (1995, 2005, 2020), so the threshold can be
  read off real numbers instead of guessed.
- Moved all 27 all-zero masks to `data/raw/_empty_masks/` so they can never be
  mistaken for valid data.

**Reason:** A blank mask is more dangerous than a missing one. A blank mask
reads as "the river disappeared here", which would silently corrupt the bankline
and every measurement downstream. Rejecting them is the safe default.

**Rejected:** keeping the masks and proceeding anyway, because 27 years of data
is tempting. Worthless data is worse than no data.

**Impact:** Landsat processing is blocked until the threshold is measured.
Sentinel-2 pipeline is unaffected and continues to work.
The lesson is that a threshold copied from one sensor to another must always be
re-derived - see D5, where we correctly unified the *index* but wrongly assumed
the *threshold* transferred too.

---

## D27 — Landsat band selections verified against the official catalog

**Date:** 2026-10-17
**Decision:** Keep the band mapping as-is, now verified rather than assumed.

| Sensor | green | SWIR1 | source |
|---|---|---|---|
| Landsat 4/5 (TM) | SR_B2 (0.52-0.60 um) | SR_B5 (1.55-1.75 um) | verified |
| Landsat 7 (ETM+) | SR_B2 (0.52-0.60 um) | SR_B5 (1.55-1.75 um) | verified |
| Landsat 8/9 (OLI) | SR_B3 (0.53-0.59 um) | SR_B6 (1.566-1.651 um) | verified |

**Note on Landsat 7:** it is easy to assume ETM+ follows the same numbering as
OLI and that green is SR_B3. It is **not** — ETM+ has no coastal-aerosol band,
so its green is SR_B2. Confirmed against the Earth Engine catalog page for
LANDSAT_LE07_C02. Glad this was checked rather than asserted from memory.

**Process lesson:** we twice asserted a technical fact from memory and were
wrong (the C2 collection ID, and now nearly Landsat 7 bands). Verification
against the vendor catalog is now the rule before changing any band, dataset
name or threshold.

---

## D28 — Landsat must cover the same box as Sentinel-2

**Date:** 2026-10-17
**Decision:** Landsat exports must use the Sentinel-2 bbox exactly:
`[89.65, 24.30, 89.85, 24.60]`. Anything smaller is a silent data-corruption
risk, not a saving.

**Reason:** unreached ground arrives as pixel value 0, and **0 means land** in our
convention. So a smaller export box produces a strip of invented "dry land"
along the study-area edge, sitting right next to the river. It would drag the
bankline inland and produce no error anywhere. This is the same failure family
as D26 (a blank mask reading as "the river vanished").

**Rejected:** keeping a slightly different box. The comment on the earlier
script claimed "use the SAME box as your Sentinel-2 exports" while the actual
rectangle differed - the comment was wrong, and the mismatch was real.

**Impact:** `01b_prepare_landsat.py` now measures coverage per year and prints a
loud warning when a year does not cover >=99% of the study area, naming the
affected years. Blocked Landsat data cannot enter the pipeline silently again.

---

## D29 — Landsat becomes the primary analysis record

**Date:** 2026-10-17
**Decision:** Analyse **Landsat (1989-2026, 37 usable years)** as the main record.
Keep Sentinel-2 (2019-2026) as the **independent cross-sensor check**, not as a
combined dataset.

**Reason:** the two sensors overlap for 2019-2026. Pooling them would mix a 10 m
record with a 30 m record inside one training set. That is dangerous because:

1. **Resolution changes the measurement's noise.** A 30 m EPR measurement is
   smoother and less certain than a 10 m one. A model could learn "less certain"
   rather than "less erodible", which is meaningless.
2. **Different cleanups.** Each sensor's speckle filter is specified in METRES
   (20 m), so it becomes 2 px at 10 m and 1 px at 30 m. Same physical amount,
   different pixel counts.
3. **Consistency beats sharpness for a model.** One sensor, one resolution, 37
   consecutive years is a cleaner training set than a sharper but mixed one.

Keeping Sentinel-2 separate is a *gain*, not a loss: it is a genuinely
independent instrument measuring the same river, which is exactly what
`08_crosssensor.py` needs for ground-truth-free validation.

**Rejected:** one merged table with a `sensor` flag. It looks tidy and is
scientifically worse - it hides a systematic difference between the two halves
of the record.

**Impact:** Landsat gives 36 year-pairs instead of 7 - roughly 5x the training
rows (1440 vs 280). This is what finally makes the model trainable (see D18).

**Implementation:** `ml/transects.py` (the shared geometry module) is now
sensor-aware; every spatial parameter is expressed in METRES and converted using
that sensor's own resolution. `04_erosion.py` and `05_features.py` take a
sensor argument and write to separate folders. Sentinel-2 output was verified
byte-identical after the refactor.

---

## D30 — Threshold 0.2 confirmed working for Landsat

**Date:** 2026-10-17
**Evidence:** the Earth Engine quality table reported water fractions of
9.1-17.2% across 1989-2026, and Landsat 2023 (10.1%) closely matches the
Sentinel-2 mask for the same year (11.6%).

**Decision:** keep `THRESH = 0.2`. The D26 hypothesis - that the threshold had
been copied from Sentinel-2 without re-deriving it - was WRONG. The real cause
of the empty masks was the `ee.Algorithms.If` construct in the composite builder
(now removed).

**Honest note:** the correct cause was found only after the owner rewrote the
script without that construct. Two of my three hypotheses were wrong (the
collection ID, and the threshold). Verify before asserting - D24/D27.

**Impact:** 37 usable Landsat years, only 1992 dropped (84% coverage). Landsat 7
striping (SLC-off, 2003-2013) did NOT prevent detection - those years show
normal water fractions, so the striping is being filled by the multi-scene
median.

## D31 — Landsat analysed on its own smaller footprint

**Date:** 2026-10-17
**Decision:** Landsat was exported over a box smaller than the Sentinel-2 study
area (starting 24.35N instead of 24.30N). Rather than re-export 37 scenes, we
**adapt the analysis** to the reduced footprint:
- Landsat is processed and analysed on its own bbox, `config.BBOX_LANDSAT`.
- Any cross-sensor comparison uses `config.BBOX_COMMON`, so both instruments are
  measured on identical ground.
- The missing southern strip (about 5.5 km wide, holding **11.7% of the traced
  river**) is excluded from *both* records in comparisons, never silently read as
  land.

**Reason:** re-exporting was judged not worth the time. The cost of adapting is
that the Landsat primary record is a shorter reach than the Sentinel-2 record.
That is acceptable because the cross-sensor check - the only place the two are
combined - is restricted to the shared box anyway.

**Rejected:**
- Reading the uncovered strip as land. That is the D26/D28 failure mode: 0 means
  land, so an empty strip beside the river truncates the bankline with no error.
- Resampling Sentinel-2 down to 24.35-24.60 silently, which would quietly change
  the study area the existing results describe.

**Implementation:** `config.sensor_bbox(sensor)`, `config.BBOX_COMMON`;
`01b_prepare_landsat.py` builds its grid from the Landsat bbox;
`08_crosssensor.py` clips both rasters to the shared box and masks Landsat by
its own `valid` band where present.

**Impact:** the primary Landsat analysis covers a shorter reach. Stated as a
limitation. The alternative - a full-length reach - remains available by
re-exporting with the corrected box, which is a one-line change if the shorter
reach becomes a problem later.

---

## D32 — A standing guard script, because the same mistakes kept recurring

**Date:** 2026-10-17
**Decision:** Add `ml/09_checks.py` and run it before trusting any output.

**Reason:** three separate failures came from the same class of mistake - a
plausible-looking artefact that was silently wrong rather than loudly broken:
1. A file whose opening comment was never closed (whole script dead).
2. A dataset id that does not exist.
3. `ee.Algorithms.If` on images, which silently produced empty composites.
Plus the MapLibre worker 404, which showed a map with no layers and no error.

None of these raise an exception. All were found only by checking output values
explicitly. A failing loudly is fine; failing quietly is not.

**What it checks:** the Earth Engine script parses and its comments balance; no
dead dataset ids; no `ee.Algorithms.If` in executable code (comments stripped,
so it does not match the comment documenting the bug); the MapLibre worker file
exists; no blank GeoJSON is being served; the Landsat footprint is what we think
it is.

**Impact:** `node --check` is now run inside the project rather than by hand,
and the comment-terminator bug cannot ship again unnoticed.

## D33 — OPEN PROBLEM: transect geometry is not yet sound

**Date:** 2026-10-17
**Status:** UNRESOLVED. Recorded here because a wrong-but-plausible number is
more dangerous than a missing one.

**What the Landsat record exposed.** With 37 years the measured erosion came out
at 8.4 m/yr for Landsat against 63.4 m/yr for Sentinel-2. Both cannot be right.
Investigating produced three findings.

**Finding 1 — the cross-sensor check PASSES, and is reassuring.**
| metric | result |
|---|---|
| mean IoU | **0.86** |
| mean water-area difference | **+1.4%** |
| bankline offset between sensors | **0-30 m** |
| total area changed, same year-pair | ratio 0.94-1.09 (ratio 1.0) |

Two independent instruments, different resolutions and dates, agree on where the
water is and on how much it changes. The masks are good.

**Finding 2 — the measurement zones are mostly NOT on the river.**
Checking how much water each measuring zone actually contains: many zones return
**0% water**. A zone sitting on dry land can only ever report "no change". This
is why Landsat reported medians near zero.

**Finding 3 — root cause: a single global PCA axis is wrong for a diagonal river.**
Median "belt width" comes out at **18 km**. The real Jamuna belt is about 9 km.
The reach runs diagonally, so one fixed "across-flow" direction is not across the
river anywhere in particular: near the ends of the diagonal a transect bin spans
the whole belt, and the derived bank edge lands on a dry corner.

**What this invalidates.**
The earlier Sentinel-2 figures (median 38-76 m/yr) were cross-validated at
+0.92 correlation - but that compared two quantities produced by the SAME flawed
geometry, so they agreed with each other while both being wrong. Agreement
between methods is only evidence when the methods do not share a failure mode.
**The +0.92 must not be cited as validation of the absolute numbers.** It remains
valid as evidence that the two measures move together over time.

**Attempted fix (in progress, incomplete).** Build transects perpendicular to the
river's own centreline: skeletonise the belt, walk the skeleton end to end,
place N transects at equal arc-length intervals, and use the local tangent.
Added `transects.centerline()` and `transects.walk_skeleton()`. The skeleton walk
currently stalls after 1 km because the greedy heading-continuation heuristic
dead-ends on the braided network. NOT yet producing usable geometry.

**Rejected:** publishing the 8.4 or 63.4 m/yr figures as results. They are not
yet trustworthy.

**Impact:** this is now the highest-priority work in the project. Everything
downstream - features, model, forecast - depends on the label being right.

---

## D34 — Transect geometry REBUILT and validated (supersedes D33's geometry)

**Date:** 2026-10-17
**Decision:** Replaced the global-PCA transect construction entirely.

New construction (`ml/transects.py`, rewritten):
1. **Centreline that follows the river.** Belt is gap-bridged and hole-filled,
   then a distance transform is taken; the deepest pixel of each slice along the
   flow axis is the thalweg, and the sequence of those points is the centreline.
   A depth gate (150 m) stops it diving into floodplain creeks.
   *Rejected:* skeleton longest-path walk - it follows whichever branch is
   longest and zig-zagged across the braided network, giving a 51 km "centreline"
   for a 30 km river. Distance-transform ridge gives 37 km and cannot jump
   between channels.
2. **Transects perpendicular to the LOCAL centreline direction**, every 500 m,
   built ONCE and reused for every year and both sensors.
3. **Length capped** at the local belt width + 800 m margin, hard cap 12 km.
4. **Quality gate:** both edges must be found, water fraction >= 0.25, wetted
   width 1.2-13 km. Every drop is reported with its reason.
5. **Edge definition:** the belt edge is where a *smoothed* water profile (300 m
   window) stops exceeding 0.35. Three earlier definitions were tried and
   rejected: first/last water pixel (width depends on where a bar falls),
   contiguous run (measures single ~2 km channels, not the ~6-9 km belt), and
   2nd/98th percentile (leaves a water tail outside the reported edge by
   construction, so it never lands on a real boundary).

**Validation (`ml/10_verify_geometry.py`, runs automatically):**
- Spot check of 7 transects: **6 PASS**. Each has water between the measured
  edges (36-86%), **0% water beyond them**, and a genuine land-water transition
  at both edges. The single failure (transect 12) cuts a wide sandbar.
- Belt width now 4.1-11.1 km, median 6.5 km - physically sensible. It was
  reporting 18 km before.
- Writes `reports/transects.geojson` and `reports/transects_overlay.png` so the
  geometry can be inspected visually.

**The +0.92 correlation from earlier is WITHDRAWN as validation of absolute
values** (D33). Agreement between two measures that share a failure mode is not
evidence.

---

## D35 — OPEN PROBLEM 2: the two sensors disagree by 3x on erosion rate

**Date:** 2026-10-17
**Status:** UNRESOLVED. Root cause identified, fix not yet found.

**What was measured.** Both sensors, same fixed transects, same overlapping
years 2019-2026:

| check | result |
|---|---|
| mean IoU (same year, same place) | 0.86 |
| mean water-area difference | +1.4% |
| total area changed, same pair | ratio 0.94-1.09 |
| **EPR rate ratio Landsat/S2** | **3.28x** |
| **EPR rate correlation** | **-0.10** |

So the sensors agree about WHERE the water is and HOW MUCH area changes, but
disagree about how fast the bank moves, and they do not even agree on which
years were worst.

**Root cause.** On one fixed transect, for 2023:
- Sentinel-2 reports the belt **5.09 km** wide
- Landsat reports the belt **1.80 km** wide
- both with high water fraction (86% and 82%), so both genuinely see water

The belt is defined as the largest connected water body. At 10 m a narrow
connection between the river and the floodplain survives the speckle filter, so
Sentinel's connected body extends into the floodplain; at 30 m that same
connection is smoothed away and Landsat's body stops at the true channel. The
belt therefore differs by ~3 km, and any rate measured across it inherits that
difference.

**Attempted fix, partial.** Measuring the outer edge on the *belt* instead of the
raw water mask removed the isolated-pond failure, but not this one, because these
floodplain bodies are genuinely connected, not isolated.

**Options for the owner to decide (see CURRENT.md):**
1. Use one sensor for the headline analysis (Landsat, 35 years, consistent) and
   treat Sentinel-2 as mask validation only, accepting that a 10 m/30 m rate
   comparison is not currently meaningful.
2. Restrict the belt definition to water connected within a bounded distance of
   the centreline, so floodplain spill is excluded identically for both.
3. Build separate transect geometry per sensor at its own native resolution, and
   compare rates only at matched along-river positions.

**Rejected:** reporting either sensor's rates as final until this is resolved.

---

## D35 — RESOLVED: the 3x sensor disagreement was a resolution bug, not a method problem

**Date:** 2026-10-17
**Status:** CLOSED. Supersedes the open problem in D35.

**Root cause (exact).** `measure_edges()` sampled the mask using `ts.res` - the
resolution of the sensor the GEOMETRY was built from (Sentinel-2, 10 m) - while
measuring a Landsat mask on a 30 m grid. Every cast was therefore compressed to
one third of its intended length, so Landsat's belt came out at ~1.8 km where
Sentinel-2 measured 5.1 km for the same year.

The decisive evidence: the two water masks were **identical bin by bin** along the
transect (65/100/100/100/100/100/85/65/31/100/27/19 percent vs
67/100/100/100/100/100/100/56/33/100/33/22 percent). Only the sampling was wrong.

**Two wrong hypotheses were tested and rejected first, both instructive:**
1. *"Speckle filter is too aggressive at 30 m."* Rejected: results were identical
   at OPEN_M = 0, 20 and 40 m.
2. *"Hole filling is resolution dependent, so define the belt geometrically."*
   Partly true - a sandbar is an enclosed hole at 10 m but not at 30 m - but it
   was not the cause of the 3x gap. The geometric edge rule was kept anyway
   because it is simpler and has no connectivity assumption, but it is not what
   fixed the numbers.

**Fix:** sample with `C.sensor_res(sensor)`, the mask being measured.

**Result after the fix:**

| metric | before | after |
|---|---|---|
| belt width ratio LS/S2 | 0.35x | **1.00x** (17 of 18 transects within 15%) |
| EPR rate ratio LS/S2 | 3.28x | **0.98x** |
| EPR rate correlation | -0.10 | **+0.96** |

This is now a genuine validation: two instruments, different resolutions, dates and
orbit paths, measuring the same fixed transects and agreeing on both the magnitude
of movement and which years were worst. Unlike the withdrawn +0.92 figure, these
two methods share no geometry and no sampling bug.

**Recomputed headline numbers (D34 geometry, corrected sampling):**
- Sentinel-2, 7 pairs: median **56.6 m/yr** (IQR 21-116)
- Landsat, 35 pairs: median **109.8 m/yr** (IQR 47-190)

---

## D36 — Two RGB-based validation attempts failed legitimately

**Date:** 2026-10-17
**Decision:** Do not use colour brightness or greenness as a pass/fail check on
this river. Keep imagery for VISUAL checking only (`reports/transects_overlay.png`).

**Reason:** both plausible assumptions are false for the Jamuna:
- *"Water is darker than land."* No. The river is extremely turbid; silt-laden
  water is pale tan and can be brighter than dark floodplain vegetation.
- *"Water has less green than land."* No. Vegetated sandbars sit INSIDE the belt
  while the floodplain beyond it can be bare silt, so the sign can reverse.

The check that works is against the mask itself: water between the measured
edges, ~0% beyond them, and a genuine transition at both edges. That passes 6 of
7 sampled transects; the one failure cuts a wide sandbar.

**Lesson:** a validation check must be validated too. Two checks were written,
both passed silently-wrong logic, and both were only caught by asking "would this
also pass on the wrong answer?"

---

## D37 — Old +0.92 correlation permanently withdrawn

**Date:** 2026-10-17
**Decision:** the "+0.92 correlation between EPR and outline distance" figure
reported earlier must not be cited anywhere.

**Reason:** it compared two quantities produced by the SAME broken geometry and
the SAME wrong sampling resolution. Agreement between methods that share a
failure mode is not evidence - it was agreeing because both were wrong the same
way. The current validation (D35) replaces it: independent instruments, no shared
geometry, no shared bug.

---

## D38 — Hydrology source: ERA5-Land (easy) offered, GloFAS (real) prepared

**Date:** 2026-10-17
**Decision:** Prepare both, start with ERA5-Land because it needs no new account.

**Finding that shaped this:** GloFAS river discharge is **not available in
Earth Engine**. It is a NetCDF download from the Copernicus Climate Data Store
which requires a free CDS account and an API key. The Earth Engine catalog only
carries GloFAS *Flood Hazard Maps*, which are flood extent, not discharge time
series. So the "one more GEE export" assumption behind D19 was wrong.

**What is actually available:**

| source | in GEE? | what it is | effort |
|---|---|---|---|
| **ERA5-Land** `ECMWF/ERA5_LAND/DAILY_AGGR` | yes | runoff, rainfall, radiation, wind; 1950-present; 0.1 degree | paste + run, no account |
| **GloFAS v2.1** | **no** | real daily discharge m3/s; 1979-present; 0.1 degree | free CDS account + API key |

**Files written:**
- `gee/hydro_export.js` - ERA5-Land export, one small GeoTIFF per year over a
  catchment box around the reach (88.5-91.0E, 23.5-25.5N), same dry-season window
  as the imagery. 8 bands: runoff, surface and subsurface runoff, precipitation,
  solar radiation, potential evaporation, and both wind components.
- `ml/11_hydro_features.py` - joins those files to the feature table. Adds each
  band's level, year-on-year change, and anomaly against the record so far.
  Enforces the same no-leakage rule: a row may only use hydrology up to its own
  year.
- `ml/12_glofas_discharge.py` - CDS download for real discharge, with monthly,
  annual, dry-season and monsoon-peak summaries. Exits with instructions if the
  `cdsapi` package or `~/.cdsapirc` is missing.

**Honest limitation, to be stated in the write-up.** ERA5-Land is ~11 km
resolution. These are **catchment-scale forcing proxies, not measurements of the
Jamuna**. That is the right scale for the physics that moves a bank, but it is a
proxy and must not be described as discharge.

**Why this is still the right next step.** The 35-year Landsat record did NOT fix
predictability (persistence 126.5 MAE vs predict-the-mean 80.6; best feature
correlation -0.12). Adding more imagery cannot help, because every feature so
far is a lagged outcome, and on a braided river hotspots migrate rather than
persist. Forcing is a different kind of variable and is the only category of
feature we have not tried.

---

## D39 — GloFAS access details corrected after checking the live catalogue

**Date:** 2026-10-17
**Decision:** Rewrite `12_glofas_discharge.py` against the verified CDS/EWDS
endpoint. Three things in the first version were wrong.

**Corrections, each verified against the Copernicus documentation:**

1. **Wrong dataset.** `reanalysis-era5-single-levels` is ERA5, not GloFAS, and
   GloFAS is not in Earth Engine at all. The correct dataset is
   **`cems-glofas-historical`**.
2. **Wrong API host.** GloFAS is served from the **CEMS Early Warning Data
   Store** at `https://ewds.climate.copernicus.eu/api`, not the main
   `cds.climate.copernicus.eu/api`. Using the main host would fail.
3. **`upstream_area` is not a variable of this dataset.** It is a separate
   ancillary dataset. Requesting it would be rejected. The script now identifies
   the correct grid cell by choosing the highest-median-discharge cell inside the
   box, and prints the chosen cell and the median so it can be sanity checked.

**Also added, because they will otherwise cost the owner time:**
- Licence acceptance is a MANUAL step on the dataset page and cannot be done in
  code. Documented as a required step, with the URL.
- One year per request. Requesting 42 years of daily data in a single call will
  be rejected or time out.
- **Resumable**: a run that dies halfway skips years it already has.
- `cdsapi>=0.7.7` is required (and installed). Confirmed
  `cdsapi.Client(url=...)` is the supported signature.
- A plausibility check: Jamuna at Kazipur should be roughly 200-60,000 m3/s. If
  the median comes out wildly different, the wrong cell was chosen and the
  script says so.

**Verified as far as possible without credentials:** the script runs, imports
cleanly, and stops with correct, actionable instructions at the missing
`~/.cdsapirc` step. The network calls themselves cannot be exercised from this
machine (no outbound network in the shell), so the first real run is the actual
test.

**`11_hydro_features.py` now consumes either source** - GloFAS if present,
ERA5-Land otherwise - and prints correlations for both so the effect of each is
visible separately.

## D40 — One year per request (confirmed by the service), plus a hand-download mode

**Date:** 2026-10-17
**Decision:** `YEARS_PER_REQUEST = 1`, and add `--from-files` so NetCDFs
downloaded by hand from the CDS website form are read directly.

**Reason:** Saad tested the form and multi-year selection is rejected — the form
turns red. So the earlier 5-year chunking was optimistic and is reverted to a
single year per request, 38 requests for 1989-2026.

**Year range trimmed** from 1985-2026 to **1989-2026** to match the Landsat
record. Discharge before 1989 has no imagery to pair against and would be
unused.

**`--from-files` added** after learning the form route is the one in play. The
old reader rebuilt column names by position (`allf.columns[-3]` etc.), which
breaks the moment the service changes coordinate naming or the file comes from
the form rather than the API. Replaced with `normalise()`, which finds columns
by meaning: latitude/lat, longitude/lon, time/valid_time/date. Filenames are now
irrelevant, so files can be dropped into `data/raw/hydro/` as downloaded.

**Verified:** built a synthetic NetCDF deliberately using the awkward
`valid_time`/`latitude`/`longitude` naming, confirmed `--from-files` parsed all
3294 values (366 days x 9 cells), selected a cell, passed the plausibility check
and wrote the annual CSV. Synthetic files then **deleted** — leaving fake
discharge in that folder would have silently joined fake hydrology into the real
feature table.

## D41 — Four bugs found by inspecting the first real GloFAS file (1989)

**Date:** 2026-10-17
**Trigger:** Saad downloaded 1989 and asked for a check. Inspecting the actual
NetCDF (rather than trusting the synthetic test) exposed four problems. All four
would have silently corrupted the result, and the synthetic test missed every one
of them because it was built from my own assumptions.

**1. The variable is `avg_dis`, not the catalogue label.**
The Copernicus form writes the GRIB short name `avg_dis` ("Time-mean discharge
from rivers or streams"). The code matched variable names containing the word
"discharge", so it would have skipped all 38 real files. `find_discharge_var()`
now falls back to matching the `long_name` attribute.

**2. Missing NetCDF4 backend.**
The real files are NetCDF4/HDF5. xarray raised "found the following matches ...
dependencies may not be installed" and could not open them. `netcdf4` installed.
The synthetic file had been written with an older default format, which is why
this did not show up earlier.

**3. Year-boundary leak — one day per file into the wrong year.**
GloFAS time-mean stamps run 2 Jan to 1 Jan of the next year. That trailing day
was being counted as the first day of the following year, so every file would
have donated a stray day to the next year's average. `fix_year_edges()` drops a
lone date on the far side of the boundary. First attempt at this was a clever
`pipe` chain that silently re-indexed by row count and never fired; rewritten as
a plain loop and verified (the 1990 row that had `min=mean=max=4577.4`, i.e. a
single day, is gone).

**4. Wrong cell — it was picking the Ganges, not the Jamuna.**
The original rule was "highest median discharge in the box". The request box
(23.5-25.5N, 88.5-91E) also contains the Ganges and the Padma below the
confluence, and those are bigger, so it returned 23.775N — a different river.
Now restricted to a 0.45-degree window around the study reach (24.50N, 89.74E)
and picks the nearest cell carrying real flow: **24.525N 89.725E**, 0.02 degrees
from the reach. This one matters scientifically, not just technically.

**Verified plausible against the physics:** monthly means run Jan 3,547 -> Feb
5,172 -> Jul peak 66,385 -> Dec 5,160 m3/s. That is the expected Himalayan
snowmelt-plus-monsoon shape. The annual median of ~17,300 initially looked
alarming but is correct for a hydrograph this seasonal - roughly half the year
sits above it. Mean annual 24,394 m3/s for 1989 is on the high side (1989 was a
severe flood year and GloFAS v4.0 is known to overestimate in some basins), so
discharge should be treated as a relative forcing signal, not a measured truth.

**Lesson recorded:** testing against a file I generated myself only proves the
code handles what I already assumed. The first real file was worth more than the
synthetic one.

## D42 — GloFAS API request schema read from the service, not guessed

**Date:** 2026-10-17
**Trigger:** Saad saved the CDS token and asked the script to do the downloads.
The first run failed. The dataset id, host and credentials were all correct (the
server returned a parameter error, not a 401), but the request was wrong.

**Root cause: guessing parameter names.** The first request used `data_type`,
`version`, `format` and a variable called `river_discharge_in_the_last_24_hours`.
None of those exist in the current API.

**Fix:** fetched the machine-readable description of the dataset's own process
and used it verbatim:

    GET https://ewds.climate.copernicus.eu/api/retrieve/v1/processes/cems-glofas-historical

**Correct request:**

    variable:            ["average_river_discharge_in_the_last_24_hours"]   (array)
    product_type:        ["consolidated"]        (was "data_type")
    system_version:      ["version_4_0"]         (was version: "4.0")
    timespan:            ["time_mean"]           (was missing)
    hydrological_model:  ["lisflood"]            (was missing)
    data_format:         "netcdf"                (a string, NOT an array)
    download_format:     "unarchived"            (was missing)
    area / year / month / day: unchanged

The service itself confirms this was the intended fix - it returns the notice
"Due to changes in the data structure of the cems-glofas-historical dataset,
previous API requests may no longer work."

**Verification that matters:** the API download for 1989 is **byte-identical**
to the file Saad downloaded by hand from the website form - both 1,157,262
bytes, both md5 `9aace9ff6a1681dd2ac05e249c03df71`. The two routes agree exactly,
so the form route already in progress is trustworthy and the API route can take
over.

**Also fixed:** a `NameError` in the chunk-to-single-year fallback path, and the
downloaded-file reader now globs every `.nc` rather than expecting our own
filenames, because the service assigns hash-based names to what it returns.

**Note on GloFAS v4.0:** `system_version` also offers `version_5_0` (released
2026-07). Staying on 4.0 for continuity with the already-downloaded 1989 file.
Flagged for later sensitivity testing, not switched mid-record.

**Practical note:** one year takes roughly 6 minutes of server time. The
network on this machine is intermittent, so the client retries; runs are
resumable and skip years already on disk.

## D43 — API also caps at one year per request (403), plus duplicate-file guard

**Date:** 2026-10-17
**Finding:** After the request schema was corrected (D42), a 10-year chunk was
refused with **HTTP 403 Forbidden**. So the one-year limit is enforced by the
service itself, not merely by the website form - Saad's observation about the form
turning red was pointing at a real server-side cap all along. The automatic
chunk-to-single-year fallback did its job and the run continued without
interruption. `YEARS_PER_REQUEST` is now pinned to 1.

**Client tuning:** the default cdsapi backoff is 500 attempts with 120-second
sleeps. This machine's DNS is intermittent, and the client kept reporting the
original failure long after the network had recovered, because it was asleep.
Changed to `retry_max=30, sleep_max=20` so it notices within seconds.

**Duplicate guard added.** The same year can legitimately arrive twice - by hand
from the form and from the API - and 1989 already had arrived both ways. Counting
a year twice would quietly distort its annual summary, so files are now hashed
(md5) and byte-identical copies are skipped with a message. For 1989 the two
copies are confirmed identical (md5 `9aace9ff...`), so no information is lost.

**Process note:** two of my own bugs in this file were introduced by scripted
string replacement that silently failed to match, leaving the file in a state I
assumed was correct. Both are now fixed with edits that fail loudly. Worth
remembering: a silent no-op in a bulk edit is indistinguishable from success
unless you re-read the file.

## D44 — Real GloFAS discharge does not predict bank erosion (honest negative result)

**Date:** 2026-10-17
**Decision:** Keep GloFAS in the project as a documented negative result, and do
NOT ship a confident year-by-year erosion forecast. Reframe the deliverable
towards measured history plus relative risk and explicit uncertainty.

**The data is good.** 37 complete years (1989-2025) at 0.05 degree resolution,
cell 24.525N 89.725E, 0.02 degrees from the study reach. Daily values m3/s.
Plausibility confirmed: monthly means run Jan ~3.5k to a Jul peak of ~66k.
Independent check against known floods: the 2004 peak sits at the 97th
percentile of the 38-year record and 2020 at the 87th, which is the right
ordering for real GloFAS hydrology.

**But it carries no predictive signal for erosion:**

| test | result |
|---|---|
| global correlation, monsoon mean discharge vs erosion rate | +0.041 |
| global correlation, annual mean discharge | +0.017 |
| **within-transect** correlation, monsoon mean | **+0.049** (54% of 48 transects positive) |
| within-transect, annual mean | +0.044 |
| within-transect, dry-season mean | -0.031 |

The within-transect test is the correct one - it compares each transect only
against itself, so reach position cancels out - and it is flat. Roughly half the
transects positive is what random noise looks like.

**And nothing else beats the trivial baseline either** (1876 rows, Landsat):

| predictor | MAE (m/yr) |
|---|---|
| predict the global mean | **83.9** |
| each transect's own past average (leave-one-out) | 87.1 |
| each transect's own past median (leave-one-out) | 84.5 |
| same transect, previous pair (persistence) | 133.7 |
| previous 5-pair mean, predicting next 5-pair mean | 98.4 |

Leave-one-out correlation between a transect's past average and its next rate:
**-0.043**. Smoothing into 5-year windows does not rescue it (-0.090).

**Interpretation.** This is a real finding, not a plumbing failure. Bank erosion
here is driven by local flow geometry and sediment - where the bend attacks the
bank, bed shear, sediment supply - while GloFAS gives one catchment-scale
discharge value for a ~5 km cell. A single number cannot say where along the
reach the water bites. There is also a real spatial gradient underneath the
noise: transects in the fastest historical third average +23.5 m/yr against
-19.5 m/yr for the slowest third, a 43 m/yr spread. That is real, but small next
to the ~84 m/yr scatter of any single year.

**Consequence for the product.** The measured history is trustworthy and
independently cross-validated (Landsat 37 years, Sentinel-2 agreement, ratio
0.98x, r +0.96, 6/7 geometry checks). A *forecast* of which transect erodes how
fast next year is not supported by this evidence. Shipping one anyway would be
presenting noise as skill.

**What is defensible:** the retrospective record, a relative-risk ranking of
which stretches of river are eroding fastest, and an uncertainty band on any
projection. That is a weaker claim than "we predict next year's erosion", and it
is one the evidence actually supports.

## D45 - Product reframed to measured history + chronic risk (D44 follow-through)

**Date:** 2026-10-18
**Decision:** Stop building a forecast. Build and ship three things the evidence
supports: the measured record, a chronic-risk ranking, and a long-run trend with
error bars. Everything is labelled so the reader cannot mistake a trend for a
forecast.

**New artefacts**
- `ml/13_risk_and_forecast.py` -> `data/processed/risk/{transect_risk.csv,risk.geojson}`, `reports/RISK.md`
- `ml/06_predict_geojson.py` rewritten -> `longrun_trend_<h>yr.geojson`
- `GET /api/risk/`, `GET /api/risk/summary/`, `GET /api/predictions/?horizon=`

**Three methodological choices made while building, each of which changed the answer**

1. **A minimum history of 10 years is required before ranking.** Without it the
   "worst chronic hotspot" was a transect with **one** usable year of +165 m/yr,
   and the top of the ranking was entirely 1-5 year records. That is noise
   presented as long-term exposure. 64 of 102 records qualify; the other 38 are
   kept, flagged `sufficient=False`, and excluded from the ranking. This is
   flagged as an assumption - the threshold is a judgement call, chosen so that
   a decade is the shortest span over which a braided river's behaviour is
   arguably stable.

2. **The interval is a block-bootstrap percentile interval for the MEDIAN**, not
   a normal interval for the mean. Two reasons. The ranking is done on the
   median (one extreme year must not reorder the river), so the interval has to
   answer the same question - an earlier version showed a median of +0.0 m/yr
   beside a range of -668 to -33, which is not a coherent statement about
   anything. And resampling in blocks of 3 consecutive years preserves the
   serial dependence that a plain bootstrap would destroy.

   Consequence, stated plainly: with the honest interval only **3 of 64**
   eligible records are distinguishable from zero, down from 7 under the
   mean-based interval. Even the top-ranked chronic hotspot cannot be called
   statistically distinct from no change. That is the truthful state of the
   evidence and it is reported rather than smoothed over.

3. **All eligible trends are drawn, not only the significant ones.** Showing
   only the 3 would imply the other 61 were measured and found normal, which is a
   different and stronger claim than "we could not distinguish them from zero".
   Significance is carried as a feature property so the map can style them
   differently.

**Errors found and fixed while building**
- `06_predict_geojson.py` called `T.frame()`, `T.bank_positions(mean, uvec,
  vvec, halfbin, bins, ...)`, `T.REF_YEAR` and `bins` - all removed in the
  transect rewrite. It could not run at all. Rewritten against
  `build_transects()` / `bank_positions(ts, year, sensor)`.
- `07_validate.py` read the stale pre-rewrite `features/features.csv` (280 rows,
  8 years) and reported it as current, and repeated the withdrawn +0.92. It also
  mislabelled a worst *pair median* as the "worst single transect". Rewritten
  around the cross-sensor comparison and with the withdrawal stated explicitly.
- The stale 280-row table was itself a live trap - it sat beside the real
  per-sensor tables and was referenced by `07_validate.py` and the Colab notes.
  Moved to `data/archive/features_pre_rewrite_280rows.csv` and a standing check
  added so it cannot reappear.
- `09_checks.py` gained sections 7-9 covering the stale-artefact trap, the
  honesty labelling of the trend GeoJSON, and GloFAS completeness.

**Still honest to state:** the 10-year trend bands are very wide (e.g. transect 21
projects +576 m over 10 years with a range of -1350 to +2547). That width is the
finding, not a defect in the drawing.

## D46 - UI relabelled; the word "forecast" removed from the interface

**Date:** 2026-10-18
**Decision:** The frontend no longer offers a "forecast" toggle. It offers
**chronic risk** and a **10-year long-run trend**, and a permanent card states
that year-to-year erosion was tested and found unpredictable.

**Reason:** the old UI read `/api/predictions/` expecting `predicted_rate` and
`predicted_year`, so after the D45 rewrite it would have rendered nothing
correctly while still being labelled a forecast - the worst combination, a
control that lies. Beyond that, a button reading "2027 forecast" invites a reader
to accept a claim the evidence does not support, regardless of what any report
says.

**Changes:**
- New risk layer from `/api/risk/`, width scaled by long-run rate, opacity split
  so statistically significant records are solid and the rest faded
- Trend layer filters to `kind == 'long_run_trend'`; the file also carries the
  measured bankline each projection was built from, and drawing that in dashed
  "forecast" styling would misrepresent where the projection actually is
- On-screen note reports the real counts ("3 of 64 statistically distinguishable
  from zero") rather than hiding them
- `App.css` gained `.note-card` styling

**Build verified:** `npm run build` clean. Frontend 200 on :5173, all API routes
200 on :8010 including `/api/risk/`, `/api/risk/summary/`, `/api/predictions/`.

**Note on the Colab notebook.** `notebooks/colab_train.md` no longer trains a
forecasting model. It now runs RandomForest and GradientBoosting against the
83.9 m/yr baseline under `GroupKFold` split **by transect**. Grouping by transect
matters: splitting randomly would put part of a bank in training and another part
of the same bank in testing, letting the model memorise where that bank tends to
erode. That leak is what makes erosion models look excellent and generalise to
nothing.

**A deliberate oddity in that notebook:** the first code block is invalid Python
(`from sklearn.dribble import make_pipeline`) and says so, with the working block
immediately after. It exists so that pasting the wrong block fails loudly. If
that reads as sloppy rather than useful, it should be deleted.

**Open item for the owner:** run that notebook and paste back the three MAE
numbers. That is the only remaining task requiring the owner's hands.

## D47 - Model test run locally: no model usefully beats "predict the average"; notebook feature-set bug fixed

**Date:** 2026-10-18

**Decision:** Three things.

1. The RandomForest / GradientBoosting test that `notebooks/colab_train.md`
   was waiting on was **run locally** as `ml/14_model_test.py` instead of
   Colab. scikit-learn 1.9.1 was installed into `.venv` for it. 1.9k rows with
   GroupKFold fits in ~80 s on this laptop, so the "needs Colab" premise was
   wrong for this job size. The Colab notebook remains for independent
   reproduction and was fixed in the same pass (point 3).

2. The published comparison bar is now the **per-fold median dummy**, not only
   the mean. For MAE the optimal constant predictor is the median, and this
   label is heavy-tailed (median 0.0 m/yr, p99 of |rate| 414 m/yr), so the
   median dummy (83.5) is a strictly harder bar than the mean dummy (84.0).
   A model must beat the *median* baseline to count as signal.

3. `notebooks/colab_train.md` had a bug: its comment said "NOT a quantity
   measured in the same year as the label", but its `LEAKY` set only excluded
   ids, so the models were actually fed five columns measured during the
   target interval (`other_side_rate`, `width_m`, `width_change_pct`,
   `width_ratio`, plus all same-year forcing). The notebook now runs three
   feature sets - FORECAST-ONLY (start-of-year information only, with
   previous-year discharge/stage derived as `q_x - q_x_chg` and
   `stage_km2 - stage_change_km2`), +SAME-YEAR FORCING, and AS-FIRST-WRITTEN
   kept as a demonstration - against both dummies. The deliberately broken
   first code cell (`sklearn.dribble`) was deleted: a notebook that errors on
   purpose is a trap, not a check.

**Measured** (GroupKFold by transect; 5 folds for the headline; seeds 0/1/2
and 5/10/20 folds for robustness; n=1876, 51 transects, 1989-2026):

- mean dummy 83.99-84.04, median dummy 83.50, global mean 83.94
  (the published 83.9 reproduces)
- RandomForest, FORECAST-ONLY: 83.42 at 5 folds (seed 0), ranging
  83.28-84.39 across seeds and fold counts - it ties the median dummy and
  drops below the mean dummy at 10 folds
- GradientBoosting, FORECAST-ONLY: 86.91, worse than every baseline in all
  settings
- prediction-vs-observation correlation r = +0.28 (r2 about 8%) for both
  models - reproducible across seeds, but it does not translate into MAE
- the five suspected same-interval columns correlate with the label at only
  r = -0.05..+0.01 (n=1876), so the old notebook's bug did NOT fake a win.
  They are excluded from the honest test on timing grounds (unavailable
  before the year starts), not because they cheated it

**Conclusion:** the no-signal finding is confirmed with real models, not just
correlations. Nothing usefully beats predicting the average; the best model
edges the mean baseline by at most 0.7 m/yr (under 1%), loses that edge
against the median baseline, and flips above both at other fold counts. The
faint r = +0.28 is consistent with hotspots persisting slightly within the
38.8 km reach, but it is far too weak to forecast with.

**Reason:** the notebook's own honesty rule - a hair-width win on one split is
not a finding - needed to be made mechanical: median dummy on the board,
seeds and fold counts swept, verdict text tied to the harder bar.

**Rejected:**
- keeping the mean dummy as the only bar (a model can "beat the average" by
  learning nothing more than predict-the-median)
- trusting a single 5-fold single-seed result in either direction
- restoring any forecast product on the strength of r = +0.28
- keeping the deliberately broken code cell

**Impact:** the headline number 83.9 m/yr stands unchanged; VALIDATION.md
section 5 now carries the model result; the owner's Colab run is no longer a
blocking item, only an optional reproduction. One new fact for the write-up:
`sklearn` is now a project dependency (1.9.1 in `.venv`).

**Assumption flag:** none of the numbers above are assumptions. The
interpretation - that r = +0.28 reflects partial hotspot persistence rather
than measurement artefact - is interpretation, and should not be presented
as a finding.

## D48 - Reach-specific transect gates, and the Ganges as a generalisation trial

**Date:** 2026-10-18

> **RECONSTRUCTED.** Written after the fact on 2026-10-18. The number D48 was
> cited twice - in `ml/config.py` and `ml/transects.py` - but no entry was ever
> recorded under it. Recovered from those surviving references. Marked as a
> reconstruction on purpose: this log is the authoritative account of why the
> pipeline works as it does, and an unmarked reconstruction would quietly
> degrade it.

**Decision:** Geometry constants that describe *how to take a measurement* - the
depth of an EPR zone, the along-flow half-width of a transect, the clamps on
cast length and channel width - are held **per reach**, not globally. Each reach
declares its own gates in `config.REACHES`, and the Jamuna keeps the original
defaults (its gate set is empty).

**The Ganges is the generalisation trial.** The single-thread meandering
Rajshahi - Hardinge Bridge reach, 1-4 km wide, is where bank movement is
*expected* to persist year on year. **That expectation is a hypothesis from the
literature, not a finding.** It exists to test whether a method developed on one
river transfers to another, rather than being tuned to a single site.

**Ganges constants are first guesses**, scaled down from the Jamuna's for a river
1-4 km rather than 9 km wide. They are to be verified against the first real data
with `10_verify_geometry.py` spot checks before anything is concluded from them.
No Ganges imagery has been downloaded.

**Reason:** The same numeric constant is not the same *measurement* on a 300 m
river and a 9 km river. A zone depth or a width clamp that is sensible on one is
either uselessly small or physically meaningless on the other. Binding the
constants per reach makes that explicit and stops a value tuned on one river from
silently governing another - a failure mode this project has already hit twice
(the pond leak, D55, and the EPR sign inversion, D58).

**Impact:** Reaches can differ geomorphologically without forking the pipeline.
The Ganges tier is configured but unverified, and `ganges` remains registered
with no data.

## D49 - Reach switched from the Jamuna to the Arial Khan (Madaripur Sadar - Muladi)

**Date:** 2026-10-18
**Decision:** The primary reach becomes the Arial Khan, box 89.80-23.45 to
90.15-23.65. The Jamuna is retained unchanged as the documented negative result
that motivated the switch, not deleted.

**Why this is a test of the hypothesis, not just a different river**

D44 diagnosed the specific reason discharge failed on the Jamuna: the belt is
~9 km wide and braided, so a single GloFAS cell (~5.5 km) cannot say *where*
along the reach the water attacks the bank. The Arial Khan averages **300 m
wide and is single-threaded**, so the reach fits inside one cell and reach
discharge is approximately cell discharge. The diagnosed cause is removed.

Supporting the choice: published migration is ~21 m/yr (0.66 km over
1993-2024, Muladi and Babuganj upazilas) against the Jamuna's ~110 m/yr. Slower
movement on a single thread should persist rather than migrate, which is exactly
the condition under which lag features should have skill.

**Expect the headline numbers to fall.** Medians will drop by roughly a factor of
five. That is the correct river, not a broken pipeline, and it must not be
"fixed" by retuning thresholds to recover the old magnitudes.

**Cautions recorded BEFORE any data exists, so they cannot be forgotten**

1. **GloFAS may not work here.** At Madaripur a 5.5 km cell contains both the
   Padma and the Arial Khan, so the cell's dominant discharge may be the Padma's
   rather than the distributary's. On the Jamuna the largest river in the box
   *was* the Jamuna; here it is probably not. If the chosen cell tracks the Padma,
   discharge must be dropped and ERA5 precipitation used as the forcing instead.
   **Do not assume the switch fixed the discharge problem - it fixed the
   scale mismatch, not the possibility that the cell is dominated by another
   river.**
2. **The MNDWI threshold is unverified.** 0.2 was tuned on a 9 km Jamuna belt.
   At 30 m a 300 m river is ~10 pixels wide, so there is little room. The GEE
   console table prints water fraction per year precisely so this can be caught.
3. **Geometry constants are unverified guesses.** Every gate in the reach config
   is scaled down for a 300 m river (SPACING 500->250 m, ZONE_M 1000->300 m,
   MIN_WET_WIDTH 1200->100 m, MAX_CAST 12000->3000 m, and more). They must be
   spot-checked by `10_verify_geometry.py` against the first real imagery and are
   expected to need adjustment. Flagged as an assumption, not a result.

**A gate that would have silently destroyed the export**

`MIN_WATER` had to drop from 0.02 to 0.005. The Jamuna box is mostly river and
returned 14-18% water. This box is mostly farmland with a 300 m river in it, so
water is expected around 1-3%. Left at the Jamuna value, **every single year
would have been skipped and the export would have produced nothing** - while
looking like it had run fine.

**Cross-sensor validation is currently missing here.** Landsat is used for both
geometry and measurement, because one export unblocks the whole pipeline. The
Jamuna's credibility rested on two instruments agreeing (0.98x, +0.98). S2 for
2019-2026 is the natural follow-up and should be added once Landsat is verified.

**Changes made**
- `ml/config.py`: reach `arial_khan` registered; `CRS_WORK` is now per-reach
  instead of hardcoded (the reach straddles 90E). Verified all three reaches load
  and that the Jamuna's values are byte-identical to before.
- `gee/landsat_export_arial_khan.js`: new export script.
- `ml/09_checks.py`: now globs every `gee/*.js` instead of naming two, so a new
  per-reach export cannot ship unverified.

**Also note:** the GloFAS files already downloaded do NOT cover this reach - their
southern edge is 23.52N and the reach runs to 23.45N. A fresh request is needed
with a box shifted south, around [24.00, 89.70, 23.30, 90.30].

**Owner action required:** run `gee/landsat_export_arial_khan.js` in Earth Engine
and read the console table before exporting any task.

## D50 - Arial Khan reach fixed to the MIDDLE reach, at 10 m, with the Padma excluded

**Date:** 2026-10-18
**Decision:** Study box `90.08-23.25 to 90.45-23.60`, EPSG:32646, Sentinel-2 as
the primary sensor and the geometry source. Two export scripts prepared.

**A geography error I made and corrected.** I initially recommended "narrow the
box to Muladi". Muladi Upazila is at **22.915N 90.415E**, in Barisal District,
near the river's MOUTH - about **70 km downstream** of Madaripur. I had read
"higher migration rates in Muladi" from the 2024 paper and wrongly assumed it was
adjacent to Madaripur. Both places are on the Arial Khan, at opposite ends. The
error was caught only because the coordinates were looked up before an export
script was written; had it not been, an hour of the owner's time would have been
spent exporting the wrong reach.

**Why the middle reach instead of Muladi.** The lower reach branches near the
Tetulia and takes tidal influence. Both move the waterline for reasons unrelated
to erosion, which would reintroduce exactly the measurement ambiguity this switch
exists to remove. Muladi is kept as a literature comparison point instead. The
higher published migration rate there is not worth an ambiguous measurement when
accuracy is the stated objective.

**The single most dangerous thing about this box.** The pipeline keeps the
**largest CONNECTED water body**. The Padma runs only **21-32 km west** of the
Arial Khan along this reach. A box that clips it would quietly measure the Padma -
a bigger, more obviously-a-river river, producing entirely plausible output for
the wrong river, with nothing anywhere failing. The western edge is set at
90.08E, about 11 km clear. Both scripts print a warning and the preview must show
exactly one thin ribbon.

**Course computed from the offtake** (51.5 km SE of Goalanda Ghat, per BWDB):

| downstream | Arial Khan | Padma | separation |
|---|---|---|---|
| 0 km | 23.54N 90.18E | 23.43N 89.97E | 21 km |
| 30 km | 23.33N 90.37E | 23.17N 90.05E | 32 km |
| 60 km | 23.13N 90.56E | 22.91N 90.14E | 42 km |

**CRS: EPSG:32646, not 32645.** The box lies entirely east of 90E. Measured both
ways on this exact box, zone 46 gives 0.19-0.21% scale error against 0.22-0.25%
for zone 45. Both are far below a 10 m pixel, but there is no reason to take the
worse one.

**Sentinel-2 promoted to primary.** A 300 m river is ~10 px at Landsat's 30 m but
~30 px at S2's 10 m. On a narrow river that is the largest single accuracy lever
available, so geometry is built from S2 (`GEOM["sensor"] = "s2"`, ref year 2024)
and Landsat supplies the 37-year record plus the cross-sensor check. Cloud is
masked with the **SCL scene-classification band**, not a brightness test, because
this river's dry sandbars and bare floodplain are bright enough to trip one.
The Jamuna never needed this; a narrow, bright river does.

**Expected water fraction ~0.9%** (45 km of river in a 1468 km2 box). Gates set
for it: `MIN_WATER` 0.003 here, against 0.02 for the Jamuna which would have
skipped every single year of this export.

**A standing check added after a near-miss.** The Earth Engine scripts carry their
own hardcoded rectangle, so editing `config.py` without editing the scripts makes
every downstream number describe a different place - and nothing crashes.
`09_checks.py` section 7 now parses the `aoi` and `crs` out of every export
script for the active reach and fails if either disagrees with config. It caught
its own scoping bug on first run (flagging other reaches' scripts) before being
corrected.

**Still unverified until data exists:** the MNDWI threshold 0.2 (tuned on a 9 km
Jamuna belt, never tested on a 300 m river), and every geometry gate scaled for
this width.

## D51 - Box was 13 km too far north and caught the Padma (caught by preview)

**Date:** 2026-10-18
**Finding:** Saad previewed `s2_export_arial_khan.js` and reported "most of the
cyan is padma". He was right and my arithmetic was wrong.

**Root cause, and it is a clean one.** The Arial Khan bifurcates from the Padma at
**23.47N 90.107E**. My box ran to **23.60N** - thirteen kilometres NORTH of the
bifurcation. North of that line the water body simply *is* the Padma. And the
Padma is much wider than the Arial Khan, so it wins the pipeline's "largest
connected water body" test outright. The box was not merely clipping the Padma,
it was containing thirteen kilometres of it.

This was not a subtle drift. I had the bifurcation coordinate in hand and still
placed the northern edge above it, because I placed the box by interpolating the
river's course from Goalanda Ghat without checking it against the known
bifurcation point.

**Correction.** Box moved to `90.05-23.00 to 90.45-23.38`, lying entirely south of
23.47N and centred on the straight line between the two authoritative Wikipedia
coordinates (bifurcation 23.4721N 90.1066E, mouth 22.7596N 90.4356E). The chord
runs lon 90.15 to 90.32 across that latitude range, leaving roughly 0.10-0.13
degrees of margin to both edges.

**Recorded as a hard constraint in config.py** so it cannot be undone by accident:
the northern edge must never be moved above 23.47N. This is stated next to the box
itself and in both export script headers.

**What this says about the process.** Two things protected us, and both are worth
keeping:
1. The scripts print a warning and the preview is meant to be read BEFORE running
   tasks. Had the exports been run first, this would have produced ~30 years of
   perfectly plausible data for the wrong river, and nothing anywhere would have
   failed.
2. Coordinate estimates from secondary sources are not good enough for this
   project. My Padma course was derived, and it was wrong by enough to matter. If
   the next preview is also wrong, the box should be set from coordinates read
   off the Earth Engine map rather than computed again.

**Note on the box size.** 41 x 42 km holding roughly 30-35 km of channel. That is
a shorter reach than the Jamuna's 30 km comparable, but a narrow river needs a
narrower box to stay clear of its parent river, so this is the trade being made:
shorter reach, far better resolution and a defensible measurement.

## D52 - Study box is now drawn by the owner, not computed

**Date:** 2026-10-18
**Decision:** Both Arial Khan export scripts now use a rectangle the owner drags
on the Earth Engine map. A hardcoded `FALLBACK_BOX` is used only when nothing has
been drawn, and the script says loudly which one is in use.

**Reason.** My coordinate arithmetic has now produced a wrong box twice (D50, D51)
from secondary sources - inferred from Goalanda Ghat and from intermediate points
along a chord. Both errors were real, and the second one put 13 km of the wrong
river inside the box. Coordinate interpolation is not good enough to locate a
reach on a delta, where channels sit tens of kilometres apart and the parent
river is the obvious thing to accidentally select. The map is the ground truth.

**Answer to the owner's question - is a shorter reach still accurate?** Yes, and
the numbers are worth stating:

| reach | transects @250 m | measurements (2 sides x ~35 yr) |
|---|---|---|
| 5 km | 20 | ~1,400 |
| 10 km | 40 | ~2,800 |
| 20 km | 80 | ~5,600 |

The Jamuna produced 1,876 measurements over 30 km. **A 5 km stretch therefore
yields more data than the entire Jamuna run**, so statistical power was never the
binding constraint and shortening the reach costs nothing there.

Measurement accuracy *improves* with a smaller box: far lower risk of catching the
Padma, a sharper export over the same pixel budget, fewer competing water bodies
(ponds, beels) to confuse the mask, and fewer transects dropped for landing on a
sandbar.

**What actually limits the choice is bend count, not length.** Bank erosion
concentrates on the outer bank of bends. A straight 5 km would legitimately
measure almost nothing, which would be a true but uninformative result and could
not be generalised along the river. Guidance given: **8-15 km containing 4-5
meander loops.** Long enough to show along-river variation, small enough to stay
clear of the parent river.

**A check bug found while doing this.** `09_checks.py` section 7 silently skipped
both scripts once the code shape changed from `var aoi = ee.Geometry.Rectangle([...])`
to a `drawn || FALLBACK_BOX` form - it just `continue`d on no match. A check that
goes quiet is worse than no check, because it reads as a pass. It now handles
both forms and reports a FAIL when a reach script has no parseable box at all.

## D53 - Landsat measured in 5-year blocks on the Arial Khan; Jamuna data archived not deleted

**Date:** 2026-10-18

### 1. Measurement window is now resolution-driven, per sensor

`C.PAIR_STEP` in config.py. Landsat 5 years, Sentinel-2 annual, on the Arial Khan.

**Why, in the project's own units.** The river erodes ~21 m/yr:
- Landsat 30 m -> **0.7 pixels per year.** A single year may not cross even one
  pixel boundary, so an annual pair measures which side of a boundary the bank
  happened to fall on. Comparing two years gives +-sqrt(2) px = **+-42 m of
  uncertainty against a 21 m signal.**
- Sentinel-2 10 m -> **2.1 px/yr**, +-14 m against 21 m. Usable.

5-year blocks put Landsat at ~3.5 px of real movement per measurement, which is
solid. The Jamuna keeps annual pairs because it erodes at ~110 m/yr = ~3.7 Landsat
pixels per year, so annual measurement was never marginal there. This is not a
change of taste; it follows from the pixel size and the published rate.

**Consequence worth stating plainly:** on this river the 37-year Landsat record
supports a LONG-TERM TREND measured in 5-year steps, not an annual time series.
Anyone reading the output as annual erosion on the Arial Khan would be reading
noise. 04_erosion.py and 05_features.py both route through `C.sensor_pairs()` so
the window cannot drift between scripts.

### 2. Jamuna data moved to data/unused_data/ - NOT deleted

Owner asked for the Jamuna folders to be cleared. **Moved rather than deleted**,
deliberately, and the reason is stated rather than assumed:

- **Space was never the problem.** 431 GB free on this disk against 599 MB of
  Jamuna data. Clearing achieved nothing that keeping did not.
- **It is the evidence for the project's central claim.** D44 - 37 years of
  imagery plus real river discharge, and year-to-year erosion still unpredictable
  - is why the project moved rivers at all. Deleting the data would leave the
  write-up asserting a finding with nothing behind it.
- **It is the control.** A 9 km braided reach against a 300 m single-thread reach
  IS the experiment. Keeping only the reach that was chosen after the Jamuna
  failed is the cherry-picking risk that D49 was written to avoid.
- **The 37 Landsat files cost the owner about an hour of Earth Engine time** and
  would have to be re-exported from scratch.

The reach is still fully runnable - `RIVERGUARD_REACH=jamuna` was re-verified
after the move and passes every blocking check with its 37 years and 35 pairs
intact. If the data is genuinely wanted gone, say so and it is one command; that
call is the owner's, not the assistant's.

## D54 - Arial Khan S2 masks verified: the "white line" is the river, and the Padma is absent

**Date:** 2026-10-18
**Trigger:** Owner downloaded 8 S2 masks and reported seeing a white line
overlapping them.

**Finding: the data is good. The white line is the Arial Khan.**

Image: `reports/arial_khan_s2_mask_check.png` (three panels - full mask, largest
connected body only, straight-run analysis).

Evidence:

1. **The box is the owner's drawn rectangle**, 4.85 x 8.91 km (485 x 891 px at
   10 m), not the 41 x 42 km fallback. The draw-on-the-map mechanism worked, and
   the size sits inside the advised 8-15 km band.

2. **The river renders as a thin line because it is a thin river.** 300 m across a
   4.85 km-wide image is 6% of the width. Anything that thin looks like a line at
   full-image zoom. Nothing is wrong with it.

3. **The Padma is NOT in the box.** The largest connected body is **2.686 km2**;
   the second largest is **0.115 km2** - a **23x** gap. A second real river would
   be comparable in size, not 23 times smaller. The scattered small bodies
   (32-86 per year, all under 0.12 km2) are floodplain ponds and oxbows, which is
   expected on this floodplain.

4. **The largest body is stable across the whole record**: 2.686-2.791 km2 in
   every year 2019-2026, with a centroid drift of only **7 px (70 m) vertically
   and 3 px (30 m) horizontally**. A mis-picked river would not hold still like
   that.

5. **No straight-line artefact.** 9 horizontal and 14 vertical runs exceeded
   1.2 km, but all three marked segments in the image lie *on* the main body -
   they are the straight legs between meander bends, which is ordinary river
   geometry, not a seam or a road.

6. **The no-data border is benign.** Invalid pixels are a 1-3 px (10-30 m) rim at
   the box edges, and `water` inside that rim is **0** in every year, so nothing
   is being fabricated at the edge. Valid coverage is **95.4% in all 8 years**,
   identical, which also confirms the composite is consistent.

7. Year-to-year pixel differences (2019 vs later: 10.6k-16.7k px, about 4% of the
   box) are a mix of real channel movement, seasonal pond fill/drain, and water
   level. The pond count varying 86 -> 32 across the record is normal for
   floodplain water bodies, not a data fault.

**Conclusion: proceed to prepare/measure.** No re-export needed.

**One optional improvement noted, not required.** The rectangle is wider than it
needs to be - the right-hand third contains almost no river, mostly ponds. A box
tightened around the diagonal channel would give more transects per unit area,
but the current box is acceptable and re-exporting costs the owner another run.

## D55 - Pond leak fixed in code, not by shrinking the box (23 -> 32 transects)

**Date:** 2026-10-18
**Trigger:** Owner asked for tighter bounds "so the small water patches don't
export". Recommendation was to fix this in code instead, with the evidence below.

**Why a tighter box was the wrong fix.** The channel's own bounding box is
8.81 x 1.80 km. At the published 21 m/yr over 37 years the bank can travel ~780 m,
so a safety margin of 1.17 km each side is needed. The resulting "tight" box is
**11.1 x 4.3 km = 47.8 km2, which is LARGER than the existing 4.85 x 8.91 km
= 43.2 km2 box.** Because the channel runs diagonally, the owner's rectangle is
already tighter than any axis-aligned box could be while leaving migration room.
Shrinking it would have pushed the river out of the frame over the record while
doing nothing about the ponds, which are inside the box either way.

**What the ponds were actually doing.** The first real geometry build showed:

    kept 23, dropped 9 at build
       drop #3: belt 3.1 km wide (implausible)
       ... all 9 the same
    s2 2024: 22/23 transects usable
    wetted width: median 410 m

Those 9 were not bad geometry. Each transect casts perpendicular to the channel
and, where a floodplain pond sits behind a bank, found water at both ends and
read a **pond as the far bank** - a "3.5 km river". The width gate then correctly
rejected it, and we silently lost **28% of the study reach**.

**Three changes, all gated to narrow rivers so the Jamuna is untouched**

1. **`C.PROFILE_MODE`, per reach.** `"smoothed"` keeps the existing rule, which is
   right for a 9 km braided belt where mid-channel bars must be averaged out.
   `"run"` takes the contiguous water run through the centre point, which is the
   correct definition of bank for a 300 m single-thread channel.

2. **Truncate a leaking run instead of dropping the transect.** Where the channel
   connects to a pond through a breach or canal, contiguity walks straight
   through. For a channel of known scale a 2.9 km "river" is a leak, not a wider
   river, so the run is clamped to `MAX_WIDTH_M` centred on the transect.

3. **`MAX_CAST_M` 3000 -> 900 m, `MARGIN_M` 800 -> 350, `MAX_WIDTH_M` 3000 -> 1200.**
   A 300 m channel needs nowhere near 3 km of cast each way; casting that far is
   what reached the ponds in the first place.

**Result: 23 -> 32 transects, 0 dropped, 39% more data.**

| | before | after |
|---|---|---|
| transects kept | 23 | **32** |
| dropped at build | 9 | **0** |
| usable per year | 22 | **30-31 of 32** |
| median wetted width | 410 m | **335-370 m** |
| total transect-years (8 yr) | ~176 | **245** |

Median width now matches the published ~300 m for the Arial Khan.

**Regression caught and fixed.** The clamp initially applied to every reach and
silently changed the JAMUNA from 58 kept transects to 70 - by quietly
reinterpreting genuinely-bad 16 km belts instead of dropping them. Re-verified
after gating on `PROFILE_MODE`: Jamuna back to **58 kept, 38.8 km, median 5610 m**,
and `09_checks.py` passes. This is the second time a bulk edit in this file
changed a reach that was not the target; the standing regression check against
known Jamuna values is what surfaced it.

**Two smaller fixes in the same pass**
- `data/reaches/arial_khan/raw/s2/` was wrong in my own instructions. The config
  convention, inherited from the Jamuna, is S2 directly in `raw/` and Landsat in
  `raw/landsat/`. Files moved; instructions corrected.
- `01_prepare.py` now treats the RGB band as **optional**. It is used only for the
  visual QC overlays and nothing in the measurement reads it, so the owner should
  not have to export 8 more colour images for a QC convenience.

## D56 - Sentinel-2 export v2: owner-authored multi-index water detection

**Date:** 2026-10-18
**Decision:** Adopt the owner's rewritten S2 export (v2) as the production script.
Its v1 masks are preserved at `data/unused_data/arial_khan_s2_v1_verified/` so a
worse v2 can be reverted without re-exporting.

**v1 masks were backed up BEFORE the new export was run.** v2 writes to the same
filenames, so without that step a worse v2 would have silently destroyed verified
data - 32 transects, 0 dropped, median width 335-370 m.

### What v2 does better, and why it should

1. **Five indices combined with `.or()`** - MNDWI, NDWI, RSWI, AWEI, plus a
   turbidity heuristic. AWEI is the meaningful addition: it is the only test
   using SWIR2/B12, so it detects water the other four miss and is far less
   confused by built-up land. Detection by agreement across independent tests is
   more robust than one tuned threshold.
2. **`INDEX_THRESH` 0.2 -> 0.02**, a ten-fold loosening. Only defensible because
   false-positive rejection moved to the morphological close and the blob filter.
   A loose threshold with no large-object filter would light up every wet field.
3. **30 m connected-blob filter** (~92 ha minimum). On this floodplain only the
   trunk reaches that size, so ponds, beels and agricultural water are removed
   outright. The single most useful line in the script here.
4. **20 m morphological close** bridging hairline breaches so the channel no
   longer leaks into adjacent ponds.
5. **Polygon shape mask** - water is clipped to a drawn polygon rather than its
   bounding box, so a known-bad pond can be excluded without moving the box.
6. **25th-percentile band composite** instead of the median. A dark-target trick:
   cloud is bright and water is dark, so pulling each band toward its lower
   quartile suppresses haze without suppressing water. It is applied to the BANDS
   before the indices are computed, not to the indices themselves.

### Three risks recorded before the data exists

1. **The blob filter runs at 30 m, where the channel is only ~10 px wide.** A
   segment needs roughly 3 km to accumulate 1000 connected pixels. Short arms and
   meander tips can be severed - harmless, because the pipeline measures the
   largest connected body - but if the TRUNK is cut, that year is ruined. Check
   the preview for disconnected pieces.
2. **The water fraction will NOT match v1's 7-9%.** v2 is more permissive at the
   threshold but removes far more with the blob filter, so 1-3% is expected. A
   figure outside that range is a reason to inspect the preview, not to retune
   the threshold.
3. **The comment above the morphological step describes two operations and the
   code performs one.** It says "erode first to sever ditches, then close", but
   the code is `focal_max` then `focal_min`, which is a CLOSE only. Harmless as
   written; worth reconciling so a future reader does not assume a step is
   running.

### BOX CHANGED, and this is the part that needs attention

The owner set `FALLBACK_BOX = [90.10, 23.02, 90.35, 23.29]`. That is **25.5 x
27.5 km = 764 km2**, against the **4.85 x 8.91 km = 43 km2** actually used for the
verified v1 export. **The area grows 18x.**

Consequences, stated plainly:

- The v1 geometry (32 transects, 8.1 km centreline) was built on a 43 km2 box and
  **does not transfer**. Geometry must be rebuilt and re-verified once v2 lands.
- **Padma risk rises with area.** The western edge moves from 90.08E to 90.10E,
  and the box widens 5x in longitude. At 43 km2 the largest body was the river and
  the runner-up was 23x smaller; at 764 km2 the Padma may fall inside. The 30 m
  blob filter will not save us here, because the Padma easily exceeds 92 ha.
- **Cross-sensor comparison requires both sensors on the same box.** The Landsat
  export was realigned to the same coordinates and `09_checks.py` section 7 now
  verifies this. If a different rectangle is drawn for one sensor it must be drawn
  for both, or the two instruments are not measuring the same reach and the
  cross-sensor check is meaningless rather than merely noisy.

**Recommendation: draw the same rectangle for both sensors, and keep it small.**
A 5 x 9 km box was verified to work. 764 km2 is 18x that for no measured benefit.

**Northern-edge constraint unchanged: the box must stay south of 23.47N**, the
bifurcation from the Padma. The new box's northern edge is 23.29N, which clears
it.

## D57 - v2 masks land, and the v1/v2 comparison comes out even

**Date:** 2026-10-18
**Result: v2 and v1 produce essentially the same measurement geometry.**

| | v1 (single index, 0.2) | v2 (owner: 5 indices + 92 ha blob filter) |
|---|---|---|
| centreline | 8.06 km | 8.08 km |
| transects kept / dropped | 32 / 0 | **32 / 0** |
| usable transect-years (8 yr) | 245 | **247** |
| median wetted width | 335-370 m | **350 m** |
| water fraction | 6.1-7.8% | **6.1-6.7%** |
| 2nd-largest body | 0.115 km2 | **0.00-0.14 km2** |
| largest:2nd ratio | 23x | **469-758x** (5 of 8 years) |

**Reading this honestly.** v2 is clearly better as a *water mask* - the
largest-to-second-largest ratio jumped from 23x to several hundred, meaning the
ponds and fragments are almost entirely gone, which is what the 92 ha blob filter
was meant to do. But once the pipeline isolates the largest connected body and
measures it with the contiguous-run method (D55), those ponds were already
excluded. **So the extra detection machinery buys mask quality that the measuring
step was throwing away anyway.**

That is worth saying plainly rather than presenting v2 as a decisive improvement.
It is still the better script - the mask is objectively cleaner, and if anyone
inspects the imagery by eye it will look right - but it did not change the
measurement, and the 1.3% of water it removed was not water we were measuring.

**The box question resolved itself.** The owner drew the same rectangle as v1
rather than relying on the 764 km2 fallback, so the Padma risk flagged in D56 did
not materialise. Actual exported extent, read back from the raster itself:
**90.1927, 23.1638 -> 90.2384, 23.2450 = 42 km2**, well clear of the 23.47N
bifurcation. `config.py` and both export scripts now carry that measured extent
rather than a guess, and `09_checks.py` verifies all three agree.

**Incidents worth recording**

1. **`data/reaches/` was deleted.** The whole `data/reaches/arial_khan/` tree
   disappeared; the v2 files had been left in `data/raw/s2/`, the old Jamuna path.
   Nothing was lost because v1 was backed up (D56) and v2 was still in
   `data/raw/s2/`, but the prepared masks and geometry were lost and had to be
   regenerated. Directory structure recreated and v2 files relocated.
   **This is the second time data has been moved out from under the pipeline**,
   which suggests the drop-point should be stated once and enforced by a check
   rather than repeated in prose.

2. **A bulk find-and-replace corrupted `config.py`**, turning two dict keys into
   the literal string `": "`. Caught immediately by a syntax check, fixed with a
   targeted edit. This is the third time a scripted bulk edit in this project has
   failed silently or corrupted its target; all three were caught only because a
   check ran afterwards. **Standing rule from here: no bulk edits without reading
   the diff.**

**Going forward:** v2 is the production script. The v1 backup stays until Landsat
is in and the cross-sensor check has run.

## D58 - EPR SIGN WAS INVERTED. Found while processing the Arial Khan.

**Date:** 2026-10-18
**Severity: high.** Every erosion rate this project has ever produced carried the
wrong sign.

### The bug

```python
lost   = (zone & w0 & ~w1)   # water in year0 -> land in year1  = land GAINED
gained = (zone & ~w0 & w1)   # land  in year0 -> water in year1  = land LOST
rate   = (lost - gained) / run
```

The two quantities were named for the opposite of what they measure, so
`rate` came out as **accretion minus erosion** - the negative of the intended
quantity. Transect 7 of 2023-2024 is the clearest example: 1700 m2 became water
(7.1 m/yr of real erosion) and the file recorded **-6.7 m/yr**.

Fixed by naming them for what they are (`w2l` = water-to-land, `l2w` =
land-to-water) and computing `(l2w - w2l) / run`. Verified: zero rows remain where
land was lost but the rate is negative.

### Why it went unnoticed so long

Every headline number in this project used a **magnitude**:

- Jamuna medians were reported as `max(|left|, |right|)` (56.6, 109.8 m/yr)
- the cross-sensor check compared magnitudes
- the risk ranking sorted on the median, which for a symmetric series of
  swapped signs is the same value with its meaning inverted

So no total was wrong. Only the **direction** was, and only where direction is
claimed. It was found only because the Arial Khan's median rate is close to zero,
which made a sign flip obvious - on a river with rates near 100 m/yr it would
have been invisible.

### What is affected

- **Arial Khan S2 record: recomputed.** Median 1.7 m/yr over 7 pairs, unchanged
  as a magnitude.
- **Jamuna risk table (`reports/RISK.md`, `transect_risk.csv`): the ranking is
  inverted.** The top-ranked "hotspots" are the banks that ACCRETED. It must be
  regenerated with the corrected signs before any of it is used or cited. The
  cross-sensor magnitude results (0.98x, +0.98) and the VALIDATION report are
  unaffected, because they are all magnitudes.
- Feature tables carry `target_rate` with the wrong sign and must be rebuilt.

### Not a data problem - an operator error

Mid-diagnosis I chased a phantom "wrong reach" failure that printed Jamuna
numbers (`/58 transects`, `stage +12.8 km2`) under an Arial Khan header. Cause:
a `sed && python` chain in which I dropped my own `RIVERGUARD_REACH` prefix, so
it ran on the default reach. The config was always correct. Worth noting because
the output looked alarming and nearly sent me looking for a nonexistent bug.
**Rule adopted: never chain an env-var-prefixed command after another command
with `&&`; put the variable on the same line as the interpreter.**

### The finding itself, stated honestly

Arial Khan, Sentinel-2, 2019-2026, 31 transects, 432 rows:

| predictor | MAE (m/yr) |
|---|---|
| predict the average | **2.92** |
| repeat the previous pair | 4.06 (lag correlation **-0.073**) |

**Still no skill, on a completely different river.** The switch was made on the
hypothesis that a 300 m single-thread meander erodes persistently at its outer
banks. Seven years say otherwise, or say the sample cannot resolve it.

The scale signal is also weak: between-transect means span only -2.6 to
+2.0 m/yr, while within-transect year-to-year scatter has a median spread of
2.5 m/yr. **The noise is as large as the spatial pattern.** That is a weaker
position than the Jamuna, where the between-transect spread was -118 to
+129 m/yr.

**This does not condemn the reach.** Seven annual pairs cannot separate a
2.5 m/yr noise floor from a real trend, and the Landsat record at 5-year blocks
is still outstanding - 30+ years at 5-year resolution is a genuinely different
test, and a 5-year block is 5x less noise-exposed than an annual pair. But the
honest position today is that the persistence hypothesis is **unsupported so
far**, and it should not be written up as supported until Landsat is in.

**Also note the absolute scale.** Measured median 1.7 m/yr against a published
channel migration of ~21 m/yr for this river. Part of that gap is definitional -
published migration is a channel shift, we measure net land change in a 300 m
bank zone. Part may be real: this section may simply be relatively stable, and
January-February low water under-represents monsoon-driven movement. Either way
it must not be "corrected" by rescaling to match the literature.

## D59 - Landsat export realigned to the Sentinel-2 detection logic (caught by the owner)

**Date:** 2026-10-18
**Raised by:** the owner, unprompted, and it was correct.

**The error.** The Landsat export used a Jamuna-tuned rule - median composite,
MNDWI > 0.2. The Sentinel-2 export uses the owner's v2 rule - 25th percentile,
five indices OR-ed at 0.02, ~90 ha blob filter. The two disagree.

**Why that matters, precisely.** Landsat and Sentinel-2 overlap from 2019 to 2026.
Comparing them across that overlap would have measured **the difference between
the two scripts**, not the difference between the two instruments. A step change
in measured river width would appear at 2019 out of nowhere, and the
cross-sensor check - the single piece of evidence that made the Jamuna's 0.98x /
+0.98 agreement credible - would have been measuring our own processing choice.
The Landsat record alone is internally consistent, so the corruption would only
have surfaced at exactly the point where the two sensors are compared.

**Fixed.** `gee/landsat_export_arial_khan.js` rewritten to use the identical
chain: same six bands, same 25th-percentile composite, same five indices at the
same thresholds, same 20 m close, same ~90 ha filter at 30 m.

Band numbers had to be mapped per platform, which is where a silent error would
have been easy to hide:
- Landsat 8/9 (OLI/TIRS): B2 blue, B3 green, B4 red, B5 NIR, B6 SWIR1, B7 SWIR2
- Landsat 4/5/7 (TM/ETM+): B1 blue, B2 green, B3 red, B4 NIR, B5 SWIR1, **B7** SWIR2
  (B6 is thermal on those platforms, not SWIR2)

The v1 Landsat script used only green/SWIR1 and so never needed this mapping.

**One difference deliberately left in place.** The 20 m morphological close is
less than one pixel at 30 m, so it does less work than the identical 20 m close
at 10 m. It was NOT scaled up to compensate. Matching the physical size is the
point: inflating it for Landsat would make the two scripts seek different ground
features at different scales, which is the exact problem this change exists to
remove. The difference is a genuine consequence of the coarser grid.

**Guard added.** `09_checks.py` section 8 now parses the four detection
constants out of both export scripts and FAILS if they differ, so the two
scripts cannot drift apart again. Currently passing: AWEI_THRESH=0.0,
GAP_CLOSE_M=20, INDEX_THRESH=0.02, TURBID_SWIR_MAX=0.12.

**Note for the write-up.** Sharing a detection chain means the two sensors are no
longer fully independent - they share a processing step. What remains independent
is the instrument itself: spectral response, 30 m against 10 m pixels, revisit
interval, and overpass geometry. That is still a meaningful check, and it is the
standard design for cross-sensor studies: isolate the sensor difference by
holding the algorithm fixed. Worth stating plainly rather than describing the
comparison as two fully independent pipelines.

## D60 - Three divergences in the owner's Landsat draft, and a check that now proves itself

**Date:** 2026-10-18
**Context:** the owner supplied a rewritten Landsat script. Its structure was
better than mine (a clean TM-versus-OLI band split rather than a table lookup),
but three details would have undone D59, and one would have crashed outright.

**1. Blob threshold `.gte(300)` against Sentinel-2's `.gte(1000)`.** At 30 m, 300
pixels is ~27 hectares and 1000 pixels is ~92. The draft would therefore have
kept ponds that Sentinel-2 removes, so Landsat would have measured a
systematically **wider** river than S2 on the identical reach - the exact bias the
alignment was for, and invisible in any summary statistic because both numbers
would still have looked plausible. Corrected to 1000.

**2. `focal_max(1, 'circle', 'pixels')` against Sentinel-2's 20 metre radius.**
A radius expressed in PIXELS silently means a different ground distance on each
sensor: 1 pixel is 30 m on Landsat and 10 m on Sentinel-2, neither of which is
20 m. Written in metres so it carries the same meaning on both. It remains
smaller than one Landsat pixel and so does very little there; that is left
alone deliberately (see D59).

**3. `Map.drawingTools().layers().get(0).toGeometry()` with no guard.** This
**throws** when nothing has been drawn, which is the normal state when the script
is simply pressed Run. Restored the `FALLBACK_BOX` fallback.

**Also added:** `MIN_VALID` and `MIN_WATER` gates. The draft checked only scene
count, so a year with imagery but a failed composite would still be exported and
would surface much later as an anomalous year in the record.

**The check now proves itself.** `09_checks.py` section 8 previously could not
see `BLOB_MIN` because the Sentinel-2 script had `.gte(1000)` hardcoded - so the
one constant most likely to drift was invisible to the very check meant to catch
it. `BLOB_MIN` is now a named constant in both scripts. Verified by deliberately
setting Landsat's to 300: the check reports
`FAIL water-detection constants differ between the two export scripts: ['BLOB_MIN']`,
then passes again once restored.

That is the pattern worth repeating: **a check that has never been seen to fail
is not known to work.** This one has now been observed failing on the exact
value that caused the problem.

## D61 - Earth Engine evaluation: one synchronous getInfo() per batch

**Date:** 2026-10-18

> **RECONSTRUCTED.** This entry was written after the fact, on 2026-10-18. The
> number D61 was cited three times - in `context/CURRENT.md` (twice) and
> `AGENTS.md` (once) - but no entry was ever recorded under it, so the log
> pointed at a decision that did not exist. The content below is recovered from
> those surviving references and from the current state of the two export
> scripts. It is a reconstruction, not a contemporaneous record, and is marked as
> such deliberately: this log is the project's authoritative account of why the
> pipeline works the way it does, and an unmarked reconstruction would quietly
> undermine that.

**Problem 1 - a race in Earth Engine evaluation.** The exporters used nested
`evaluate()` calls to gather per-year statistics. Those calls are asynchronous
and raced each other, so results were attributed to the wrong year. Two tells
made it visible: years holding 15 scenes reported **0% valid**, and two
*different* years printed an *identical* 12.55% - a coincidence that stopped
being plausible once noticed.

**Problem 2 - a memory limit on the long record.** `connectedPixelCount(1024)`
means 1024 pixels in *each* of eight directions, so on a 30 m Landsat grid it is
roughly a **31 km window**, far wider than any river feature being screened.
Evaluating the full 38-year record in one pass exceeded Earth Engine's user memory
limit.

**Decision:** Evaluate statistics with **one synchronous `getInfo()` per batch**,
and split the exports into batches - **8 years** per call for Landsat, **4** for
Sentinel-2. This removes the race and bounds peak memory. `tileScale` was later
raised as well (D66).

**Reason:** The statistics printed by these scripts are the go/no-go gate on
every export: a year that reports as invalid is dropped, and a year silently
attributed the wrong metrics can be exported with the wrong mask. An async race in
that gate is worse than a crash, because it produces a confident wrong answer.

**Impact:** Export statistics are now trustworthy per year. No downstream
measurement changed; what changed is whether the numbers deciding *what got
exported* could be believed.

**Note:** D66 later revisits the memory problem for the expanded study area,
where the first S2 run still exceeded the limit and the connected-component
screen was coarsened to a 60 m grid.

## D62 - SUPERSEDES the forecast branch being called closed. It was closed too early.

**Date:** 2026-10-18
**Supersedes:** the practical conclusion of D44, that no forecast is supportable.

**What went wrong.** The forecast branch was declared closed on the basis of
simple baselines - predict the average, repeat the previous pair - and pairwise
correlations. **No machine-learning model was ever trained on the Arial Khan.**
The Colab notebook that would have done it was written, handed to the owner, and
left unrun, while the conclusion was reported as settled. Baselines losing to
each other is not evidence that a model loses; it is only evidence that the
*easy* signals are absent.

**Run properly, the model wins.**

Arial Khan, Sentinel-2, 432 rows, 31 transects, 17 features, `GroupKFold(5)`
grouped BY TRANSECT so no part of a bank appears in both training and test:

| | MAE (m/yr) | correlation |
|---|---|---|
| predict the average | 2.919 | — |
| repeat the previous pair | 4.060 | -0.073 |
| **RandomForest** | **2.835** | **+0.520** |
| GradientBoosting | 2.949 | +0.568 |

RandomForest beats the baseline and correlates at **+0.52**, against **+0.05** on
the Jamuna. GradientBoosting loses on MAE but still correlates at +0.57, so the
signal is real and the model's calibration, not its ability to find structure, is
the weaker part.

**This is the result the river switch was for.** The whole argument for moving
from the 9 km braided Jamuna to the 300 m single-thread Arial Khan (D49) was that
persistent outer-bank erosion should leave a findable signal. It does. Saying
otherwise was not cautious, it was wrong.

**What is still true, and what is now corrected**

Still true:
- Nothing simple works. The lag correlation is -0.073. Persistence loses badly.
- The Jamuna genuinely has no signal, at +0.049. That finding stands.
- The Arial Khan numbers are small: ~2.9 m/yr median. That is the river.

Now corrected:
- "Year-to-year erosion is not predictable" is **true of the Jamuna and false of
  the Arial Khan.**
- The forecast branch is **open**. `06_predict_geojson.py` is rewritten to
  produce long-run trend geometry and will be repointed at real model output.

**Caveats, stated so they are not mistaken for confidence**
1. The margin is **2.9%** of MAE. Real, not large.
2. 432 rows over 7 year-pairs is thin. The Landsat record at 5-year blocks is
   what would make this defensible rather than promising.
3. The strongest features are `width_change_pct`, `other_side_rate`,
   `rate_roll3` - that is, how the channel is already changing. Plausible
   physically, and consistent with the single-thread hypothesis, but it also
   means the model is partly reading the current state of the bank, which needs
   care when applied forward.

**Process lesson, recorded because it will recur.** Declaring a research question
closed requires running the method, not inferring the answer from its
neighbours. A negative result that has not been tested with the actual method is
an assumption wearing the costume of a finding.

## D63 - Withdraw the 2.843 m/yr score as evidence of future prediction

**Date:** 2026-10-18
**Supersedes:** D62's conclusion that the Arial Khan RandomForest had shown
future-prediction skill. The goal of building a future-bankline prediction
system remains; this correction changes the evidence, not the goal.

**What was wrong.** `14_model_train.py` used `GroupKFold` by transect, which
kept each transect out of the matching training fold, but it selected nearly
every numeric feature. This included observations from the same interval as the
target, including `other_side_rate`, `width_m`, `width_change_pct`, and current
stage values. Those measurements are not available before predicting that
interval. Grouping rows by transect does not prevent this time leakage. The
reported 2.843 m/yr MAE and +0.517 correlation therefore do not validate a
future prediction.

**Corrected test.** The model now uses only prior-year information and is
evaluated with an expanding time window: each test year is predicted using
earlier years only. Missing feature values are filled using training data only.
Across 310 held-out bank-side/year records for 2022–2026:

| predictor | MAE (m/yr) |
|---|---:|
| RandomForest candidate | 3.175 |
| training-median baseline | **2.507** |
| training-mean baseline | 2.680 |
| repeat previous pair | 3.977 |

The candidate loses to the median baseline. `forecast_supported` is therefore
false. Its 62 bank-side outputs remain available as **experimental** rates and
10-year linear extensions, not as a validated bankline forecast. The scaled
MAE band is a rough display aid, not a calibrated 10-year uncertainty interval.

**Changes made.** `14_model_train.py` now limits features to values available
before the target year and records chronological test metrics. `06_predict_geojson.py`
includes those metrics and marks unsupported output `is_forecast: false` and
`projection_status: experimental`. The API, map, project notes and README now
describe prediction as the goal and the current overlay as experimental.

**Next evidence needed.** Restore/export the Arial Khan Landsat record, compare
candidate models under the same time-forward test, retain a later period for a
final untouched test, and measure spatial bankline error against later observed
banklines. More rows alone do not prove forecast skill.

**Reason.** A model must be tested with information it could actually have at
prediction time. A transect-grouped split addresses spatial leakage but not
future-information leakage. We keep the intended system ambitious while making
its current limits visible.

## D64 - Prepare an expanded Arial Khan study area; bounds pending

**Date:** 2026-10-18
**Decision:** The owner wants to include a longer portion of the Arial Khan.
The new rectangle has not been selected yet, so `ml/config.py` remains on the
previous box until its exact bounds are captured and synchronized.

**Changes made:** Both Arial Khan Earth Engine exporters now require one drawn
rectangle, prefer a fresh map drawing over imported geometry, print exact bounds,
and refuse to export when no rectangle is present. The previous coordinates are
shown only as a reference. The handover instructs the operator to use the same
rectangle for both sensors and update `REFERENCE_BOX`, `bbox`, and
`bbox_landsat` before local processing.

**Constraints:** Keep the northern edge south of 23.47N to exclude the Padma.
Inspect both sensor previews for one continuous Arial Khan channel; a larger box
that includes another river or floodplain water is not acceptable.

**Impact:** All existing 32-transect geometry, processed products, model scores,
and 2036 experimental projections describe only the old box. They must not be
reported as results for the expanded area. Rebuild masks, measurements,
transects, features, and the time-forward model evaluation after configuration
is updated. More river coverage is not evidence of better forecast skill.

**Next gate:** Record the selected bounds, synchronize config and both exporters,
run `09_checks.py`, then export and verify both sensors before training.

## D65 - Expanded Arial Khan bounds selected and synchronized

**Date:** 2026-10-18
**Supersedes:** D64's statement that the larger rectangle was awaiting
selection. It does not supersede D63's model evaluation or claim forecast skill.

**Selected bounds:**
`90.16808799423755, 23.134319063780836, 90.26902488388599, 23.261491731177696`
(west, south, east, north), EPSG:32646. The northern edge remains south of
23.47N, outside the Padma.

**Synchronized:** `ml/config.py` (`bbox` and `bbox_landsat`),
`gee/s2_export_arial_khan.js`, and `gee/landsat_export_arial_khan.js` now use
these bounds. `09_checks.py` sections 7 and 8 pass, and both scripts parse. The
map's initial fit bounds use the selected rectangle as well.

**Not yet done:** Earth Engine exports have not been run for this AOI. Existing
processed masks, 32-transect geometry, model inputs, MAE values, and projected
lines belong to the previous smaller box and must not be reported as results
for this expanded area. Rebuild and inspect transects before retraining.

**Next gate:** Run both exporters with this same rectangle, verify both previews
and the printed bounds, then start Tasks and rebuild the full pipeline.

## D66 - Coarsen connected-area filtering for the expanded AOI

**Date:** 2026-10-18
**Context:** The first S2 run for D65 exceeded Earth Engine's user memory limit
while evaluating yearly statistics, even after reducing the batch to one year
and increasing `tileScale`.

**Decision:** Apply the connected-component screen to a 60 m grid in both GEE
exporters, with `BLOB_MAX_SIZE=256` and `BLOB_MIN=250`. This keeps the nominal
minimum connected area at about 90 hectares (`250 × 60 m × 60 m`) while reducing
the component computation size. Both scripts use identical constants;
`09_checks.py` section 8 enforces this. S2 statistics are evaluated one year at
a time with `tileScale=4`.

**Tradeoff:** Equal area does not guarantee identical connectivity. A 60 m grid
can change small edge details compared with the former 30 m screen. Inspect the
S2 and Landsat previews, especially narrow meanders and tips, before starting
Tasks. Existing processed results describe the previous box and old filter; the
new method has not yet completed an Earth Engine run.

**Reason:** Preserve the intended nominal pond-size rejection while reducing
memory pressure on the expanded study area. Do not weaken the area threshold to
force the run through.

## D67 - Guard the dry-season window, and make DRY_SEASON a live value

**Date:** 2026-10-18

**Found:** `ml/config.py` declared `DRY_SEASON = ("01-01", "02-28")` while both
Earth Engine exporters actually request `Jan 1 - Mar 25`. The config value was
never read by any script, so the contradiction was invisible: the config claimed
a window the pipeline never used. Section 8 checked the detection constants but
not the date window, so the one constant that decides *which part of the year*
is measured had no guard at all.

**Decision:** Set `DRY_SEASON = ("01-01", "03-25")` to match what the exporters
do, and extend `09_checks.py` section 8 to parse the `filterDate` window out of
both scripts and compare it against config. The check was verified by
deliberately reverting the config value and confirming it fails.

**Not required to match:** the two sensors keep different `START`/`END` years —
Landsat reaches 1989, Sentinel-2 starts 2019. That asymmetry is the point of the
long record, so year coverage is compared against config rather than between
sensors. Only the detection constants and the dry-season window must be identical
across sensors.

**Also found:** a stale `__pycache__/config.cpython-312.pyc` silently served the
old `02-28` value after the file on disk had been corrected, because Python
compares the source mtime to the second and the restore landed in the same second
as the edit it undid. A guard check reported FAIL for a file that was already
fixed — and would equally have reported PASS for code that no longer existed.
Recorded as a standing constraint in `AGENTS.md`: clear `__pycache__/` after
restoring or rapidly re-editing a module.

**Reason:** The dry-season window is as load-bearing as the index thresholds. It
decides which months contribute to every mask, so drift in it silently shifts
water levels, the cross-sensor overlap, and every measured rate, with nothing
raising an alarm. A value that no code reads cannot be wrong loudly, only
quietly.

**Impact:** No measured number changes — the exporters never consulted the
config value. The pipeline's description of itself is now true, and the window is
guarded rather than documented.

## D68 - The exporters accept only the synchronized box; drawing always fails

**Date:** 2026-10-18

**Found:** `docs/DATA_HANDOVER.md` instructed the operator to draw the study
rectangle on the map, and D64 described the exporters as requiring a drawn
rectangle. Neither matches the code. Both scripts:

- use `REFERENCE_BOX` automatically when the map is empty,
- accept a drawn rectangle only if it matches `REFERENCE_BOX` to within `1e-6`
  degrees (about 10 cm), and throw otherwise,
- throw when two or more shapes are present.

**Consequence:** A hand-drawn rectangle can never pass a 10 cm tolerance, so the
documented procedure fails 100% of the time with
`Rectangle differs from REFERENCE_BOX`. The instruction was not merely
imprecise - it was impossible to follow.

**Decision:** Correct the handover to instruct the operator to **draw nothing**
and simply press Run. The scripts then use the synchronized bounds and verify
them against config. Drawing remains supported for deliberately relocating the
study area, but it requires editing `REFERENCE_BOX` and `ml/config.py` together
first; it is not an export-time action.

**Reason:** With the bounds now selected and synchronized (D65), the safest
export is the one with no operator input at all. The verification is already in
the script and in `09_checks.py` section 7. Asking a person to reproduce six
decimal places by hand added a failure mode without adding a safeguard.

**Impact:** No measured number changes. The export procedure is now executable as
written, and the tolerance check stays in place as the safeguard it was meant to
be rather than as an obstacle.

## D69 - The exporters' `valid` band was always 100%; the quality gate was dead

**Date:** 2026-10-18

**Found:** Both Arial Khan exporters computed

```js
var comp = ( ... ).clip(aoi).unmask(0);     // mask destroyed here
var valid = green.mask().unmask(0);         // therefore always 1
```

`.unmask(0)` fills every masked pixel with 0 and removes the mask entirely, so
`green.mask()` on the composite afterwards returns an all-ones image. The `valid`
band was therefore 100% for every year, and `valid >= MIN_VALID` - the gate that
decides whether a year is exported at all - could never fail.

The regression is confirmed against the sibling scripts: `landsat_export.js` and
`landsat_export_ganges.js` both do `var comp = pool(y).median().clip(aoi)` with no
unmask, then `comp.select('green').mask()`, which is correct. The surviving v1
Sentinel-2 masks carry a real `valid` band (95.1% set, 4.3% clear). The Arial Khan
pair, written later, regressed.

**Why it mattered:** The gate is the only thing standing between a year with
almost no usable imagery and that year being exported, measured, and fed into the
model as if it were sound. The failure was silent by construction - the console
said 100% valid, so the operator saw nothing wrong. On Landsat, whose scan-line
gaps make this the single most likely failure mode, a broken gate is precisely
the wrong one to have.

**Fixed:** Validity is sampled from the composite BEFORE `.unmask(0)`, reprojected
to the working grid and re-thresholded, because reprojection resamples a binary
mask into fractional values. Both scripts now carry the identical code.

**Also changed in the same revision:**

- The working grid is stated explicitly as `RES_M` (10 for Sentinel-2, 30 for
  Landsat) so the `focal_max`/`focal_min` radius, which is given in METRES, cannot
  be silently reinterpreted against an unknown pixel size.
- `ee.Algorithms.If` is gone from the export path. The caller now checks the
  scene count before building, so the composite is never constructed for an empty
  collection - which was the only reason the guard existed.
- The study area is resolved once, with `REFERENCE_BOX` authoritative. A drawn
  rectangle may override it, but differences print a loud warning instead of
  throwing, because the previous `1e-6` tolerance (~10 cm) was impossible for any
  hand-drawn shape to satisfy (D68).
- The Padma limit is now enforced in code rather than by eye: both scripts throw
  if the northern edge reaches 23.47N.
- Statistics are taken on the coarse grid the blob filter already uses, and
  `tileScale` is raised to 8, to reduce the memory pressure D66 recorded.

**Guards added:** `09_checks.py` section 8 now fails if either exporter samples
`valid` after unmasking, and fails if the north edge reaches the Padma limit.
Both were verified by reintroducing the fault and confirming the check fires.

**Reason:** A gate that cannot fail is worse than no gate, because it reports
success. The project's whole claim rests on distinguishing "we measured this"
from "we did not look here", and this band is how that distinction reaches the
export at all.

**Impact:** No measured number changes on its own, but the next export will
report real validity, and years that previously passed silently may now SKIP.
That is the gate beginning to work.

## D70 - The exporters ignore map drawings and use REFERENCE_BOX only

**Date:** 2026-10-18

**Found:** Running the pre-fix exporter produced, in the Earth Engine Code
Editor:

```
Error
Line 168: ee.Algorithms.If(...).rename is not a function. Earth Engine requires
you to specify the object type before calling 'rename'.
```

`ee.Algorithms.If` returns a value whose server-side type is undetermined, so no
method may be called on its result. This was fixed in D69 by deleting the branch
rather than by wrapping it, because the guard existed only to handle an empty
collection, and the caller now checks the scene count first.

**Decision:** The exporters no longer read the map at all. `REFERENCE_BOX` is
authoritative and shapes drawn on the map are ignored, with a printed note.
Removing the drawing path also removes the `Map.drawingTools().layers().get(0)
.toGeometry()` call, which was doing real work in the previous version and would
have been the next failure of the same kind.

**Why not keep drawing:** It carried three separate risks - an editor API whose
behaviour was never exercised (the previous version threw on any drawn shape
before it could reach that code), an impossible tolerance, and the silent
wrong-area failure the tolerance was meant to prevent. Editing four numbers in
two scripts and one config file is unambiguous and is verified mechanically by
`09_checks.py` section 7, which is a stronger guarantee than reading a shape back
off a map.

**Also fixed:** the operator was running the version from commits `46646c8` /
`990d2a1`, which the Code Editor had cached as a paste. Nothing in the repository
was wrong at the time of the error report; the browser held the old text. Worth
remembering that editing the file does not change what is already pasted, and
that until the repository is pushed, nobody else can obtain the corrected copy.

**Guard added:** `09_checks.py` section 8 fails if any method is called directly
on `ee.Algorithms.If(...)`, with the wrapping fix stated in the message. Verified
by reintroducing the exact reported code and confirming the check fires.

## D71 - The exporters queue Tasks instead of surveying every year

**Date:** 2026-10-18

**Found:** The export scripts froze the Earth Engine Code Editor. Each year's
scene count was fetched with its own synchronous `getInfo()`, and each year's
water/valid statistics with another - 76 blocking round-trips for the 38-year
Landsat range. Worse, each statistics call re-ran the entire detection chain,
including the focal close and the connected-component filter, so the browser
blocked on 38 consecutive heavy computations. This is also the likely cause of
the memory-limit error recorded in D66.

**Decision:** Fetch every year's scene count in **one** batched `getInfo()`
(`ee.List.sequence(...).map(...)`), and do not evaluate the statistics server
side by default. Every year with enough scenes is queued immediately, because
`Export.image.toDrive` only records a task - the computation happens later on
Earth Engine's servers, not in the browser. The statistics remain available
behind `SURVEY = true`, intended for use with a narrowed `YEAR_FROM`/`YEAR_TO`.

**Why this is not a weakening of the gate:** Quality is now checked locally
against the downloaded GeoTIFFs, which is a *stronger* check than a server-side
reduction - it measures the pixels actually exported rather than a preview of
them, and `ml/01_prepare.py` reports water area per year. The scene-count gate,
the Padma assertion and the `valid`-before-unmask invariant all still run.

**Reason:** A script that appears to hang is worse than one that reports an
error, because the natural response is to retry or to lower the gates rather
than to read them. The synchronous survey also duplicated work that the local
pipeline already does, and did it somewhere the result could not be inspected.

**Impact:** Running either exporter is now one cheap round-trip plus the Task
registrations. The code now matches its own documentation, which previously
promised "one synchronous getInfo() per batch" while doing one per year.

## D72 - The download gate now really is local, and config.py is checked for shadowed keys

**Date:** 2026-10-18

**Found:** D71 moved the quality judgement out of the exporters and into the
local preparation step, and stated that this was a stronger check. It was not
yet true: `01_prepare.py` read only band 1 of the mask - the `water` band - and
printed water area alone. The `valid` band was never opened, so the `MIN_VALID`
gate had simply stopped existing anywhere. Landsat's script did report footprint
coverage, but that counts pixels that ARRIVED, not pixels that are usable, so an
all-cloud year would have passed.

Also found while placing the thresholds:

- `config.py`'s `arial_khan` geometry gates contained `"MARGIN_M"` and
  `"MAX_WIDTH_M"` **twice each**. A duplicated dict key is legal Python and
  silent - the last value wins - so the first of each pair never applied and
  nothing ever said so. The effective values were correct by accident.
- `01b_prepare_landsat.py` printed a hardcoded fallback box `(89.65, 24.30,
  89.85, 24.60)` next to its "fix" advice. That is the **Jamuna** box. The
  message would have sent a reader to the wrong reach.

**Decision:** Put the thresholds in `config.py` as
`REACHES["arial_khan"]["download_gates"]`, exposed as `C.DOWNLOADS`, and have
`01_prepare.py` and `01b_prepare_landsat.py` report the `valid` fraction and
flag years below `MIN_VALID`. Extend `09_checks.py` with:

- section 8: the script constants `MIN_IMAGES / MIN_VALID / MIN_WATER /
  MAX_CLOUD` must equal `C.DOWNLOADS`, so the local gate and the script's
  optional survey cannot drift;
- section 8b: parse `config.py` with `ast` and fail on any duplicated dict key.

Remove the two shadowed gate entries and the hardcoded Jamuna box.

**Reason:** A gate that has been relocated is a gate that has to be re-verified.
Moving the check without moving the threshold would have replaced a dead gate in
JavaScript with a dead gate in Python - the same failure wearing different
clothes, and harder to see because the local script *looks* like it is checking
something. The duplicate keys are the same class of silent-wrong-number failure
this project keeps meeting, and `ast` detects them exactly.

**Rejected:** Keeping the thresholds only in the scripts and having the local
step read them with a regex. The scripts are not imported by the pipeline, the
regex would be a second hand-rolled parser, and the numbers belong with the rest
of the reach's parameters.

**Impact:** `01_prepare.py` prints `valid NN.N%` per year and warns below the
gate; `01b_prepare_landsat.py` prints both coverage and valid and warns
separately for each, since for Landsat they mean different things (footprint vs
scan-line gaps). Verified by reintroducing all three faults - a shadowed key, a
drifted `MIN_VALID`, and a disabled valid-band read - and confirming each is
caught or reported, then restoring and re-passing.

## D73 - The map preview is off by default; it is not the same budget as an export

**Date:** 2026-10-18

**Found:** Running the Sentinel-2 exporter produced repeated

```
Tile error: Output of image computation is too large
(6 bands for 1925093 pixels = 88.1 MiB > 80.0 MiB)
```

against the layer `Water 2024 (main river only)`. This is the **interactive map**
path, which has an 80 MiB per-tile ceiling that batch exports do not. Two causes:
`water` depends on the six-band composite, so the chain carries six bands even
when one is drawn; and the focal close plus the connected-component filter mean
each tile must pull in its neighbours.

**Decision:** `SHOW_PREVIEW = false` by default. When enabled it draws
`water.reproject({scale: 60})` and nothing else - 36x fewer pixels, and the
six-band composite is not drawn at all. `Map.centerObject` zoom reduced from 12
to 11 for the larger box.

**Reason:** The preview is a convenience; the export is the deliverable, and the
error message named the preview layer while looking like an export failure. That
is exactly the kind of misleading signal this project has been bitten by before.
Batch exports are not tiled this way and carry `maxPixels: 1e9`, so the Tasks
were created regardless - but nothing said so, and the natural response is to
assume the whole run failed.

**Not a fix by lowering the box:** the box is correct (D65) and the pixel counts
in the error are consistent with it. The tile ceiling applies to the interactive
render of a 10 m focal-op chain over ~145 km^2; it is a display constraint, not a
reason to shrink the study area.

**Impact:** no preview by default, so no misleading tile errors. The river-shape
check moves to after download, where `01_prepare.py` reports water area and
`valid` coverage per year from the real files. Set `SHOW_PREVIEW = true` to
inspect a 60 m preview before exporting.

## D74 - The trainer now scores against every trivial baseline, and the Jamuna's derived output is gone

**Date:** 2026-10-18

**Found, in `14_model_train.py`:**

1. `forecast_supported` was `model_mae < median_mae and model_mae < lag_mae`. It
   never compared against the **training-mean** baseline, even though that
   baseline was computed and printed one line earlier. If the mean baseline had
   come out lower than the model, the flag would have read "supported" while a
   flat "predict the average" beat it. On the current data the mean (2.680) is
   worse than the median (2.507) so the verdict does not change - the model
   loses either way - but the check was not testing what it claimed to.
2. The backtest fitted `min_samples_leaf=5` while the projection was fitted with
   `min_samples_leaf=3`, and the saved artefact described only the 5. So the
   reported MAE did not describe the model that drew the map on the website.
3. `FORECAST_FEATURES` had no protection against a same-interval column being
   added back. D63's leakage was exactly that mistake.

**Decision:** `forecast_supported` now requires beating the **best** of all three
trivial predictors (`best_baseline`, recorded alongside a `beaten_by` list). One
`RF_PARAMS` dict defines the forest for both the backtest and the final fit, and
the artefact is generated from it. A `LEAKY_COLUMNS` set raises rather than
proceeding if any same-interval column enters `FORECAST_FEATURES`.

**Also:** the Jamuna's `processed/` tree (248 MB) and its `_duplicates/` were
deleted. What remains is raw material only - the 37 Landsat masks, 8 S2 masks,
the downloaded GloFAS discharge table, and the D26 quarantine. That does not
weaken D44: the finding is measured from the raw masks and the discharge table,
both of which are still present and still re-derivable. The RGB exports (301 MB,
display only, nothing measures them) were left in place pending an explicit
decision.

**Reason:** The first two are the same failure the project keeps meeting - a
number that describes something other than what it is attached to. The third
turns a hard-won finding (D63) into a standing check instead of a note.

**Impact:** Re-running the trainer on the current data still gives MAE 3.175
against a 2.507 baseline, `forecast_supported: false`, now with `beaten_by:
["training median", "training mean"]`. Both are recorded in
`ml/artifacts/model_report.json`. The jamuna reach is registered but not
currently runnable until its derived files are rebuilt from the raw inputs.

## D75 - 09_checks.py crashed instead of reporting when a GloFAS table existed without a risk table

**Date:** 2026-10-18

**Found:** Section 10 imported `csv` as `_csv` **inside** its `if risk_csv.exists():`
branch. Section 11 also uses `_csv`, to read the GloFAS annual table. So whenever
a GloFAS table existed but the risk table did not, section 11 raised
`NameError: name '_csv' is not defined` and the whole check script died with a
traceback instead of printing results.

Exposed while deleting the Jamuna's derived output: the jamuna reach still had
its GloFAS table in `hydro/` but no longer had `risk/transect_risk.csv`, which is
exactly the combination that triggers it.

**Why it had never been seen:** the arial_khan reach currently has *neither* table,
so section 11 was bailing out at its "no GloFAS annual table yet" warning before
reaching the bad line. It would have fired on the rebuild, which runs
`12_glofas_discharge.py` (writes the GloFAS table) before
`13_risk_and_forecast.py` (writes the risk table) - so the first honest run of the
checks after the rebuild would have died with a Python traceback rather than
reporting anything.

**Decision:** Move `import csv as _csv` to the module-level imports, where section
11 can rely on it.

**Reason:** A guard script that crashes is worse than one that fails a check. It
returns exit 1 in both cases, but a traceback names an internal variable rather
than the condition that is wrong, and the checks after the crash never run at all
- so an unrelated later failure would be hidden by this earlier one.

**Impact:** Both reaches now exit 0: arial_khan 28 PASS, jamuna 18 PASS. The
J46 GloFAS re-derivation is confirmed intact by section 11 on the raw table that
survived the cleanup: 38 years, 37 complete, 2026 flagged incomplete.
