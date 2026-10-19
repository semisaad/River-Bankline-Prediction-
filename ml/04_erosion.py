"""04 - Erosion rate (EPR) per transect, measured from raw water masks.

METHOD
  For each transect and each pair of years, count the pixels that were water in
  year A and land in year B (erosion), and land that became water (accretion),
  inside a 1 km zone straddling each belt edge. Net area divided by river
  frontage length gives metres of movement per year. This is the standard EPR
  (Erosion/Progradation Rate) construction.

  The two outer banks are measured separately and never averaged: over the whole
  ~8 km belt they would cancel, because while one side erodes the other accretes.

GEOMETRY
  Transects come from `transects.build_transects()` and are built ONCE, then
  reused for every year and both sensors, so a rate always compares the same two
  pieces of river. They are perpendicular to the LOCAL direction of the river's
  centreline - see transects.py for why a single global axis was wrong.

ZONE ANCHORING
  The EPR zone is anchored to the belt edge of the pair's OWN starting year, not
  to one reference year for the whole record. Within a pair the zone is immobile
  so the change is captured; between pairs it re-anchors, because over 36 years
  this river has migrated more than 1.5 km and a single fixed zone would sit on
  dry ground and report zero everywhere.

Run:  ../.venv/bin/python 04_erosion.py [s2|landsat]
"""

import sys

import geopandas as gpd
import numpy as np
from rasterio.features import geometry_mask

import config as C
import transects as T


def pairs_for(sensor, extra=None):
    """Year pairs at the sensor's configured window (see C.PAIR_STEP).

    Landsat on a slow river is measured in multi-year blocks because at 30 m the
    bank moves less than one pixel per year, so an annual pair measures nothing.

    `extra` adds one-off pairs for an experiment without changing the reach
    config; see C.sensor_pairs.
    """
    return C.sensor_pairs(sensor, extra)


def build_geometry(verbose=True):
    """Fixed transect geometry, built once and shared by both sensors."""
    ts = T.build_transects()
    return ts


def main(sensor="s2", geom=None, extra_pairs=None):
    pairs = pairs_for(sensor, extra_pairs)
    if not pairs:
        print(f"No consecutive processed years for {sensor}.")
        return

    res = C.sensor_res(sensor)
    out_dir = C.sensor_transects_dir(sensor)

    ts = geom if geom is not None else build_geometry()
    print(f"\nsensor {sensor} at {res} m | geometry from {ts.sensor_geom} "
          f"{ts.ref_year} | {len(ts.transects)} fixed transects\n")

    all_rates = []
    pair_rows = []

    for y0, y1 in pairs:
        # measure both years; a transect is usable only if BOTH are good
        T.measure_edges(ts, y0, sensor, quiet=True)
        edges0 = {t.i: (t.vmin, t.vmax) for t in ts.transects if t.ok}
        T.measure_edges(ts, y1, sensor, quiet=True)

        w0, tr, hw = T.load_water(y0, sensor)
        w1, _, _ = T.load_water(y1, sensor)
        s0 = w0.sum() * res**2 / 1e6
        s1 = w1.sum() * res**2 / 1e6

        pad = T.BUFFER_M
        feats, rates = [], []

        for t in ts.transects:
            if t.i not in edges0 or not t.ok:
                continue
            av0, av1 = edges0[t.i]
            run = 2 * pad

            zl, zr = T.bank_zones(t, pad, av0, av1)

            # Name these for what they ARE, because the obvious names are the
            # wrong way round:
            #   w2l = water in year0, land in year1 -> land was GAINED (accretion)
            #   l2w = land in year0,  water in year1 -> land was LOST  (erosion)
            # They used to be called "lost" and "gained", which is exactly
            # backwards, so every rate carried an inverted sign. Magnitudes
            # survived (most reporting used |rate|) but the SIGN did not, which
            # matters wherever direction is claimed - notably the risk ranking,
            # which would have ranked accretion as the highest erosion risk.
            def net(poly):
                zone = geometry_mask([poly], out_shape=hw, transform=tr,
                                     invert=True)
                w2l = float((zone & w0 & ~w1).sum()) * res**2
                l2w = float((zone & ~w0 & w1).sum()) * res**2
                return w2l, l2w

            wl, lw = net(zl)
            wr, rw = net(zr)
            feats.append({
                "id": t.i,
                "arc_m": round(float(t.arc_m), 1),
                # positive = land LOST = erosion
                "left_rate": round((lw - wl) / run, 1),
                "right_rate": round((rw - wr) / run, 1),
                "left_lost_m2": round(lw, 1),
                "left_gained_m2": round(wl, 1),
                "right_lost_m2": round(rw, 1),
                "right_gained_m2": round(wr, 1),
                "width0_m": round(float(t.width_m), 1),
                "water_frac": round(float(t.water_frac), 3),
                "stage0_km2": round(s0, 1),
                "stage1_km2": round(s1, 1),
                "geometry": T.transect_line(t),
            })
            rates.append(max(abs((lw - wl) / run), abs((rw - wr) / run)))

        if not feats:
            print(f"{y0}->{y1}: no transect usable in BOTH years, skipped")
            continue

        gdf = gpd.GeoDataFrame(feats, crs=C.CRS_WORK)
        gdf["mag"] = rates
        out = out_dir / f"epr_{y0}_{y1}.geojson"
        gdf.to_crs("EPSG:4326").to_file(out, driver="GeoJSON")

        arr = np.array(rates)
        all_rates.extend(arr.tolist())
        pair_rows.append((y0, y1, float(np.median(arr)), len(feats)))
        print(f"{y0}->{y1}  {len(feats):2d}/{len(ts.transects)} transects  "
              f"stage {s1-s0:+5.1f} km2 | median {np.median(arr):6.1f} m/yr  "
              f"IQR {np.percentile(arr,25):5.1f}..{np.percentile(arr,75):5.1f}  "
              f"max {arr.max():6.1f}")

    if not all_rates:
        print("no rates computed")
        return

    arr = np.array(all_rates)
    print(f"\nALL {len(pair_rows)} PAIRS: median {np.median(arr):.1f} m/yr, "
          f"IQR {np.percentile(arr,25):.1f}..{np.percentile(arr,75):.1f}, "
          f"max {arr.max():.1f}, n={len(arr)}")
    return pair_rows, arr


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "s2"
    geom = build_geometry(verbose=True)
    main(which, geom)
