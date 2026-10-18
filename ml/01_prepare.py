"""01 - Prepare: reproject + clip raw GEE exports to a common UTM grid.

Turns EPSG:4326 lat/lon exports into a fixed EPSG:32645 (metres) grid at
RES metres, so every year lines up pixel-for-pixel and distances are real.
"""

import math

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.transform import from_origin
from rasterio.warp import reproject, transform_bounds

import config as C


def build_grid():
    left, bottom, right, top = transform_bounds(
        "EPSG:4326", C.CRS_WORK, *C.BBOX_WGS84, densify_pts=21
    )
    width = math.ceil((right - left) / C.RES)
    height = math.ceil((top - bottom) / C.RES)
    transform = from_origin(left, top, C.RES, C.RES)
    return transform, width, height


def prepare_year(year, transform, width, height):
    out_mask = C.proc_mask_path(year)
    out_rgb = C.proc_rgb_path(year)

    # --- mask (nearest so 0/255 stays exact) ---
    valid_frac = None
    with rasterio.open(C.mask_path(year)) as src:
        # The exporter writes a `valid` band alongside `water`: the fraction of
        # the box that had usable, cloud-free imagery that year. It is measured
        # on the SOURCE raster, before reprojection, because that is what the
        # satellite actually delivered.
        #
        # Only band 1 is kept downstream - `water` - so if this is not recorded
        # here the number is lost. It used to be gated inside the Earth Engine
        # script, but that survey was removed to stop the Code Editor freezing
        # (D71), which moved the judgement to this file.
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
        meta = dict(
            driver="GTiff", height=height, width=width, count=1,
            dtype="uint8", crs=C.CRS_WORK, transform=transform,
            compress="deflate", nodata=0,
        )
        with rasterio.open(out_mask, "w", **meta) as d:
            d.write(dst, 1)

    # --- rgb (bilinear, display only) ---
    # Optional. RGB is used purely for the visual QC overlays; nothing in the
    # measurement reads it. The Arial Khan export produces only the two-band
    # water/valid mask, so a missing RGB file is normal there and must not stop
    # the pipeline.
    rgb_in = C.rgb_path(year)
    if not rgb_in.exists():
        return valid_frac
    with rasterio.open(rgb_in) as src:
        dst = np.zeros((3, height, width), dtype="uint16")
        for b in range(1, 4):
            reproject(
                source=rasterio.band(src, b),
                destination=dst[b - 1],
                src_transform=src.transform,
                src_crs=src.crs,
                dst_transform=transform,
                dst_crs=C.CRS_WORK,
                resampling=Resampling.bilinear,
            )
        meta = dict(
            driver="GTiff", height=height, width=width, count=3,
            dtype="uint16", crs=C.CRS_WORK, transform=transform,
            compress="deflate",
        )
        with rasterio.open(out_rgb, "w", **meta) as d:
            d.write(dst)

    return valid_frac


def main():
    transform, width, height = build_grid()
    print(f"grid: {width} x {height} px @ {C.RES} m, crs={C.CRS_WORK}")

    gates = C.DOWNLOADS.get("s2", {})
    min_valid = gates.get("MIN_VALID")

    # The exporter no longer judges validity before downloading (D71), so this
    # is where a year gets flagged. Measured on the file that actually arrived,
    # not on a server-side preview of it.
    thin = []
    for year in C.YEARS:
        valid_frac = prepare_year(year, transform, width, height)
        with rasterio.open(C.proc_mask_path(year)) as s:
            water = np.count_nonzero(s.read(1) > 127)
        km2 = water * (C.RES ** 2) / 1e6
        if valid_frac is None:
            print(f"  {year}: water {km2:8.1f} km2   no valid band")
            continue
        flag = ""
        if min_valid is not None and valid_frac < min_valid:
            flag = f"   <-- below the {min_valid * 100:.0f}% gate"
            thin.append((year, valid_frac))
        print(f"  {year}: water {km2:8.1f} km2   valid {valid_frac * 100:5.1f}%{flag}")

    if thin:
        print("\n" + "=" * 66)
        print("WARNING: some years are mostly cloud, shadow or empty.")
        print("The water area for those years is measured from too little")
        print("imagery to trust, and bankline movement derived from it is noise.")
        print(f"Affected years: {', '.join(str(y) for y, _ in thin)}")
        print("Inspect them before using them; do not just lower the gate.")
        print("=" * 66 + "\n")


if __name__ == "__main__":
    main()
