# WHAT SAAD NEEDS TO DO (1 thing, ~1 hour)

**Everything is ready on the laptop. The only thing missing is imagery for the
new river, and only your Google Earth Engine account can get it.**

We have switched from the Jamuna to the **Arial Khan (Madaripur Sadar -
Muladi)** because the Jamuna's year-to-year movement turned out to be
unpredictable. The Arial Khan is 300 m wide and single-threaded rather than 9 km
wide and braided, which is the specific reason the old approach failed there.

---

## ACTION 1 — Export Landsat for the Arial Khan

**How long:** ~30-60 minutes, mostly waiting.

**Steps:**

1. Open **https://code.earthengine.google.com**
2. Open `riverguard/gee/landsat_export_arial_khan.js` and copy the **whole** file.
3. Paste into the GEE editor, press **Run**.
4. **STOP HERE. Read the console table before running anything.**

The script prints one line per year:

```
year | images | valid | water | status
```

**What you should see:**

| Column | Expect |
|---|---|
| `water` | **1-3%** — this box is mostly farmland with a 300 m river |
| `status` | ~30-40 years marked **EXPORT** |

**Two warnings in the file, both important:**

- If `water` shows something wildly different, the water threshold may not suit
  this river. **Bring me the table instead of exporting.**
- If the preview map at the end shows a **wide braided belt**, the study box is
  wrong. It should look like a **single thin ribbon**.

5. Once the table looks right: open the **Tasks** tab, right-click → **Run task**,
   about **5 at a time**.
6. Download the folder **`riverguard_arial_khan`** from Google Drive.
7. Unzip it and drop every `.tif` into:
   ```
   mkdir -p ~/Projects/riverguard/data/reaches/arial_khan/raw/landsat
   ```
   **No renaming needed** — the filenames already match what the pipeline wants.

**Then tell me "arial khan done"** and I will verify the data, tune the geometry
for a 300 m river, and run the full analysis.

---

## After that, these are already built and waiting

I have already done, and verified:

- the reach registered in the pipeline (it's a config change — the Jamuna's
  results are untouched)
- the export script, syntax-checked
- every geometry threshold rescaled for a 300 m river
- **three cautions written down in advance** so they can't be forgotten:
  - GloFAS may report the *Padma's* discharge rather than the distributary's
  - the water threshold 0.2 was tuned on the Jamuna and is unverified here
  - the geometry thresholds are guesses until real imagery exists

---

## Your own notes from the Jamuna work

The Jamuna result stands and is documented in `reports/RISK.md` and
`reports/VALIDATION.md`: 37 years of imagery and real river discharge, and
year-to-year erosion still could not be predicted. That negative result is a
genuine finding, not a failure — keep it for your write-up.

---

## Running the old reach (optional, still works)

```
cd ~/Projects/riverguard/ml
RIVERGUARD_REACH=jamuna ../.venv/bin/python 13_risk_and_forecast.py
RIVERGUARD_REACH=ganges ../.venv/bin/python 04_erosion.py landsat
RIVERGUARD_REACH=arial_khan ../.venv/bin/python 04_erosion.py landsat
```
