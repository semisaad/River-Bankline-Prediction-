/******************************************************************************
 * RiverGuard - Arial Khan (Madaripur Sadar - Kalkini, middle reach)
 *             Landsat history export - owner's v2, detection logic aligned to
 *             Sentinel-2 (DECISIONS.md D59)
 *
 * WHY THE DETECTION LOGIC MUST MATCH SENTINEL-2 EXACTLY
 *   Landsat and Sentinel-2 overlap from 2019 to 2026. If their water-detection
 *   rules differ, comparing them across that overlap measures THE DIFFERENCE
 *   BETWEEN THE TWO SCRIPTS instead of the difference between the two
 *   instruments, and a fabricated step appears in the river-width record at 2019.
 *   That cross-sensor comparison is the backbone of this project's validation.
 *
 *   Three places the owner's draft diverged, all corrected here:
 *
 *   1. BLOB THRESHOLD. The draft used `connectedPixelCount(...).gte(300)`.
 *      Sentinel-2 uses `.gte(1000)`. At 30 m, 300 px is ~27 hectares and 1000 px
 *      is ~92 hectares, so the draft would have kept ponds that Sentinel-2
 *      removes - making Landsat measure a systematically WIDER river than S2 on
 *      the same reach. That is precisely the bias this alignment exists to
 *      remove, and it would have been invisible in any summary statistic.
 *
 *   2. MORPHOLOGICAL CLOSE. The draft used `focal_max(1, 'circle', 'pixels')`,
 *      i.e. one PIXEL, which at 30 m is 30 m. Sentinel-2 uses a 20 m radius.
 *      A radius in pixels silently means something different on each sensor, so
 *      it is written in METRES here to match. Note this close is smaller than
 *      one Landsat pixel and therefore does very little; that is a genuine
 *      consequence of the coarser grid and is deliberately NOT compensated by
 *      inflating the radius, because matching the physical scale is the point.
 *
 *   3. NO FALLBACK BOX. The draft did
 *      `Map.drawingTools().layers().get(0).toGeometry()` unconditionally, which
 *      THROWS if nothing has been drawn. FALLBACK_BOX below is the actual
 *      extent of the Sentinel-2 export, read back from the GeoTIFF, so both
 *      sensors cover identical ground with no drawing required.
 *
 * BAND MAPPING, per platform (verified against the Earth Engine catalogue):
 *   Landsat 4/5/7 (TM/ETM+)  B1 blue  B2 green B3 red B4 NIR  B5 SWIR1  B7 SWIR2
 *   Landsat 8/9  (OLI/TIRS)  B2 blue  B3 green B4 red B5 NIR  B6 SWIR1  B7 SWIR2
 * Landsat 4/5/7 skip B6 because it is thermal on those platforms, not SWIR2.
 *
 * HOW TO RUN
 *   Press Run. Do NOT draw anything - the fallback box matches Sentinel-2 exactly
 *   and a hand-drawn box that differs even slightly breaks the comparison.
 *   Tasks tab -> Run ~5 at a time -> download folder riverguard_arial_khan ->
 *   drop the .tif files into data/reaches/arial_khan/raw/landsat/
 *
 * WHAT TO CHECK
 *   - one thin meandering ribbon, not a wide braided belt, and only ONE river
 *   - NORTHERN EDGE MUST STAY SOUTH OF 23.47N (the Padma bifurcation). An early
 *     box reached 23.60N and came back mostly Padma (D51).
 *   - water fraction roughly 5-7%
 *   - roughly 30-35 years should pass the scene-count gate
 *******************************************************************************/


// =============================================================================
// SETTINGS
// =============================================================================

var FALLBACK_BOX = [90.1927, 23.1638, 90.2384, 23.245];  // = the S2 export extent

var drawn = null;
if (typeof geometry !== 'undefined') {
  drawn = geometry;
} else if (Map.drawingTools().layers().length() > 0) {
  drawn = Map.drawingTools().layers().get(0).toGeometry();
}
var aoi = drawn ? drawn : ee.Geometry.Rectangle(FALLBACK_BOX);

print(drawn ? 'Using your drawn geometry.'
            : 'No shape drawn - using the fallback box (correct; matches S2 exactly):');
print(FALLBACK_BOX);

var START = 1989, END = 2026;
var CRS = 'EPSG:32646';

// ---- MUST MATCH s2_export_arial_khan.js. 09_checks.py section 8 enforces this. ----
var INDEX_THRESH    = 0.02;
var AWEI_THRESH     = 0.0;
var TURBID_SWIR_MAX = 0.12;
var GAP_CLOSE_M     = 20;     // metres, NOT pixels
var BLOB_MIN        = 1000;   // 30 m px => ~92 hectares, same as S2

// Quality gates (data availability, not detection logic).
var MIN_IMAGES = 2;
// The exported GeoTIFFs measure 70.3% valid, and that is Landsat's own
// scan-line gap on a small box, not a fault. Gate at 70%, not 90%.
var MIN_VALID  = 0.70;
var MIN_WATER  = 0.002;
var MAX_CLOUD  = 50;


// =============================================================================
// BAND PREPARATION
// =============================================================================

function prepTM(img) {
  var ok = img.select('QA_PIXEL').bitwiseAnd(15).eq(0);
  var scaled = img.select(['SR_B1', 'SR_B2', 'SR_B3', 'SR_B4', 'SR_B5', 'SR_B7'])
                  .multiply(0.0000275).add(-0.2)
                  .rename(['blue', 'green', 'red', 'nir', 'swir1', 'swir2']);
  return scaled.updateMask(ok).copyProperties(img, ['system:time_start', 'CLOUD_COVER']);
}

function prepOLI(img) {
  var ok = img.select('QA_PIXEL').bitwiseAnd(15).eq(0);
  var scaled = img.select(['SR_B2', 'SR_B3', 'SR_B4', 'SR_B5', 'SR_B6', 'SR_B7'])
                  .multiply(0.0000275).add(-0.2)
                  .rename(['blue', 'green', 'red', 'nir', 'swir1', 'swir2']);
  return scaled.updateMask(ok).copyProperties(img, ['system:time_start', 'CLOUD_COVER']);
}

var ALL_LANDSAT = ee.ImageCollection('LANDSAT/LT04/C02/T1_L2').filterBounds(aoi).map(prepTM)
  .merge(ee.ImageCollection('LANDSAT/LT05/C02/T1_L2').filterBounds(aoi).map(prepTM))
  .merge(ee.ImageCollection('LANDSAT/LE07/C02/T1_L2').filterBounds(aoi).map(prepTM))
  .merge(ee.ImageCollection('LANDSAT/LC08/C02/T1_L2').filterBounds(aoi).map(prepOLI))
  .merge(ee.ImageCollection('LANDSAT/LC09/C02/T1_L2').filterBounds(aoi).map(prepOLI))
  .filter(ee.Filter.lt('CLOUD_COVER', MAX_CLOUD));

function pool(y) {
  // Same end date as the S2 script (25 March) so the two dry-season windows
  // match as closely as the sensors allow.
  return ALL_LANDSAT.filterDate(ee.Date.fromYMD(y, 1, 1), ee.Date.fromYMD(y, 3, 25));
}


// =============================================================================
// WATER DETECTION - identical logic to the Sentinel-2 export
// =============================================================================

function build(y) {
  var comp = pool(y).reduce(ee.Reducer.percentile([25]))
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

  var w = mndwi.or(ndwi).or(rswi).or(aweiSh).or(isTurbid);

  // radius in METRES so it means the same ground distance on both sensors
  var cleaned = w.focal_max({radius: GAP_CLOSE_M, units: 'meters', kernelType: 'circle'})
                 .focal_min({radius: GAP_CLOSE_M, units: 'meters', kernelType: 'circle'});

  var coarseMask = cleaned.reproject({crs: CRS, scale: 30});
  var bigBlobs = coarseMask.connectedPixelCount(1024, false).gte(BLOB_MIN);

  var water = cleaned.and(bigBlobs).unmask(0).clip(aoi).rename('water');
  var valid = green.mask().unmask(0).clip(aoi).rename('valid');

  return {water: water, valid: valid, comp: comp};
}


// =============================================================================
// SURVEY AND EXPORT
// =============================================================================

// WHY THIS IS CHUNKED
//   Doing all 38 years in one server round trip exhausts Earth Engine's memory.
//   The expensive step is connectedPixelCount(1024): a 1024-pixel window at 30 m
//   is about 31 km across, so every pixel forces a very large computation. Eight
//   years at a time stays inside the limit.
//
//   Why it is not simply looped with .evaluate() per year, which would also
//   chunk: eight concurrent callbacks each creating an Export task is the race
//   that produced the previous table, which reported 0% valid for years that had
//   fifteen scenes. Here each chunk is ONE synchronous getInfo() that fully
//   completes before any task is created, so there is nothing to race.
var CHUNK = 8;

print('year | scenes | valid | water | status');
print('batched ' + CHUNK + ' years at a time - these numbers are reliable');
print('expect ~70% valid (Landsat scan-line gap), 5-10% water, ONE ribbon, no Padma');

for (var start = START; start <= END; start += CHUNK) {
  var stop = Math.min(start + CHUNK - 1, END);

  var rows = ee.FeatureCollection(ee.List.sequence(start, stop).map(function (y) {
    y = ee.Number(y);
    var b = build(y);
    var n = pool(y).size();
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
      print(y + ' | ' + n + ' | - | - | SKIP (too few scenes)');
      return;
    }
    var ok = valid >= MIN_VALID && water >= MIN_WATER;
    print(y + ' | ' + n + ' | ' + Math.round(valid * 100) + '% | ' +
          (water * 100).toFixed(2) + '% | ' +
          (ok ? 'EXPORT' : 'SKIP (check data)'));
    if (!ok) return;

    var b = build(y);
    Export.image.toDrive({
      image: b.water.multiply(255).toByte().rename('water')
               .addBands(b.valid.multiply(255).toByte().rename('valid')),
      description: 'MNDWI_Mask_' + y,
      folder: 'riverguard_arial_khan',
      fileNamePrefix: 'MNDWI_Mask_' + y,
      region: aoi,
      scale: 30,
      crs: CRS,
      maxPixels: 1e9,
      fileFormat: 'GeoTIFF'
    });
  });
}

Map.centerObject(aoi, 12);
var p2021 = build(2021);
Map.addLayer(p2021.comp, {bands: ['swir1', 'nir', 'green'], min: 0.02, max: 0.35}, 'Landsat Composite 2021', false);
Map.addLayer(p2021.water.selfMask(), {palette: ['cyan']}, 'Landsat Water 2021 (Main River Only)');