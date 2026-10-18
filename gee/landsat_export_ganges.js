/******************************************************************************
 * RiverGuard - Ganges trial reach, Landsat history export for Earth Engine
 *
 * PROVENANCE
 *   Derived from gee/landsat_export.js (the Jamuna script that actually
 *   produced the project's data). Everything is shared except the study area,
 *   the Drive folder, and the file-name prefix. This version has NOT been run
 *   yet - the first run is the owner's, so read the console table before
 *   trusting any export (see "WHAT TO CHECK" below).
 *
 * WHY THIS REACH (DECISIONS.md D48)
 *   The Jamuna is braided, and its year-to-year bank movement was shown to be
 *   unpredictable (D44, D47) because erosion hotspots migrate instead of
 *   persisting. This reach is the single-thread meandering Ganges between
 *   Rajshahi and the Hardinge Bridge, where erosion is anchored to the outer
 *   bank of each bend and is expected to persist - the hypothesis this trial
 *   exists to test. Same sensors, same dry-season window, same pipeline.
 *
 * THE AREA
 *   Box 88.55-23.95 to 89.10-24.40 (lon-lat), about 57 x 50 km, holding
 *   roughly 75 km of river. The north-eastern corner grazes the southern
 *   fringe of Chalan Beel (seasonal wetland); in the Jan-Feb dry window that
 *   water is small and not connected to the river, and the pipeline only
 *   measures the largest connected water body, so it cannot contaminate the
 *   banklines. Both sensors use the same box here - there is no Sentinel-2
 *   export planned for the trial, so the old Jamuna footprint mismatch does
 *   not apply.
 *
 * WHAT TO CHECK when you run it
 *   The MNDWI threshold 0.2 was VERIFIED on the Jamuna, not here. The console
 *   table prints the water fraction per year: expect roughly 4-8% of the box.
 *   If a year prints something wildly different, do not run that export task;
 *   bring the table back instead.
 *
 * HOW TO RUN
 *   1. https://code.earthengine.google.com
 *   2. Paste this script, press Run.
 *   3. Read the console table. Only years marked EXPORT produce a task.
 *   4. Right-click tasks -> Run, about 5 at a time.
 *   5. Download the folder "riverguard_ganges" from Google Drive and drop the
 *      .tif files into  data/reaches/ganges/raw/landsat/  - the file names
 *      already match what the pipeline expects, no renaming needed.
 *
 * OUTPUT
 *   Two bands, so data quality travels with the data:
 *     band 1 "water"  - 255 water / 0 land
 *     band 2 "valid"  - 255 where imagery existed, 0 where it did not
 *   File name MNDWI_Mask_<year>.tif, folder riverguard_ganges,
 *   30 m, EPSG:32645 (the whole box sits inside UTM zone 45N, 84E-90E).
 *******************************************************************************/


// =============================================================================
// SETTINGS
// =============================================================================

var aoi = ee.Geometry.Rectangle([88.55, 23.95, 89.10, 24.40]);

var START = 1989, END = 2026;
var THRESH = 0.2;       // water cutoff, verified on the Jamuna - see header

// Quality gates. A year that fails any of these is NOT exported.
var MIN_IMAGES = 2;     // fewer than this and a "median" is meaningless
var MIN_VALID  = 0.9;   // under 90% of the box covered -> something is wrong
var MIN_WATER  = 0.02;  // under 2% water -> almost certainly a failed export
var MAX_CLOUD  = 50;    // per-scene cloud cover %, generous because we median

// Band names per sensor (verified against the Earth Engine catalog; see the
// Jamuna script header for the Landsat 7 note).
var SENS = [
  {col: 'LANDSAT/LT04/C02/T1_L2', g: 'SR_B2', s: 'SR_B5'},
  {col: 'LANDSAT/LT05/C02/T1_L2', g: 'SR_B2', s: 'SR_B5'},
  {col: 'LANDSAT/LE07/C02/T1_L2', g: 'SR_B2', s: 'SR_B5'},
  {col: 'LANDSAT/LC08/C02/T1_L2', g: 'SR_B3', s: 'SR_B6'},
  {col: 'LANDSAT/LC09/C02/T1_L2', g: 'SR_B3', s: 'SR_B6'}
];


// =============================================================================
// BUILD ONE SENSOR'S SCENES FOR ONE YEAR
// =============================================================================

function prep(sensor, y) {
  return ee.ImageCollection(sensor.col)
    .filterBounds(aoi)
    .filterDate(ee.Date.fromYMD(y, 1, 1), ee.Date.fromYMD(y, 3, 1))
    .filter(ee.Filter.lt('CLOUD_COVER', MAX_CLOUD))
    .map(function (img) {
      // QA_PIXEL bits 0-4 as one test: 31 = 0b11111, pixel kept when all zero.
      var ok = img.select('QA_PIXEL').bitwiseAnd(31).eq(0);

      var g = img.select(sensor.g).multiply(0.0000275).add(-0.2).rename('green');
      var s = img.select(sensor.s).multiply(0.0000275).add(-0.2).rename('swir');

      return g.addBands(s).updateMask(ok);
    });
}

function pool(y) {
  var p = prep(SENS[0], y);
  for (var i = 1; i < SENS.length; i++) {
    p = p.merge(prep(SENS[i], y));
  }
  return p;
}


// =============================================================================
// BUILD THE WATER MASK AND THE VALID-DATA MASK
// =============================================================================

function build(y) {
  var comp = pool(y).median().clip(aoi);

  var mndwi = comp.normalizedDifference(['green', 'swir']).rename('MNDWI');
  var w = mndwi.gt(THRESH);

  // Drop tiny blobs: isolated pixels are noise, not river.
  var size = w.connectedPixelCount(50, true);
  var water = w.updateMask(w.and(size.gte(17))).unmask(0);

  var valid = comp.select('green').mask();

  return {water: water, valid: valid};
}


// =============================================================================
// SURVEY THE YEARS
// =============================================================================

var counts = ee.FeatureCollection(ee.List.sequence(START, END).map(function (y) {
  y = ee.Number(y);
  var n = ee.Number(0);
  SENS.forEach(function (s) { n = n.add(prep(s, y).size()); });
  return ee.Feature(null, {year: y, n: n});
})).getInfo().features;

print('year | images | valid | water | status');

counts.forEach(function (f) {
  var y = f.properties.year, n = f.properties.n;

  if (n < MIN_IMAGES) {
    print(y + ' | ' + n + ' | - | - | SKIP (too few images)');
    return;
  }

  var b = build(y);

  var r = b.water.rename('water').addBands(b.valid.rename('valid')).reduceRegion({
    reducer: ee.Reducer.mean(), geometry: aoi, scale: 90,
    maxPixels: 1e9, bestEffort: true
  }).getInfo();

  var ok = r.valid >= MIN_VALID && r.water >= MIN_WATER;

  print(y + ' | ' + n + ' | ' + Math.round(r.valid * 100) + '% | ' +
        (r.water * 100).toFixed(1) + '% | ' + (ok ? 'EXPORT' : 'SKIP (check data)'));

  if (!ok) return;

  Export.image.toDrive({
    image: b.water.multiply(255).toByte().rename('water')
            .addBands(b.valid.multiply(255).toByte().rename('valid')),
    description: 'MNDWI_Mask_' + y,
    folder: 'riverguard_ganges',
    fileNamePrefix: 'MNDWI_Mask_' + y,
    region: aoi,
    scale: 30,
    crs: 'EPSG:32645',
    maxPixels: 1e9,
    fileFormat: 'GeoTIFF'
  });
});

// Eyeball check: the mid-record water mask, to see the meandering channel.
Map.centerObject(aoi, 11);
Map.addLayer(build(2020).water.selfMask(), {palette: ['cyan']}, 'Water 2020');
