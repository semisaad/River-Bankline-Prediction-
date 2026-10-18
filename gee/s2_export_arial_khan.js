/******************************************************************************
 * RiverGuard - Arial Khan (Madaripur Sadar - Kalkini, middle reach)
 *             Sentinel-2 export - multi-index water detection
 *
 * This script and landsat_export_arial_khan.js run THE SAME DETECTION LOGIC.
 * They must: the two sensors overlap 2019-2026, and if their rules differed the
 * cross-sensor comparison would measure the difference between two SCRIPTS
 * rather than two INSTRUMENTS, fabricating a step in the river-width record at
 * 2019. 09_checks.py section 8 enforces the shared constants.
 *
 * ---------------------------------------------------------------------------
 * THIS REVISION FIXES A BROKEN QUALITY GATE
 *
 * The previous version took `green.mask()` from a composite that had already
 * been `.unmask(0)`-ed. Unmasking erases the mask, so `mask()` returned all
 * ones and the `valid` band was 100% for EVERY year. The gate below
 * (`valid >= MIN_VALID`) could therefore never fail, and years with little or
 * no usable imagery were exported as if they were fine - silently.
 *
 * Validity is now read from the composite BEFORE unmasking. The sibling
 * scripts boards/landsat_export.js and landsat_export_ganges.js always did it
 * this way; the Arial Khan pair regressed.
 *
 * The working grid is also now stated explicitly (RES_M) so that the focal
 * radius below, which is given in METRES, cannot be silently reinterpreted
 * against an unknown pixel size.
 * ---------------------------------------------------------------------------
 *
 * WHY THE DETECTION IS SHAPED THIS WAY
 *
 *   1. FIVE INDICES combined with .or(): MNDWI (green vs SWIR1), NDWI (green vs
 *      NIR), RSWI (red vs SWIR1), AWEI (Feyer's, the only test using SWIR2) and
 *      a turbidity heuristic. Any one firing counts as water. AWEI is far less
 *      confused by built-up land than MNDWI.
 *
 *   2. INDEX_THRESH is deliberately LOW (0.02). That is safe ONLY because the
 *      morphological close and the connected-area filter then remove what a
 *      loose threshold admits. A loose threshold without a large-object filter
 *      would light up every wet field in the box.
 *
 *   3. 25th PERCENTILE composite, applied to the BANDS before the indices are
 *      computed. Clouds and haze are BRIGHT, water is DARK, so pulling each
 *      band toward its lower quartile suppresses cloud without suppressing
 *      water.
 *
 *   4. 60 m CONNECTED-AREA FILTER. At this grid scale 250 pixels is still about
 *      90 hectares, but the component computation is far smaller than at 10 m.
 *      Inspect the preview for a continuous river trunk and retained meanders.
 *
 *   5. 20 m MORPHOLOGICAL CLOSE: focal_max then focal_min. Only a CLOSE is
 *      performed. An erode-then-close was once described in a comment here but
 *      never implemented; the comment has been corrected to match the code.
 *
 * THE AREA
 *   REFERENCE_BOX is authoritative and is already synchronized with
 *   ml/config.py and the Landsat script. Draw nothing and press Run.
 *
 *   If you DO draw one rectangle, it is used instead, its bounds are printed,
 *   and a warning appears when it differs from REFERENCE_BOX - because the
 *   exported masks would then not match ml/config.py and every downstream
 *   number would describe a different place with nothing erroring.
 *
 *   *** The northern edge must stay SOUTH of 23.47N, the bifurcation from the
 *   *** Padma. North of that line the water body IS the Padma. An earlier box
 *   *** reached 23.60N and the preview came back mostly Padma (DECISIONS D51).
 *   *** This is now checked in code, not left to the eye.
 *
 * WHAT TO CHECK WHEN YOU RUN IT
 *   - the water layer must show ONE thin meandering ribbon, not a wide braided
 *     belt, and definitely not two rivers
 *   - the console must say EXPORT for the years you expect. A SKIP now means
 *     something: it previously could not have meant anything.
 *   - do not lower the gates just to force an export
 *
 * Then drop the .tif files into  data/reaches/arial_khan/raw/
 * (v1 masks are backed up at data/unused_data/arial_khan_s2_v1_verified/).
 *******************************************************************************/


// =============================================================================
// SETTINGS
// =============================================================================

// Authoritative study area. Keep synchronized with ml/config.py and Landsat.
var REFERENCE_BOX = [90.16808799423755, 23.134319063780836,
                     90.26902488388599, 23.261491731177696];

// The Arial Khan leaves the Padma at this latitude. North of it the water is a
// different river. Hard constraint (D51).
var PADMA_LAT_MAX = 23.47;

var START = 2019, END = 2026;

// Narrow this to export a slice, e.g. 2019..2022, if a single Run exceeds the
// Code Editor's execution limit. Each Run only creates Tasks for its own range.
var YEAR_FROM = START, YEAR_TO = END;

var CRS = 'EPSG:32646';
var RES_M = 10;              // Sentinel-2 native. Landsat uses 30 and is never
                             // resampled up to this value.

// ---- Detection logic. MUST MATCH landsat_export_arial_khan.js. --------------
var INDEX_THRESH    = 0.02;
var AWEI_THRESH     = 0.0;
var TURBID_SWIR_MAX = 0.12;
var GAP_CLOSE_M     = 20;     // metres, NOT pixels
var BLOB_SCALE_M    = 60;
var BLOB_MAX_SIZE   = 256;
var BLOB_MIN        = 250;    // 250 pixels at 60 m ~= 90 hectares
// -----------------------------------------------------------------------------

// Quality gates: data availability, not detection logic. These may differ
// between the sensors.
var MIN_IMAGES = 3;
var MIN_VALID  = 0.90;
var MIN_WATER  = 0.002;
var MAX_CLOUD  = 80;


// =============================================================================
// STUDY AREA
// =============================================================================

function boundsOf(geom) {
  var ring = geom.bounds().coordinates().getInfo()[0];
  var lons = ring.map(function (p) { return p[0]; });
  var lats = ring.map(function (p) { return p[1]; });
  return [Math.min.apply(null, lons), Math.min.apply(null, lats),
          Math.max.apply(null, lons), Math.max.apply(null, lats)];
}

var aoi = (function () {
  var layers = Map.drawingTools().layers();
  if (layers.length() > 1) {
    throw new Error('There are ' + layers.length() + ' shapes on the map. ' +
      'Clear them all: the study area is either REFERENCE_BOX or ONE drawn ' +
      'rectangle, never several.');
  }
  if (layers.length() === 1) {
    var drawn = layers.get(0).toGeometry().bounds();
    var b = boundsOf(drawn);
    print('DRAWN RECTANGLE [west, south, east, north]:', b);
    var same = b.every(function (v, i) {
      return Math.abs(v - REFERENCE_BOX[i]) <= 1e-4;   // ~10 m
    });
    if (!same) {
      print('');
      print('*** WARNING: the drawn rectangle does not match REFERENCE_BOX. ***');
      print('    REFERENCE_BOX:', REFERENCE_BOX);
      print('    drawn        :', b);
      print('    The exported masks WILL NOT match ml/config.py, so every ' +
            'downstream number would describe a different place with nothing ' +
            'erroring. Either clear the drawing to use REFERENCE_BOX, or ' +
            'update bbox/bbox_landsat in ml/config.py AND REFERENCE_BOX in ' +
            'both export scripts before processing.');
      print('');
    }
    return drawn;
  }
  print('No shape drawn; using the synchronized REFERENCE_BOX.');
  return ee.Geometry.Rectangle(REFERENCE_BOX, 'EPSG:4326', false);
})();

var bbox = boundsOf(aoi);
print('EXPORT RECTANGLE [west, south, east, north]:', bbox);

if (bbox[3] >= PADMA_LAT_MAX) {
  throw new Error('Northern edge ' + bbox[3].toFixed(5) + 'N reaches or ' +
    'crosses ' + PADMA_LAT_MAX + 'N, where the Arial Khan leaves the Padma. ' +
    'North of that line the water body is the PADMA, a different and much ' +
    'larger river, and the whole measurement would describe the wrong ' +
    'watercourse (D51). Move the northern edge south.');
}
print('Northern edge ' + bbox[3].toFixed(5) + 'N is south of the Padma ' +
      'bifurcation at ' + PADMA_LAT_MAX + 'N. Correct river.');


// =============================================================================
// BAND PREPARATION
// =============================================================================

function prep(y) {
  return ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
    .filterBounds(aoi)
    .filterDate(ee.Date.fromYMD(y, 1, 1), ee.Date.fromYMD(y, 3, 25))
    .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', MAX_CLOUD))
    .map(function (img) {
      // SCL classes masked: 0 no-data, 1 saturated/defective, 8 cloud medium,
      // 9 cloud high, 10 thin cirrus. Class 2 (dark area) and 3 (cloud shadow)
      // are deliberately KEPT: on this floodplain a dark area is usually open
      // water or wet soil, and dropping cloud shadows would remove real water
      // bodies during the dry season.
      var scl = img.select('SCL');
      var bad = scl.eq(0).or(scl.eq(1)).or(scl.eq(8)).or(scl.eq(9)).or(scl.eq(10));
      var ok = bad.eq(0);

      var b2  = img.select('B2').multiply(0.0001).rename('blue');
      var b3  = img.select('B3').multiply(0.0001).rename('green');
      var b4  = img.select('B4').multiply(0.0001).rename('red');
      var b8  = img.select('B8').multiply(0.0001).rename('nir');
      var b11 = img.select('B11').multiply(0.0001).rename('swir1');
      var b12 = img.select('B12').multiply(0.0001).rename('swir2');

      return b2.addBands([b3, b4, b8, b11, b12]).updateMask(ok);
    });
}


// =============================================================================
// WATER DETECTION
// =============================================================================

// Requires a NON-EMPTY collection. The caller checks the scene count first, so
// this never has to cope with an empty reduce - which is what the previous
// ee.Algorithms.If guard was for. That guard is gone because ee.Algorithms.If
// can defeat the optimiser and force both branches to be computed.
function build(col) {
  var reduced = col.reduce(ee.Reducer.percentile([25]))
      .rename(['blue', 'green', 'red', 'nir', 'swir1', 'swir2'])
      .reproject({crs: CRS, scale: RES_M});

  // VALIDITY FIRST, while the mask still exists. Reading .mask() after
  // .unmask(0) returns all ones and reports 100% valid for every year.
  var valid = reduced.select('green').mask()
      .reproject({crs: CRS, scale: RES_M}).gt(0.5)
      .rename('valid').clip(aoi);

  var comp = reduced.clip(aoi).unmask(0);

  var blue  = comp.select('blue');
  var green = comp.select('green');
  var red   = comp.select('red');
  var nir   = comp.select('nir');
  var swir1 = comp.select('swir1');
  var swir2 = comp.select('swir2');

  var mndwi = comp.normalizedDifference(['green', 'swir1']).gt(INDEX_THRESH);
  var ndwi  = comp.normalizedDifference(['green', 'nir']).gt(INDEX_THRESH);
  var rswi  = comp.normalizedDifference(['red', 'swir1']).gt(INDEX_THRESH);

  var aweiSh = blue.add(green.multiply(2.5))
    .subtract(nir.add(swir1).multiply(1.5))
    .subtract(swir2.multiply(0.25))
    .gt(AWEI_THRESH);

  var isTurbid = green.max(red).gt(nir.multiply(0.95)).and(swir1.lt(TURBID_SWIR_MAX));

  var combinedWater = mndwi.or(ndwi).or(rswi).or(aweiSh).or(isTurbid);

  var polyMask = ee.Image.constant(1).clip(aoi).unmask(0);
  var w = combinedWater.and(polyMask);

  // 20 m morphological CLOSE: dilate then erode, bridging hairline breaches
  // that would otherwise leak the channel into every adjacent pond. Only the
  // close is performed - there is no erode-open step.
  var cleaned = w.focal_max({radius: GAP_CLOSE_M, units: 'meters', kernelType: 'circle'})
                 .focal_min({radius: GAP_CLOSE_M, units: 'meters', kernelType: 'circle'})
                 .and(polyMask);

  // Connected-area filter on a coarse grid. 250 pixels at 60 m preserves the
  // ~90 hectare minimum while keeping the component computation small enough
  // for the expanded study area.
  var coarseMask = cleaned.reproject({crs: CRS, scale: BLOB_SCALE_M});
  var bigBlobs = coarseMask.connectedPixelCount(BLOB_MAX_SIZE, false).gte(BLOB_MIN);

  var water = cleaned.and(bigBlobs).unmask(0).clip(aoi).rename('water');

  return {water: water, valid: valid, comp: comp};
}


// =============================================================================
// SURVEY AND EXPORT
// =============================================================================

print('');
print('year | scenes | valid | water | status');
print('one synchronous getInfo() per year, so each completes before any export');
print('expect ~99% valid, 5-10% water, ONE ribbon, no Padma');
print('');

for (var y = YEAR_FROM; y <= YEAR_TO; y++) {
  // Count FIRST. Nothing is built for a year that cannot be exported, which
  // keeps a 38-year Landsat loop from constructing graphs it will discard.
  var col = prep(y);
  var n = Number(col.size().getInfo());

  if (n < MIN_IMAGES) {
    print(y + ' | ' + n + ' | - | - | SKIP (too few scenes)');
    continue;
  }

  var b = build(col);

  // Statistics are taken on the coarse grid the blob filter already uses, so
  // the reduction does not have to be rescaled from 10 m to 60 m on the fly.
  var st = b.water.addBands(b.valid)
             .reproject({crs: CRS, scale: BLOB_SCALE_M})
             .reduceRegion({
               reducer: ee.Reducer.mean(), geometry: aoi, scale: BLOB_SCALE_M,
               maxPixels: 1e9, bestEffort: true, tileScale: 8
             }).getInfo();

  var valid = st.valid === undefined ? 0 : st.valid;
  var water = st.water === undefined ? 0 : st.water;

  var ok = valid >= MIN_VALID && water >= MIN_WATER;
  print(y + ' | ' + n + ' | ' + Math.round(valid * 100) + '% | ' +
        (water * 100).toFixed(2) + '% | ' + (ok ? 'EXPORT' : 'SKIP (check data)'));

  if (!ok) continue;

  Export.image.toDrive({
    image: b.water.multiply(255).toByte().rename('water')
             .addBands(b.valid.multiply(255).toByte().rename('valid')),
    description: 'MNDWI_Mask_' + y,
    folder: 'riverguard_arial_khan_s2',
    fileNamePrefix: 'MNDWI_Mask_' + y,
    region: aoi,
    scale: RES_M,
    crs: CRS,
    maxPixels: 1e9,
    fileFormat: 'GeoTIFF'
  });
}


// =============================================================================
// PREVIEW
// =============================================================================

Map.centerObject(aoi, 12);

var PREVIEW_YEAR = 2024;
if (Number(prep(PREVIEW_YEAR).size().getInfo()) >= MIN_IMAGES) {
  var p = build(prep(PREVIEW_YEAR));
  Map.addLayer(p.comp, {bands: ['swir1', 'nir', 'green'], min: 0.02, max: 0.35},
               'Composite ' + PREVIEW_YEAR, false);
  Map.addLayer(p.water.selfMask(), {palette: ['cyan']},
               'Water ' + PREVIEW_YEAR + ' (main river only)');
} else {
  print('No preview: ' + PREVIEW_YEAR + ' has too few scenes.');
}
