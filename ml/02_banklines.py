"""02 - Banklines: outer bankline of the active channel belt.

Rule (documented limitation): the bankline is the OUTER boundary of the
active channel belt = all water, morphologically closed to bridge narrow
bars, largest connected body, holes filled. Internal bar/sandbar migration
is out of scope; this measures active-channel-belt migration, which is
stable for a braided river like the Jamuna.
"""

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.features import shapes
from scipy.ndimage import binary_fill_holes
from skimage.measure import label, regionprops
from skimage.morphology import closing, disk
from shapely.geometry import Polygon, shape

import config as C

CLOSE_M = 40          # bridge land gaps narrower than ~40 m
MIN_POLY_AREA_M2 = 200_000
SIMPLIFY_M = 10.0


def extract_bankline(year):
    with rasterio.open(C.proc_mask_path(year)) as src:
        water = src.read(1) > 127
        transform = src.transform

    px = int(round(CLOSE_M / C.RES))
    water = closing(water, disk(px))
    water = binary_fill_holes(water)

    # keep the largest connected body (the channel belt)
    lab = label(water)
    if lab.max() == 0:
        raise RuntimeError(f"{year}: no water found")
    biggest = max(regionprops(lab), key=lambda r: r.area)
    belt = lab == biggest.label

    geoms = [
        shape(g) for g, v in shapes(belt.astype("uint8"), mask=belt, transform=transform)
    ]
    geoms = [g for g in geoms if g.area >= MIN_POLY_AREA_M2]
    belt_poly = max(geoms, key=lambda g: g.area)
    bank = Polygon(belt_poly.exterior).exterior.simplify(SIMPLIFY_M)

    gdf = gpd.GeoDataFrame(
        {"year": [year], "kind": ["bankline"]},
        geometry=[bank],
        crs=C.CRS_WORK,
    )
    gdf.to_crs("EPSG:4326").to_file(C.bankline_path(year), driver="GeoJSON")
    return gdf


def main():
    for year in C.YEARS:
        gdf = extract_bankline(year)
        length_km = gdf.geometry.length.sum() / 1000
        print(f"  {year}: bankline {length_km:7.1f} km  -> {C.bankline_path(year).name}")


if __name__ == "__main__":
    main()
