"""08 - Cross-sensor agreement between Sentinel-2 and Landsat.

This is the strongest validation available without ground truth. Sentinel-2 and
Landsat are different instruments, flown at different times, with different
resolutions. If both independently say "this bank moved" and "this one did not",
we have good reason to believe it. If they disagree wildly, one of them is
wrong and we need to know that before trusting either.

HOW IT WORKS
  Both sensors cover 2019-2026, so we can compare them directly for those
  years. To compare fairly we put both on a common 30 m grid, because that is
  Landsat's native resolution. Sentinel-2 is 10 m, so we make 3x3 blocks and call
  a block "water" if the majority of its pixels are water. That is the honest
  way to compare, rather than pretending Landsat sees 10 m detail.

  Three things get measured:
    - IoU: how much the two water maps overlap (1.0 = perfect agreement)
    - water-area difference: are they estimating the same amount of water
    - bankline offset: how far apart the two traced river edges are

Run 01b_prepare_landsat.py first.
"""

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.features import shapes
from rasterio.warp import reproject
from shapely.geometry import Point, Polygon, shape

import config as C
import transects as T


# Both sensors must be compared on the SAME ground. Landsat's export starts at
# 24.35N while Sentinel-2's starts at 24.30N, so the southern strip has no
# Landsat data and would read as land. We clip both to the shared footprint
# (config.BBOX_COMMON) before comparing anything.
COMMON = C.BBOX_COMMON


def clip_to_common(mask, transform, width, height):
    """Zero out anything outside the shared Sentinel-2 / Landsat footprint."""
    from rasterio.features import geometry_mask
    from rasterio.warp import transform_bounds
    from shapely.geometry import box

    l, b, r, t = transform_bounds("EPSG:4326", C.CRS_WORK, *COMMON, densify_pts=21)
    from rasterio.transform import array_bounds
    x0, y0, x1, y1 = array_bounds(height, width, transform)
    poly = box(max(l, x0), max(b, y0), min(r, x1), min(t, y1))
    zone = geometry_mask([poly], out_shape=(height, width), transform=transform,
                         invert=True)
    return mask & zone


def load_s2(year):
    with rasterio.open(C.sensor_mask_path("s2", year)) as s:
        m = s.read(1) > 127
        m = clip_to_common(m, s.transform, s.width, s.height)
        return m, s.transform, s.crs, (s.height, s.width)


def load_landsat(year):
    """Band 1 is water. Band 2, when present, is the valid-data mask."""
    p = C.land_proc_mask_path(year)
    with rasterio.open(p) as s:
        water = s.read(1) > 127
        if s.count >= 2:
            valid = s.read(2) > 127
            # Uncovered ground is not land. Mask it out rather than trusting 0.
            water = water & valid
        water = clip_to_common(water, s.transform, s.width, s.height)
        return water, s.transform, s.crs, (s.height, s.width)


def downsample_to_30m(bool_mask, transform, target_transform, shape_hw):
    """Majority-vote a fine mask down to 30 m so both sensors share a grid.

    The resampling is done in float. Averaging 0/1 pixels yields values between
    0 and 1, so the threshold must be 0.5 - testing "> 127" (which was the
    earlier bug here) is never true and silently produced an all-zero mask.
    """
    out = np.zeros(shape_hw, dtype="float32")
    reproject(
        source=bool_mask.astype("float32"),
        destination=out,
        src_transform=transform,
        src_crs=C.CRS_WORK,
        dst_transform=target_transform,
        dst_crs=C.CRS_WORK,
        resampling=Resampling.average,
    )
    return out > 0.5


def iou(a, b):
    inter = np.logical_and(a, b).sum()
    union = np.logical_or(a, b).sum()
    return float(inter / union) if union else float("nan")


def bank_offset(mask, transform):
    """Trace the outer belt on this mask and return it as a polygon."""
    from scipy.ndimage import binary_fill_holes, label
    from skimage.morphology import closing, disk

    m = binary_fill_holes(closing(mask, disk(1)))
    lab, _ = label(m)
    counts = np.bincount(lab.ravel())[1:]
    if len(counts) == 0:
        return None
    belt = lab == (int(np.argmax(counts)) + 1)
    geoms = [shape(g) for g, v in shapes(belt.astype("uint8"), mask=belt, transform=transform)]
    if not geoms:
        return None
    return max(geoms, key=lambda g: g.area).exterior


def main():
    landsat_years = C.available_landsat_years()
    if not landsat_years:
        print("No Landsat data yet.")
        print("Run gee/landsat_export.js in Google Earth Engine, put the files in")
        print(C.DATA_RAW_LANDSAT, "then run 01b_prepare_landsat.py")
        return

    overlap = sorted(set(landsat_years) & set(C.YEARS))
    if not overlap:
        print(f"Landsat years {landsat_years[0]}-{landsat_years[-1]} but no overlap")
        print(f"with Sentinel-2 ({C.YEARS[0]}-{C.YEARS[-1]}), nothing to compare.")
        return

    print(f"shared footprint: lon {COMMON[0]}-{COMMON[2]}  lat {COMMON[1]}-{COMMON[3]}")
    print("(the strip below 24.35N has no Landsat data and is excluded)")
    print(f"Landsat record: {len(landsat_years)} years "
          f"({landsat_years[0]}-{landsat_years[-1]})")
    print(f"Overlapping with Sentinel-2: {overlap}\n")
    print(f"{'year':<6} {'S2 km2':>8} {'LS km2':>8} {'area diff':>10} {'IoU':>7} "
          f"{'bank offset':>12}")
    print("-" * 58)

    ious, diffs = [], []
    for y in overlap:
        s2, tr_s2, _, hw_s2 = load_s2(y)
        ls, tr_ls, _, _ = load_landsat(y)

        # output grid must be the LANDSAT grid, not Sentinel-2's
        s2_30 = downsample_to_30m(s2, tr_s2, tr_ls, (ls.shape[0], ls.shape[1]))
        # Belt-only comparison: land far from the river is easy to agree on and
        # would inflate IoU, hiding disagreement exactly where it matters.
        both_near = s2_30 | ls
        s2_b = s2_30 & both_near
        ls_b = ls & both_near

        a2 = s2_30.sum() * (C.RES_LANDSAT ** 2) / 1e6
        a1 = ls.sum() * (C.RES_LANDSAT ** 2) / 1e6
        j = iou(s2_b, ls_b)
        diff = 100.0 * (a1 - a2) / a2 if a2 else float("nan")

        b2 = bank_offset(s2_30, tr_ls)
        b1 = bank_offset(ls, tr_ls)
        if b2 is not None and b1 is not None:
            ds = [b1.distance(Point(float(p[0]), float(p[1])))
                  for p in np.asarray(b2.coords)[::5]]
            off = float(np.median(ds))
        else:
            off = float("nan")

        ious.append(j); diffs.append(diff)
        print(f"{y:<6} {a2:8.1f} {a1:8.1f} {diff:9.1f}% {j:7.2f} {off:11.0f} m")

    ious = np.array(ious); diffs = np.array(diffs)
    print(f"\nmean IoU      : {np.nanmean(ious):.2f}  (1.0 = identical)")
    print(f"median IoU    : {np.nanmedian(ious):.2f}")
    print(f"mean area diff: {np.nanmean(diffs):+.1f}%")

    print("\nHow to read this:")
    print("  IoU is computed only where either sensor saw water, so agreement")
    print("  is not inflated by the large areas of easy dry land.")
    print("  IoU 0.85+  -> the two sensors agree closely, strong validation")
    print("  IoU 0.70-0.85 -> usable, expect small systematic bias")
    print("  IoU below 0.70 -> investigate: wrong threshold, cloud contamination,")
    print("                    or a genuine difference in what each sensor sees")
    if abs(np.nanmean(diffs)) > 15:
        print(f"\n  NOTE: Landsat is measuring {np.nanmean(diffs):+.0f}% "
              "differently from Sentinel-2.")
        print("  A consistent offset suggests the 0.2 threshold suits one sensor")
        print("  better than the other. That is tunable - but only tune it on the")
        print("  overlap years, and say so in the write-up.")


def compare_rates():
    """Compare the EPR rate each sensor measures on the SAME transects, SAME years.

    This is the real cross-sensor test. The IoU above asks "do they see the same
    water?"; this asks "do they measure the same movement?", which is the number
    the project actually reports.
    """
    import json as _json

    s2_dir = C.sensor_transects_dir("s2")
    ls_dir = C.sensor_transects_dir("landsat")
    pairs = []
    for p in sorted(ls_dir.glob("epr_*.geojson")):
        y0, y1 = p.stem.replace("epr_", "").split("_")
        if (s2_dir / f"epr_{y0}_{y1}.geojson").exists():
            pairs.append((y0, y1))
    if not pairs:
        print("\nno overlapping year-pairs between the two sensors")
        return

    print("\nEPR rate comparison on identical transects and years")
    print(f"{'pair':>10} {'n shared':>9} {'S2 median':>10} {'LS median':>10} {'ratio':>7}")
    print("-" * 50)
    a, b = [], []
    for y0, y1 in pairs:
        A = _json.load(open(s2_dir / f"epr_{y0}_{y1}.geojson"))
        B = _json.load(open(ls_dir / f"epr_{y0}_{y1}.geojson"))
        ma = {f["properties"]["id"]: f["properties"] for f in A["features"]}
        mb = {f["properties"]["id"]: f["properties"] for f in B["features"]}
        shared = sorted(set(ma) & set(mb))
        if not shared:
            continue
        va = [max(abs(ma[i]["left_rate"]), abs(ma[i]["right_rate"])) for i in shared]
        vb = [max(abs(mb[i]["left_rate"]), abs(mb[i]["right_rate"])) for i in shared]
        ma_, mb_ = float(np.median(va)), float(np.median(vb))
        a.append(ma_); b.append(mb_)
        print(f"{y0}->{y1} {len(shared):9d} {ma_:10.1f} {mb_:10.1f} "
              f"{mb_/ma_ if ma_ else float('nan'):6.2f}x")
    if len(a) > 1:
        a, b = np.array(a), np.array(b)
        print(f"\nmean ratio LS/S2 = {np.mean(b/a):.2f}x")
        print(f"correlation      = {np.corrcoef(a,b)[0,1]:+.2f}")
        print("\nA ratio near 1 with a high correlation means both instruments are")
        print("measuring the same movement. A scatter of ratios means the two disagree")
        print("pair by pair, which is the thing to understand before publishing.")


if __name__ == "__main__":
    main()
    compare_rates()
