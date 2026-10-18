/******************************************************************************
 * RiverGuard - hydrology / climate export for Google Earth Engine
 *
 * WHY THIS EXISTS
 *   With 35 years of imagery the model still could not predict bank erosion,
 *   because every feature we had was either a LAGGED OUTCOME (how fast the bank
 *   moved last year) or weak geometry. On a braided river erosion hotspots
 *   MIGRATE rather than persist, so lag features cannot work - we measured the
 *   correlation at -0.09 and persistence lost to simply predicting the average.
 *
 *   What is missing is the FORCING: how much water the river is being asked to
 *   carry. That is a driver, not an outcome, so there is something real for a
 *   model to learn a relationship with.
 *
 * WHAT THIS EXPORTS
 *   Daily ERA5-Land, aggregated per year, over a box AROUND the reach rather
 *   than the reach itself. The box matters: runoff over the river is part of the
 *   signal but we want the whole catchment that feeds it.
 *
 *   Bands:
 *     runoff_sum          total runoff, surface + subsurface      [m]
 *     surface_runoff_sum  water running over the surface          [m]
 *     sub_surface_runoff_sum
 *     total_precipitation_sum                                   [m]
 *     surface_solar_radiation_downwards_sum  - proxy for drought/evaporation
 *     potential_evaporation_sum
 *     u_component_of_wind_10m, v_component_of_wind_10m  - flow direction
 *
 *   ERA5-Land is 0.1 degree (~11 km), so this is a CATCHMENT-SCALE forcing, not
 *   a measurement of the Jamuna itself. That is the right scale for the physics
 *   that moves a bank, but it must be described as a proxy in the write-up.
 *
 * NOTE ON ERA5-LAND HISTORY
 *   The dataset goes back to 1950, which covers our Landsat record from 1989.
 *   Export 1985-2026 to leave a margin.
 *
 * HOW TO RUN
 *   1. https://code.earthengine.google.com
 *   2. Paste, press Run.
 *   3. Open the Tasks tab, right-click -> Run, about 5 at a time.
 *   4. Download each file when it finishes. No renaming needed.
 *
 * NOTE ON EXPORT SIZE
 *   One small GeoTIFF per year, ~42 files. Export in batches.
 *******************************************************************************/

// =============================================================================
// SETTINGS
// =============================================================================

// Larger box than the study reach: this is the catchment feeding the river.
var REGION = ee.Geometry.Rectangle([88.5, 23.5, 91.0, 25.5]);

var START_YEAR = 1985;
var END_YEAR = 2026;

// Keep the dry-season window consistent with the imagery record.
var START_MONTH_DAY = '-01-01';
var END_MONTH_DAY = '-02-28';

var BANDS = [
  'runoff_sum',
  'surface_runoff_sum',
  'sub_surface_runoff_sum',
  'total_precipitation_sum',
  'surface_solar_radiation_downwards_sum',
  'potential_evaporation_sum',
  'u_component_of_wind_10m',
  'v_component_of_wind_10m'
];


// =============================================================================
// ONE YEAR
// =============================================================================

function yearImage(year) {
  var start = year + START_MONTH_DAY;
  var end = year + END_MONTH_DAY;

  var col = ee.ImageCollection('ECMWF/ERA5_LAND/DAILY_AGGR')
    .filterDate(start, end);

  // Mean across the dry season. Flow bands are daily sums; averaging the sums
  // gives the mean daily flow, which is the quantity we want to relate to erosion.
  var img = col.select(BANDS).mean().clip(REGION);

  return img.rename(BANDS);
}


// =============================================================================
// EXPORT EVERY YEAR
// =============================================================================

print('ERA5-Land hydrology, ' + START_YEAR + '-' + END_YEAR);
print('region: ' + REGION);
print('bands: ' + BANDS.join(', '));
print('');

for (var year = START_YEAR; year <= END_YEAR; year++) {
  var name = 'Hydro_' + year;

  Export.image.toDrive({
    image: yearImage(year),
    description: name,
    folder: 'riverguard_hydro',
    fileNamePrefix: name,
    region: REGION,
    scale: 11000,          // native ERA5-Land resolution
    crs: 'EPSG:4326',
    maxPixels: 1e9,
    fileFormat: 'GeoTIFF'
  });

  print('  export task created: ' + name);
}

print('');
print('Run the tasks in batches of about 5.');
print('Then tell Saad and the pipeline will pick them up.');
print('');
print('If your write-up needs ACTUAL river discharge (m3/s) rather than a');
print('runoff proxy, that is GloFAS and it is NOT in Earth Engine - it has to');
print('come from the Copernicus Climate Data Store. Ask Saad about that.');
