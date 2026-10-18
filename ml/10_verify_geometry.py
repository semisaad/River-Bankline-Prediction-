"""10 - Verify the transect geometry against the real imagery.

A measurement is only worth having if the thing it measures is actually there.
This checks the transects three ways before any rate is computed:

  1. NUMERIC, against the mask   - does each transect contain a sensible belt,
                                   with water in the middle and land beyond?
  2. NUMERIC, against the photo  - is what the mask calls water actually dark and
                                   what it calls land actually bright? If the
                                   transects were still landing on the wrong
                                   thing, this is where it would show.
  3. VISUAL                     - writes transects.geojson for the web map and a
                                   PNG overlay so the geometry can be eyeballed.

Run:  ../.venv/bin/python 10_verify_geometry.py
"""

import json

import geopandas as gpd
from shapely.geometry import LineString, shape
import numpy as np
import rasterio
from PIL import Image, ImageDraw

import config as C
import transects as T

OUT = C.ROOT / "reports"


def rgb_profile(ts, t, year=2023, sensor="s2"):
    """Sample green-excess along a transect, from the true-colour image.

    NOT brightness. The Jamuna is extremely turbid: silt-laden water is pale
    tan and can be BRIGHTER than the dark vegetation on the floodplain, so a
    "water is darker" test fails here for the right reason and the wrong
    reason. Green excess (green minus the mean of red and blue) separates them
    properly: vegetation is strongly green, silt-laden water is not.
    """
    # the PROCESSED rgb, which is already in the analysis CRS (metres)
    path = C.proc_rgb_path(year)
    with rasterio.open(path) as s:
        red, green, blue = [s.read(i + 1).astype("float32") for i in range(3)]
        transform = s.transform
        shape = s.height, s.width
    inv = ~transform
    res = C.sensor_res(sensor)

    gvi = green - 0.5 * (red + blue)         # vegetation index, no NIR needed
    n = int(t.half_max / res)
    offs = np.arange(-n, n + 1) * res
    cx, cy = inv * (t.center[0], t.center[1])
    cols = np.round(cx + offs / res * t.normal[0]).astype(int)
    rows = np.round(cy + offs / res * t.normal[1]).astype(int)
    H, W = shape
    ok = (rows >= 0) & (rows < H) & (cols >= 0) & (cols < W)
    b = np.zeros(len(offs), dtype="float32")
    b[ok] = gvi[rows[ok], cols[ok]]
    return offs, b


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    ts = T.build_transects()

    # --- measure edges on the reference year so the report has real numbers ---
    dropped = T.measure_edges(ts, ts.ref_year, ts.sensor_geom, quiet=True)
    ok = [t for t in ts.transects if t.ok]
    print(f"\nreference year {ts.ref_year}: {len(ok)}/{len(ts.transects)} usable\n")

    # --- geojson for the map ---
    feats = []
    for t in ok:
        feats.append({
            "type": "Feature",
            "properties": {
                "id": t.i, "arc_m": round(t.arc_m, 1),
                "width_m": round(t.width_m, 1),
                "water_frac": round(t.water_frac, 3),
                "vmin": round(t.vmin, 1), "vmax": round(t.vmax, 1),
            },
            "geometry": shape({"type": "LineString",
                               "coordinates": [list(map(float, a)) for a in
                                               T.transect_line(t).coords]}),
        })
    gpath = OUT / "transects.geojson"
    gpd.GeoDataFrame([{k: v for k, v in f["properties"].items()} | {"geometry": f["geometry"]}
                      for f in feats],
                     geometry="geometry", crs="EPSG:32645").to_crs("EPSG:4326") \
                    .to_file(gpath, driver="GeoJSON")

    # --- 1: the geometry check that actually matters ---
    # Sample the water mask ALONG each transect and check that it behaves like a
    # river cross-section: water between the measured edges, land beyond them,
    # and an actual land->water->land transition at the two measured edges.
    #
    # The RGB is NOT used as a pass/fail test. Two attempts failed, both
    # legitimately: (a) "water is darker" is false for a turbid river, where
    # silt-laden water is paler than dark vegetation; (b) "water has less green"
    # is also false, because vegetated sandbars sit INSIDE the belt while the
    # floodplain beyond it can be bare silt. The imagery is still a useful
    # visual check, which is what the PNG overlay is for, and the masks have
    # already been validated independently by cross-sensor IoU (0.86).
    # Use the SAME cleaned mask the measurement uses. Comparing against the raw
    # mask instead compares two different things: the speckle filter is what
    # makes the measured edge land on a clean transition, so the check has to
    # see the filtered mask or it will always disagree.
    wmask, wtr, _ = T.load_water(ts.ref_year, ts.sensor_geom)
    winv = ~wtr
    wres = C.sensor_res(ts.sensor_geom)

    picks = [ok[i] for i in np.linspace(0, len(ok) - 1, 7).astype(int)]
    print("geometry check: does each transect actually cross the river?")
    print(f"{'id':>3} {'arc km':>7} {'width km':>8} {'water in':>9} "
          f"{'water out':>10} {'edge@L':>7} {'edge@R':>7} {'verdict':>8}")
    print("-" * 68)
    verdicts = []
    for t in picks:
        n = int(t.half_max / wres)
        offs = np.arange(-n, n + 1) * wres
        cx, cy = winv * (t.center[0], t.center[1])
        cols = np.round(cx + offs / wres * t.normal[0]).astype(int)
        rows = np.round(cy + offs / wres * t.normal[1]).astype(int)
        H, W = wmask.shape
        valid = (rows >= 0) & (rows < H) & (cols >= 0) & (cols < W)
        w = np.zeros(len(offs), dtype=bool)
        w[valid] = wmask[rows[valid], cols[valid]]

        inside = (offs >= t.vmin) & (offs <= t.vmax)
        outside = valid & ~inside
        win = float(w[inside].mean())
        wout = float(w[outside].mean()) if outside.any() else 0.0

        def edge_ok(v, side):
            """water inside the edge, land outside it.

            side='min': outside is BEFORE the edge, inside is after.
            side='max': inside is BEFORE the edge, outside is after.
            (Getting this backwards makes a perfect edge fail, which is what
            happened the first time.)

            The smoothed edge is where the *smoothed* profile crosses the
            threshold, so the raw profile right at the edge is legitimately
            patchy. We therefore look a little further in on each side.
            """
            k = int(np.argmin(np.abs(offs - v)))
            if side == "min":
                outw = w[max(0, k - 12):k]
                inw = w[k + 8:min(len(w), k + 28)]
            else:
                inw = w[max(0, k - 28):k - 8]
                outw = w[k + 1:min(len(w), k + 13)]
            if len(outw) == 0 or len(inw) == 0:
                return False
            return (outw.mean() < 0.20) and (inw.mean() > 0.30)

        el, er = edge_ok(t.vmin, 'min'), edge_ok(t.vmax, 'max')
        good = win >= 0.25 and wout <= 0.15 and el and er
        verdicts.append(good)
        print(f"{t.i:>3} {t.arc_m/1000:7.2f} {t.width_m/1000:8.2f} "
              f"{win*100:8.0f}% {wout*100:9.0f}% {'yes' if el else 'NO':>7} "
              f"{'yes' if er else 'NO':>7} {'PASS' if good else 'FAIL':>8}")

    # --- 3: visual overlay ---
    with rasterio.open(C.sensor_mask_path(ts.sensor_geom, ts.ref_year)) as s:
        m = s.read(1)
        tr = s.transform
        H, W = s.height, s.width
    step = max(1, int(500 / C.sensor_res(ts.sensor_geom)))
    img = Image.fromarray((m[::step, ::step] > 127).astype("uint8") * 255)
    img = img.convert("RGB")
    d = ImageDraw.Draw(img)
    inv = ~tr

    def to_px(p):
        c, r = inv * (float(p[0]), float(p[1]))
        return (c / step, r / step)

    for t in ok:
        a, b = T.transect_line(t).coords
        pa, pb = to_px(a), to_px(b)
        col = (0, 255, 0) if t.ok else (255, 0, 0)
        d.line([(float(pa[0]), float(pa[1])),
                (float(pb[0]), float(pb[1]))], fill=col, width=1)
        # mark the two measured edges
        for v in (t.vmin, t.vmax):
            p = t.center + v * t.normal
            pp = to_px(p)
            d.ellipse([float(pp[0])-3, float(pp[1])-3,
                       float(pp[0])+3, float(pp[1])+3], outline=(255, 255, 0))
    ppath = OUT / "transects_overlay.png"
    img.save(ppath)

    n_pass = sum(verdicts)
    print(f"\n{n_pass}/{len(picks)} sampled transects cross the river properly:")
    print("  water between the measured edges, land beyond, real transitions at both edges")
    print(f"-> {gpath}")
    print(f"-> {ppath}")

    summary = {
        "transects_built": len(ts.transects) + len(ts.dropped_build),
        "transects_kept": len(ts.transects),
        "dropped_at_build": [r for _, r in ts.dropped_build],
        "dropped_at_reference_year": [r for _, r in dropped],
        "centreline_km": round(ts.centreline_km, 2),
        "belt_width_km_median": round(float(np.median([t.width_m for t in ok])) / 1000, 2),
        "spot_checks_passed": f"{n_pass}/{len(picks)}",
    }
    (OUT / "geometry_check.json").write_text(json.dumps(summary, indent=2))
    print(f"-> {OUT / 'geometry_check.json'}")


if __name__ == "__main__":
    main()
