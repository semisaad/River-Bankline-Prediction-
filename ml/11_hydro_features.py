"""11 - Hydrology features: join climate forcing to the transect table.

Loads the ERA5-Land exports (gee/hydro_export.js) and adds weather-over-the-reach
forcing columns to the ML feature table.

WHAT THESE NUMBERS ACTUALLY ARE, AND WHAT THEY ARE NOT
  ERA5-Land is 0.1 degree, about 11 km. The study box is about 10 x 14 km, so we
  are reading roughly ONE model cell - the weather sitting over the reach. It is
  not a measurement of the river, and it is not catchment-scale either: to call
  it that would be overselling it. The claim these features can support is
  modest, and should be written up that way: "the weather over the reach in
  year0", as a proxy for the water the river was being asked to carry.

  We tried to get the real thing. GloFAS is genuine discharge in m3/s, but at
  this reach its nearest cell reads a maximum of 13 m3/s for an entire year: a
  5 km grid cannot see a 300 m distributary, so it models a small local
  catchment instead. See D88. A perfect 38-year download would still have been
  the wrong river.

NO LEAKAGE
  A row for pair (y0, y1) describes what happened BETWEEN y0 and y1, so every
  forcing column attached here is taken at year0 or earlier - the last year whose
  data exists at the moment the forecast has to be made.

  This previously read from year1 instead, justified as "erosion responds to the
  flow in the same window". That is true as physics and false as forecasting: at
  prediction time y1's discharge is up to five years in the future, so a model
  using it would score well and be useless in operation. Same class of bug as
  D63/D80.

  The cost of the fix is stated plainly rather than hidden: y0's flow is only a
  PROXY for the flow during (y0, y1], because wet and dry years cluster. That is
  a genuine weakening of the physical claim and belongs in the write-up.

Run:  ../.venv/bin/python 11_hydro_features.py [s2|landsat]
"""

import sys

import numpy as np
import pandas as pd
import rasterio

import config as C

HYDRO_RAW = C.DATA_RAW / "hydro"
HYDRO_PROC = C.DATA_PROC / "hydro"

def available_hydro_years():
    if not HYDRO_RAW.exists():
        return []
    ys = []
    for p in HYDRO_RAW.glob("Hydro_*.tif"):
        try:
            ys.append(int(p.stem.split("_")[-1]))
        except ValueError:
            continue
    return sorted(ys)


def catchment_means(year):
    """Mean of each hydrology band over the study area, for one year."""
    p = HYDRO_RAW / f"Hydro_{year}.tif"
    if not p.exists():
        return None
    with rasterio.open(p) as s:
        a = s.read().astype("float32")
        names = list(s.descriptions) if s.descriptions else \
            [f"band{i+1}" for i in range(a.shape[0])]
        # keep only pixels inside the study box, so the catchment box does not
        # dilute the value with distant terrain
        from rasterio.warp import transform_geom
        from rasterio.features import geometry_mask
        from shapely.geometry import box, shape

        box_ll = box(*C.BBOX_WGS84)
        # No densify_pts here: that is a pyproj argument, and
        # rasterio.warp.transform_geom rejects it outright. This line could not
        # run before the first ERA5-Land export existed, so the wrong keyword sat
        # here harmlessly until there was finally data to read.
        #
        # In practice this transform is the identity - hydro_export.js writes
        # EPSG:4326 and the study box is in EPSG:4326 too. It is kept so that an
        # export in a projected CRS still lands in the right place; for a box this
        # small, skipping densification costs well under one pixel.
        geom = transform_geom(s.crs, "EPSG:4326", box_ll)
        inside = geometry_mask([shape(geom)], out_shape=s.shape,
                               transform=s.transform, invert=True)

    out = {}
    for i, n in enumerate(names):
        band = a[i][inside]
        band = band[np.isfinite(band)]
        out[n] = float(np.median(band)) if band.size else np.nan
    return out


def attach_year_and_change(df, series, prefix):
    """Attach `prefix` and `prefix_chg` from a per-year series, at y0 only.

    `series` is indexed by year. The value is taken at year0, the last year known
    when the prediction is made, and the change is measured over the same length
    as the target window so the two are comparable: for a 5-year pair, the change
    is from y0-5 to y0.

    Taking these at year1 (which this used to do) reads a year from inside the
    interval being predicted. It is the D63/D80 leak class and the reason this
    helper exists: the anchor year is set in exactly one place.
    """
    step = (df["year1"] - df["year0"]).replace(0, 1)
    now = df["year0"].map(series)
    before = (df["year0"] - step).map(series)
    df[prefix] = now
    df[f"{prefix}_chg"] = now - before
    return [prefix, f"{prefix}_chg"]


def attach_anomaly(df, series, colname):
    """Departure from the record so far: normal weather does not move a bank.

    The baseline is an expanding median over years up to and including y0, so it
    never sees the future. This previously did
        df.groupby("year1")[col].transform(lambda s: s.expanding().median())
    but the value is constant within a year, so the expanding median inside that
    group WAS the value, and the anomaly came out identically zero - a column of
    zeros that looks like a feature and carries nothing.
    """
    s = series.dropna().sort_index()
    if s.empty:
        df[colname] = np.nan
        return colname
    hist = s.expanding().median()
    df[colname] = df["year0"].map(s) - df["year0"].map(hist)
    return colname


def main(sensor="landsat"):
    years = available_hydro_years()
    if not years:
        print(f"No hydrology data in {HYDRO_RAW}")
        print("Run gee/hydro_export.js in Google Earth Engine, download the "
              "Hydro_<year>.tif files, and put them in that folder.")
        return

    fcsv = C.DATA_PROC / "features" / sensor / "features.csv"
    if not fcsv.exists():
        print(f"No feature table for {sensor}. Run 05_features.py {sensor} first.")
        return

    df = pd.read_csv(fcsv)
    print(f"feature rows: {len(df)}")
    print(f"ERA5-Land proxy : "
          f"{'none' if not years else f'{len(years)} years ({years[0]}-{years[-1]})'}")

    names = []
    if years:
        # mean over the catchment for each year
        clim = {}
        for y in years:
            v = catchment_means(y)
            if v:
                clim[y] = v
        if not clim:
            print("could not read any ERA5-Land file")
            clim = {}
        if clim:
            names = sorted(next(iter(clim.values())).keys())
            print(f"ERA5-Land bands: {', '.join(names)}\n")

            for n in names:
                series = pd.Series({y: v.get(n, np.nan) for y, v in clim.items()})
                attach_year_and_change(df, series, f"clim_{n}")
                attach_anomaly(df, series, f"clim_{n}_anom")

    out = C.DATA_PROC / "features" / sensor / "features_hydro.csv"
    df.to_csv(out, index=False)
    added = len([c for c in df.columns if c.startswith("clim_")])
    print(f"added {added} hydrology columns in total")
    print(f"-> {out}")

    # honest look at whether it helped
    print("\ncorrelation with the erosion label (physical expectation: positive)")
    for n in names:
        s = df[[f"clim_{n}", "target_rate"]].dropna()
        if len(s) > 50:
            print(f"  clim_{n:<34} {s[f'clim_{n}'].corr(s.target_rate):+.3f}  (n={len(s)})")
    s = df[["clim_runoff_sum", "target_rate"]].dropna() \
        if "clim_runoff_sum" in df.columns else None
    if s is not None and len(s) > 50:
        mae_m = float(np.abs(s.target_rate - s.target_rate.mean()).mean())
        print(f"\nbaseline to beat (predict the mean): MAE {mae_m:.1f} m/yr")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "landsat")
