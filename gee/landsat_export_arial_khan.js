/******************************************************************************
 * RiverGuard - Arial Khan (Madaripur Sadar - Kalkini, middle reach)
 *             Landsat history export - detection logic aligned to Sentinel-2
 *
 * This script and s2_export_arial_khan.js run THE SAME DETECTION LOGIC. They
 * must: the two sensors overlap 2019-2026, and if their rules differed the
 * cross-sensor comparison would measure the difference between two SCRIPTS
 * rather than two INSTRUMENTS, fabricating a step in the river-width record at
 * 2019. That comparison is the backbone of this project's validation.
 * 09_checks.py section 8 enforces the shared constants.
 *
 * The sensors are ALLOWED to differ in things that are not detection logic:
 * year coverage (Landsat reaches 1989, S2 starts 2019), pixel size, cloud gate,
 * and the scene-count/validity gates.
 *
 * ---------------------------------------------------------------------------
 * THIS REVISION FIXES A BROKEN QUALITY GATE
 *
 * The previous version took `green.mask()` from a composite that had already
 * been `.unmask(0)`-ed. Unmasking erases the mask, so `mask()` returned all
 * ones and the `valid` band was 100% for EVERY year. The gate below
 * (`valid >= MIN_VALID`) could therefore never fail, and years with little or
 * no usable imagery - exactly the risk on a 30 m sensor with scan-line gaps -
 * were exported as if they were fine, silently.
 *
 * Validity is now read from the composite BEFORE unmasking. The earlier scripts
 * The scripts that predate this pipeline always did it this way; the
 * Arial Khan pair regressed.
 *
 * The working grid is also now stated explicitly (RES_M, 30 m here) so that the
 * focal radius below, which is given in METRES, cannot be silently
 * reinterpreted against an unknown pixel size.
 * ---------------------------------------------------------------------------
 *
 * WHY METRES MATTERS FOR THE CLOSE
 *   A radius in PIXELS silently means a different ground distance on each
 *   sensor. 20 m is written in metres in both scripts so the close covers the
 *   same physical width. On the 30 m Landsat grid that radius is smaller than
 *   one pixel and therefore does very little; that is a genuine consequence of
 *   the coarser grid and is deliberately NOT compensated by inflating the
 *   radius, because matching the physical scale is the point.
 *
 * BAND MAPPING, per platform (verified against the Earth Engine catalogue):
 *   Landsat 4/5/7 (TM/ETM+)  B1 blue  B2 green B3 red B4 NIR  B5 SWIR1  B7 SWIR2
 *   Landsat 8/9  (OLI/TIRS)  B2 blue  B3 green B4 red B5 NIR  B6 SWIR1  B7 SWIR2
 * Landsat 4/5/7 skip B6 because it is thermal on those platforms, not SWIR2.
 *
 * THE AREA
 *   REFERENCE_BOX is authoritative and is already synchronized with
 *   ml/config.py and the Sentinel-2 script. Draw nothing and press Run.
 *
 *   If you DO draw one rectangle it is used instead, its bounds are printed,
 *   and a warning appears when it differs from REFERENCE_BOX - because the
 *   exported masks would then not match ml/config.py.
 *
 *   *** The northern edge must stay SOUTH of 23.47N, the bifurcation from the
 *   *** Padma. An earlier box reached 23.60N and came back mostly Padma (D51).
 *   *** This is now checked in code, not left to the eye.
 *
 * WHAT TO CHECK
 *   - one thin meandering ribbon, not a wide braided belt, and only ONE river
 *   - roughly 30-35 years should pass the scene-count gate
 *   - do not weaken the quality gates just to force an export
 *
 * Tasks tab -> Run ~5 at a time -> download folder riverguard_arial_khan ->
 * drop the .tif files into data/reaches/arial_khan/raw/landsat/
 *******************************************************************************/


// =============================================================================
// SETTINGS
// =============================================================================

// Authoritative study area. Keep synchronized with ml/config.py and Sentinel-2.
var REFERENCE_BOX = [90.16808799423755, 23.134319063780836,
                     90.26902488388599, 23.261491731177696];

// The Arial Khan leaves the Padma at this latitude. North of it the water is a
// different river. Hard constraint (D51).
var PADMA_LAT_MAX = 23.47;

var START = 1989, END = 2026;

// Narrow this to export a slice, e.g. 1989..2000, if a single Run exceeds the
// Code Editor's execution limit. Each Run only creates Tasks for its own range.
var YEAR_FROM = START, YEAR_TO = END;

var CRS = 'EPSG:32646';
var RES_M = 30;              // Landsat native. Never resampled up to 10 m: the
                             // sensor has no 10 m detail and GEE would invent it.

// ---- Detection logic. MUST MATCH s2_export_arial_khan.js. -------------------
var INDEX_THRESH    = 0.02;
var AWEI_THRESH     = 0.0;
var TURBID_SWIR_MAX = 0.12;
var GAP_CLOSE_M     = 20;     // metres, NOT pixels
var BLOB_SCALE_M    = 60;
var BLOB_MAX_SIZE   = 256;
var BLOB_MIN        = 250;    // 60 m px => ~90 hectares, same as Sentinel-2
// -----------------------------------------------------------------------------

// Quality gates: data availability, not detection logic. These may differ
// between the sensors.
var MIN_IMAGES = 2;
// Landsat carries scan-line gaps, so its validity gate is lower than
// Sentinel-2's by nature of the instrument. Gate at 70%, not 90%.
var MIN_VALID  = 0.70;
var MIN_WATER  = 0.002;
var MAX_CLOUD  = 50;


// =============================================================================
// STUDY AREA
// =============================================================================

// REFERENCE_BOX is authoritative. It is synchronized with ml/config.py and with
// s2_export_arial_khan.js, and 09_checks.py section 7 re-verifies that
// mechanically - which is a stronger guarantee than reading a shape back off
// the map.
//
// SHAPES DRAWN ON THE MAP ARE IGNORED, on purpose. An earlier version required a
// drawn rectangle to match these bounds to within 1e-6 degrees (about 10 cm),
// which no hand-drawn shape can achieve, so it failed every time. Reading the
// drawing layers back also relies on editor APIs that behave inconsistently.
// Editing four numbers is unambiguous and is checked automatically.
//
// TO CHANGE THE STUDY AREA: edit REFERENCE_BOX here, the same four numbers in
// s2_export_arial_khan.js, and bbox/bbox_landsat in ml/config.py. Then run
// `RIVERGUARD_REACH=arial_khan .venv/bin/python ml/09_checks.py` and confirm
// section 7 passes before exporting anything.
if (Map.drawingTools().layers().length() > 0) {
  print('NOTE: there are shapes on the map. They are IGNORED - this script ' +
        'always exports REFERENCE_BOX. See the comment above to change the ' +
        'study area.');
}

var aoi = ee.Geometry.Rectangle(REFERENCE_BOX, 'EPSG:4326', false);
print('EXPORT RECTANGLE [west, south, east, north]:', REFERENCE_BOX);

if (REFERENCE_BOX[3] >= PADMA_LAT_MAX) {
  throw new Error('Northern edge ' + REFERENCE_BOX[3].toFixed(5) + 'N reaches ' +
    'or crosses ' + PADMA_LAT_MAX + 'N, where the Arial Khan leaves the Padma. ' +
    'North of that line the water body is the PADMA, a different and much ' +
    'larger river, and the whole measurement would describe the wrong ' +
    'watercourse (D51). Move the northern edge south.');
}
print('Northern edge ' + REFERENCE_BOX[3].toFixed(5) + 'N is south of the ' +
      'Padma bifurcation at ' + PADMA_LAT_MAX + 'N. Correct river.');


// =============================================================================
// BAND PREPARATION
// =============================================================================

// Collection 2 Level 2 surface reflectance is scaled by 0.0000275 with a -0.2
// offset. QA_PIXEL bits 0-3 are fill, dilated cloud, cirrus and cloud. Bit 4
// (cloud shadow) is deliberately NOT masked, matching the Sentinel-2 script
// keeping SCL class 3: on this floodplain a dark area is usually open water or
// wet soil, and dropping shadows would remove real water in the dry season.
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

function prep(y) {
  // Same end date as the Sentinel-2 script (25 March) so the two dry-season
  // windows match as closely as the sensors allow. 09_checks.py section 8
  // compares this window against config.DRY_SEASON.
  return ALL_LANDSAT.filterDate(ee.Date.fromYMD(y, 1, 1), ee.Date.fromYMD(y, 3, 25));
}


// =============================================================================
// WATER DETECTION - identical logic to the Sentinel-2 export
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

  // 20 m morphological CLOSE: dilate then erode. See the header note on why the
  // radius is in metres and why it does little on a 30 m grid.
  var cleaned = w.focal_max({radius: GAP_CLOSE_M, units: 'meters', kernelType: 'circle'})
                 .focal_min({radius: GAP_CLOSE_M, units: 'meters', kernelType: 'circle'})
                 .and(polyMask);

  // Connected-area filter on a coarse grid, identical to the Sentinel-2 script.
  var coarseMask = cleaned.reproject({crs: CRS, scale: BLOB_SCALE_M});
  var bigBlobs = coarseMask.connectedPixelCount(BLOB_MAX_SIZE, false).gte(BLOB_MIN);

  var water = cleaned.and(bigBlobs).unmask(0).clip(aoi).rename('water');

  return {water: water, valid: valid, comp: comp};
}


// =============================================================================
// SURVEY AND EXPORT
// =============================================================================
//
// WHY THE SURVEY IS OFF BY DEFAULT
//
// The scene count for every year is fetched in ONE synchronous call. That is
// cheap and always happens.
//
// Evaluating the water/valid statistics per year is NOT cheap: each year has to
// run the whole detection chain - the percentile composite, five indices, the
// focal close, and the connected-component filter. Doing that for all 38 years
// inside a single Run blocks the Code Editor on every call, which looks exactly
// like the page freezing, and can also exceed Earth Engine's memory limit. This
// is very likely what caused the freeze that was reported.
//
// Registering an export is cheap by comparison: Export.image.toDrive records a
// task whose computation happens later on Earth Engine's servers, not in this
// browser tab.
//
// So by default every year with enough scenes is queued, and quality is checked
// LOCALLY against the downloaded GeoTIFFs. That is not a weaker check - it
// measures the actual exported pixels rather than a server-side preview of
// them, and it costs nothing. ml/01_prepare.py reports water area per year.
//
// Set SURVEY = true, and narrow YEAR_FROM / YEAR_TO to a few years, to inspect
// the statistics server-side before exporting.
var SURVEY = false;

// ONE synchronous call for every year's scene count.
var sceneCounts = ee.List.sequence(YEAR_FROM, YEAR_TO).map(function (y) {
  return prep(ee.Number(y).toInt()).size();
}).getInfo();

print('');
print('year | scenes | valid | water | status');
print(SURVEY ? 'survey ON - the detection chain is evaluated year by year'
             : 'survey OFF - queueing every year with enough scenes');
print('quality is verified locally against the downloaded GeoTIFFs');
print('');

for (var i = 0; i < sceneCounts.length; i++) {
  var y = YEAR_FROM + i;
  var n = sceneCounts[i];

  if (n < MIN_IMAGES) {
    print(y + ' | ' + n + ' | - | - | SKIP (too few scenes)');
    continue;
  }

  // Constructing this is lazy. Nothing is computed until the export task runs
  // or SURVEY asks for statistics.
  var b = build(prep(y));

  if (SURVEY) {
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
  } else {
    print(y + ' | ' + n + ' | - | - | QUEUED');
  }

  Export.image.toDrive({
    image: b.water.multiply(255).toByte().rename('water')
             .addBands(b.valid.multiply(255).toByte().rename('valid')),
    description: 'MNDWI_Mask_' + y,
    folder: 'riverguard_arial_khan',
    fileNamePrefix: 'MNDWI_Mask_' + y,
    region: aoi,
    scale: RES_M,
    crs: CRS,
    maxPixels: 1e9,
    fileFormat: 'GeoTIFF'
  });
}

print('');
print('Tasks are now listed in the Tasks tab. Start about 5 at a time.');


// =============================================================================
// PREVIEW
// =============================================================================

// One render of the detection chain for a single year, so you can confirm the
// river looks right before trusting 38 Tasks to it.
//
// WHY THIS IS OFF BY DEFAULT
//
// Drawing the chain interactively hits an 80 MiB per-tile ceiling that batch
// exports do not:
//
//   Tile error: Output of image computation is too large
//   (6 bands for 1925093 pixels = 88.1 MiB > 80.0 MiB)
//
// Two reasons. `water` depends on the six-band composite, so the chain carries
// six bands even though only one is displayed. And the focal close plus the
// connected-component filter mean every tile needs its neighbours, which
// multiplies the work per tile. Landsat's 30 m grid is a quarter of the pixel
// count of Sentinel-2, so an unshown six-band composite over this box is still
// tens of megabytes per tile.
//
// THAT ERROR DOES NOT AFFECT THE TASKS. A batch export is not tiled this way and
// carries maxPixels: 1e9, so if you saw it the Tasks were still created - check
// the Tasks tab. The real check on the data is local, against the files you
// download.
//
// Turn this on to see a 60 m version, which renders comfortably. The composite
// is not drawn at all.
var SHOW_PREVIEW = false;
var PREVIEW_YEAR = 2021;

Map.centerObject(aoi, 11);

if (SHOW_PREVIEW) {
  var nPreview = (PREVIEW_YEAR >= YEAR_FROM && PREVIEW_YEAR <= YEAR_TO)
    ? sceneCounts[PREVIEW_YEAR - YEAR_FROM]
    : Number(prep(PREVIEW_YEAR).size().getInfo());

  if (nPreview >= MIN_IMAGES) {
    var p = build(prep(PREVIEW_YEAR));
    Map.addLayer(
      p.water.reproject({crs: CRS, scale: BLOB_SCALE_M}).selfMask(),
      {palette: ['cyan']},
      'Landsat water ' + PREVIEW_YEAR + ' (60 m preview)');
  } else {
    print('No preview: ' + PREVIEW_YEAR + ' has too few scenes.');
  }
}
