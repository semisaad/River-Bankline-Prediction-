"""00 - Collect the Landsat files you downloaded from Google Drive.

WHAT THIS IS FOR
  The Landsat masks live in your Google Drive. This script finds them wherever
  your browser put them, checks each one is actually usable, renames it to the
  exact name the pipeline expects, and moves it into data/raw/landsat/.

WHAT IT CHECKS ON EVERY FILE
  - single band, unsigned 8-bit
  - values are only 0 or 255 (0 = land, 255 = water)
  - it is not blank
  - it covers roughly the right area
  Files that fail are REPORTED, not silently accepted. A blank or corrupted year
  is worse than a missing one, because a blank mask looks like "the river was not
  there", which would quietly corrupt the measurement.

HOW TO USE
  1. In Chrome, open https://drive.google.com/drive/folders/...
     (the "RiverGuard_Landsat" folder Earth Engine wrote to)
  2. Select all files -> right-click -> Download -> Zip file
  3. Unzip it in your Downloads folder (double-click the zip)
  4. Come back and say "done". This script does the rest.

You can also just download the files one at a time; this handles either way.
"""

import re
import shutil
import sys
from pathlib import Path

import numpy as np
import rasterio

import config as C

# Where a browser might have put them.
SEARCH_DIRS = [
    Path.home() / "Downloads",
    Path.home() / "Downloads" / "RiverGuard_Landsat",
    Path("/media/saad/HDD/riverguard/data/raw/landsat"),
]

YEAR_RE = re.compile(r"(19|20)\d{2}")


def find_candidates():
    seen = {}
    for d in SEARCH_DIRS:
        if not d.exists():
            continue
        for p in d.rglob("*.tif"):
            # Files already in the target folder are still validated, because a
            # blank mask sitting in the right place is exactly as dangerous as
            # one in the wrong place.
            seen.setdefault(p.name, p)
            seen[p.name.lower()] = p
    return list({str(v): v for v in seen.values()}.values())


def inspect(path):
    """Return (ok, note, water_fraction).

    Accepts either a 1-band water mask, or the 2-band form the Earth Engine
    script writes: band 1 = water, band 2 = valid-data fraction. When band 2 is
    present we require decent coverage, because a year that is mostly missing
    data is not a usable record.
    """
    try:
        with rasterio.open(path) as s:
            if s.count not in (1, 2):
                return False, f"{s.count} bands (expected 1 or 2)", 0.0
            if s.dtypes[0] != "uint8":
                return False, f"dtype {s.dtypes[0]} (expected uint8)", 0.0
            a = s.read(1)
            valid = s.read(2) if s.count == 2 else None
            crs = s.crs
    except Exception as e:
        return False, f"cannot open: {type(e).__name__}", 0.0

    vals = np.unique(a)
    unexpected = [int(v) for v in vals if v not in (0, 255)]
    if unexpected:
        return False, f"unexpected values {unexpected[:4]}", 0.0

    frac = float((a > 127).mean())
    if frac < 0.01:
        return False, "blank (almost no water)", frac
    if frac > 0.85:
        return False, f"suspiciously wet ({frac*100:.0f}% water)", frac

    note = f"{a.shape[1]}x{a.shape[0]}"
    if valid is not None:
        vfrac = float((valid > 127).mean())
        if vfrac < 0.90:
            return False, f"only {vfrac*100:.0f}% of the box has imagery", frac
        note += f" {vfrac*100:.0f}%valid"
    if crs is None:
        note += " (no CRS!)"
    return True, note, frac


def main():
    C.DATA_RAW_LANDSAT.mkdir(parents=True, exist_ok=True)

    cands = find_candidates()
    if not cands:
        print("No .tif files found. Looked in:")
        for d in SEARCH_DIRS:
            print(f"  {d}{'' if d.exists() else '   (does not exist)'}")
        print()
        print("Download them from Google Drive first:")
        print("  https://drive.google.com  ->  RiverGuard_Landsat folder")
        print("  Select all -> Download (as zip) -> unzip in Downloads")
        return

    print(f"found {len(cands)} candidate file(s)\n")
    good, bad, stale = [], [], []

    for p in sorted(cands):
        m = YEAR_RE.search(p.stem)
        if not m:
            bad.append((p, "no 4-digit year in the name"))
            continue

        ok, note, frac = inspect(p)
        if not ok:
            bad.append((p, note))
            continue

        year = int(m.group(0))
        dest = C.DATA_RAW_LANDSAT / f"MNDWI_Mask_{year}.tif"
        # The Earth Engine script writes LS_MNDWI_Mask_<year>.tif; normalise it
        # to the name the pipeline expects so nothing downstream has to care.
        if p.resolve() == dest.resolve():
            good.append((year, p, note, frac, "in place"))
            continue
        if dest.exists():
            # A differently-named copy already holds this year. Keep one
            # canonical file only, otherwise every run adds another duplicate.
            good.append((year, dest, note, frac, "already normalised"))
            try:
                if p.resolve() != dest.resolve() and p.stat().st_size == dest.stat().st_size:
                    stale.append(p)
            except OSError:
                pass
            continue
        shutil.move(str(p), str(dest))
        good.append((year, dest, note, frac, "moved"))

    for p in stale:
        shutil.move(str(p), str(C.DATA_RAW / "_duplicates" / p.name))

    good.sort()
    print(f"{'year':<6} {'water %':>8}  {'size':<14} status")
    print("-" * 52)
    for year, path, note, frac, status in good:
        print(f"{year:<6} {frac*100:7.1f}%  {note:<14} {status}")

    if bad:
        print(f"\nSKIPPED {len(bad)} file(s):")
        for p, why in bad:
            print(f"  {p.name:<34} {why}")

    years = C.available_landsat_years()
    print(f"\nready: {len(years)} year(s)")
    if years:
        print(f"range: {years[0]} .. {years[-1]}")
        gaps = [y for y in range(years[0], years[-1] + 1) if y not in years]
        if gaps:
            print(f"gaps ({len(gaps)}): {', '.join(map(str, gaps))}")
            print("  Landsat 7 failed in 2003 (SLC-off), so 2003-2013 gaps are expected.")
        if len(years) >= 2:
            new_pairs = len(years) - 1
            print(f"that gives {new_pairs} year-to-year intervals for training")
    else:
        print("nothing usable yet")

    if len(years) >= 3:
        print("\nnext step:  ../.venv/bin/python 01b_prepare_landsat.py")


if __name__ == "__main__":
    main()