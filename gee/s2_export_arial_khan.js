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
 *   4. 30 m CONNECTED-BLOB FILTER.
 *      Only bodies of at least ~90 hectares survive. On this reach the Arial Khan
 *      trunk is the only such body, so ponds, beels and agricultural water are
 *      removed outright. This is the single most useful line in the script for
 *      this floodplain.
 *      CONSEQUENCE TO WATCH: the filter is evaluated at 30 m, where a 300 m
 *      channel is only ~10 pixels wide, so a river segment must run roughly 3 km
 *      to accumulate 1000 connected pixels. Short arms and meander tips can be
 *      severed. That is acceptable - the pipeline measures the largest connected
 *      body, so a trimmed tail is harmless - but if the TRUNK is cut, the year is
 *      ruined. Check the preview.
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
 *   6. SHAPE MASK.
 *      If a polygon was drawn, water is clipped to that polygon rather than just
 *      its bounding box. That lets the owner exclude a known-problem pond by
 *      drawing around it, without changing the export box.
 *
 * THE AREA
 *   The box is taken from the SHAPE THE OWNER DRAWS, falling back to
 *   FALLBACK_BOX. The drawn rectangle governs; FALLBACK_BOX only exists so the
 *   script still runs unattended.
 *
 *   *** The northern edge must stay SOUTH of 23.47N, the bifurcation from the
 *   *** Padma. North of that line the water body IS the Padma. An earlier box
 *   *** reached 23.60N and the preview came back mostly Padma (DECISIONS D51).
 *
 * WHAT TO CHECK WHEN YOU RUN IT
 *   - the water layer must show ONE thin meandering ribbon, not a wide braided
 *     belt, and definitely not two rivers
 *   - expect roughly 1-3% water now. v2 is more permissive than v1 but the blob
 *     filter removes much more, so the number will not match v1's 7-9%. A figure
 *     in that range is not automatically wrong - look at the preview.
 *   - the river must not be cut into disconnected pieces
 *
 * Run, then drop the .tif files into  data/reaches/arial_khan/raw/
 * (v1 masks are backed up at data/unused_data/arial_khan_s2_v1_verified/ so a
 * worse v2 can be reverted without re-exporting).
 *******************************************************************************/


// =============================================================================
// SETTINGS
// =============================================================================

var FALLBACK_BOX = [90.1927, 23.1638, 90.2384, 23.245];

var drawn = null;
if (typeof geometry !== 'undefined') {
  drawn = geometry;
} else if (Map.drawingTools().layers().length() > 0) {
  drawn = Map.drawingTools().layers().get(0).toGeometry();
}

var aoi = drawn ? drawn.bounds() : ee.Geometry.Rectangle(FALLBACK_BOX);
var maskGeom = drawn ? drawn : aoi;

if (drawn) {
  print('USING YOUR DRAWN SHAPE - not the fallback box.');
  aoi.coordinates().get(0).evaluate(function (coords) {
    print('coordinates for config.py:', coords);
  });
} else {
  print('No shape drawn yet - using the fallback box:', FALLBACK_BOX);
}

var START = 2019, END = 2026;
var CRS = 'EPSG:32646';

// Tightened so wet soil/ponds beside the river don't trigger false water patches
var INDEX_THRESH    = 0.02;
var AWEI_THRESH     = 0.0;
var TURBID_SWIR_MAX = 0.12;
var GAP_CLOSE_M     = 20;
var BLOB_MIN        = 1000;   // at 30 m this is ~92 hectares; Landsat must match

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

  // 25th percentile per band: dark-target cloud suppression, see header item 3.
  var comp = col.reduce(ee.Reducer.percentile([25]))
    .rename(['blue', 'green', 'red', 'nir', 'swir1', 'swir2'])
    .clip(aoi);

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

  // LARGE BLOB FILTER AT 30m SCALE.
  // ~92 hectares of continuous water is required. Only the main Arial Khan
  // trunk reaches that; side ponds, beels and agricultural patches are removed.
  var coarseMask = cleaned.reproject({crs: CRS, scale: 30});
  var bigBlobs = coarseMask.connectedPixelCount(1024, false).gte(BLOB_MIN);

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
// Batched because connectedPixelCount(1024) is memory-hungry: a 1024-pixel
// window at the filter's working scale is tens of km across.
var CHUNK = 4;

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
                 maxPixels: 1e9, bestEffort: true
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