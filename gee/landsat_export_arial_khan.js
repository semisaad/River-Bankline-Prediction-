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
 *   1. CONNECTED-AREA FILTER. Both sensors use a 60 m working grid,
 *      connectedPixelCount(256), and a 250-pixel cutoff (~90 hectares). This
 *      preserves the physical minimum area while reducing memory on the expanded
 *      study area.
 *
 *   2. MORPHOLOGICAL CLOSE. The draft used `focal_max(1, 'circle', 'pixels')`,
 *      i.e. one PIXEL, which at 30 m is 30 m. Sentinel-2 uses a 20 m radius.
 *      A radius in pixels silently means something different on each sensor, so
 *      it is written in METRES here to match. Note this close is smaller than
 *      one Landsat pixel and therefore does very little; that is a genuine
 *      consequence of the coarser grid and is deliberately NOT compensated by
 *      inflating the radius, because matching the physical scale is the point.
 *
 *   3. ONE DRAWN RECTANGLE REQUIRED. The selected rectangle is printed to the
 *      console. It must match Sentinel-2 exactly and be copied into ml/config.py
 *      before local processing. The previous extent below is reference only.
 *
 * BAND MAPPING, per platform (verified against the Earth Engine catalogue):
 *   Landsat 4/5/7 (TM/ETM+)  B1 blue  B2 green B3 red B4 NIR  B5 SWIR1  B7 SWIR2
 *   Landsat 8/9  (OLI/TIRS)  B2 blue  B3 green B4 red B5 NIR  B6 SWIR1  B7 SWIR2
 * Landsat 4/5/7 skip B6 because it is thermal on those platforms, not SWIR2.
 *
 * HOW TO RUN
 *   Draw the same single rectangle used for Sentinel-2, then press Run. The
 *   script refuses to export if no rectangle is present.
 *   Tasks tab -> Run ~5 at a time -> download folder riverguard_arial_khan ->
 *   drop the .tif files into data/reaches/arial_khan/raw/landsat/
 *
 * WHAT TO CHECK
 *   - one thin meandering ribbon, not a wide braided belt, and only ONE river
 *   - NORTHERN EDGE MUST STAY SOUTH OF 23.47N (the Padma bifurcation). An early
 *     box reached 23.60N and came back mostly Padma (D51).
 *   - water percentage depends on the selected rectangle; inspect the preview
 *     and do not weaken the quality gates just to force an export
 *   - roughly 30-35 years should pass the scene-count gate
 *******************************************************************************/


// =============================================================================
// SETTINGS
// =============================================================================

// Selected expanded extent. Keep synchronized with ml/config.py and Sentinel-2.
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
print('Rectangle matches Sentinel-2, REFERENCE_BOX, and ml/config.py BBOX_WGS84.');
print('Configured rectangle:', REFERENCE_BOX);

var START = 1989, END = 2026;
var CRS = 'EPSG:32646';

// ---- MUST MATCH s2_export_arial_khan.js. 09_checks.py section 8 enforces this. ----
var INDEX_THRESH    = 0.02;
var AWEI_THRESH     = 0.0;
var TURBID_SWIR_MAX = 0.12;
var GAP_CLOSE_M     = 20;     // metres, NOT pixels
var BLOB_SCALE_M    = 60;
var BLOB_MAX_SIZE   = 256;
var BLOB_MIN        = 250;    // 60 m px => ~90 hectares, same as S2

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
  var col = pool(y);
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

  var w = mndwi.or(ndwi).or(rswi).or(aweiSh).or(isTurbid);

  // radius in METRES so it means the same ground distance on both sensors
  var cleaned = w.focal_max({radius: GAP_CLOSE_M, units: 'meters', kernelType: 'circle'})
                 .focal_min({radius: GAP_CLOSE_M, units: 'meters', kernelType: 'circle'});

  var coarseMask = cleaned.reproject({crs: CRS, scale: BLOB_SCALE_M});
  var bigBlobs = coarseMask.connectedPixelCount(BLOB_MAX_SIZE, false).gte(BLOB_MIN);

  var water = cleaned.and(bigBlobs).unmask(0).clip(aoi).rename('water');
  var valid = green.mask().unmask(0).clip(aoi).rename('valid');

  return {water: water, valid: valid, comp: comp};
}


// =============================================================================
// SURVEY AND EXPORT
// =============================================================================

print('year | scenes | valid | water | status');
print('one synchronous getInfo() per year - each completes before any export');
print('expect ~70% valid (Landsat scan-line gap), 5-10% water, ONE ribbon, no Padma');

for (var y = START; y <= END; y++) {
  var b = build(y);
  var n = Number(pool(y).size().getInfo());
  var st = b.water.rename('water').addBands(b.valid.rename('valid'))
             .reduceRegion({
               reducer: ee.Reducer.mean(), geometry: aoi, scale: 60,
               maxPixels: 1e9, bestEffort: true, tileScale: 4
             }).getInfo();
  var valid = st.valid === undefined ? 0 : st.valid;
  var water = st.water === undefined ? 0 : st.water;

  if (n < MIN_IMAGES) {
    print(y + ' | ' + n + ' | - | - | SKIP (too few scenes)');
    continue;
  }
  var ok = valid >= MIN_VALID && water >= MIN_WATER;
  print(y + ' | ' + n + ' | ' + Math.round(valid * 100) + '% | ' +
        (water * 100).toFixed(2) + '% | ' + (ok ? 'EXPORT' : 'SKIP (check data)'));
  if (!ok) continue;
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
}

Map.centerObject(aoi, 12);
var p2021 = build(2021);
Map.addLayer(p2021.comp, {bands: ['swir1', 'nir', 'green'], min: 0.02, max: 0.35}, 'Landsat Composite 2021', false);
Map.addLayer(p2021.water.selfMask(), {palette: ['cyan']}, 'Landsat Water 2021 (Main River Only)');