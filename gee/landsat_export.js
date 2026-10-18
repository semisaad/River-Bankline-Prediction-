/******************************************************************************
 * RiverGuard - Landsat history export for Google Earth Engine
 *
 * PROVENANCE / READ THIS FIRST
 *   This is the script version that ACTUALLY PRODUCED THE DATA, rewritten in the
 *   project style and commented. It is not the earlier one in git history.
 *
 *   Two things had to change before it worked, and both were discovered by
 *   running it, not by reading it:
 *
 *   1. The earlier version wrapped the per-sensor composite in
 *      `ee.Algorithms.If(...)` to guard against empty collections. That guard
 *      silently produced an EMPTY composite for every single year, so all 37
 *      exported masks came back with zero water pixels. Removing the guard and
 *      pooling every scene of a year into one collection fixed it. The
 *      emptiness problem is now handled the right way: by the quality checks
 *      below (MIN_VALID / MIN_WATER), which skip bad years instead of
 *      exporting garbage.
 *
 *   2. There is no merged Collection 2 dataset. Landsat C2 is published per
 *      sensor, so each one is loaded from its own id and merged here.
 *
 *   The threshold of 0.2 was VERIFIED, not assumed: water fractions came out at
 *   9.1-17.2% across 1989-2026, and Landsat's 2023 value (10.1%) sits close to
 *   the independently measured Sentinel-2 value for the same year (11.6%).
 *
 * KNOWN DEVIATION - read before trusting cross-sensor work
 *   The area of interest below is SMALLER than the Sentinel-2 study box. It
 *   starts at 24.35N while Sentinel-2 starts at 24.30N, so a strip roughly
 *   5.5 km wide along the southern edge contains no Landsat data. That strip
 *   holds about 11.7% of the traced river.
 *
 *   Anything outside the footprint arrives as pixel value 0, and 0 means LAND
 *   in this project. Taken naively that reads as dry ground beside the river
 *   and truncates the bankline.
 *
 *   Handling: the Landsat record is analysed on its own smaller footprint
 *   (see config.py BBOX_LANDSAT) and the cross-sensor comparison is restricted
 *   to the area both sensors actually cover. See reports/DECISIONS.md D31.
 *
 * HOW TO RE-RUN
 *   1. https://code.earthengine.google.com
 *   2. Paste, press Run.
 *   3. Read the console table. It prints, per year: image count, how much of
 *      the box has imagery, what fraction is water, and EXPORT or SKIP.
 *   4. Only years marked EXPORT produce a usable task. Years marked SKIP are
 *      deliberately not exported, so a blank mask can never enter the project.
 *   5. Right-click tasks -> Run, about 5 at a time.
 *
 * OUTPUT
 *   Two bands, so that data quality travels with the data:
 *     band 1 "water"  - 255 water / 0 land
 *     band 2 "valid"  - 255 where imagery existed, 0 where it did not
 *   File name LS_MNDWI_Mask_<year>.tif, folder riverguard_landsat,
 *   30 m, EPSG:32645 (metres, matching the analysis CRS).
 *******************************************************************************/


// =============================================================================
// SETTINGS
// =============================================================================

// Smaller than the Sentinel-2 box on purpose - see "KNOWN DEVIATION" above.
var aoi = ee.Geometry.Rectangle([89.62, 24.35, 89.85, 24.65]);

var START = 1989, END = 2026;
var THRESH = 0.2;       // water cutoff, verified (see header)

// Quality gates. A year that fails any of these is NOT exported.
var MIN_IMAGES = 2;     // fewer than this and a "median" is meaningless
var MIN_VALID  = 0.9;   // under 90% of the box covered -> something is wrong
var MIN_WATER  = 0.02;  // under 2% water -> almost certainly a failed export
var MAX_CLOUD  = 50;    // per-scene cloud cover %, generous because we median

// Band names per sensor. Green and SWIR1 are both around 1.6 um / 0.53-0.60 um
// across the mission, which is what makes the index comparable to Sentinel-2.
//   Landsat 7 note: ETM+ has no coastal-aerosol band, so its GREEN is SR_B2,
//   not SR_B3 as on Landsat 8. Verified against the Earth Engine catalog.
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
      // QA_PIXEL bits 0-4 as a single test: 31 = 0b11111, and the pixel is kept
      // only when all five are zero.
      //   0 Fill   1 Dilated Cloud   2 Cirrus   3 Cloud   4 Cloud Shadow
      var ok = img.select('QA_PIXEL').bitwiseAnd(31).eq(0);

      var g = img.select(sensor.g).multiply(0.0000275).add(-0.2).rename('green');
      var s = img.select(sensor.s).multiply(0.0000275).add(-0.2).rename('swir');

      return g.addBands(s).updateMask(ok);
    });
}

// Every sensor's scenes for a year, in one pool. merge() copes with sensors
// that contribute nothing, so no emptiness test is needed.
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

  // Same index as the Sentinel-2 record: (green - swir) / (green + swir).
  var mndwi = comp.normalizedDifference(['green', 'swir']).rename('MNDWI');
  var w = mndwi.gt(THRESH);

  // Drop tiny blobs: isolated pixels are noise, not river.
  var size = w.connectedPixelCount(50, true);
  var water = w.updateMask(w.and(size.gte(17))).unmask(0);

  // Where did we actually get imagery? Travels with the mask so downstream code
  // can tell "land" apart from "we never looked".
  var valid = comp.select('green').mask();

  return {water: water, valid: valid};
}


// =============================================================================
// SURVEY THE YEARS
// =============================================================================

// Step A: how many scenes per year. Safe for years with no imagery at all,
// because size() on an empty collection is simply 0.
var counts = ee.FeatureCollection(ee.List.sequence(START, END).map(function (y) {
  y = ee.Number(y);
  var n = ee.Number(0);
  SENS.forEach(function (s) { n = n.add(prep(s, y).size()); });
  return ee.Feature(null, {year: y, n: n});
})).getInfo().features;

// Step B: measure each usable year and export only the ones that pass.
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
    description: 'LS_MNDWI_Mask_' + y,
    folder: 'riverguard_landsat',
    fileNamePrefix: 'LS_MNDWI_Mask_' + y,
    region: aoi,
    scale: 30,
    crs: 'EPSG:32645',
    maxPixels: 1e9,
    fileFormat: 'GeoTIFF'
  });
});

// A quick eyeball check in the Landsat 7 era, which is the era most likely to
// be affected by the scan-line-corrector fault.
Map.centerObject(aoi, 11);
Map.addLayer(build(2005).water.selfMask(), {palette: ['cyan']}, 'Water 2005');