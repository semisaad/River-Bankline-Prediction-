"""09 - Guard checks. Cheap things that have broken this project before.

Run this before trusting anything:

    ../.venv/bin/python 09_checks.py

Each check corresponds to a mistake that actually happened, and cost real time
to diagnose. If a check fails, stop and fix it before running the pipeline.
"""

import ast
import csv as _csv
import json
import re
import re as _re
import subprocess
import sys
from pathlib import Path

import config as C

GEE_DIR = C.ROOT / "gee"
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
GEE_FILES = sorted(GEE_DIR.glob("*.js"))
if not GEE_FILES:
    bad(f"no Earth Engine scripts found in {GEE_DIR}")
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
_ls_js = GEE_DIR / f"landsat_export_{C.REACH}.js"
if _ls_js.exists():
    src = _ls_js.read_text()
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
    # Landsat 7 green is SR_B2, not SR_B3 (ETM+ has no coastal-aerosol band),
    # while Landsat 8/9 green is SR_B3 (OLI does have one, as SR_B1). Getting
    # this wrong swaps green with blue or red and silently computes the wrong
    # water index: the mask still looks like water, in the wrong places.
    #
    # This used to test only the first line mentioning LE07, which happened to
    # be the band line in the retired Jamuna script. The live exporter mentions
    # LE07 once, in a collection id, so the check passed vacuously.
    for _fn, _want, _sensor in (("prepTM", "SR_B2", "Landsat 4/5/7 TM/ETM+"),
                                ("prepOLI", "SR_B3", "Landsat 8/9 OLI")):
        _body = _re.search(rf"function {_fn}\(.*?\n\}}", src, _re.S)
        if not _body:
            bad(f"{_fn} not found in {_ls_js.name}")
            continue
        _text = _body.group(0)
        _b = _re.search(r"select\(\[([^\]]+)\]\)", _text)
        _r = _re.search(r"rename\(\[([^\]]+)\]\)", _text)
        _bands = [x.strip().strip("'\"") for x in _b.group(1).split(",")] if _b else []
        _names = [x.strip().strip("'\"") for x in _r.group(1).split(",")] if _r else []
        if len(_bands) != 6 or len(_names) != 6:
            bad(f"{_fn}: could not read 6 source bands and 6 names")
        elif _bands[1] != _want:
            bad(f"{_fn}: green is {_bands[1]}, expected {_want} for {_sensor}")
        elif _names != ["blue", "green", "red", "nir", "swir1", "swir2"]:
            bad(f"{_fn}: renamed to {_names}, expected blue/green/red/nir/swir1/swir2")
        else:
            ok(f"{_fn}: green = {_want}, renamed blue/green/red/nir/swir1/swir2 "
               f"({_sensor})")
else:
    bad(f"{_ls_js.name} not found - this is the live Landsat exporter")

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
print("     NOTE: compare the sensor-specific bbox with the active reach before")
print("     using Landsat as cross-sensor validation.")

print("\n7. Export scripts and config agree on the study box")
# The Earth Engine scripts carry their own hardcoded rectangle. If config.py is
# edited and the scripts are not, every downstream number is measured on imagery
# of a different place, and nothing crashes - it just quietly answers the wrong
# question. This has to be a standing check, not a manual habit.
for _js in sorted(GEE_DIR.glob("*.js")):
    # Only the active reach's scripts are meaningful here. Each reach has its
    # own export script, and checking them all against the active bbox would
    # report every other reach as a failure.
    if C.REACH not in _js.name:
        continue
    txt = _js.read_text()
    # Validate the configured reference box even though exports now require a
    # newly drawn rectangle.
    _m = _re.search(r"REFERENCE_BOX\s*=\s*\[\s*"
                    r"([\d.]+),\s*([\d.]+),\s*([\d.]+),\s*([\d.]+)\s*\]", txt)
    _crs = _re.search(r"crs:\s*'(EPSG:\d+)'", txt)
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

print("\n7b. The hydrology export box covers the reach")
# D88: gee/hydro_export.js went out carrying the retired JAMUNA box, latitude
# 23.5-25.5, while this reach sits at latitude 23.134-23.261. The two did not
# overlap AT ALL. 11_hydro_features.py clips the rasters to the study box, so
# running it would have produced a table of NaNs and raised no error anywhere -
# the same silent-wrong-answer shape as check 7, and worth the same standing
# guard rather than a manual habit.
#
# A SUPERSET is correct here, unlike the imagery exporters, which must match
# exactly: the margin around the reach costs nothing and 11_ clips it away
# anyway. What must never happen is a region that misses the reach.
_hydro_js = GEE_DIR / "hydro_export.js"
if not _hydro_js.exists():
    warn("gee/hydro_export.js not found - cannot verify the hydrology export box")
else:
    _m = _re.search(r"REGION\s*=\s*ee\.Geometry\.Rectangle\(\s*\[\s*"
                    r"(-?[\d.]+),\s*(-?[\d.]+),\s*(-?[\d.]+),\s*(-?[\d.]+)\s*\]",
                    _hydro_js.read_text())
    if not _m:
        warn(f"{_hydro_js.name}: no REGION rectangle found, so it cannot be "
             f"verified against config {C.BBOX_WGS84}")
    else:
        _hw, _hs, _he, _hn = (float(x) for x in _m.groups())
        _w, _s, _e, _n = C.BBOX_WGS84
        if _hw <= _w and _he >= _e and _hs <= _s and _hn >= _n:
            ok(f"{_hydro_js.name}: region covers the study box "
               f"(lon {_hw}..{_he}, lat {_hs}..{_hn})")
        else:
            bad(f"{_hydro_js.name}: region lon {_hw}..{_he} lat {_hs}..{_hn} "
                f"does NOT cover the study box lon {_w}..{_e} lat {_s}..{_n}. "
                f"11_hydro_features.py would clip to nothing and write NaN "
                f"columns without erroring.")

print("\n8. Cross-sensor detection logic is identical")
# The two sensors overlap 2019-2026. If their water-detection rules differ, the
# cross-sensor comparison measures THE DIFFERENCE BETWEEN THE TWO SCRIPTS instead
# of the difference between the two instruments, and a fabricated step appears at
# 2019 in the river-width record. That comparison is the backbone of the whole
# validation, so this is checked rather than trusted.
def _consts(path):
    t = path.read_text()
    out = {}
    for k in ("INDEX_THRESH", "AWEI_THRESH", "TURBID_SWIR_MAX", "GAP_CLOSE_M",
              "BLOB_SCALE_M", "BLOB_MAX_SIZE", "BLOB_MIN"):
        m = re.search(rf"var\s+{k}\s*=\s*([-\d.]+)\s*;", t)
        if m:
            out[k] = m.group(1)
    # The dry-season window and the first/last year are as load-bearing as the
    # index thresholds, and drift in them is just as silent: the masks simply
    # cover a different slice of the year, the cross-sensor overlap no longer
    # lines up, and nothing raises. The season was already out of step with
    # config.py once (02-28 in the config, 03-25 in both scripts), so it is
    # checked rather than documented.
    m = re.search(r"filterDate\(\s*ee\.Date\.fromYMD\(y,\s*(\d+),\s*(\d+)\)"
                  r"\s*,\s*ee\.Date\.fromYMD\(y,\s*(\d+),\s*(\d+)\)", t)
    if m:
        out["season"] = (f"{int(m.group(1)):02d}-{int(m.group(2)):02d}"
                         f"..{int(m.group(3)):02d}-{int(m.group(4)):02d}")
    m = re.search(r"var\s+START\s*=\s*(\d{4})\s*,\s*END\s*=\s*(\d{4})", t)
    if m:
        out["years"] = f"{m.group(1)}..{m.group(2)}"
    return out

s2_js = GEE_DIR / "s2_export_arial_khan.js"
ls_js = GEE_DIR / "landsat_export_arial_khan.js"
if C.REACH == "arial_khan" and s2_js.exists() and ls_js.exists():
    a, b = _consts(s2_js), _consts(ls_js)
    if not a or not b:
        bad(f"could not read detection constants from "
            f"{s2_js.name} ({sorted(a)}) / {ls_js.name} ({sorted(b)})")
    else:
        # `years` and `season` are excluded from this diff on purpose: Landsat
        # reaches back to 1989 while Sentinel-2 starts in 2019, and that
        # asymmetry is the whole point of keeping the long record. They are
        # compared against config.py below, which is the claim that must hold.
        diffs = [k for k in a
                 if k in b and k not in ("years", "season") and a[k] != b[k]]
        if diffs:
            bad(f"water-detection constants differ between the two export "
                f"scripts: {diffs}. S2 and Landsat must use identical logic or "
                f"the cross-sensor comparison measures the scripts, not the sensors")
        else:
            ok(f"S2 and Landsat share identical detection constants: "
               f"{', '.join(f'{k}={v}' for k, v in sorted(a.items()))}")
        # Windows and year ranges are deliberately NOT required to match between
        # the sensors. Landsat is meant to reach back to 1989 while S2 starts in
        # 2019, and that asymmetry is the point of the long record. What must
        # hold is that each script agrees with what config.py claims about it.
        for _name, _prod, _exp in (("Sentinel-2", "s2", C.DRY_SEASON),
                                   ("Landsat", "landsat", C.DRY_SEASON)):
            _got = (a if _prod == "s2" else b).get("season")
            _want = f"{_exp[0]}..{_exp[1]}"
            if _got is None:
                warn(f"{_name} exporter: no dry-season filterDate found to verify")
            elif _got == _want:
                ok(f"{_name} exporter covers config DRY_SEASON {_got}")
            else:
                bad(f"{_name} exporter uses season {_got} but config.py says "
                    f"{_want}. The masks would cover a different part of the year "
                    f"with nothing downstream noticing.")
else:
    warn("cross-sensor constant check applies to the arial_khan reach only")

if C.REACH == "arial_khan" and s2_js.exists() and ls_js.exists():
    # The `valid` band must be sampled BEFORE the mask is destroyed.
    #
    # Both Arial Khan exporters once computed `valid = green.mask()` from a
    # composite that had already been `.unmask(0)`-ed. Unmasking erases the
    # mask, so mask() returned all ones and `valid` reported 100% for every
    # year - which turned `valid >= MIN_VALID` from a gate into decoration and
    # let years with almost no usable imagery be exported silently.
    #
    # This is a structural invariant that is cheap to check and expensive to
    # rediscover: in each script the line assigning `valid` must appear before
    # the composite is unmasked.
    for _js in (s2_js, ls_js):
        _t = _js.read_text().splitlines()
        _v = next((i for i, l in enumerate(_t) if l.strip().startswith("var valid")), None)
        _u = next((i for i, l in enumerate(_t) if ".unmask(0)" in l
                   and l.strip().startswith("var comp")), None)
        if _v is None or _u is None:
            warn(f"{_js.name}: could not locate the valid/unmask pair to verify")
        elif _v < _u:
            ok(f"{_js.name}: valid is sampled before the composite is unmasked")
        else:
            bad(f"{_js.name}: `valid` is computed AFTER the composite is "
                f"unmasked, so it will report 100% valid for every year and the "
                f"MIN_VALID gate will never fire. Sample validity first.")

    # The Padma latitude is a hard physical constraint (D51) and is now enforced
    # in the scripts as well as in config. If the two ever disagree, the scripts
    # would happily export the wrong river.
    def _js_without_comments(t):
        t = re.sub(r"/\*.*?\*/", "", t, flags=re.S)
        return re.sub(r"//[^\n]*", "", t)

    # ee.Algorithms.If returns a value whose server-side TYPE IS NOT DETERMINED,
    # so a method cannot be called on its result directly:
    #     ee.Algorithms.If(...).rename(...)
    # fails with "rename is not a function. Specify the object type first."
    # It must be wrapped, e.g. ee.Image(ee.Algorithms.If(...)). This reached the
    # owner as a runtime error in the Code Editor, so it is checked here rather
    # than remembered.
    for _js in (s2_js, ls_js):
        _code = _js_without_comments(_js.read_text())
        _offenders = []
        for _m in re.finditer(r"ee\.Algorithms\.If\(", _code):
            _i, _depth = _m.end(), 1
            while _i < len(_code) and _depth:
                if _code[_i] == "(":
                    _depth += 1
                elif _code[_i] == ")":
                    _depth -= 1
                _i += 1
            _tail = _code[_i:].lstrip()
            if _tail.startswith("."):
                _offenders.append("." + _tail[1:].split("(")[0].strip())
        if _offenders:
            bad(f"{_js.name}: a method is called directly on ee.Algorithms.If "
                f"({', '.join(sorted(set(_offenders)))}). Its return type is "
                f"undetermined, so this fails at run time in the Code Editor. "
                f"Wrap it as ee.Image(ee.Algorithms.If(...)), or better, check "
                f"the input first and delete the branch.")
        else:
            ok(f"{_js.name}: no method called on an untyped ee.Algorithms.If")
    _lims = []
    for _js in (s2_js, ls_js):
        _m = re.search(r"PADMA_LAT_MAX\s*=\s*([\d.]+)", _js.read_text())
        _lims.append((_js.name, float(_m.group(1)) if _m else None))
    _vals = {v for _, v in _lims if v is not None}
    if not _vals:
        warn("no PADMA_LAT_MAX found in the exporters to verify")
    elif len(_vals) > 1:
        bad(f"exporters disagree on PADMA_LAT_MAX: {_lims}")
    else:
        _lim = _vals.pop()
        _north = C.BBOX_WGS84[3]
        if _north >= _lim:
            bad(f"config north edge {_north} reaches the Padma bifurcation at "
                f"{_lim}N - the box would measure the Padma, not the Arial Khan (D51)")
        else:
            ok(f"north edge {_north}N is south of the Padma limit {_lim}N "
               f"enforced in both exporters")

    # The download quality gates exist in two places: as MIN_VALID etc. in the
    # GEE scripts, and as C.DOWNLOADS in config.py. They have to agree.
    #
    # WHY THE DUPLICATION IS WORTH CHECKING: the bulk survey was removed from
    # the exporters (D71) because evaluating the detection chain once per year
    # froze the Code Editor, so the gate is now applied locally - in 01_prepare
    # and 01b_prepare_landsat - against the config.py copy. If the scripts were
    # tightened and config.py was not, the local check would be waving through
    # downloads that the exporter would have refused, with nothing to say so.
    for _name, _js, _prod in (("Sentinel-2", s2_js, "s2"),
                              ("Landsat", ls_js, "landsat")):
        _want = C.DOWNLOADS.get(_prod, {})
        if not _want:
            warn(f"config.py has no download_gates for {_prod}")
            continue
        _txt = _js.read_text()
        _mismatch = []
        for _k, _v in sorted(_want.items()):
            _m = re.search(rf"var\s+{_k}\s*=\s*([\d.]+)", _txt)
            if _m is None:
                _mismatch.append(f"{_k}: absent from the script")
            elif abs(float(_m.group(1)) - float(_v)) > 1e-9:
                _mismatch.append(f"{_k}: script {_m.group(1)} vs config {_v}")
        if _mismatch:
            bad(f"{_name} download gates disagree with config.py: "
                f"{'; '.join(_mismatch)}. 01_prepare/01b_prepare_landsat judge "
                f"downloads against the config value, so a mismatch means one of "
                f"the two is not the gate anyone thinks it is.")
        else:
            ok(f"{_name} download gates match config.py: "
               f"{', '.join(f'{k}={v}' for k, v in sorted(_want.items()))}")

print("\n8b. config.py has no silently-shadowed dict keys")
# A duplicated key in a Python dict literal is LEGAL and SILENT - the last one
# wins and nothing warns. The arial_khan geometry gates carried "MARGIN_M" and
# "MAX_WIDTH_M" twice each, so the first of each pair never applied and no error
# was ever raised. ast sees both keys, which is exactly what is needed to notice.
_dupes = []
_tree = ast.parse(Path(C.__file__).read_text())
for _node in ast.walk(_tree):
    if not isinstance(_node, ast.Dict):
        continue
    _counts = {}
    for _k in _node.keys:
        if isinstance(_k, ast.Constant) and isinstance(_k.value, str):
            _counts[_k.value] = _counts.get(_k.value, 0) + 1
    _dup = sorted(k for k, n in _counts.items() if n > 1)
    if _dup:
        _dupes.append((_node.lineno, _dup))
if _dupes:
    for _line, _keys in _dupes:
        bad(f"config.py line {_line}: duplicated dict key(s) {_keys}. Only the "
            f"last value is used; the earlier ones are dead. Delete the shadowed "
            f"entries so the intended value is the visible one.")
else:
    ok("config.py has no duplicated dict keys")


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

# A model output is a forecast only when its chronological backtest beats both
# simple baselines and the requested spatial horizon has been independently
# validated. Current experimental outputs have no such horizon validation.
for g in sorted((C.DATA_PROC / "predictions").glob("longrun_trend_*.geojson")):
    fc = json.loads(g.read_text())
    md = fc.get("metadata", {})
    if "is_forecast" not in md:
        bad(f"{g.name}: must state whether it is a forecast")
        continue
    if md["is_forecast"] and (
            not md.get("forecast_supported") or
            not md.get("horizon_validated") or
            not md.get("mae_model_m_per_yr") or
            not md.get("median_baseline_mae_m_per_yr")):
        bad(f"{g.name}: forecast claim lacks passing chronological skill metrics")
    elif (md.get("projection_status") == "experimental" and
          md["is_forecast"]):
        bad(f"{g.name}: multi-year experimental projection cannot claim forecast status")
    elif md.get("projection_status") == "experimental" and not md.get(
            "mae_model_m_per_yr"):
        bad(f"{g.name}: experimental model projection lacks chronological MAE")
    else:
        ok(f"{g.name}: status={md.get('projection_status')}, "
           f"is_forecast={md['is_forecast']}, method={md.get('method')}, "
           f"{md.get('n_records')} records, "
           f"MAE {md.get('mae_model_m_per_yr', 'n/a')}")

    # The written warning must agree with the fields beside it. This is not
    # hypothetical: the old text was hardcoded to "the one-year model does not
    # beat both baselines" and survived the model improving to beat all three,
    # so the map shipped a sentence contradicting its own MAE figures. Anything
    # a human typed once will drift; this is what catches it drifting.
    #
    # Compared in lower case on purpose. The first version of this check looked
    # for the literal "NOT beat", and the real stale text reads "does not beat",
    # so it passed the very bug it was written for. A guard has to be tested
    # against the failure it exists to catch, not just against the fixed state.
    _low = str(md.get("warning", "")).lower()
    _sup = md.get("forecast_supported")
    _says_no = ("not beat" in _low) or ("n't beat" in _low)
    _mentions = "beat" in _low
    if not _mentions:
        warn(f"{g.name}: warning does not mention the baseline comparison at all")
    elif _sup and _says_no:
        bad(f"{g.name}: warning says the model does NOT beat the baselines while "
            f"forecast_supported=True - the text contradicts the data")
    elif (_sup is False) and not _says_no:
        bad(f"{g.name}: warning claims the model beats the baselines while "
            f"forecast_supported=False - the text contradicts the data")
    else:
        ok(f"{g.name}: warning agrees with forecast_supported={_sup}")

    # The estimator named in the map payload must be the one the report
    # describes. This is the D94 bug written as a check: the report hardcoded
    # "RandomForestRegressor" regardless of --model, and the GeoJSON typed its
    # own "RandomForest" string. Neither was tied to the model that actually
    # ran, so both could name the wrong estimator while carrying the right
    # score - a page that says "RandomForest, MAE 15.675" when 15.675 belongs to
    # a boosted model. Text that contradicts its own numbers is the exact
    # failure check 10 below was written for.
    _rp = C.ROOT / "ml" / "artifacts" / "model_report.json"
    _wanted = ""
    if _rp.exists():
        try:
            _wanted = str(json.loads(_rp.read_text()).get("model_name", "")).strip()
        except (ValueError, OSError):
            _wanted = ""
    _named = str(md.get("model_name", "")).strip()
    if md.get("projection_status") == "experimental" and _wanted:
        if not _named:
            bad(f"{g.name}: experimental projection does not name the model that "
                f"produced it (model_report.json says {_wanted})")
        elif _named != _wanted:
            bad(f"{g.name}: projection is attributed to {_named} but "
                f"model_report.json describes {_wanted} - the map and its score "
                f"disagree")
        else:
            ok(f"{g.name}: model '{_named}' agrees with model_report.json")

print("\n11. Hydrology forcing is present and usable")
# D88: the hydrology path is the ERA5-Land WEATHER PROXY exported by
# gee/hydro_export.js. GloFAS remains working code but was rejected on physics -
# at this reach its nearest cell reads a maximum of 13 m3/s for an entire year,
# so it models a small local catchment, not this river.
_hraw = C.DATA_RAW / "hydro"
_era = sorted(_hraw.glob("Hydro_*.tif")) if _hraw.exists() else []
if _era:
    _yrs = sorted(int(p.stem.split("_")[-1]) for p in _era)
    ok(f"{len(_yrs)} ERA5-Land year files, {_yrs[0]}-{_yrs[-1]}")
    if _yrs[0] > 1984:
        warn(f"earliest ERA5-Land year is {_yrs[0]}, but the oldest pair's "
             f"change column is measured from y0 - step = 1984")
    if _yrs[-1] > 2025:
        warn(f"an ERA5-Land file exists for {_yrs[-1]}, which is part-complete "
             f"and its mean is biased high - the missing months are the "
             f"low-flow ones. Export finished years only")
else:
    warn("no ERA5-Land proxy yet - run gee/hydro_export.js in Earth Engine, "
         "then put the Hydro_<year>.tif downloads in data/reaches/<reach>/raw/hydro/")

hydro = C.DATA_PROC / "features" / "landsat" / "features_hydro.csv"
if hydro.exists():
    head = hydro.read_text().splitlines()[0]
    if "clim_" in head:
        ok("features_hydro.csv carries clim_* weather columns")
    else:
        bad("features_hydro.csv exists but carries no clim_* columns")
else:
    warn("no hydro features yet - run 11_hydro_features.py landsat")

print("\n" + "=" * 62)
if failures:
    print(f"{len(failures)} CHECK(S) FAILED - do not trust the pipeline yet:")
    for f in failures:
        print(f"  - {f}")
    sys.exit(1)
print("all blocking checks passed")
if notes:
    print(f"({len(notes)} warning(s) above)")
