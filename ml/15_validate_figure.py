"""15 - Held-out validation figure: predicted vs observed 2026 bankline.

WHAT THIS SHOWS, AND WHY IT IS A REAL TEST
  The model is trained only on year pairs that END at or before 2021. It never
  sees anything from 2022-2026. It is then asked to predict the 2021 -> 2026
  bank movement, and that prediction is drawn against the bankline that was
  actually measured in 2026.

  Drawing the model's 2036 projection over the 2026 bankline would show nothing:
  there is no observation yet to compare it with. A validation figure has to
  predict a year we already have and then hold it up against that year.

  BLUE   = real 2026 bankline, measured from the 2026 Landsat water mask
  MAROON = our system's predicted 2026 bankline

  Both lines are built the SAME way, from the same fixed transects, so the
  difference between them is the prediction error and nothing else.

Run:  RIVERGUARD_REACH=arial_khan ../.venv/bin/python 15_validate_figure.py
"""

import importlib
import sys

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

import config as C
import transects as T

mt = importlib.import_module("14_model_train")

TRAIN_UPTO = 2021          # every pair ending at or before this is training data
TARGET_Y0, TARGET_Y1 = 2021, 2026
YEARS_AHEAD = TARGET_Y1 - TARGET_Y0
SENSOR = "landsat"
CLIP_M = 600.0             # do not draw a cast that ran away


def main():
    sensor = sys.argv[1] if len(sys.argv) > 1 else SENSOR
    out_png = C.ROOT / "reports" / "validation_bankline_2026.png"

    df = mt.load(C.REACH, sensor)
    cols = mt.features(df)

    train = df[df["year1"] <= TRAIN_UPTO]
    test = df[(df["year0"] == TARGET_Y0) & (df["year1"] == TARGET_Y1)]
    if train.empty or test.empty:
        raise SystemExit(f"need pairs up to {TRAIN_UPTO} and a "
                         f"{TARGET_Y0}->{TARGET_Y1} pair; found "
                         f"{sorted(df.year1.unique())[:3]}...")

    print(f"training on {len(train)} rows, pairs ending <= {TRAIN_UPTO} "
          f"({train.year1.min()}-{train.year1.max()})")
    print(f"held out: the {TARGET_Y0}->{TARGET_Y1} pair, {len(test)} rows")

    model_name = mt.MODEL_NAMES[mt.DEFAULT_MODEL]
    med = train[cols].median().fillna(0)
    model = mt.make_model(mt.DEFAULT_MODEL)
    model.fit(train[cols].fillna(med), train["target_rate"])

    pred = model.predict(test[cols].fillna(med))
    test = test.assign(pred=pred)
    obs = test["target_rate"].to_numpy()

    # ---- how close are the PREDICTED RATES to the measured ones? -----------
    err = np.abs(pred - obs)
    base_err = np.abs(train["target_rate"].median() - obs)
    print(f"\npredicted-rate error: median {np.median(err):.1f} m/yr, "
          f"mean {err.mean():.1f} m/yr")
    print(f"'predict the training median' error: median {np.median(base_err):.1f} m/yr")
    print(f"model beats that baseline: "
          f"{'YES' if err.mean() < base_err.mean() else 'NO'}")

    # ---- bank positions ---------------------------------------------------
    ts = T.build_transects(sensor_geom=T.GEOM_SENSOR, quiet=True)

    T.measure_edges(ts, TARGET_Y0, sensor, quiet=True)
    pos0 = {t.i: (t.vmin, t.vmax) for t in ts.transects if t.ok}
    T.measure_edges(ts, TARGET_Y1, sensor, quiet=True)
    pos1 = {t.i: (t.vmin, t.vmax) for t in ts.transects if t.ok}
    T.measure_edges(ts, TARGET_Y0, sensor, quiet=True)

    pmap = {(int(r.transect_id), r.side): float(r.pred)
            for r in test.itertuples()}

    rows = []
    for t in ts.transects:
        if t.i not in pos0 or t.i not in pos1:
            continue
        l0, r0 = pos0[t.i]
        l1, r1 = pos1[t.i]
        pl = pmap.get((t.i, "left"))
        pr = pmap.get((t.i, "right"))
        if pl is None or pr is None:
            continue
        # positive rate = land lost = the water expands = the bank moves OUT.
        # Left is the -normal side, so its offset becomes more negative.
        lp = np.clip(l0 - pl * YEARS_AHEAD, -CLIP_M, CLIP_M)
        rp = np.clip(r0 + pr * YEARS_AHEAD, -CLIP_M, CLIP_M)
        rows.append(dict(id=t.i, arc_m=t.arc_m, obs_l=l1, obs_r=r1,
                         pred_l=lp, pred_r=rp,
                         err_l=abs(lp - l1), err_r=abs(rp - r1),
                         static_l=abs(l0 - l1), static_r=abs(r0 - r1),
                         geometry=T.transect_line(t)))

    if not rows:
        raise SystemExit("no transect had both a prediction and both years measured")

    gdf = gpd.GeoDataFrame(rows, crs=C.CRS_WORK)
    allerr = np.concatenate([gdf.err_l.values, gdf.err_r.values])
    # The honest benchmark for a bankline figure: assume the bank never moved
    # since the last year we measured it. That is the do-nothing prediction the
    # model has to beat, and it is the same quantity being drawn.
    static_err = np.concatenate([gdf.static_l.values, gdf.static_r.values])
    med_off = float(np.median(allerr))
    mean_off = float(allerr.mean())
    med_static = float(np.median(static_err))
    mean_static = float(static_err.mean())
    within = {m: float((allerr <= m).mean() * 100) for m in (15, 30, 60, 120)}
    within_static = {m: float((static_err <= m).mean() * 100)
                     for m in (15, 30, 60, 120)}

    print(f"\nbank-position agreement over {len(gdf)} transects "
          f"({len(allerr)} bank sides), {YEARS_AHEAD} yr ahead:")
    print(f"  OUR MODEL      median {med_off:5.1f} m   mean {mean_off:5.1f} m")
    print(f"  bank unchanged median {med_static:5.1f} m   mean {mean_static:5.1f} m")
    for m in within:
        print(f"  within {m:>3} m : ours {within[m]:5.1f}%   "
              f"unchanged {within_static[m]:5.1f}%")
    improved = mean_off < mean_static
    print(f"\n  model beats 'assume no movement': {'YES' if improved else 'NO'}")

    # ---- the figure -------------------------------------------------------
    fig = plt.figure(figsize=(15.5, 9.5), dpi=150)
    ax = fig.add_axes([0.04, 0.06, 0.70, 0.88])
    bx = fig.add_axes([0.755, 0.06, 0.235, 0.88])
    bx.axis("off")

    arc = gdf.arc_m.values / 1000.0
    ax.plot(arc, gdf.obs_l, color="#1257c4", lw=2.6, label="REAL 2026 bankline")
    ax.plot(arc, gdf.obs_r, color="#1257c4", lw=2.6)
    ax.plot(arc, gdf.pred_l, color="#8c1f28", lw=2.2, ls="--",
            label="PREDICTED 2026 bankline")
    ax.plot(arc, gdf.pred_r, color="#8c1f28", lw=2.2, ls="--")
    ax.fill_between(arc, gdf.obs_l, gdf.obs_r, color="#1257c4", alpha=0.10)

    ax.set_xlabel("distance along the river centreline (km)", fontsize=11)
    ax.set_ylabel("bank offset across the river (m)", fontsize=11)
    ax.set_title(
        f"RiverGuard - predicted vs observed bankline, Arial Khan {TARGET_Y1}\n"
        f"{model_name} trained only on data up to {TRAIN_UPTO}; "
        f"the {TARGET_Y0}-{TARGET_Y1} interval was never seen in training",
        fontsize=12)
    ax.grid(alpha=0.25)
    ax.legend(loc="upper right", fontsize=11, framealpha=0.95)

    txt = [
        "HOW CLOSE ARE THEY?",
        "",
        f"model  {model_name}",
        f"training ends        {TRAIN_UPTO}",
        "",
        f"transects compared   {len(gdf)}",
        f"bank sides           {len(allerr)}",
        f"forecast horizon     {YEARS_AHEAD} years",
        "",
        "OUR PREDICTION",
        f"  median error  {med_off:6.1f} m",
        f"  mean error    {mean_off:6.1f} m",
        "",
        "IF THE BANK NEVER",
        "MOVED (do nothing)",
        f"  median error  {med_static:6.1f} m",
        f"  mean error    {mean_static:6.1f} m",
        "",
        f"  => {'BETTER' if improved else 'not better'}",
        f"     {mean_static / max(mean_off, 1e-9):.2f}x at the mean",
        "",
        "share of banks within:",
    ]
    for m in within:
        txt.append(f"   {m:>3} m   ours {within[m]:5.1f}%")
    txt += [
        "",
        f"the channel is about",
        f"300 m wide, so the",
        f"median error is",
        f"{med_off / 300 * 100:.0f}% of its width",
        "",
        "-" * 24,
        "",
        "SCORED ON THE",
        f"{TARGET_Y0}-{TARGET_Y1} INTERVAL,",
        "WHICH WAS HELD OUT",
        "OF TRAINING ENTIRELY",
    ]
    bx.text(0.0, 1.0, "\n".join(txt), va="top", ha="left", family="monospace",
            fontsize=10.5, linespacing=1.5)

    fig.savefig(out_png, facecolor="white", bbox_inches="tight")
    print(f"\n-> {out_png}")

    csv = C.DATA_PROC / "predictions" / f"validation_{TARGET_Y0}_{TARGET_Y1}.csv"
    gdf.drop(columns=["geometry"]).to_csv(csv, index=False)
    print(f"-> {csv}")


if __name__ == "__main__":
    main()
