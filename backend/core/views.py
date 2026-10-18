"""Read-only API over the processed RiverGuard outputs.

Serves the bankline / transect GeoJSON produced by the ml/ pipeline.
No database is used for M0 - files on disk are the source of truth.
"""

import json
import re
from pathlib import Path

from rest_framework.decorators import api_view
from rest_framework.response import Response

PAIR_RE = re.compile(r"^\d{4}_\d{4}$")

# repo root: backend/core/views.py -> parents[2]
ROOT = Path(__file__).resolve().parents[2]
PROCESSED = ROOT / "data" / "processed"
BANKLINES = PROCESSED / "banklines"
TRANSECTS = PROCESSED / "transects"


def _load(path: Path):
    with open(path) as f:
        return json.load(f)


def available_years():
    years = []
    for p in BANKLINES.glob("bankline_*.geojson"):
        try:
            years.append(int(p.stem.split("_")[1]))
        except (IndexError, ValueError):
            continue
    return sorted(years)


@api_view(["GET"])
def health(request):
    return Response({"status": "ok", "years": available_years()})


@api_view(["GET"])
def years(request):
    return Response({"years": available_years()})


@api_view(["GET"])
def erosion(request):
    """Erosion/Progradation Rate per transect. Optional ?pair=2022_2023."""
    pair = request.query_params.get("pair")
    if pair:
        if not PAIR_RE.fullmatch(pair):
            return Response(
                {"error": "pair must look like 2022_2023"}, status=400
            )
        path = TRANSECTS / f"epr_{pair}.geojson"
    else:
        found = sorted(TRANSECTS.glob("epr_*.geojson"))
        if not found:
            return Response({"error": "no erosion computed; run 04_erosion.py"}, status=404)
        path = found[-1]
    if not path.exists():
        return Response({"error": f"not found: {path.name}"}, status=404)
    return Response(_load(path))


def erosion_pairs():
    pairs = []
    for p in sorted(TRANSECTS.glob("epr_*.geojson")):
        stem = p.stem.replace("epr_", "")
        a, _, b = stem.partition("_")
        if a and b:
            pairs.append(f"{a}_{b}")
    return pairs


@api_view(["GET"])
def erosion_years(request):
    return Response({"pairs": erosion_pairs()})


PREDICTIONS = ROOT / "data" / "processed" / "predictions"
ARTIFACTS = ROOT / "ml" / "artifacts"
RISK_DIR = ROOT / "data" / "processed" / "risk"


@api_view(["GET"])
def risk(request):
    """Long-run erosion risk per transect and bank side.

    Produced by ml/13_risk_and_forecast.py. Optional ?min_years=N to hide
    records with a short history, ?tier=very high to filter.
    """
    path = RISK_DIR / "risk.geojson"
    if not path.exists():
        return Response(
            {"error": "no risk data yet",
             "detail": "run ml/13_risk_and_forecast.py"},
            status=404,
        )
    fc = _load(path)

    min_years = request.query_params.get("min_years")
    tier = request.query_params.get("tier")
    if min_years or tier:
        try:
            floor = int(min_years) if min_years else 0
        except ValueError:
            return Response({"error": "min_years must be an integer"}, status=400)
        kept = []
        for f in fc.get("features", []):
            p = f.get("properties", {})
            if p.get("n_years", 0) < floor:
                continue
            if tier and p.get("tier") != tier:
                continue
            kept.append(f)
        fc["features"] = kept
    return Response(fc)


@api_view(["GET"])
def risk_summary(request):
    """Compact tier counts so the UI can show a legend without the geometry."""
    csv_path = RISK_DIR / "transect_risk.csv"
    if not csv_path.exists():
        return Response({"error": "no risk data yet"}, status=404)
    import csv as _csv
    from collections import Counter

    with open(csv_path) as f:
        rows = list(_csv.DictReader(f))
    eligible = [r for r in rows if r.get("sufficient") == "True"]
    tiers = Counter(r["tier"] for r in eligible)
    sig = sum(1 for r in eligible if r.get("significant") == "True")
    return Response({
        "records_total": len(rows),
        "records_eligible": len(eligible),
        "records_insufficient": len(rows) - len(eligible),
        "records_significant": sig,
        "tiers": dict(tiers),
        "note": ("Long-run rates measured over the Landsat record. Not a "
                 "forecast; see reports/RISK.md."),
    })


def _missing_predictions_response():
    return Response(
        {
            "error": "no long-run trend available",
            "detail": "run ml/13_risk_and_forecast.py then ml/06_predict_geojson.py",
        },
        status=404,
    )


@api_view(["GET"])
def predictions(request):
    """Long-run trend geometry, produced by ml/06_predict_geojson.py.

    NOTE: this is a long-run trend carrying error bars, NOT a machine-learning
    forecast. Year-to-year erosion was tested and found unpredictable; see
    reports/RISK.md and DECISIONS.md D44.
    """
    if not (PREDICTIONS / "predictions.csv").exists():
        return _missing_predictions_response()

    files = sorted(PREDICTIONS.glob("longrun_trend_*.geojson"))
    if not files:
        return _missing_predictions_response()

    horizon = request.query_params.get("horizon")
    if horizon:
        try:
            want = int(horizon)
        except ValueError:
            return Response({"error": "horizon must be an integer"}, status=400)
        match = [f for f in files if f.stem == f"longrun_trend_{want}yr"]
        if not match:
            return Response({"error": f"no trend for {want} years"}, status=404)
        path = match[0]
    else:
        path = files[-1]

    return Response(_load(path))


@api_view(["GET"])
def status(request):
    """One call that tells the frontend what is available."""
    model_file = ARTIFACTS / "xgboost_model.json"
    pred_file = PREDICTIONS / "predictions.csv"
    # Count Landsat years directly from the folder. We deliberately do NOT
    # import ml/config.py here: Django's own settings package is also called
    # "config", so importing it here would import the wrong module.
    landsat_dir = ROOT / "data" / "raw" / "landsat"
    landsat_years = sorted(
        p.stem.split("_")[-1] for p in landsat_dir.glob("MNDWI_Mask_*.tif")
    ) if landsat_dir.exists() else []

    return Response({
        "years": available_years(),
        "erosion_pairs": erosion_pairs(),
        "landsat_years": landsat_years,
        "features_ready": (
            ROOT / "data" / "processed" / "features" / "landsat" / "features.csv"
        ).exists(),
        "hydro_ready": (ROOT / "data" / "raw" / "hydro" / "glofas_annual.csv").exists(),
        "risk_ready": (RISK_DIR / "risk.geojson").exists(),
        "trend_ready": bool(sorted(PREDICTIONS.glob("longrun_trend_*.geojson"))),
        # kept for the UI's benefit-of-doubt panel
        "model_trained": model_file.exists(),
        "predictions_ready": pred_file.exists(),
    })


@api_view(["GET"])
def banklines(request):
    """Bankline for a given year, or all years if none specified."""
    year = request.query_params.get("year")
    if year is not None:
        try:
            year = int(year)
        except ValueError:
            return Response({"error": "year must be an integer"}, status=400)
        path = BANKLINES / f"bankline_{year}.geojson"
        if not path.exists():
            return Response({"error": f"no bankline for {year}"}, status=404)
        return Response(_load(path))

    feats = []
    for y in available_years():
        fc = _load(BANKLINES / f"bankline_{y}.geojson")
        feats.extend(fc.get("features", []))
    return Response({"type": "FeatureCollection", "features": feats})


@api_view(["GET"])
def transects(request):
    """Transect migration table. Optional ?pair=2022_2023."""
    pair = request.query_params.get("pair")
    if pair:
        if not PAIR_RE.fullmatch(pair):
            return Response(
                {"error": "pair must look like 2022_2023"}, status=400
            )
        path = TRANSECTS / f"transects_{pair}.geojson"
    else:
        found = sorted(TRANSECTS.glob("transects_*.geojson"))
        if not found:
            return Response({"error": "no transects computed"}, status=404)
        path = found[-1]
    if not path.exists():
        return Response({"error": f"not found: {path.name}"}, status=404)
    return Response(_load(path))
