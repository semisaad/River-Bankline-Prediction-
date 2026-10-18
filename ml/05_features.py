"""05 - Build the ML feature table from the EPR measurements.

One row per (transect, bank side, year pair). The label is the erosion rate from
04_erosion.py; everything else is a feature the model may look at.

NO DATA LEAKAGE - the most important rule in this project.
Every feature for a row ending in year Y is computed using ONLY years up to and
including Y. If the model can peek at Y+1 we would be handing it the answer and
the test score would be a lie. The lag columns exist precisely so this holds.
Do not add a feature that breaks it.

Features fall into three groups:
  history   - how fast this bank moved last year, and the recent trend
  geometry  - bend curvature and position along the reach, from the centreline
  water     - width and stage, which stand in for the water-level confound

Water level: a low-water year exposes more bank and can look like erosion with
no land actually lost. We do not hand-correct for that; we give the model
stage_km2, stage_change_km2 and stage_ratio so it can learn to discount it.

Run:  ../.venv/bin/python 05_features.py [s2|landsat]
"""

import sys

import geopandas as gpd
import numpy as np
import pandas as pd

import config as C
import transects as T

FEATURES_DIR = C.DATA_PROC / "features"


def feature_dir(sensor):
    d = FEATURES_DIR / sensor
    d.mkdir(parents=True, exist_ok=True)
    return d


def load_rates(sensor):
    """rates[(transect_id, side)][target_year] = erosion rate in m/yr."""
    rates = {}
    # window length comes from C.PAIR_STEP - annual for S2, multi-year for
    # Landsat on a narrow river (see config.py for why)
    for y0, y1 in C.sensor_pairs(sensor):
        p = C.sensor_transects_dir(sensor) / f"epr_{y0}_{y1}.geojson"
        if not p.exists():
            continue
        for _, r in gpd.read_file(p).iterrows():
            tid = int(r["id"])
            for side in ("left", "right"):
                rates.setdefault((tid, side), {})[y1] = float(r[f"{side}_rate"])
    return rates


def centreline_shape(ts):
    """Bend geometry per transect, from the centreline itself.

    curvature_k - how tightly the river bends (1/m); large means a sharp bend,
                  and a sharp outer bank is what erodes.
    meander_off - how far the centreline bows away from the straight reach axis.
    """
    P, arcs = ts.points, ts.arcs
    # curvature of the planar centreline
    d1 = np.gradient(P, axis=0)
    d2 = np.gradient(d1, axis=0)
    num = np.abs(d1[:, 0] * d2[:, 1] - d1[:, 1] * d2[:, 0])
    den = (d1[:, 0] ** 2 + d1[:, 1] ** 2) ** 1.5
    with np.errstate(divide="ignore", invalid="ignore"):
        kappa = np.where(den > 0, num / np.maximum(den, 1e-12), 0.0)

    # distance from the straight line joining the two ends
    a, b = P[0], P[-1]
    ab = b - a
    L = float(np.hypot(*ab))
    off = np.zeros(len(P))
    if L > 0:
        # 2-D cross product magnitude (numpy.cross needs 3-D vectors)
        rel = P - a
        off = np.abs(ab[0] * rel[:, 1] - ab[1] * rel[:, 0]) / L

    out = {}
    for i, t in enumerate(ts.transects):
        j = int(np.argmin(np.abs(arcs - t.arc_m)))
        out[t.i] = {
            "curvature_k": float(kappa[j]),
            "meander_off_m": float(off[j]),
        }
    return out


def main(sensor="s2"):
    fdir = feature_dir(sensor)
    res = C.sensor_res(sensor)
    years = C.sensor_years(sensor)
    if len(years) < 3:
        print(f"{sensor}: need at least 3 processed years, found {len(years)}")
        return

    ts = T.build_transects()
    stage = {y: T.stage_km2(y, sensor) for y in years}
    shape = centreline_shape(ts)
    rates = load_rates(sensor)

    # widths per year, measured on the fixed transects
    width = {}
    for y in years:
        T.measure_edges(ts, y, sensor, quiet=True)
        width[y] = {t.i: t.width_m for t in ts.transects if t.ok}

    arcs = [t.arc_m for t in ts.transects]
    a_lo, a_hi = min(arcs), max(arcs)

    rows = []
    for y0, y1 in C.sensor_pairs(sensor):
        hist_years = [y for y in years if y <= y1]
        stage_med = float(np.median([stage[y] for y in hist_years]))
        stage_med_prev = float(np.median([stage[y] for y in hist_years if y <= y0]))

        for t in ts.transects:
            i = t.i
            sh = shape.get(i, {})
            w_now = width.get(y1, {}).get(i)
            w_prev = width.get(y0, {}).get(i)
            prior_w = [width[y][i] for y in hist_years
                       if i in width.get(y, {}) and width[y][i] > 0]
            w_med = float(np.median(prior_w)) if prior_w else np.nan

            for side in ("left", "right"):
                prior = rates.get((i, side), {})
                target = prior.get(y1)
                if target is None or w_now is None:
                    continue
                other = rates.get((i, "right" if side == "left" else "left"), {})

                last3 = [prior.get(y) for y in (y1 - 1, y1 - 2, y1 - 3)]
                last3 = [v for v in last3 if v is not None]
                n_prior = len([v for y in hist_years if (v := prior.get(y)) is not None])

                rows.append({
                    "sensor": sensor,
                    "res_m": res,
                    "transect_id": i,
                    "side": side,
                    "year0": y0,
                    "year1": y1,
                    "target_rate": round(target, 2),
                    "rate_lag1": prior.get(y1 - 1, np.nan),
                    "rate_lag2": prior.get(y1 - 2, np.nan),
                    "rate_roll3": float(np.mean(last3)) if last3 else np.nan,
                    "rate_std3": float(np.std(last3)) if len(last3) >= 2 else np.nan,
                    "n_prior": n_prior,
                    "other_side_rate": other.get(y1, np.nan),
                    "width_m": round(w_now, 1),
                    "width_lag1": w_prev,
                    "width_change_pct": (100.0 * (w_now - w_prev) / w_prev
                                         if w_prev else np.nan),
                    "width_ratio": (w_now / w_med if w_med and w_med > 0 else np.nan),
                    "curvature_k": sh.get("curvature_k", np.nan),
                    "meander_off_m": sh.get("meander_off_m", np.nan),
                    "stage_km2": round(stage[y1], 2),
                    "stage_change_km2": round(stage[y1] - stage[y0], 2),
                    "stage_ratio": round(stage[y1] / stage_med, 3) if stage_med else np.nan,
                    "stage_change_ratio": (round((stage[y1] - stage[y0]) / stage_med_prev, 3)
                                           if stage_med_prev else np.nan),
                    "arc_norm": round((t.arc_m - a_lo) / (a_hi - a_lo), 4)
                                if a_hi > a_lo else np.nan,
                })

    df = pd.DataFrame(rows).dropna(subset=["target_rate"])
    df = df.sort_values(["year1", "transect_id", "side"]).reset_index(drop=True)
    out_csv = fdir / "features.csv"
    df.to_csv(out_csv, index=False)

    # transect lines for the map
    lines = [{"id": t.i, "arc_m": round(t.arc_m, 1),
              "geometry": T.transect_line(t)} for t in ts.transects]
    gpd.GeoDataFrame(lines, crs=C.CRS_WORK).to_crs("EPSG:4326") \
        .to_file(fdir / "transect_lines.geojson", driver="GeoJSON")

    print(f"sensor {sensor} ({res} m)  years {years[0]}-{years[-1]}  "
          f"{len(df)} rows  {df.transect_id.nunique()} transects")
    print(f"label: median {df.target_rate.median():.1f} m/yr  "
          f"IQR {df.target_rate.quantile(.25):.1f}..{df.target_rate.quantile(.75):.1f}  "
          f"|rate| max {df.target_rate.abs().max():.0f}")
    na = df.isna().sum()
    miss = {c: int(v) for c, v in na.items() if v > 0 and c not in
            ("sensor", "res_m", "transect_id", "side", "year0", "year1",
             "target_rate", "arc_norm")}
    if miss:
        print("missing:", ", ".join(f"{k} {v}" for k, v in miss.items()))
    print(f"-> {out_csv}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "s2")
