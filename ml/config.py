"""Shared configuration for the RiverGuard pipeline.

The analysis reach is chosen with one environment variable:

    RIVERGUARD_REACH=ganges ../.venv/bin/python 04_erosion.py landsat

    Unset, it means arial_khan, and every path and value is exactly what it has
always been - the backend serves from these folders, so the reach switch
must never move the jamuna data. All spatial analysis is done in a
projected CRS (metres), not lat/lon.
"""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# --- reach registry ----------------------------------------------------------
# ganges is the generalisation trial of DECISIONS.md D48: the single-thread
# meandering Rajshahi - Hardinge Bridge reach, where bank movement is expected
# to persist year on year. That expectation is a hypothesis from literature,
# not a finding. Its transect gates are first guesses scaled down from the
# Jamuna's for a river 1-4 km wide, to be verified against the first real
# data (10_verify_geometry.py spot checks).
REACHES = {
    # ARCHIVED 2026-10-18, not deleted. The Jamuna data was moved to
    # data/unused_data/jamuna/ when the Arial Khan became the active reach (D49).
    # It is kept for three reasons:
    #   1. it is the EVIDENCE for the project's central negative result (D44) -
    #      37 years and real river discharge still could not predict erosion, and
    #      that finding is what motivated the switch;
    #   2. it is the CONTROL. Comparing a 9 km braided reach against a 300 m
    #      single-thread one is the actual experiment;
    #   3. the 37 Landsat files took the owner about an hour of Earth Engine work
    #      to download and would have to be repeated from scratch.
    # The reach remains fully runnable: RIVERGUARD_REACH=jamuna still works.
    "jamuna": {
        "label": "Jamuna (Kazipur / Sirajganj)",
        "bbox": (89.65, 24.30, 89.85, 24.60),
        "bbox_landsat": (89.65, 24.35, 89.85, 24.60),
        "raw_dir": ROOT / "data" / "unused_data" / "jamuna",
        "proc_dir": ROOT / "data" / "unused_data" / "jamuna" / "processed",
        "geom": {"ref_year": 2023, "sensor": "s2"},
        "gates": {},
    },
    "ganges": {
        "label": "Ganges (Rajshahi - Hardinge Bridge)",
        "bbox": (88.55, 23.95, 89.10, 24.40),
        "bbox_landsat": (88.55, 23.95, 89.10, 24.40),
        "crs": "EPSG:32645",
        "raw_dir": ROOT / "data" / "reaches" / "ganges" / "raw",
        "proc_dir": ROOT / "data" / "reaches" / "ganges" / "processed",
        "geom": {"ref_year": 2020, "sensor": "landsat"},
        "gates": {
            "MIN_WIDTH_M": 1200.0,
            "MIN_WET_WIDTH_M": 900.0,
            "MAX_CAST_M": 6000.0,
            "MARGIN_M": 500.0,
            "ZONE_M": 600.0,
        },
    },
    # Arial Khan, MIDDLE reach: Madaripur Sadar down to Kalkini. Chosen
    # 2026-10-18 after D44/D47 found the Jamuna unpredictable (D49).
    #
    # WHY THIS REACH. The Jamuna's belt is ~9 km wide and braided, so one GloFAS
    # cell (~5.5 km) cannot say WHERE along the reach the water attacks the bank.
    # That is the specific reason discharge showed no signal there. The Arial Khan
    # averages 300 m wide and is single-threaded, so the reach fits inside one
    # cell. Published migration is ~21 m/yr (0.66 km over 1993-2024) against the
    # Jamuna's ~110 m/yr - slower, so more predictable, but smaller numbers.
    #
    # WHY THE MIDDLE REACH AND NOT MULADI. Muladi Upazila (22.92N 90.42E) is on
    # this river, but near its MOUTH, about 70 km downstream - it is not near
    # Madaripur at all. The lower reach branches near the Tetulia and takes
    # tidal influence, both of which move the waterline for reasons that have
    # nothing to do with erosion. That would reintroduce exactly the ambiguity
    # this switch exists to remove. Muladi stays a literature comparison point.
    #
    # THE BOX EXCLUDES THE PADMA, and this is the single most important thing to
    # check when the export is previewed. The pipeline keeps the largest CONNECTED
    # water body. The Padma runs only 21 km west of the Arial Khan here, so a box
    # that clips it would silently measure the Padma instead - a bigger, more
    # obvious river, and entirely wrong. The western edge sits at 90.08E, about
    # 11 km clear of the Padma. If the preview map shows two rivers, stop.
    "arial_khan": {
        "label": "Arial Khan (Madaripur Sadar - Kalkini, middle reach)",
        "bbox": (90.16808799423755, 23.134319063780836,
             90.26902488388599, 23.261491731177696),
        "bbox_landsat": (90.16808799423755, 23.134319063780836,
                 90.26902488388599, 23.261491731177696),
        # Entirely east of 90E, so UTM zone 46N (CM 93E). Measured both ways on
        # this box: zone 46 is marginally better here, ~0.20% against ~0.25%,
        # and both are far below the 10 m pixel size.
        "crs": "EPSG:32646",
        "raw_dir": ROOT / "data" / "reaches" / "arial_khan" / "raw",
        "proc_dir": ROOT / "data" / "reaches" / "arial_khan" / "processed",
        # Geometry from Sentinel-2, not Landsat: at 10 m a 300 m river is 30
        # pixels across against 10 at 30 m. Accuracy was the deciding criterion.
        "geom": {"ref_year": 2024, "sensor": "s2"},
        # 30 m Landsat sees ~0.7 px/yr of a 21 m/yr river, so annual pairs there
        # would measure noise. Blocks of 5 yr give ~3.5 px. S2 at 10 m moves
        # ~2.1 px/yr, so it stays annual.
        "pair_step": {"landsat": 5, "s2": 1},
        # narrow single-thread river: find the banks by the contiguous water run
        # through the centre, not by the smoothed-fraction rule that suits a 9 km
        # braided belt and mistakes a pond for the far bank
        "profile_mode": "run",
        # Every gate below is scaled from the Jamuna's for a river ~300 m wide
        # instead of a 9 km belt. THESE ARE UNVERIFIED GUESSES until real
        # imagery exists - 10_verify_geometry.py must spot-check them and they
        # are expected to need adjustment.
        "gates": {
            "SPACING_M": 250.0,
            "MIN_RIDGE_DEPTH_M": 40.0,
            "MARGIN_M": 250.0,
            "GAP_BRIDGE_M": 100.0,
            "MIN_WIDTH_M": 150.0,
            "MIN_WET_WIDTH_M": 100.0,
            "MAX_WIDTH_M": 3000.0,
            # a 300 m channel needs no more than ~800 m of cast each way; casting
            # 3 km reaches connected ponds and reports them as a 3 km river
            "MAX_CAST_M": 900.0,
            # a channel 300 m wide is not plausibly 3 km wide, so anything past
            # 1200 m means the run leaked into a pond
            "MAX_WIDTH_M": 1200.0,
            "MARGIN_M": 350.0,
            "EDGE_WINDOW_M": 100.0,
            "MIN_EDGE_FRAC": 0.30,
            "ZONE_M": 300.0,
            "BUFFER_M": 120.0,
        },
    },
}

REACH = os.environ.get("RIVERGUARD_REACH", "arial_khan").strip().lower()
if REACH not in REACHES:
    raise SystemExit(f"unknown reach {REACH!r}; choose one of {sorted(REACHES)}")
_r = REACHES[REACH]
REACH_LABEL = _r["label"]
GEOM = _r["geom"]
REACH_TRANSECT_GATES = _r["gates"]
PROFILE_MODE = _r.get("profile_mode", "smoothed")

DATA_RAW = _r["raw_dir"]
DATA_PROC = _r["proc_dir"]
BANKLINES = DATA_PROC / "banklines"
TRANSECTS = DATA_PROC / "transects"

for _d in (DATA_PROC, BANKLINES, TRANSECTS):
    _d.mkdir(parents=True, exist_ok=True)

# Study region (same bbox the GEE exports were made with).
BBOX_WGS84 = _r["bbox"]  # min_lon, min_lat, max_lon, max_lat

# Projected CRS for the reach. Per-reach, because reaches that straddle a UTM
# zone boundary need this chosen deliberately rather than inherited.
# Every reach here uses a projected CRS in metres, never lat/lon.
CRS_WORK = _r.get("crs", "EPSG:32645")

# Working pixel size (metres). Sentinel-2 native = 10 m.
RES = 10.0

# Years we currently have downloaded (Sentinel-2, 2019-2026).
YEARS = [2019, 2020, 2021, 2022, 2023, 2024, 2025, 2026]

# Fixed dry-season window (constant across every year to avoid
# water-level-driven fake migration). This is the window the GEE export scripts
# actually request, and 09_checks.py section 8 verifies that they agree with it.
DRY_SEASON = ("01-01", "03-25")

# --- Sentinel-2 record (what we originally downloaded) ---
S2_YEARS = list(range(2019, 2027))

# --- Landsat record (1984 onwards, downloaded from gee/landsat_export.js) ---
# Landsat is 30 m, not 10 m. We never resample it to 10 m because that would
# invent detail the sensor does not have. It gets its own grid instead.
RES_LANDSAT = 30.0
DATA_RAW_LANDSAT = DATA_RAW / "landsat"
DATA_PROC_LANDSAT = DATA_PROC / "landsat"
BANKLINES_LANDSAT = DATA_PROC_LANDSAT / "banklines"
TRANSECTS_LANDSAT = DATA_PROC_LANDSAT / "transects"

for _d in (DATA_PROC_LANDSAT, BANKLINES_LANDSAT, TRANSECTS_LANDSAT):
    _d.mkdir(parents=True, exist_ok=True)


def mask_path(year: int) -> Path:
    return DATA_RAW / f"MNDWI_Mask_{year}.tif"


def rgb_path(year: int) -> Path:
    return DATA_RAW / f"RGB_{year}.tif"


def proc_mask_path(year: int) -> Path:
    return DATA_PROC / f"mask_{year}.tif"


def proc_rgb_path(year: int) -> Path:
    return DATA_PROC / f"rgb_{year}.tif"


def bankline_path(year: int) -> Path:
    return BANKLINES / f"bankline_{year}.geojson"


def land_raw_mask_path(year: int) -> Path:
    return DATA_RAW_LANDSAT / f"MNDWI_Mask_{year}.tif"


def land_proc_mask_path(year: int) -> Path:
    return DATA_PROC_LANDSAT / f"mask_{year}.tif"


def available_landsat_years() -> list[int]:
    """Years the owner has actually downloaded and dropped into data/raw/landsat."""
    years = []
    if DATA_RAW_LANDSAT.exists():
        for p in DATA_RAW_LANDSAT.glob("MNDWI_Mask_*.tif"):
            try:
                years.append(int(p.stem.split("_")[-1]))
            except ValueError:
                continue
    return sorted(years)


# --- sensor registry -------------------------------------------------------
# We analyse each sensor at its OWN native resolution and in its OWN output
# folder. Nothing is ever resampled between them, because upsampling a 30 m
# sensor to 10 m would invent detail that was never captured and would make the
# measurements look falsely precise.
#
# The primary analysis record is Landsat (long, single resolution, consistent).
# Sentinel-2 keeps a shorter, sharper record and is used as the INDEPENDENT
# cross-sensor check. See reports/DECISIONS.md D29.

# The area BOTH sensors actually cover.
#
# Landsat was exported over 89.62-24.35 to 89.85-24.65, which is SMALLER than
# the Sentinel-2 box (89.65-24.30 to 89.85-24.60). A southern strip about 5.5 km
# wide holds no Landsat data and contains roughly 11.7% of the traced river.
#
# Rather than resample or invent data, each sensor is analysed on its own
# footprint, and any cross-sensor comparison is restricted to this shared box so
# both instruments are looking at identical ground. For the ganges trial the
# two boxes are identical, so the shared box is simply the box.
BBOX_LANDSAT = _r["bbox_landsat"]
BBOX_COMMON  = BBOX_LANDSAT

SENSORS = {
    "s2": {
        "res": 10.0,
        "bbox": BBOX_WGS84,
        "mask_dir": DATA_PROC,
        "out_dir": DATA_PROC,
        "years": list(range(2019, 2027)),
    },
    "landsat": {
        "res": 30.0,
        "bbox": BBOX_LANDSAT,
        "mask_dir": DATA_PROC_LANDSAT,
        "out_dir": DATA_PROC_LANDSAT,
        "years": None,          # filled in from what was actually downloaded
    },
}


def sensor_res(sensor: str) -> float:
    return SENSORS[sensor]["res"]


def sensor_bbox(sensor: str) -> tuple:
    """Analysis bounding box for a sensor."""
    return SENSORS[sensor]["bbox"]


def sensor_mask_path(sensor: str, year: int) -> Path:
    return SENSORS[sensor]["mask_dir"] / f"mask_{year}.tif"


def sensor_out_dir(sensor: str) -> Path:
    d = SENSORS[sensor]["out_dir"]
    return d


def sensor_transects_dir(sensor: str) -> Path:
    d = SENSORS[sensor]["out_dir"] / "transects"
    d.mkdir(parents=True, exist_ok=True)
    return d


# How many years each measurement window spans, per sensor.
#
# This is a RESOLUTION decision, not a preference. The Arial Khan erodes at
# roughly 21 m/yr:
#     Landsat 30 m -> the bank moves ~0.7 PIXELS per year. A single year may not
#                     cross even one pixel boundary, so annual pairs measure
#                     which way a random pixel boundary happened to fall.
#     Sentinel-2 10 m -> ~2.1 pixels per year. Annual pairs are genuinely visible.
#
# So Landsat is measured in 5-year blocks (~3.5 px, solid) and Sentinel-2
# annually. The Jamuna defaults to 1 for both because it erodes at ~110 m/yr,
# which is ~3.7 Landsat pixels per year - annual pairs are fine at that rate.
PAIR_STEP = _r.get("pair_step", {"landsat": 1, "s2": 1})


def sensor_pairs(sensor: str) -> list:
    """Year pairs for a sensor, at that sensor's configured window length."""
    step = PAIR_STEP.get(sensor, 1)
    ys = sensor_years(sensor)
    return [(y, y + step) for y in ys if y + step in ys]


def sensor_years(sensor: str) -> list[int]:
    """Years available for a sensor, from the processed masks on disk."""
    d = SENSORS[sensor]["mask_dir"]
    if not d.exists():
        return []
    ys = []
    for p in d.glob("mask_*.tif"):
        try:
            ys.append(int(p.stem.split("_")[1]))
        except (IndexError, ValueError):
            continue
    return sorted(ys)
