# TODO

## BLOCKED ON SAAD
- [ ] **Landsat 1984-2026 export** (GEE) -> `data/raw/landsat/`
      Then: run `01b_prepare_landsat.py`, extend 04/05 to all years,
      regenerate features, re-run `07_validate.py`
- [x] **Colab training** - done 2026-10-18, and not on Colab: the model test
      ran locally (`ml/14_model_test.py`, D47) because 1.9k rows is a
      laptop-sized job. Result: no model usefully beats the baseline, so the
      forecast branch stays closed. Colab notebook kept for optional
      reproduction only.

## READY TO GO THE MOMENT DATA ARRIVES
- [ ] Landsat pipeline for 30 m: extend `04_erosion.py` with a sensor argument
      so EPR runs on both the 10 m Sentinel-2 record and the 30 m Landsat record
- [ ] Cross-sensor agreement check: do S2 and Landsat agree on which banks are
      eroding for the overlapping years? This is the strongest validation we can
      do without ground truth

## NEXT (after Landsat)
- [ ] Add **discharge** data (GloFAS reanalysis / GRDC). Discharge is the dominant
      physical driver of bank erosion and we currently have none.
      Owner action: another GEE export or a CSV from a public source.
- [ ] Add **rainfall** (CHIRPS, already used once) as a seasonal covariate
- [ ] Add **DEM slope** and **bank material** (Copernicus DEM, ESA WorldCover)
- [ ] Retrain, re-validate, and only then claim a forecast

## OPTIONAL / STRETCH
- [ ] Sentinel-1 SAR water masks (2014+) — works through cloud, good cross-check
- [ ] Uncertainty bands on the forecast (ensemble or quantile regression)
- [ ] More transects / denser sampling near hotspots
- [ ] Extend to a second reach to test generalisation

## HOUSEKEEPING
- [ ] Decide prediction horizon (1 year or 5 years)
- [ ] Decide whether to publish (repo, deployment target)
