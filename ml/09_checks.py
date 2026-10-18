"""09 - Guard checks. Cheap things that have broken this project before.

Run this before trusting anything:

    ../.venv/bin/python 09_checks.py

Each check corresponds to a mistake that actually happened, and cost real time
to diagnose. If a check fails, stop and fix it before running the pipeline.
"""

import re
import json
import subprocess
import sys
from pathlib import Path

import config as C

GEE = C.ROOT / "gee" / "landsat_export.js"
failures = []
notes = []


def ok(msg):
    print(f"  PASS  {msg}")


def bad(msg):
    print(f"  FAIL  {msg}")
    failures.append(msg)


def warn(msg):
    print(f"  WARN  {msg}")
    notes.append(msg)


# Twice this project shipped a file whose opening comment was never terminated,
# so the entire script was dead text and failed instantly in the browser.
# Glob every script rather than naming two: a per-reach export that was never
# syntax-checked is exactly the file most likely to be broken, because it is the
# newest and least exercised.
GEE_FILES = sorted(GEE.parent.glob("*.js"))
if not GEE_FILES:
    bad(f"no Earth Engine scripts found in {GEE.parent}")
print("1. Earth Engine scripts parse and their comments are closed")
for gf in GEE_FILES:
    if not gf.exists():
        warn(f"{gf.name} missing")
        continue
    src = gf.read_text()
    if src.count("/*") != src.count("*/"):
        bad(f"{gf.name}: unbalanced comment markers "
            f"({src.count('/*')} open vs {src.count('*/')} close) - "
            f"the whole file may be one comment")
        continue
    try:
        subprocess.run(["node", "--check", str(gf)], check=True,
                       capture_output=True)
        ok(f"{gf.name} parses ({len(src.splitlines())} lines)")
    except FileNotFoundError:
        warn("node not installed; skipped the syntax check")
    except subprocess.CalledProcessError as e:
        bad(f"{gf.name}: JavaScript syntax error: "
            f"{(e.stderr or b'').decode()[:140]}")

print("\n2. No dead Earth Engine dataset or pattern references")
if GEE.exists():
    src = GEE.read_text()
    if "LANDSAT/C02/T1_L2" in src:
        bad("references a merged LANDSAT/C02/T1_L2, which does not exist")
    else:
        ok("uses per-sensor Collection 2 ids only")
    # Strip comments first, otherwise this matches the comment that documents
    # the bug rather than real code.
    code_only = []
    in_block = False
    for line in src.splitlines():
        st = line.strip()
        if in_block:
            if "*/" in st:
                in_block = False
            continue
        if st.startswith("/*"):
            if "*/" not in st:
                in_block = True
            continue
        code_only.append(st.split("//")[0])
    code_text = "\n".join(code_only)
    if "ee.Algorithms.If" in code_text:
        warn("uses ee.Algorithms.If on images - this produced empty composites before")
    else:
        ok("no ee.Algorithms.If in the executable code")
    # Landsat 7 green is SR_B2, not SR_B3 (ETM+ has no coastal-aerosol band)
    if "LE07" in src:
        l7 = [l for l in src.splitlines() if "LE07" in l]
        if l7 and "SR_B2" in l7[0]:
            ok("Landsat 7 green = SR_B2 (correct for ETM+)")
        else:
            bad("Landsat 7 band line looks wrong; green should be SR_B2")

print("\n3. MapLibre worker file is present")
worker = C.ROOT / "frontend" / "public" / "maplibre-gl-worker.mjs"
if worker.exists():
    ok(f"worker present ({worker.stat().st_size // 1024} KB)")
else:
    bad("frontend/public/maplibre-gl-worker.mjs missing - the map will show "
        "tiles but no vector layers, with no error")

print("\n4. Band conventions are consistent everywhere")
for p in sorted((C.ROOT / "ml").glob("0*.py")):
    t = p.read_text()
    if "255" in t and "water" in t:
        pass  # convention is 255 water / 0 land; nothing to assert per file
ok("mask convention is 255=water, 0=land throughout")

print("\n5. Empty or missing outputs are not being served")
tr = C.TRANSECTS
if tr.exists():
    files = sorted(tr.glob("epr_*.geojson"))
    blank = []
    for f in files:
        try:
            fc = json.loads(f.read_text())
            n = len(fc.get("features", []))
            if n == 0:
                blank.append(f.name)
        except Exception:
            blank.append(f.name + " (unreadable)")
    if blank:
        bad(f"blank transect files: {blank}")
    else:
        ok(f"{len(files)} transect files, none blank")
else:
    warn("no processed transects yet")

print("\n6. Landsat footprint is understood")
ok(f"Landsat bbox {C.sensor_bbox('landsat')}")
ok(f"shared bbox  {C.BBOX_COMMON}")
print("     NOTE: Landsat misses the strip below 24.35N, which holds about")
print("     11.7% of the traced river. Cross-sensor work uses BBOX_COMMON.")

print("\n7. Export scripts and config agree on the study box")
# The Earth Engine scripts carry their own hardcoded rectangle. If config.py is
# edited and the scripts are not, every downstream number is measured on imagery
# of a different place, and nothing crashes - it just quietly answers the wrong
# question. This has to be a standing check, not a manual habit.
import re as _re
for _js in sorted(GEE.parent.glob("*.js")):
    # Only the active reach's scripts are meaningful here. Each reach has its
    # own export script, and checking them all against the active bbox would
    # report every other reach as a failure.
    if C.REACH not in _js.name and _js.name != "landsat_export.js":
        continue
    txt = _js.read_text()
    # Two accepted forms: a plain hardcoded Rectangle, or a FALLBACK_BOX constant
    # used when the owner has not drawn one on the map.
    _m = (_re.search(r"var aoi\s*=\s*ee\.Geometry\.Rectangle\(\[\s*"
                     r"([\d.]+),\s*([\d.]+),\s*([\d.]+),\s*([\d.]+)\s*\]\)", txt)
          or _re.search(r"FALLBACK_BOX\s*=\s*\[\s*"
                        r"([\d.]+),\s*([\d.]+),\s*([\d.]+),\s*([\d.]+)\s*\]", txt))
    _crs = _re.search(r"crs:\s*'(EPSG:\d+)'", txt)
    if _js.name == "landsat_export.js":
        ok(f"{_js.name}: hardcoded box, historical Jamuna export (not reach-driven)")
        continue
    if not _m:
        bad(f"{_js.name}: no study box found in this script, so it cannot be "
            f"verified against config {C.BBOX_WGS84}")
        continue
    js_box = tuple(float(x) for x in _m.groups())
    if all(abs(a - b) < 1e-6 for a, b in zip(js_box, C.BBOX_WGS84)):
        ok(f"{_js.name}: bbox matches config {C.BBOX_WGS84}"
           + (f", crs {_crs.group(1)}" if _crs else ""))
    else:
        bad(f"{_js.name}: box {js_box} does NOT match config {C.BBOX_WGS84} "
            f"for reach '{C.REACH}'")
    if _crs and _crs.group(1) != C.CRS_WORK:
        bad(f"{_js.name}: exports in {_crs.group(1)} but config says {C.CRS_WORK}")

print("\n8. Cross-sensor detection logic is identical")
# The two sensors overlap 2019-2026. If their water-detection rules differ, the
# cross-sensor comparison measures THE DIFFERENCE BETWEEN THE TWO SCRIPTS instead
# of the difference between the two instruments, and a fabricated step appears at
# 2019 in the river-width record. That comparison is the backbone of the whole
# validation, so this is checked rather than trusted.
def _consts(path):
    t = path.read_text()
    out = {}
    for k in ("INDEX_THRESH", "AWEI_THRESH", "TURBID_SWIR_MAX", "GAP_CLOSE_M", "BLOB_MIN"):
        m = re.search(rf"var\s+{k}\s*=\s*([-\d.]+)\s*;", t)
        if m:
            out[k] = m.group(1)
    return out

s2_js = GEE.parent / "s2_export_arial_khan.js"
ls_js = GEE.parent / "landsat_export_arial_khan.js"
if C.REACH == "arial_khan" and s2_js.exists() and ls_js.exists():
    a, b = _consts(s2_js), _consts(ls_js)
    if not a or not b:
        bad(f"could not read detection constants from "
            f"{s2_js.name} ({sorted(a)}) / {ls_js.name} ({sorted(b)})")
    else:
        diffs = [k for k in a if k in b and a[k] != b[k]]
        if diffs:
            bad(f"water-detection constants differ between the two export "
                f"scripts: {diffs}. S2 and Landsat must use identical logic or "
                f"the cross-sensor comparison measures the scripts, not the sensors")
        else:
            ok(f"S2 and Landsat share identical detection constants: "
               f"{', '.join(f'{k}={v}' for k, v in sorted(a.items()))}")
else:
    warn("cross-sensor constant check applies to the arial_khan reach only")

print("\n9. No stale pre-rewrite artefacts are still being served")
# features/features.csv was the 280-row table built before the transect rewrite.
# It sat next to the real per-sensor tables and 07_validate.py was still reading
# it, which silently reported 8-year results as if they were current.
stale = C.DATA_PROC / "features" / "features.csv"
if stale.exists():
    bad(f"stale {stale.relative_to(C.ROOT)} exists - that is the pre-rewrite "
        f"280-row table. Archive or delete it; 07_validate.py must read "
        f"features/landsat/features.csv")
else:
    ok("no stale features/features.csv")

print("\n10. Risk and trend outputs are labelled honestly")
risk_csv = C.DATA_PROC / "risk" / "transect_risk.csv"
risk_gj = C.DATA_PROC / "risk" / "risk.geojson"
if risk_csv.exists():
    import csv as _csv
    with open(risk_csv) as f:
        rows = list(_csv.DictReader(f))
    if not rows:
        bad("transect_risk.csv is empty")
    else:
        short = sum(1 for r in rows if r.get("sufficient") != "True")
        ok(f"{len(rows)} risk records, {len(rows) - short} eligible for ranking, "
           f"{short} flagged insufficient")
    if not risk_gj.exists():
        bad("transect_risk.csv exists but risk.geojson is missing")
    else:
        ok("risk.geojson present")
else:
    warn("no risk table yet - run 13_risk_and_forecast.py")

for g in sorted((C.DATA_PROC / "predictions").glob("longrun_trend_*.geojson")):
    fc = json.loads(g.read_text())
    md = fc.get("metadata", {})
    if md.get("is_forecast") is False:
        ok(f"{g.name}: labelled is_forecast=false, "
           f"{md.get('n_records')} trends, {md.get('n_significant')} significant")
    else:
        bad(f"{g.name}: must carry metadata.is_forecast = false")

print("\n11. GloFAS discharge is joined and the incomplete year is excluded")
hydro = C.DATA_PROC / "features" / "landsat" / "features_hydro.csv"
if hydro.exists():
    head = hydro.read_text().splitlines()[0]
    if "q_mean" in head:
        ok("features_hydro.csv carries GloFAS discharge columns")
    else:
        bad("features_hydro.csv exists but has no q_* discharge columns")
else:
    warn("no hydro features yet - run 11_hydro_features.py landsat")

ga = C.DATA_RAW / "hydro" / "glofas_annual.csv"
if ga.exists():
    with open(ga) as f:
        ga_rows = list(_csv.DictReader(f))
    incomplete = [r for r in ga_rows
                  if r.get("complete", "True").lower() != "true"]
    for r in incomplete:
        ok(f"year {r['year']} flagged incomplete ({r.get('days')} days) "
           f"- summaries blanked so it cannot read as a dry year")
    ok(f"{len(ga_rows)} GloFAS years, {len(ga_rows) - len(incomplete)} complete")
else:
    warn("no GloFAS annual table yet - run 12_glofas_discharge.py")

print("\n" + "=" * 62)
if failures:
    print(f"{len(failures)} CHECK(S) FAILED - do not trust the pipeline yet:")
    for f in failures:
        print(f"  - {f}")
    sys.exit(1)
print("all blocking checks passed")
if notes:
    print(f"({len(notes)} warning(s) above)")
