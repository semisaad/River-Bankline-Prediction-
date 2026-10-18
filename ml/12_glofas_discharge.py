"""
RiverGuard - download REAL river discharge (GloFAS) from Copernicus.

Run on your own machine:
    cd ~/Projects/riverguard/ml
    ../.venv/bin/pip install "cdsapi>=0.7.7" xarray
    ../.venv/bin/python 12_glofas_discharge.py

WHY THIS EXISTS
    35 years of Landsat imagery did NOT make the bank-erosion model work.
    Predicting last year's movement was worse than predicting the average
    (MAE 126.5 vs 80.6 m/yr). Every feature so far is a lagged outcome, and on
    a braided river erosion hotspots MIGRATE rather than persist. What is missing
    is the FORCING - how much water the river is asked to carry. GloFAS is that
    variable: modelled daily river discharge in cubic metres per second, 1979 to
    present.

WHY THIS IS NOT AN EARTH ENGINE SCRIPT
    GloFAS is not in Earth Engine. It lives in the Copernicus CEMS Early Warning
    Data Store as NetCDF and needs a free account plus an API key.

ONE-TIME SETUP (about 10 minutes)
    1. Create a free account: https://ewds.climate.copernicus.eu
    2. Open the dataset page and ACCEPT the licence. The API will refuse to
       serve the data until you do this. This step cannot be done in code:
           https://ewds.climate.copernicus.eu/datasets/cems-glofas-historical?tab=download
       Scroll to the bottom of the form and tick the licence box.
    3. Copy your personal access token from:
           https://ewds.climate.copernicus.eu/user
    4. Create ~/.cdsapirc and paste (note the ewds.climate.copernicus.eu URL -
       GloFAS is NOT on the main cds.climate.copernicus.eu API):

           url: https://ewds.climate.copernicus.eu/api
           key: <YOUR-TOKEN-HERE>

           The file is:
               nano ~/.cdsapirc

    5. Install the client:
           ../.venv/bin/pip install "cdsapi>=0.7.7" xarray

NOTES THAT SAVE PAIN
    * Requests are made ONE YEAR AT A TIME. Asking for 40 years of daily data
      in a single call will be rejected or will time out.
    * The script is resumable. If it dies halfway, run it again: it skips the
      years it already has.
    * Roughly 42 small NetCDF files, a few MB each.
    * "consolidated" data_type is the ERA5-forced record we want (not
      "intermediate", which uses preliminary near-real-time forcing).
    * Upstream catchment area is a SEPARATE ancillary dataset, not a variable in
      this one. We therefore identify the right cell by discharge magnitude
      instead, and print the cell we picked so you can sanity-check it.

EXPECTED RESULT
    Jamuna discharge at Kazipur runs roughly 1,000-15,000 m3/s, peaking in the
    Aug-Oct monsoon and lowest in Feb-Apr. If the numbers come out as 0.001 or
    10,000,000, the wrong cell was chosen and the script prints a warning.

OUTPUT
    data/raw/hydro/glofas_<lat>_<lon>.csv
        date, discharge_m3s
    data/raw/hydro/glofas_annual.csv
        year, mean, min, max, cv, dry_season_mean, monsoon_mean, monsoon_max
"""

import argparse
import hashlib
import sys
import time
from pathlib import Path

import numpy as np

OUT = Path(__file__).resolve().parents[1] / "data" / "raw" / "hydro"
OUT.mkdir(parents=True, exist_ok=True)

DATASET = "cems-glofas-historical"
API_URL = "https://ewds.climate.copernicus.eu/api"
DATA_TYPE = "consolidated"
VERSION = "4.0"           # v5.0 also exists (2026-07); 4.0 is the well-tested one
# Every name and type below was read from the API's own process description at
#   GET /api/retrieve/v1/processes/cems-glofas-historical
# rather than guessed. Guessing is what produced four wrong names the first time
# (the variable is 'average_river_discharge_in_the_last_24_hours' as an ARRAY;
# the product flag is 'product_type' not 'data_type'; the version is
# 'system_version' with value 'version_4_0'; and 'timespan' and
# 'hydrological_model' are both mandatory).
#
# The file the service writes contains a variable called 'avg_dis' - that is the
# GRIB short name of this same quantity, so the two are consistent.
VARIABLE = "average_river_discharge_in_the_last_24_hours"
PRODUCT_TYPE = "consolidated"      # not "intermediate": that is preliminary
SYSTEM_VERSION = "version_4_0"
TIMESPAN = "time_mean"
MODEL = "lisflood"
DATA_FORMAT = "netcdf"             # a plain string, not a list
DOWNLOAD_FORMAT = "unarchived"

# Box around the reach. N, W, S, E as the CDS API wants them.
AREA = [25.5, 88.5, 23.5, 91.0]

YEARS = list(range(1989, 2027))     # matches the Landsat record

# How many years to ask for in ONE request.
#
# The API refuses a multi-year request with HTTP 403 - verified 2026-10-17, the
# same limit the website form enforces by turning red. So one year per request.
# The chunking code is kept only as a fallback path.
YEARS_PER_REQUEST = 1

# A Jamuna cell should look like this; used only to sanity check.
PLAUSIBLE = (200, 60000)

# The box above is deliberately generous because the CDS service needs a clean
# rectangular request. It unavoidably contains the Ganges and the Padma below the
# confluence as well as the Jamuna, and the Jamuna is NOT the biggest river in
# it. So the cell is chosen inside this tighter window around the actual study
# reach (the AOI used for the Landsat export) rather than by "biggest river in
# the box", which would silently return the Ganges.
REACH_LAT = 24.50
REACH_LON = 89.74
REACH_WINDOW = 0.45          # degrees; keep cells within ~50 km of the reach


def fail(msg, extra=""):
    print(f"\n{msg}\n")
    if extra:
        print(extra)
    sys.exit(1)


def check_setup():
    try:
        import cdsapi
        import xarray as xr
    except ImportError as exc:
        fail(f"Missing package: {exc}",
             "Install with:\n"
             '   ../.venv/bin/pip install "cdsapi>=0.7.7" xarray')

    rc = Path.home() / ".cdsapirc"
    if not rc.exists():
        fail("No ~/.cdsapirc file.",
             "Create it and paste:\n"
           "   url: https://ewds.climate.copernicus.eu/api\n"
           "   key: <YOUR-TOKEN>\n"
           "Get the token from https://ewds.climate.copernicus.eu/user\n"
           "Then:  nano ~/.cdsapirc")
    text = rc.read_text()
    if "ewds" not in text:
        print("WARNING: your ~/.cdsapirc does not mention ewds.climate.copernicus.eu")
        print("         GloFAS lives on the Early Warning store, not the main CDS API.")

    return cdsapi, xr


def make_client(cdsapi):
    """Build the client with short, frequent retries.

    The default backoff is 500 attempts with 120-second sleeps. On this machine
    DNS comes and goes, and the connection had already recovered while the client
    was still asleep, so it kept reporting the original failure. Short retries
    let it notice that the network is back within a few seconds.
    """
    for kwargs in ({"url": API_URL, "retry_max": 30, "sleep_max": 20},
                   {"url": API_URL},
                   {}):
        try:
            return cdsapi.Client(**kwargs)
        except TypeError:
            continue
    raise RuntimeError("could not construct a cdsapi client")


def build_request(years):
    """Build the request exactly as the API's process description specifies."""
    return {
        "variable": [VARIABLE],
        "product_type": [PRODUCT_TYPE],
        "system_version": [SYSTEM_VERSION],
        "timespan": [TIMESPAN],
        "hydrological_model": [MODEL],
        "year": [str(y) for y in years],
        "month": [f"{m:02d}" for m in range(1, 13)],
        "day": [f"{d:02d}" for d in range(1, 32)],
        "area": AREA,
        "data_format": DATA_FORMAT,
        "download_format": DOWNLOAD_FORMAT,
    }


def request_chunk(client, years, dest):
    client.retrieve(DATASET, build_request(years), str(dest))


def fetch_year(client, xr, year, tmp_dir):
    """One NetCDF for one year. Returns the path, or None to skip."""
    dest = tmp_dir / f"glofas_{year}.nc"
    if dest.exists() and dest.stat().st_size > 1000:
        return dest
    before = {p.name for p in tmp_dir.glob("*.nc")}
    try:
        request_chunk(client, [year], dest)
    except Exception as exc:
        print(f"    {year}: FAILED - {type(exc).__name__}: {str(exc)[:200]}")
        return None
    if dest.exists():
        return dest
    # the service may have chosen its own filename
    new = [tmp_dir / n for n in {p.name for p in tmp_dir.glob("*.nc")} - before]
    return new[0] if new else None


def fetch_chunk(client, years, tmp_dir):
    """Several years in one request. Falls back to single years on failure."""
    dest = tmp_dir / ("glofas_%d_%d.nc" % (years[0], years[-1]))
    if all((tmp_dir / f"glofas_{y}.nc").exists() for y in years):
        return True, [y for y in years if (tmp_dir / f"glofas_{y}.nc").exists()]

    label = f"{years[0]}-{years[-1]}"
    try:
        request_chunk(client, years, dest)
        print(f"    {label}: ok (one request for {len(years)} years)")
        return True, list(years)
    except Exception as exc:
        print(f"    {label}: chunk failed, retrying year by year")
        print(f"    server said: {str(exc)[:300]}")
        if dest.exists():
            dest.unlink()
        import xarray as xr
        ok_years = []
        for y in years:
            if fetch_year(client, xr, y, tmp_dir):
                ok_years.append(y)
        return False, ok_years


def find_discharge_var(ds):
    """Locate the river-discharge variable inside a GloFAS NetCDF.

    The Copernicus form writes the GRIB short name 'avg_dis' ("Time-mean
    discharge from rivers or streams"), not the long catalogue label. Matching on
    the variable NAME alone therefore misses every real file, so also match on
    the long_name attribute.
    """
    for v in ds.data_vars:
        if "discharge" in v.lower():
            return v
    for v in ds.data_vars:
        label = " ".join(str(ds[v].attrs.get(k, "")) for k in ("long_name", "GRIB_name"))
        if "discharge" in label.lower():
            return v
    return None


def fix_year_edges(tidy, path):
    """GloFAS time-mean stamps run 2 Jan -> 1 Jan next year.

    The trailing 1 January would be counted as the FIRST day of the following
    year, leaking a day into the wrong annual average for every single file. Each
    file is supposed to describe one year, so if one date sits alone on the far
    side of the boundary, drop it and note it.
    """
    import pandas as pd

    years = tidy["date"].dt.year
    days = tidy.assign(_y=years).groupby("_y")["date"].nunique()
    if len(days) < 2:
        return tidy

    main_year = int(days.idxmax())
    others = [int(y) for y in days.index if int(y) != main_year]

    if len(others) == 1 and days.loc[others[0]] <= 2:
        stray = others[0]
        print(f"  {path.name}: dropped {int(days.loc[stray])} stray {stray} "
              f"day(s) on the far side of the year boundary")
        tidy = tidy[years == main_year]
    elif others:
        print(f"  {path.name}: NOTE spans {sorted(days.index)} with "
              f"{len(others)} partial year(s) - kept as downloaded")
    return tidy


def normalise(frame):
    """Turn one CDS NetCDF into a tidy daily table.

    The Copernicus service changes the exact coordinate names between dataset
    versions ('lat' vs 'latitude', 'time' vs 'valid_time'), and files downloaded
    by hand from the website form have yet another naming convention. Rather than
    hard-code one layout, find the columns by meaning. This is what lets Saad drop
    in files named anything at all.
    """
    import pandas as pd

    cols = {c.lower(): c for c in frame.columns}
    lat = next((cols[k] for k in ("lat", "latitude") if k in cols), None)
    lon = next((cols[k] for k in ("lon", "longitude") if k in cols), None)
    when = next((cols[k] for k in ("time", "valid_time", "date") if k in cols), None)
    if lat is None or lon is None or when is None:
        return None
    out = frame[[lat, lon, when, "discharge_m3s"]].copy()
    out.columns = ["lat", "lon", "time", "discharge_m3s"]
    out["date"] = pd.to_datetime(out["time"], errors="coerce", utc=True)
    return out.dropna(subset=["date", "discharge_m3s"])


def read_local_nc():
    import xarray as xr
    """Read every NetCDF already sitting in the hydro folder.

    Used with --from-files, for NetCDFs downloaded by hand from the CDS website
    form rather than through the API. Filenames are ignored on purpose.
    """
    import pandas as pd

    found = sorted(p for p in OUT.glob("*.nc") if not p.name.startswith("glofas_"))
    # the API route caches downloads in _nc/, so look there too - missing this
    # once silently reduced a 38-year record to a single year
    sub = OUT / "_nc"
    if sub.is_dir():
        found += sorted(sub.glob("*.nc"))
    if not found:
        fail(f"No .nc files in {OUT}.",
             "Download NetCDF (not GRIB) for each year from\n"
           "  https://ewds.climate.copernicus.eu/datasets/cems-glofas-historical?tab=download\n"
           "then drop them in this folder. Filenames do not matter.")

    frames = []
    for p in found:
        try:
            ds = xr.open_dataset(p)
        except Exception as exc:
            print(f"  skip {p.name}: {exc}")
            continue
        vname = find_discharge_var(ds)
        if vname is None:
            print(f"  skip {p.name}: no discharge variable")
            ds.close()
            continue
        raw = ds[vname].to_dataframe(name="discharge_m3s").reset_index()
        tidy = normalise(raw)
        if tidy is not None:
            tidy = fix_year_edges(tidy, p)
            frames.append(tidy)
        unit = ds[vname].attrs.get("units", "?")
        print(f"  read {p.name}: var={vname} units={unit} "
              f"n={0 if tidy is None else len(tidy)} "
              f"years={sorted(tidy.date.dt.year.unique()) if tidy is not None else '-'}")
        ds.close()

    if not frames:
        fail("Files found but none could be read as daily discharge.",
             "Expected a NetCDF. If you downloaded GRIB2 by mistake, re-download "
             "with Format = NetCDF.")
    return pd.concat(frames, ignore_index=True)


def pick_cell(series):
    """Choose the GloFAS grid cell that represents the Jamuna at the study reach.

    Ranking the whole request box by discharge is wrong here: the box also
    contains the Ganges and the Padma, and those are bigger, so "biggest river"
    returns a different river entirely. Instead restrict to a window around the
    study reach and take the cell nearest its centre that carries real flow.
    """
    stats = series.groupby(["lat", "lon"])["discharge_m3s"].agg(["median", "mean"])
    stats = stats.reset_index()

    dist = np.hypot(stats["lat"] - REACH_LAT, stats["lon"] - REACH_LON)
    stats["dist"] = dist
    near = stats[stats["dist"] <= REACH_WINDOW]

    if near.empty:
        print(f"WARNING: no cell within {REACH_WINDOW} deg of the study reach; "
              f"widening the search")
        near = stats

    wet = near[near["median"] > PLAUSIBLE[0] * 0.25]
    if not wet.empty:
        near = wet

    # nearest to the reach centre, but never land on a cell that is essentially
    # dry - that would mean the reach is not where this file thinks it is
    best = near.sort_values("dist").iloc[0]
    sub = series[(series["lat"] == best["lat"]) & (series["lon"] == best["lon"])]
    return float(best["lat"]), float(best["lon"]), sub, near


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from-files", action="store_true",
                    help="skip the download and read NetCDFs already in "
                         "data/raw/hydro/")
    args = ap.parse_args()

    print("RiverGuard - GloFAS real river discharge")
    print(f"dataset : {DATASET}  ({PRODUCT_TYPE}, {SYSTEM_VERSION}, "
          f"{TIMESPAN}, {MODEL})")
    print(f"output  : {OUT}")

    import pandas as pd

    if args.from_files:
        allf = read_local_nc()
    else:
        cdsapi, xr = check_setup()
        client = make_client(cdsapi)

        tmp = OUT / "_nc"
        tmp.mkdir(exist_ok=True)

        n_chunks = (len(YEARS) + YEARS_PER_REQUEST - 1) // YEARS_PER_REQUEST
        print(f"\nRequesting {YEARS_PER_REQUEST} year(s) at a time, "
              f"all 12 months each.\n")
        print(f"{n_chunks} requests for {len(YEARS)} years "
              f"({YEARS[0]}-{YEARS[-1]}). This takes a while.\n")
        got = 0
        for i in range(0, len(YEARS), YEARS_PER_REQUEST):
            _, ok_years = fetch_chunk(client, YEARS[i:i + YEARS_PER_REQUEST], tmp)
            got += len(ok_years)
            time.sleep(1.0)      # be polite to the service

        print(f"\n{got}/{len(YEARS)} year files available")
        if got == 0:
            fail("No years downloaded.",
                 "Most common causes:\n"
                 "  - you have not accepted the licence on the dataset page\n"
                 "  - ~/.cdsapirc has the wrong url or token\n"
                 "  - the service rejected the request as too large")

        frames = []
        seen = {}
        # glob every .nc, not just glofas_*: the service assigns its own
        # hash-based filenames to the files it returns
        for p in sorted(tmp.glob("*.nc")):
            # Skip byte-identical duplicates. The same year can legitimately
            # arrive twice - by hand from the website form and from the API - and
            # counting it twice would quietly distort every annual summary.
            digest = hashlib.md5(p.read_bytes()).hexdigest()
            if digest in seen:
                print(f"  {p.name}: duplicate of {seen[digest]}, skipped")
                continue
            seen[digest] = p.name
            try:
                ds = xr.open_dataset(p)
            except Exception as exc:
                print(f"  skip {p.name}: {exc}")
                continue
            vname = find_discharge_var(ds)
            if vname is None:
                ds.close()
                continue
            raw = ds[vname].to_dataframe(name="discharge_m3s").reset_index()
            tidy = normalise(raw)
            if tidy is not None:
                frames.append(tidy)
            ds.close()

        if not frames:
            fail("Files downloaded but no discharge variable found inside them.")
        allf = pd.concat(frames, ignore_index=True)

    allf = allf.dropna(subset=["date", "discharge_m3s"])
    print(f"\nread {len(allf)} daily values over "
          f"{allf.date.min().date()} to {allf.date.max().date()}")

    lat, lon, sub, near = pick_cell(allf)
    print(f"chosen grid cell: {lat:.3f}N {lon:.3f}E "
          f"({abs(lat-REACH_LAT):.2f} deg from the study reach)")
    print("nearest candidates:")
    for _, r in near.sort_values("dist").head(5).iterrows():
        print(f"   {r['lat']:.3f}N {r['lon']:.3f}E  dist={r['dist']:.3f}  "
              f"median={r['median']:.0f}  mean={r['mean']:.0f} m3/s")

    v = sub["discharge_m3s"]
    if not (PLAUSIBLE[0] <= v.median() <= PLAUSIBLE[1]):
        print(f"\nWARNING: median discharge {v.median():.1f} m3/s is outside the")
        print(f"plausible Jamuna range {PLAUSIBLE}. The chosen cell may be wrong.")
    else:
        print(f"median discharge there: {v.median():.0f} m3/s  (plausible)")

    sub = sub.copy()
    sub["year"] = sub["date"].dt.year
    sub["month"] = sub["date"].dt.month

    daily = OUT / f"glofas_{lat:.2f}_{lon:.2f}_daily.csv"
    sub[["date", "discharge_m3s"]].to_csv(daily, index=False)

    yr = sub.groupby("year")["discharge_m3s"].agg(["mean", "min", "max", "std"])
    yr["cv"] = yr["std"] / yr["mean"]
    yr["dry_season_mean"] = sub[sub.month.isin([1, 2, 3])].groupby("year")["discharge_m3s"].mean()
    yr["monsoon_mean"] = sub[sub.month.isin([6, 7, 8, 9])].groupby("year")["discharge_m3s"].mean()
    yr["monsoon_max"] = sub[sub.month.isin([6, 7, 8, 9])].groupby("year")["discharge_m3s"].max()

    # A year with missing days must not be compared with complete years. The
    # consolidated GloFAS record runs several months behind the present, so the
    # most recent year arrives half-finished. Summarising it as if it were whole
    # made 2026 look like the driest year in 38 years, when in truth it simply
    # stopped on 1 July. Flag it, and keep the summary columns empty rather than
    # publishing a number that invites a wrong conclusion.
    yr["days"] = sub.groupby("year")["date"].nunique()
    expected = pd.Series({y: (366 if y % 4 == 0 else 365) for y in yr.index})
    yr["complete"] = yr["days"] >= (expected - 2)
    incomplete = yr.index[~yr["complete"]].tolist()
    if incomplete:
        print(f"\nWARNING: incomplete year(s) {incomplete} - the GloFAS record "
              f"has not finished them yet.")
        for y in incomplete:
            print(f"    {y}: only {int(yr.loc[y,'days'])} days present; "
                  f"summary columns blanked so it cannot be mistaken for a full year")
        stat_cols = ["mean", "min", "max", "std", "cv",
                     "dry_season_mean", "monsoon_mean", "monsoon_max"]
        yr.loc[~yr["complete"], stat_cols] = float("nan")

    yr["lat"], yr["lon"] = lat, lon
    annual = OUT / "glofas_annual.csv"
    yr.round(2).to_csv(annual)

    print(f"\nannual rows: {len(yr)}  years {int(yr.index.min())}-{int(yr.index.max())}"
          f"  complete: {int(yr['complete'].sum())}")
    print("columns: mean, min, max, std, cv, dry_season_mean, monsoon_mean, "
          "monsoon_max, days, complete")
    print(f"-> {daily}")
    print(f"-> {annual}")
    print("\nDone. Tell Saad and these get joined into the ML feature table.")


if __name__ == "__main__":
    main()
