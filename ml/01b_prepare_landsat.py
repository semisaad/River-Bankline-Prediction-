"""01b - Prepare Landsat masks onto their own 30 m grid.

Runs this only after you have downloaded the Landsat masks from Google Earth
Engine into  data/raw/landsat/  (see gee/landsat_export.js).

Why Landsat gets its own folder instead of replacing Sentinel-2:
  - Landsat is 30 m per pixel, Sentinel-2 is 10 m. Blowing Landsat up to 10 m
    would invent detail the sensor never captured, and our measurements would
    then look more precise than they really are. So each sensor is processed at
    its own native resolution, in its own folder, and results are compared
    honestly.

If the folder is empty this script does nothing and tells you so. That is normal
until you run the Earth Engine export.
"""

import math

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.transform import from_origin
from rasterio.warp import reproject, transform_bounds

import config as C


def build_grid():
    # Use the LANDSAT footprint, not the wider Sentinel-2 box. Building the grid
    # on the wider box would leave a strip with no data, which reads as 0, which
    # reads as land - silently truncating the river. See config.BBOX_LANDSAT.
    left, bottom, right, top = transform_bounds(
        "EPSG:4326", C.CRS_WORK, *C.sensor_bbox("landsat"), densify_pts=21
    )
    width = math.ceil((right - left) / C.RES_LANDSAT)
    height = math.ceil((top - bottom) / C.RES_LANDSAT)
    transform = from_origin(left, top, C.RES_LANDSAT, C.RES_LANDSAT)
    return transform, width, height


def prepare_year(year, transform, width, height):
    """Reproject one Landsat mask onto our grid.

    Returns (array, coverage, valid_frac). Coverage is the fraction of our grid
    the source actually covers; valid_frac is the fraction of the source that
    had usable, cloud-free imagery, read from the `valid` band.

    WHY COVERAGE MATTERS: anything the source does not cover stays 0 in the
    output, and 0 means LAND in our convention. So an uncovered strip would be
    read as dry land sitting next to the river, which would drag the bankline
    inland with no error anywhere. We measure it and complain loudly instead.

    WHY valid_frac MATTERS: coverage counts pixels that ARRIVED, not pixels that
    are usable. A year returned entirely as cloud and shadow still covers the
    grid. Landsat 7 in particular has scan-line gaps. This number used to be
    gated inside the Earth Engine script; that survey was removed to stop the
    Code Editor freezing (D71), so the judgement happens here now.
    """
    src_path = C.land_raw_mask_path(year)
    out_path = C.land_proc_mask_path(year)

    valid_frac = None
    with rasterio.open(src_path) as src:
        if src.count >= 2:
            b2 = src.read(2)
            if b2.size:
                valid_frac = float(np.count_nonzero(b2 > 127)) / b2.size

        dst = np.zeros((height, width), dtype="uint8")
        reproject(
            source=rasterio.band(src, 1),
            destination=dst,
            src_transform=src.transform,
            src_crs=src.crs,
            dst_transform=transform,
            dst_crs=C.CRS_WORK,
            resampling=Resampling.nearest,
        )

        # a companion raster of ones, to see which parts we actually received
        ones = np.ones((src.height, src.width), dtype="uint8")
        cov = np.zeros((height, width), dtype="uint8")
        reproject(
            source=ones,
            destination=cov,
            src_transform=src.transform,
            src_crs=src.crs,
            dst_transform=transform,
            dst_crs=C.CRS_WORK,
            resampling=Resampling.nearest,
        )

    coverage = float((cov > 0).mean())

    meta = dict(
        driver="GTiff", height=height, width=width, count=1,
        dtype="uint8", crs=C.CRS_WORK, transform=transform,
        compress="deflate", nodata=0,
    )
    with rasterio.open(out_path, "w", **meta) as d:
        d.write(dst, 1)

    return dst, coverage, valid_frac


def main():
    years = C.available_landsat_years()
    if not years:
        print("No Landsat files found in:", C.DATA_RAW_LANDSAT)
        print("Nothing to do. Run gee/landsat_export.js in Google Earth Engine first,")
        print("then put the downloaded MNDWI_Mask_<year>.tif files in that folder.")
        return

    transform, width, height = build_grid()
    print(f"Landsat grid: {width} x {height} px @ {C.RES_LANDSAT} m, crs={C.CRS_WORK}")
    print(f"years found: {len(years)} ({years[0]}..{years[-1]})\n")

    min_valid = C.DOWNLOADS.get("landsat", {}).get("MIN_VALID")

    areas = []
    thin = []
    cloudy = []
    for y in years:
        arr, cov, vfrac = prepare_year(y, transform, width, height)
        km2 = int((arr > 127).sum()) * (C.RES_LANDSAT ** 2) / 1e6
        areas.append((y, km2))
        flag = ""
        if cov < 0.99:
            flag = f"   <-- only {cov*100:.0f}% of our grid covered"
            thin.append((y, cov))
        if vfrac is None:
            vtxt = "valid     -"
        else:
            vtxt = f"valid {vfrac*100:5.1f}%"
            if min_valid is not None and vfrac < min_valid:
                flag += "   <-- mostly cloud/shadow or empty"
                cloudy.append((y, vfrac))
        print(f"  {y}: water {km2:8.1f} km2  coverage {cov*100:5.1f}%  {vtxt}{flag}")

    if thin:
        print("\n" + "=" * 66)
        print("WARNING: some years do not cover the full study area.")
        print("Uncovered ground arrives as 0, which we read as LAND.")
        print("Using these years would pull the bankline inland.")
        print("Fix: re-export Landsat over the box the S2 script prints, and")
        print("check the printed EXPORT RECTANGLE against config.sensor_bbox():")
        print(f"   {tuple(C.sensor_bbox('landsat'))}")
        print(f"Affected years: {', '.join(str(y) for y, _ in thin)}")
        print("=" * 66 + "\n")

    if cloudy:
        print("\n" + "=" * 66)
        print("WARNING: some years are mostly cloud, shadow, or empty.")
        print("Landsat 7 scan-line gaps make this normal for 2003-2012, but a")
        print("year below the gate has too little imagery to measure a bankline.")
        print(f"Affected years: {', '.join(str(y) for y, _ in cloudy)}")
        print("Inspect them before using them; do not just lower the gate.")
        print("=" * 66 + "\n")

    good = [k for _, k in areas if k > 5]
    blank = [y for y, k in areas if k <= 5]
    if good:
        print(f"usable years (water > 5 km2): {len(good)}/{len(areas)}")
        print(f"median water area {np.median(good):.1f} km2")
    else:
        print("\nWARNING: no year had more than 5 km2 of water. Check the export.")
    if blank:
        print(f"blank years (water <= 5 km2): {blank}")
        print("  these are the empty-mask problem from D26 - do not use them.")


if __name__ == "__main__":
    main()