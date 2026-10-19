"""16 - Does more training data help? Same target, growing training sets.

THE QUESTION
  "Train through 2021 and predict 2026" vs "train through 2023 and predict 2026".

THE TRAP THIS AVOIDS
  Landsat pairs are 5-year steps. If the target stayed 2021 -> 2026 while we
  trained on pairs up to 2023, the training pair (2018, 2023) would OVERLAP the
  target - 2021, 2022 and 2023 sit inside both. The score would improve because
  the model had already been shown three of the five years it is being asked to
  predict. That is not accuracy, it is peeking, and it is the same class of bug
  as D80.

  So the target is moved to a window that does not overlap anything we train on:
  (2023 -> 2026). Both models then predict exactly the same interval and differ
  ONLY in how much history they were allowed to see. That is a fair learning
  curve.

WHAT IS BUILT
  1. EPR for the extra (2023, 2026) pair, through the ordinary 04_erosion code
     path, so it is measured the same way as every other pair.
  2. features_with2023.csv - the normal table plus the extra pair, so the
     ordinary features.csv keeps exactly the rows it had.
  3. A model per training cutoff, all scored on (2023, 2026).
  4. reports/validation_bankline_2026_from2023.png - same style as the 2021
     figure: blue real 2026 bankline, dashed maroon predicted.

Run:  RIVERGUARD_REACH=arial_khan ../.venv/bin/python 16_more_data.py
"""

import importlib
import sys

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import config as C
import transects as T

E = importlib.import_module("04_erosion")
F = importlib.import_module("05_features")
mt = importlib.import_module("14_model_train")

SENSOR = "landsat"
TARGET_Y0, TARGET_Y1 = 2023, 2026
EXTRA = [(TARGET_Y0, TARGET_Y1)]
EXT_TABLE = "features_with2023.csv"
CUTOFFS = [1999, 2004, 2009, 2014, 2019, 2021, 2023]
CLIP_M = 600.0


def ensure_measurements(force=False):
    """EPR for the extra pair, via the normal 04_erosion path."""
    out = C.sensor_transects_dir(SENSOR) / f"epr_{TARGET_Y0}_{TARGET_Y1}.geojson"
    if out.exists() and not force:
        print(f"[1/4] {out.name} already measured")
        return out
    print(f"[1/4] measuring the extra pair {TARGET_Y0}->{TARGET_Y1} ...")
    E.main(SENSOR, extra_pairs=EXTRA)
    if not out.exists():
        raise SystemExit(f"{out} was not produced")
    return out


def ensure_table(force=False):
    fdir = C.DATA_PROC / "features" / SENSOR
    out = fdir / EXT_TABLE
    if out.exists() and not force:
        print(f"[2/4] {out.name} already built")
        return out
    print(f"[2/4] building {EXT_TABLE} (normal rows + the extra pair) ...")
    F.main(SENSOR, extra_pairs=EXTRA, out_name=EXT_TABLE)
    return out


def main():
    force = "--force" in sys.argv
    ensure_measurements(force)
    table = ensure_table(force)

    df = pd.read_csv(table)
    cols = mt.features(df)

    test = df[(df.year0 == TARGET_Y0) & (df.year1 == TARGET_Y1)]
    if test.empty:
        raise SystemExit(f"no {TARGET_Y0}->{TARGET_Y1} rows in {table}")
    obs = test.target_rate.to_numpy()
    print(f"[3/4] target {TARGET_Y0}->{TARGET_Y1}: {len(test)} rows "
          f"({test.transect_id.nunique()} transects)")

    # ---- learning curve: same target, growing history ---------------------
    preds, curve = {}, []
    for cut in CUTOFFS:
        train = df[df.year1 <= cut]
        if len(train) < 100:
            continue
        med = train[cols].median().fillna(0)
        m = mt.make_model(mt.DEFAULT_MODEL)
        m.fit(train[cols].fillna(med), train.target_rate)
        p = m.predict(test[cols].fillna(med))
        preds[cut] = p
        e = np.abs(p - obs)
        curve.append(dict(cutoff=cut, train_rows=len(train),
                          pairs=train.year1.nunique(),
                          mae=float(e.mean()), med_ae=float(np.median(e))))

    cur = pd.DataFrame(curve)
    print("\nlearning curve - target fixed at "
          f"{TARGET_Y0}->{TARGET_Y1}, only the training years change:\n")
    print(f"{'trained through':>15} {'rows':>6} {'pairs':>6} "
          f"{'MAE m/yr':>9} {'medAE':>7}   vs previous")
    best = None
    for r in curve:
        delta = ""
        if best is not None:
            d = r["mae"] - best
            delta = f"{d:+.2f} {'better' if d < 0 else 'WORSE'}"
        print(f"{r['cutoff']:>15} {r['train_rows']:>6} {r['pairs']:>6} "
              f"{r['mae']:>9.2f} {r['med_ae']:>7.2f}   {delta}")
        best = r["mae"]
    cur.to_csv(C.DATA_PROC / "predictions" / "learning_curve.csv", index=False)

    # Is the gain from MORE data, or from more RECENT data? Growing the training
    # set chronologically adds both at once, so the curve above cannot tell them
    # apart. This count-matched test can: same number of pairs, oldest vs newest.
    y1s = sorted(y for y in df.year1.unique() if y < TARGET_Y1)
    match = []

    def score_on(train):
        med = train[cols].median().fillna(0)
        m = mt.make_model(mt.DEFAULT_MODEL)
        m.fit(train[cols].fillna(med), train.target_rate)
        return float(np.abs(m.predict(test[cols].fillna(med)) - obs).mean())

    print(f"\ncount-matched: same number of pairs, OLDEST vs NEWEST\n")
    print(f"{'pairs':>7} {'rows':>6} {'oldest first':>14} {'newest first':>14}")
    for k in (4, 8, 12, 16, len(y1s)):
        old = df[df.year1.isin(y1s[:k])]
        new = df[df.year1.isin(y1s[-k:])]
        mo, mn = score_on(old), score_on(new)
        match.append(dict(pairs=k, rows=len(old), mae_oldest=mo, mae_newest=mn))
        print(f"{k:>7} {len(old):>6} {mo:>14.2f} {mn:>14.2f}")
    pd.DataFrame(match).to_csv(
        C.DATA_PROC / "predictions" / "learning_curve_matched.csv", index=False)
    print("\n  m/yr. If 'newest first' is far better at equal size, the gain is")
    print("  mostly RECENCY, not quantity - the two are confounded above.")

    # ---- bank positions ---------------------------------------------------
    ts = T.build_transects(sensor_geom=T.GEOM_SENSOR, quiet=True)
    T.measure_edges(ts, TARGET_Y0, SENSOR, quiet=True)
    pos0 = {t.i: (t.vmin, t.vmax) for t in ts.transects if t.ok}
    T.measure_edges(ts, TARGET_Y1, SENSOR, quiet=True)
    pos1 = {t.i: (t.vmin, t.vmax) for t in ts.transects if t.ok}
    T.measure_edges(ts, TARGET_Y0, SENSOR, quiet=True)

    years = float(TARGET_Y1 - TARGET_Y0)

    def bank_errors(p, cut):
        pmap = {}
        idx = 0
        for r in test.itertuples():
            pmap[(int(r.transect_id), r.side)] = float(p[idx]); idx += 1
        rows = []
        for t in ts.transects:
            if t.i not in pos0 or t.i not in pos1:
                continue
            if (t.i, "left") not in pmap or (t.i, "right") not in pmap:
                continue
            l0, r0 = pos0[t.i]
            l1, r1 = pos1[t.i]
            lp = np.clip(l0 - pmap[(t.i, "left")] * years, -CLIP_M, CLIP_M)
            rp = np.clip(r0 + pmap[(t.i, "right")] * years, -CLIP_M, CLIP_M)
            rows.append(dict(id=t.i, arc_m=t.arc_m, obs_l=l1, obs_r=r1,
                             pred_l=lp, pred_r=rp,
                             err_l=abs(lp - l1), err_r=abs(rp - r1),
                             static_l=abs(l0 - l1), static_r=abs(r0 - r1),
                             cutoff=cut))
        return pd.DataFrame(rows)

    a = bank_errors(preds[2021], 2021)
    b = bank_errors(preds[2023], 2023)

    def stats(g):
        e = np.concatenate([g.err_l.values, g.err_r.values])
        s = np.concatenate([g.static_l.values, g.static_r.values])
        return (float(np.median(e)), float(e.mean()),
                float((e <= 30).mean() * 100),
                float(np.median(s)), float(s.mean()),
                float((s <= 30).mean() * 100))

    m21, a21, w21, s21m, s21a, s21w = stats(a)
    m23, a23, w23, s23m, s23a, s23w = stats(b)
    better = a23 < a21

    print(f"\n[4/4] bank position over {years:.0f} years "
          f"({len(b)} transects, {2*len(b)} bank sides):\n")
    print(f"{'':34}{'median':>9}{'mean':>9}{'<=30m':>9}")
    print(f"{'trained through 2021':34}{m21:>9.1f}{a21:>9.1f}{w21:>8.1f}%")
    print(f"{'trained through 2023':34}{m23:>9.1f}{a23:>9.1f}{w23:>8.1f}%")
    print(f"{'bank never moved (do nothing)':34}{s23m:>9.1f}{s23a:>9.1f}{s23w:>8.1f}%")
    print(f"\n  more data is {'BETTER' if better else 'WORSE'} at the mean: "
          f"{a21:.1f} -> {a23:.1f} m ({100*(a23-a21)/a21:+.1f}%)")
    print(f"  and the do-nothing baseline is {s23a:.1f} m")

    # ---- figure -----------------------------------------------------------
    fig = plt.figure(figsize=(15.5, 9.5), dpi=150)
    ax = fig.add_axes([0.04, 0.06, 0.70, 0.88])
    bx = fig.add_axes([0.755, 0.06, 0.235, 0.88])
    bx.axis("off")

    arc = b.arc_m.values / 1000.0
    ax.plot(arc, b.obs_l, color="#1257c4", lw=2.6, label=f"REAL {TARGET_Y1} bankline")
    ax.plot(arc, b.obs_r, color="#1257c4", lw=2.6)
    ax.plot(arc, a.pred_l, color="#b8860b", lw=1.6, ls=":", alpha=0.9,
            label=f"predicted, trained thru 2021")
    ax.plot(arc, a.pred_r, color="#b8860b", lw=1.6, ls=":", alpha=0.9)
    ax.plot(arc, b.pred_l, color="#8c1f28", lw=2.2, ls="--",
            label=f"predicted, trained thru 2023")
    ax.plot(arc, b.pred_r, color="#8c1f28", lw=2.2, ls="--")
    ax.fill_between(arc, b.obs_l, b.obs_r, color="#1257c4", alpha=0.10)

    ax.set_xlabel("distance along the river centreline (km)", fontsize=11)
    ax.set_ylabel("bank offset across the river (m)", fontsize=11)
    ax.set_title(
        f"RiverGuard - does more training data help? Arial Khan {TARGET_Y1}\n"
        f"{mt.MODEL_NAMES[mt.DEFAULT_MODEL]}: both models predict the SAME "
        f"{TARGET_Y0}-{TARGET_Y1} interval; they differ only in how much "
        f"history they saw",
        fontsize=12)
    ax.grid(alpha=0.25)
    ax.legend(loc="upper right", fontsize=9.5, framealpha=0.95)

    txt = [
        "SAME TARGET, MORE",
        "TRAINING DATA",
        f"model   {mt.MODEL_NAMES[mt.DEFAULT_MODEL]}",
        f"target  {TARGET_Y0}->{TARGET_Y1} ({years:.0f} yr)",
        f"scored  {len(b)} transects",
        "",
        "bank position error:",
        "",
        f"{'':2}thru 2021   {a21:6.1f} m",
        f"{'':2}thru 2023   {a23:6.1f} m",
        f"  => {'BETTER' if better else 'WORSE'}",
        f"     {100*(a23-a21)/a21:+.1f}%",
        "",
        "median error:",
        f"  thru 2021   {m21:6.1f} m",
        f"  thru 2023   {m23:6.1f} m",
        "",
        f"within 30 m:",
        f"  thru 2021   {w21:5.1f}%",
        f"  thru 2023   {w23:5.1f}%",
        "",
        "do nothing    "
        f"{s23a:6.1f} m",
        f"  (within 30 m {s23w:.1f}%)",
        "",
        "-" * 24,
        "",
        "LEARNING CURVE",
        "(same target)",
        "",
    ]
    for r in curve:
        txt.append(f"  thru {r['cutoff']} {r['mae']:5.2f}")
    txt += ["", "units: m/yr of bank", "movement"]
    bx.text(0.0, 1.0, "\n".join(txt), va="top", ha="left", family="monospace",
            fontsize=9.5, linespacing=1.5)

    out_png = C.ROOT / "reports" / "validation_bankline_2026_from2023.png"
    fig.savefig(out_png, facecolor="white", bbox_inches="tight")
    print(f"\n-> {out_png}")

    csv = C.DATA_PROC / "predictions" / f"validation_{TARGET_Y0}_{TARGET_Y1}.csv"
    b.to_csv(csv, index=False)
    print(f"-> {csv}")


if __name__ == "__main__":
    main()
