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
import maskops


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
    box_cov = None
    with rasterio.open(C.mask_path(year)) as src:
        # The exporter writes a `valid` band alongside `water`. MEASURED ON THE
        # REAL FILES (D76), it is NOT a measure of cloud or imagery quality: it
        # reads 96.1% for every Sentinel-2 year and 95.9% for every Landsat year,
        # and the pattern is pixel-for-pixel identical across 28 years.
        #
        # What it actually measures is geometry. The study area is a lat/lon
        # rectangle; the export grid is UTM 46N, and the two are rotated ~1.1
        # degrees apart. 14.3 km * tan(1.1 deg) ~ 275 m of the UTM raster falls
        # outside the rectangle at each corner, and `clip(aoi)` masks it. So the
        # band is the rectangle-to-grid overlap, which is a constant.
        #
        # It is kept and reported because it WOULD drop if a year's scenes failed
        # to cover the box at all, but it cannot detect a cloudy year. Cloud is
        # handled by the exporter's MAX_CLOUD filter and by the 25th-percentile
        # composite. Do not read this number as image quality.
        if src.count >= 2:
            b2 = src.read(2)
            if b2.size:
                box_cov = float(np.count_nonzero(b2 > 127)) / b2.size

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

        # Drop the ponds before writing, on OUR grid, so the rule is visible and
        # testable instead of buried in a server-side script whose version we
        # cannot see (D77).
        raw_km2 = float(np.count_nonzero(dst) * (C.RES ** 2) / 1e6)
        dst, dropped = maskops.river_body(dst, C.RES, C.RIVER_BODY_MIN_KM2)

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
        return box_cov, dropped, raw_km2
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

    return box_cov, dropped, raw_km2


def main():
    transform, width, height = build_grid()
    print(f"grid: {width} x {height} px @ {C.RES} m, crs={C.CRS_WORK}")

    gates = C.DOWNLOADS.get("s2", {})
    min_box = gates.get("MIN_VALID")

    # `box coverage` is the exporter's `valid` band: how much of the exported
    # raster is inside the study rectangle (D76). It is NOT image quality - it is
    # a near-constant for this reach. It is still checked, because it would fall
    # if a year's scenes failed to cover the box, but a low number here means a
    # footprint problem, not a cloudy one.
    thin = []
    areas = []
    ponds = []
    for year in C.YEARS:
        box_cov, dropped, raw_km2 = prepare_year(year, transform, width, height)
        with rasterio.open(C.proc_mask_path(year)) as s:
            water = np.count_nonzero(s.read(1) > 127)
        km2 = water * (C.RES ** 2) / 1e6
        areas.append((year, km2))
        if dropped:
            ponds.append((dropped, raw_km2, km2))

        parts = [f"  {year}: water {km2:8.1f} km2"]
        if box_cov is None:
            parts.append("box coverage     -")
        else:
            flag = ""
            if min_box is not None and box_cov < min_box:
                flag = f" <-- below the {min_box * 100:.0f}% gate"
                thin.append((year, box_cov))
            parts.append(f"box coverage {box_cov * 100:5.1f}%{flag}")
        if dropped:
            parts.append(f"dropped {len(dropped)} ponds "
                         f"({raw_km2 - km2:.1f} km2, largest {dropped[0][0]:.2f})")
        print("   ".join(parts))

    if thin:
        print("\n" + "=" * 66)
        print("WARNING: the exported raster does not cover the study rectangle.")
        print("That is a footprint problem, not cloud - check the export bounds.")
        print(f"Affected years: {', '.join(str(y) for y, _ in thin)}")
        print("=" * 66 + "\n")

    # The pond filter has to be audible. Silently dropping water would be worse
    # than keeping the ponds, because the bankline step would then measure a
    # truncated river and nothing would say so.
    maskops.summarise(ponds, C.RIVER_BODY_MIN_KM2)

    # Water area is the only quality signal these files carry. A year whose area
    # sits far from the rest of THIS reach's record is worth looking at before it
    # reaches the bankline step, because bankline movement derived from a wrong
    # water mask is noise that looks like a measurement.
    if len(areas) >= 5:
        vals = np.array([k for _, k in areas])
        med = float(np.median(vals))
        odd = [(y, k) for y, k in areas if med > 0 and (k < 0.5 * med or k > 2.0 * med)]
        if odd:
            print("NOTE: water area far from this reach's median "
                  f"({med:.1f} km2) - inspect before using:")
            for y, k in odd:
                print(f"  {y}: {k:.1f} km2  ({k / med:.2f}x median)")
            print()


if __name__ == "__main__":
    main()
