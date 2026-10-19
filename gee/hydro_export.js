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
 *   UPDATE - THIS REASONING WAS TESTED AND IT DID NOT HOLD (D90).
 *   This export was downloaded, joined and scored against the identical
 *   backtest. It made the model WORSE: MAE 15.886 -> 16.562. The argument above
 *   is sound as physics, but one ~11 km cell averaged over a year is
 *   approximately a single number per year for the whole reach, and against a
 *   30 m target where 63% of values are exactly 0 that carries no usable
 *   signal. The data is still worth having for the write-up. It is NOT part of
 *   the default model. Do not re-export expecting it to help - see D90.
 *
 * WHAT THIS EXPORTS
 *   Daily ERA5-Land, averaged over each full calendar year, on a box covering
 *   the reach's study box with a margin.
 *
 *   SCALE, STATED HONESTLY: 11_hydro_features.py clips these rasters to the
 *   study box, so what reaches the feature table is the weather over the reach
 *   itself. ERA5-Land is 0.1 degree (about 11 km) and the study box is roughly
 *   10 x 14 km, so this is close to a single model cell. Calling it
 *   "catchment-scale" would oversell it. It is a WEATHER PROXY over the reach,
 *   NOT a measurement of the river, and it must be described that way.
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
 * NOTE ON ERA5-LAND HISTORY
 *   The dataset goes back to 1950, which comfortably covers our Landsat record
 *   from 1989. We export 1983-2025: 1983 so the oldest pair's change column has
 *   a base year, and stopping at 2025 because the current year is part-complete.
 *
 * HOW TO RUN
 *   1. https://code.earthengine.google.com
 *   2. Paste the whole file, press Run. Draw NOTHING and do not press the
 *      preview button - this script needs no drawn geometry.
 *   3. Open the Tasks tab, right-click each task -> Run. About 5 at a time;
 *      Earth Engine limits how many export tasks run at once.
 *   4. When a file finishes, download it. Keep the name as it is.
 *
 * NOTE ON EXPORT SIZE
 *   One small GeoTIFF per year, 43 files. Once one has landed you can start
 *   the rest of the pipeline immediately: the scripts use whatever years are
 *   present and say which ones they found.
 *******************************************************************************/

// =============================================================================
// SETTINGS
// =============================================================================

// The reach's own study box, with a margin.
//
// This was the JAMUNA box - [88.5, 23.5, 91.0, 25.5], latitude 23.5 to 25.5 -
// while the Arial Khan study box sits at latitude 23.134 to 23.261. The two do
// not overlap AT ALL, so the export would have covered a different river's
// catchment and 11_hydro_features.py, which clips to the study box, would have
// found no pixels inside it and written a table of NaNs with no error raised
// anywhere. Same class as D86.
//
// Kept south of 23.47N like the imagery boxes, so nothing here can silently
// reach up into the Padma.
var REGION = ee.Geometry.Rectangle([89.95, 22.90, 90.50, 23.45]);

// 1983, not 1985. The feature table's earliest pair is (1989, 1994), and the
// change column is measured from y0 - step = 1984, so starting at 1985 left the
// oldest rows' change value permanently missing. One extra year is cheaper than
// a hole in the record.
var START_YEAR = 1983;

// 2025, not 2026. ERA5-Land is near-real-time, so the current year is only
// part-complete and its MEAN is biased high - the missing months are the
// post-monsoon low-flow ones. No pair uses 2026 as its y0 anyway (the latest is
// 2023), so the file would have been built, shipped and never used.
var END_YEAR = 2025;

// FULL CALENDAR YEAR - deliberately not the dry season.
//
// This used to average 1 Jan to 28 Feb, which is the LOWEST-flow part of the
// year. That describes drought, not the forcing that moves a bank: banks erode
// when the river is high, in the monsoon. A dry-season number is a proxy for
// the wrong season, and no amount of modelling skill recovers the monsoon
// signal from it. Averaging the whole year keeps the monsoon in.
var START_MONTH_DAY = '-01-01';

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
  // filterDate's end is EXCLUSIVE, so the next year's 1 January is what
  // actually includes 31 December. Ending on '2020-12-31' would silently drop
  // the last day of every single year.
  var end = (year + 1) + START_MONTH_DAY;

  var col = ee.ImageCollection('ECMWF/ERA5_LAND/DAILY_AGGR')
    .filterDate(start, end);

  // Mean across the year. Flow bands are daily sums; averaging the sums gives
  // the mean daily flow, which is the quantity we want to relate to erosion.
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
print('Files land in Google Drive under riverguard_hydro/ as Hydro_<year>.tif.');
print('Then download them all into:');
print('  data/reaches/arial_khan/raw/hydro/');
print('Filenames must stay Hydro_<year>.tif - 11_hydro_features.py finds the');
print('years by reading the name.');
print('');
print('WHY NOT GloFAS (tried 2026-10-19, and it does not work here):');
print('  GloFAS IS the real river discharge in m3/s, but it is not in Earth');
print('  Engine. It was downloaded from Copernicus instead. At this reach the');
print('  nearest cells read a mean of 5 m3/s and a maximum of 13 m3/s for a');
print('  whole year, with the right seasonal shape but a magnitude orders of');
print('  magnitude too small: a 5 km cell cannot see a 300 m distributary, so');
print('  it measures a small local catchment, NOT the Arial Khan. A perfect');
print('  38-year download would still have been the wrong river.');
