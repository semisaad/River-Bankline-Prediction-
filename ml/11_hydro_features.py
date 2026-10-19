"""11 - Hydrology features: join climate forcing to the transect table.

Loads the ERA5-Land exports (gee/hydro_export.js) and adds catchment-scale
forcing columns to the ML feature table.

WHY CATCHMENT SCALE, NOT THE REACH
  ERA5-Land is 0.1 degree, about 11 km. Our reach is a few km wide, so one cell
  does not describe the river itself. What it does describe is the weather over
  the catchment that feeds it, and that is the forcing that decides how hard the
  river is pushing on its banks. So these features are honest proxies for
  catchment hydrology, not measurements of Jamuna discharge. Say so in the
  write-up.

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


def globlas_annual():
    """Real GloFAS discharge, if 12_glofas_discharge.py has been run.

    Returns None when it is not available, so this script still works with the
    ERA5-Land runoff proxy on its own.
    """
    p = HYDRO_RAW / "glofas_annual.csv"
    if not p.exists():
        return None
    df = pd.read_csv(p)
    df = df.rename(columns={df.columns[0]: "year"})
    df["year"] = df["year"].astype(int)
    df = df.set_index("year")

    # The consolidated GloFAS record runs a few months behind the present, so the
    # last year arrives part-finished. 12_glofas_discharge.py blanks its summary
    # columns and sets complete=False. Keep those years out entirely rather than
    # joining a half-year average against 37 full ones - it would otherwise read
    # as the driest year on record.
    if "complete" in df.columns:
        dropped = df.index[~df["complete"].astype(bool)].tolist()
        if dropped:
            print(f"  dropping incomplete GloFAS year(s) {dropped} "
                  f"(record not finished by the service)")
        df = df[df["complete"].astype(bool)]
    return df


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
        geom = transform_geom(s.crs, "EPSG:4326", box_ll, densify_pts=21)
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
    gl = globlas_annual()
    if not years and gl is None:
        print(f"No hydrology data in {HYDRO_RAW}")
        print("Either run gee/hydro_export.js in Google Earth Engine, or run "
              "12_glofas_discharge.py for real GloFAS discharge.")
        return

    fcsv = C.DATA_PROC / "features" / sensor / "features.csv"
    if not fcsv.exists():
        print(f"No feature table for {sensor}. Run 05_features.py {sensor} first.")
        return

    df = pd.read_csv(fcsv)
    print(f"feature rows: {len(df)}")
    print(f"ERA5-Land proxy : "
          f"{'none' if not years else f'{len(years)} years ({years[0]}-{years[-1]})'}")
    print(f"GloFAS discharge: "
          f"{'none' if gl is None else f'{len(gl)} years ({gl.index.min()}-{gl.index.max()})'}")

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

    # real discharge first, because it is the better variable and should be
    # listed first in the report below
    if gl is not None:
        # lat/lon are location metadata, days/complete are record-keeping, and
        # std duplicates information already in cv. None of them are features.
        skip = {"lat", "lon", "days", "complete"}
        gcols = [c for c in gl.columns
                 if c not in skip and not c.endswith("_std")]
        for c in gcols:
            attach_year_and_change(df, gl[c], f"q_{c}")
        attach_anomaly(df, gl["q_mean"], "q_mean_anom")
        print(f"added {len(gcols)*2+1} GloFAS discharge columns "
              f"({', '.join('q_' + c for c in gcols)})")
        got = df["q_mean"].notna().mean() * 100
        print(f"q_mean available on {got:.0f}% of rows")

    out = C.DATA_PROC / "features" / sensor / "features_hydro.csv"
    df.to_csv(out, index=False)
    added = len([c for c in df.columns
                 if c.startswith("clim_") or c.startswith("q_")])
    print(f"added {added} hydrology columns in total")
    print(f"-> {out}")

    # honest look at whether it helped
    print("\ncorrelation with the erosion label (physical expectation: positive)")
    qcols = [c for c in df.columns if c.startswith("q_") and "_chg" not in c]
    for n in qcols:
        s2 = df[[n, "target_rate"]].dropna()
        if len(s2) > 50:
            print(f"  {n:<34} {s2[n].corr(s2.target_rate):+.3f}  (n={len(s2)})")
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
