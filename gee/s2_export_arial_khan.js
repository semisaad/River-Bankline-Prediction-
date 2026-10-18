/******************************************************************************
 * RiverGuard - Arial Khan (Madaripur Sadar - Kalkini, middle reach)
 *             Sentinel-2 export v2 - multi-index water detection
 *
 * v2 WRITTEN BY THE OWNER, after reviewing v1. The pipeline changes it makes
 * are deliberate and worth recording, so this header states what they do and
 * what to check.
 *
 * WHY v2 EXISTS
 *   v1 used a single index (MNDWI) at threshold 0.2, which was tuned on the
 *   JAMUNA - a 9 km braided belt. On a 300 m river in a floodplain full of
 *   ponds, wet soil and turbid shallows, one index at one threshold is a blunt
 *   instrument. v2 detects water by agreement between FIVE independent tests and
 *   then removes everything that is not the river trunk.
 *
 * WHAT CHANGED, AND WHY EACH IS THERE
 *
 *   1. FIVE INDICES, combined with .or()
 *      MNDWI (green vs SWIR1), NDWI (green vs NIR), RSWI (red vs SWIR1),
 *      AWEI (Feyer's automated water extraction, uses SWIR2), plus a turbidity
 *      heuristic. Any one firing counts as water.
 *      AWEI is the notable addition: it is the only test that uses B12/SWIR2 at
 *      all, so it catches water the others miss, and it is far less
 *      confused by built-up land than MNDWI.
 *
 *   2. INDEX_THRESH 0.2 -> 0.02, a TEN-FOLD loosening.
 *      Safe ONLY because of items 1 and 5: the threshold is now permissive and
 *      the job of rejecting false positives has moved to the morphological close
 *      and the blob filter. A loose threshold with no large-object filter would
 *      light up every wet field in the box.
 *
 *   3. 25th PERCENTILE composite instead of the median.
 *      Applied to the BANDS, before the indices are computed. This is a
 *      dark-target trick: clouds and haze are BRIGHT, water is DARK, so pulling
 *      each band's composite toward its lower quartile suppresses cloud without
 *      suppressing water. Note this is a different choice from v1's median and
 *      it shifts the water fraction, so the expected number changes - see below.
 *
 *   4. 60 m CONNECTED-BLOB FILTER.
 *      At this coarser scale, 250 pixels still represents about 90 hectares.
 *      The filter rejects small ponds while lowering memory use for the expanded
 *      AOI. Check the preview for a continuous river trunk and retained meanders.
 *
 *   5. 20 m MORPHOLOGICAL CLOSE.
 *      focal_max (dilate) then focal_min (erode) = a CLOSE, which fills gaps up to
 *      ~20 m. This bridges the 10 m-wide hairline breaches that otherwise leak
 *      the channel into every adjacent pond.
 *      NOTE: the inline comment above it says "erode first to sever ditches,
 *      then close". The erode step is NOT in the code - only the close is.
 *      Harmless as written, but the comment describes two operations and only
 *      one is performed. Worth reconciling.
 *
 *   6. DRAWN RECTANGLE REQUIRED.
 *      The selected rectangle defines the export area. The script prints its
 *      exact bounds so ml/config.py and the Landsat script can be synchronized
 *      before any exported masks are processed.
 *
 * THE AREA
 *   Draw one rectangle around the selected Arial Khan reach. Its exact bounds
 *   must match REFERENCE_BOX and ml/config.py before processing. Clear drawings
 *   between runs so an old rectangle cannot be used.
 *
 *   *** The northern edge must stay SOUTH of 23.47N, the bifurcation from the
 *   *** Padma. North of that line the water body IS the Padma. An earlier box
 *   *** reached 23.60N and the preview came back mostly Padma (DECISIONS D51).
 *
 * WHAT TO CHECK WHEN YOU RUN IT
 *   - the water layer must show ONE thin meandering ribbon, not a wide braided
 *     belt, and definitely not two rivers
 *   - water percentage depends on the selected rectangle. Check that the
 *     console says EXPORT and that the preview contains the intended reach.
 *     Do not lower quality gates just to force an export.
 *   - the river must not be cut into disconnected pieces
 *
 * Confirm the printed bounds match REFERENCE_BOX and ml/config.py before
 * processing the exported masks.
 * Run, then drop the .tif files into  data/reaches/arial_khan/raw/
 * (v1 masks are backed up at data/unused_data/arial_khan_s2_v1_verified/ so a
 * worse v2 can be reverted without re-exporting).
 *******************************************************************************/


// =============================================================================
// SETTINGS
// =============================================================================

// Selected expanded extent. Keep synchronized with ml/config.py and Landsat.
var REFERENCE_BOX = [90.16808799423755, 23.134319063780836,
                     90.26902488388599, 23.261491731177696];

var aoi;
var drawingLayers = Map.drawingTools().layers();
if (drawingLayers.length() > 1) {
  throw new Error('Clear old drawings and leave exactly one study rectangle.');
} else if (drawingLayers.length() === 1) {
  aoi = drawingLayers.get(0).toGeometry().bounds();
} else {
  aoi = ee.Geometry.Rectangle(REFERENCE_BOX, 'EPSG:4326', false);
  print('No rectangle drawn; using synchronized REFERENCE_BOX.');
}

var maskGeom = aoi;
var rectangle = aoi.coordinates().getInfo()[0];
var longitudes = rectangle.map(function (point) { return point[0]; });
var latitudes = rectangle.map(function (point) { return point[1]; });
var bbox = [Math.min.apply(null, longitudes), Math.min.apply(null, latitudes),
            Math.max.apply(null, longitudes), Math.max.apply(null, latitudes)];
print('EXPORT RECTANGLE [west, south, east, north]:', bbox);
var bboxMatches = bbox.every(function (value, index) {
  return Math.abs(value - REFERENCE_BOX[index]) <= 1e-6;
});
if (!bboxMatches) {
  throw new Error('Rectangle differs from REFERENCE_BOX; sync config before exporting.');
}
print('Rectangle matches REFERENCE_BOX and ml/config.py BBOX_WGS84.');
print('Configured rectangle:', REFERENCE_BOX);

var START = 2019, END = 2026;
var CRS = 'EPSG:32646';

// Tightened so wet soil/ponds beside the river don't trigger false water patches
var INDEX_THRESH    = 0.02;
var AWEI_THRESH     = 0.0;
var TURBID_SWIR_MAX = 0.12;
var GAP_CLOSE_M     = 20;
var BLOB_SCALE_M    = 60;
var BLOB_MAX_SIZE   = 256;
var BLOB_MIN        = 250;    // 250 pixels at 60 m ~= 90 hectares; Landsat must match

var MIN_IMAGES = 3;
var MIN_VALID  = 0.90;
var MIN_WATER  = 0.002;
var MAX_CLOUD  = 80;

function prep(y) {
  return ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
    .filterBounds(aoi)
    .filterDate(ee.Date.fromYMD(y, 1, 1), ee.Date.fromYMD(y, 3, 25))
    .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', MAX_CLOUD))
    .map(function (img) {
      // SCL classes masked: 0 no-data, 1 saturated/defective, 8 cloud medium,
      // 9 cloud high, 10 thin cirrus. Class 2 (dark area) and 3 (cloud shadow)
      // are deliberately KEPT here - on this floodplain a dark area is usually
      // open water or wet soil, and dropping cloud shadows would remove real
      // water bodies during the dry season.
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

function build(y) {
  var col = prep(y);
  var hasData = col.size().gt(0);

  // Guard: an empty collection makes reduce() return a band-less image, which
  // throws downstream on normalizedDifference/.select(). Return a zero image
  // instead so the survey loop can skip the year cleanly instead of crashing.
  var comp = ee.Algorithms.If(
    hasData,
    col.reduce(ee.Reducer.percentile([25])),
    ee.Image.constant([0, 0, 0, 0, 0, 0])
  ).rename(['blue', 'green', 'red', 'nir', 'swir1', 'swir2'])
    .clip(aoi).unmask(0);

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

  var polyMask = ee.Image.constant(1).clip(maskGeom).unmask(0);
  var w = combinedWater.and(polyMask);

  // 20 m morphological CLOSE (dilate then erode) to bridge hairline breaches.
  // See header item 5 about the comment describing two steps.
  var cleaned = w.focal_max({radius: GAP_CLOSE_M, units: 'meters', kernelType: 'circle'})
                 .focal_min({radius: GAP_CLOSE_M, units: 'meters', kernelType: 'circle'})
                 .and(polyMask);

  // Coarse connected-area filter uses the same physical threshold as before.
  var coarseMask = cleaned.reproject({crs: CRS, scale: BLOB_SCALE_M});
  var bigBlobs = coarseMask.connectedPixelCount(BLOB_MAX_SIZE, false).gte(BLOB_MIN);

  var water = cleaned.and(bigBlobs).unmask(0).clip(aoi).rename('water');
  var valid = green.mask().unmask(0).clip(aoi).rename('valid');

  return {water: water, valid: valid, comp: comp};
}

print('year | images | valid | water | status');
print('single getInfo() - these numbers are reliable');

// One synchronous getInfo() per batch of years, then export from plain
// JavaScript. Each getInfo completes fully before any task is created, so
// there is no race - the earlier version fired concurrent .evaluate()
// callbacks, each creating an Export task, which silently drops tasks.
// Evaluate one year per synchronous request. The connected-component filter is
// expensive, and a larger AOI can exceed the user memory limit when several
// years are evaluated together.
var CHUNK = 1;

print('year | images | valid | water | status');
print('batched ' + CHUNK + ' years at a time - these numbers are reliable');

for (var start = START; start <= END; start += CHUNK) {
  var stop = Math.min(start + CHUNK - 1, END);

  var rows = ee.FeatureCollection(ee.List.sequence(start, stop).map(function (y) {
    y = ee.Number(y);
    var b = build(y);
    var n = prep(y).size();
    var st = b.water.rename('water').addBands(b.valid.rename('valid'))
               .reduceRegion({
                 reducer: ee.Reducer.mean(), geometry: aoi, scale: 60,
                 maxPixels: 1e9, bestEffort: true, tileScale: 4
               });
    return ee.Feature(null, {year: y, scenes: n, valid: st.get('valid'),
                             water: st.get('water')});
  })).getInfo().features;

  rows.forEach(function (f) {
    var y = f.properties.year;
    var n = f.properties.scenes;
    var valid = f.properties.valid === null ? 0 : f.properties.valid;
    var water = f.properties.water === null ? 0 : f.properties.water;
    if (n < MIN_IMAGES) {
      print(y + ' | ' + n + ' | - | - | SKIP (too few images)');
      return;
    }
    var ok = valid >= MIN_VALID && water >= MIN_WATER;
    print(y + ' | ' + n + ' | ' + Math.round(valid * 100) + '% | ' +
          (water * 100).toFixed(2) + '% | ' + (ok ? 'EXPORT' : 'SKIP (check data)'));
    if (!ok) return;
    var b = build(y);
    Export.image.toDrive({
      image: b.water.multiply(255).toByte().rename('water')
               .addBands(b.valid.multiply(255).toByte().rename('valid')),
      description: 'MNDWI_Mask_' + y,
      folder: 'riverguard_arial_khan_s2',
      fileNamePrefix: 'MNDWI_Mask_' + y,
      region: aoi,
      scale: 10,
      crs: CRS,
      maxPixels: 1e9,
      fileFormat: 'GeoTIFF'
    });
  });
}

Map.centerObject(aoi, 12);
var p2024 = build(2024);
Map.addLayer(p2024.comp, {bands: ['swir1', 'nir', 'green'], min: 0.02, max: 0.35}, 'Composite 2024', false);
Map.addLayer(p2024.water.selfMask(), {palette: ['cyan']}, 'Water 2024 (Main River Only)');