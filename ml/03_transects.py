"""03 - Transects + migration: cast transects perpendicular to the river's
flow direction (estimated by PCA) and measure outer-bank displacement
between two years.

Why PCA: the Jamuna reach flows diagonally, so row-wise / horizontal
transects graze along the belt and give nonsense distances. Working in a
flow-aligned frame (u = along flow, v = across) gives clean cross-sections.
Bank positions are read from the closed belt mask, so we measure the OUTER
banks of the active channel belt only.
"""

import geopandas as gpd
import numpy as np
import rasterio
import shapely
from rasterio.features import shapes
from scipy.ndimage import binary_fill_holes
from skimage.measure import label, regionprops
from skimage.morphology import closing, disk
from shapely.geometry import LineString

import config as C

REF_YEAR = 2023
YEAR0, YEAR1 = 2022, 2023
N_TRANSECTS = 20


def load_belt_points(year):
    with rasterio.open(C.proc_mask_path(year)) as src:
        water = src.read(1) > 127
        transform = src.transform
    water = binary_fill_holes(closing(water, disk(int(round(40 / C.RES)))))
    lab = label(water)
    biggest = max(regionprops(lab), key=lambda r: r.area)
    belt = lab == biggest.label

    rows, cols = np.where(belt)
    xs, ys = rasterio.transform.xy(transform, rows, cols)
    return np.column_stack([xs, ys])


def main():
    P_ref = load_belt_points(REF_YEAR)
    mean = P_ref.mean(axis=0)
    centered = P_ref - mean
    cov = np.cov(centered.T)
    eigvals, eigvecs = np.linalg.eigh(cov)
    u = eigvecs[:, -1]   # along flow
    v = eigvecs[:, 0]    # across flow

    t_ref = (P_ref - mean) @ u
    t_lo, t_hi = np.percentile(t_ref, 1), np.percentile(t_ref, 99)
    edges = np.linspace(t_lo, t_hi, N_TRANSECTS + 1)
    centers = 0.5 * (edges[:-1] + edges[1:])
    halfbin = 0.5 * (edges[1] - edges[0])

    proj = {}
    for y in (YEAR0, YEAR1):
        P = P_ref if y == REF_YEAR else load_belt_points(y)
        proj[y] = ((P - mean) @ u, (P - mean) @ v)

    features = []
    for i, tc in enumerate(centers):
        vals = {}
        for y in (YEAR0, YEAR1):
            t, vv = proj[y]
            sel = np.abs(t - tc) <= halfbin
            if not sel.any():
                vals[y] = None
                continue
            vals[y] = (vv[sel].min(), vv[sel].max())  # left, right bank
        if vals[YEAR0] is None or vals[YEAR1] is None:
            continue
        (l0, r0), (l1, r1) = vals[YEAR0], vals[YEAR1]
        # transect segment in map space (span the widest extent)
        span = max(r0, r1) - min(l0, l1)
        pad = 0.05 * span
        vmin, vmax = min(l0, l1) - pad, max(r0, r1) + pad
        p0 = mean + tc * u + vmin * v
        p1 = mean + tc * u + vmax * v

        features.append(
            {
                "id": i,
                "t_m": round(float(tc), 1),
                "left0": round(float(l0), 1),
                "left1": round(float(l1), 1),
                "right0": round(float(r0), 1),
                "right1": round(float(r1), 1),
                "d_left_m": round(float(l1 - l0), 1),
                "d_right_m": round(float(r1 - r0), 1),
                "width0_m": round(float(r0 - l0), 1),
                "width1_m": round(float(r1 - l1), 1),
                "geometry": LineString([tuple(p0), tuple(p1)]),
            }
        )

    gdf = gpd.GeoDataFrame(features, crs=C.CRS_WORK)
    out = C.TRANSECTS / f"transects_{YEAR0}_{YEAR1}.geojson"
    gdf.to_crs("EPSG:4326").to_file(out, driver="GeoJSON")

    dl = gdf["d_left_m"].abs()
    dr = gdf["d_right_m"].abs()
    allm = np.concatenate([dl.values, dr.values])
    print(f"transects {YEAR0}->{YEAR1}: {len(gdf)}")
    print(f"  bank shift (median)  = {np.median(allm):.0f} m/yr")
    print(f"  bank shift (mean)    = {allm.mean():.0f} m/yr  (outlier-sensitive)")
    print(f"  left  bank: median {dl.median():.0f} m  max {dl.max():.0f} m")
    print(f"  right bank: median {dr.median():.0f} m  max {dr.max():.0f} m")
    print(f"  mean width  {YEAR0}: {gdf['width0_m'].mean():.0f} m -> {YEAR1}: {gdf['width1_m'].mean():.0f} m")
    print(f"  -> {out}")


if __name__ == "__main__":
    main()
