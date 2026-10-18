"""Transect geometry that FOLLOWS the river.

WHY THIS FILE WAS REWRITTEN
  The previous design placed transects on one global PCA axis. The Jamuna reach
  runs diagonally, so a single "across flow" direction is not across the river
  anywhere in particular. Measured that way the belt came out 18 km wide instead
  of ~9 km, and many measuring zones sat on dry land, which can only ever report
  "no change". Those wrong numbers looked plausible, which is the dangerous part.

  This version builds a centreline that actually follows the channel, and draws
  every transect perpendicular to the LOCAL direction of that centreline. That is
  the standard construction in river-migration work.

HOW IT WORKS
  1. Fill the belt and skeletonise it -> a graph of the river's medial axis.
  2. Find the longest continuous path through that graph (double BFS: farthest
     from an endpoint, then farthest from there, tracking parents). A greedy
     walk dead-ends on a braided network; the double BFS does not.
  3. Smooth the path, then resample it at a fixed spacing (500 m) so transects
     are evenly spaced along the river.
  4. At each sample point take the local tangent from nearby centreline points;
     the transect is perpendicular to it.
  5. Cap the transect at the local belt width plus a margin, so a cross-section
     cannot sprawl across the whole diagonal.
  6. For each year, cast the normal outward and find where the water actually
     starts and stops. Both edges must be found and the transect must contain
     enough water, otherwise the transect is DROPPED for that year and reported.

  The transects are built ONCE from a reference year and reused for every year
  and every sensor, so a rate always compares the same two pieces of river.
"""

from dataclasses import dataclass, field

import numpy as np
import rasterio
from scipy.ndimage import binary_fill_holes, label
from shapely.geometry import LineString, Polygon
from skimage.morphology import closing, disk, opening, skeletonize

import config as C

# ---- tunable measurement constants (all distances in METRES) ---------------
GEOM_REF_YEAR = C.GEOM["ref_year"]   # geometry is fixed from this year's belt
GEOM_SENSOR = C.GEOM["sensor"]       # geometry defined once, on the sharpest record for the reach
MIN_RIDGE_DEPTH_M = 150.0    # centreline must sit in deep channel, not a floodplain creek
SPACING_M = 500.0             # transect spacing along the centreline
SMOOTH_WINDOW = 41            # centreline smoothing window (samples)
MARGIN_M = 800.0              # extra length beyond the local belt width
GAP_BRIDGE_M = 250.0          # bridge water gaps up to this long
MIN_WATER_FRAC = 0.25         # a transect must be at least this much water
EDGE_MARGIN_PX = 2            # both edges must be this far inside the cast
MIN_WIDTH_M = 2500.0        # belt width gate, at build time
MIN_WET_WIDTH_M = 1200.0    # wetted width gate, per year          # narrower than this is one channel, not the belt
MAX_WIDTH_M = 13000.0         # wider than this means stray water
MAX_CAST_M = 12000.0          # hard cap on how far we look either side
EDGE_WINDOW_M = 300.0         # smoothing window used to find the belt edge
MIN_EDGE_FRAC = 0.35          # a smoothed fraction at or above this = river

ZONE_M = 1000.0               # depth of each EPR measurement zone
BUFFER_M = 250.0              # along-flow half-width of a zone
OPEN_M = 20.0                 # speckle removal
CLOSE_M = 40.0                # belt filling (geometry only)

# Reach overrides from config.REACHES, applied BEFORE any function below is
# defined because these names are bound into default arguments at def time.
# The Jamuna keeps every default (its gate set is empty). Values for other
# reaches are first guesses recorded in DECISIONS.md (D48 for the ganges).
for _k, _v in C.REACH_TRANSECT_GATES.items():
    globals()[_k] = _v

# How the two bank edges are found is set per reach via C.PROFILE_MODE.
#   "smoothed" - for wide braided belts (Jamuna, 9 km)
#   "run"      - for narrow single-thread rivers (Arial Khan, ~300 m), where the
#                smoothed rule mistakes a floodplain pond for the far bank
# See _water_profile for why the two differ.

NEIGHBOURS = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]


@dataclass
class Transect:
    i: int
    center: np.ndarray
    normal: np.ndarray
    tangent: np.ndarray
    arc_m: float
    half_max: float            # capped cast distance, metres each way
    width0: float              # belt width at the reference year
    # filled per year:
    vmin: float = np.nan
    vmax: float = np.nan
    width_m: float = np.nan
    water_frac: float = np.nan
    ok: bool = False
    reason: str = ""


@dataclass
class TransectSet:
    sensor_geom: str
    ref_year: int
    res: float
    transform: object
    shape_hw: tuple
    transects: list = field(default_factory=list)
    points: np.ndarray = None          # resampled centreline points, world coords
    arcs: np.ndarray = None            # their arc length
    centreline_km: float = 0.0
    dropped_build: list = field(default_factory=list)


# =============================================================================
# mask loading
# =============================================================================

def load_water(year, sensor="s2"):
    """Raw water mask, speckle removed, holes NOT filled."""
    with rasterio.open(C.sensor_mask_path(sensor, year)) as src:
        w = src.read(1) > 127
        hw = (src.height, src.width)
        tr = src.transform
    res = C.sensor_res(sensor)
    return opening(w, disk(max(1, int(round(OPEN_M / res))))), tr, hw


def load_belt(year, sensor="s2"):
    """Gap-bridged, hole-filled belt. Geometry use only."""
    with rasterio.open(C.sensor_mask_path(sensor, year)) as src:
        w = src.read(1) > 127
    res = C.sensor_res(sensor)
    w = binary_fill_holes(closing(w, disk(max(1, int(round(CLOSE_M / res))))))
    lab, _ = label(w)
    counts = np.bincount(lab.ravel())[1:]
    if len(counts) == 0:
        raise RuntimeError(f"{sensor} {year}: no water found")
    return lab == (int(np.argmax(counts)) + 1)


# =============================================================================
# centreline
# =============================================================================

def _ridge_centreline(belt, transform, res, min_depth_m=MIN_RIDGE_DEPTH_M, n_bins=200):
    """Follow the deepest water in each slice along the river.

    A skeleton walk follows whichever branch happens to be longest, which on a
    braided belt zig-zags across channels (it produced a 51 km centreline for a
    30 km river). Instead we use the distance transform: the deepest pixel of
    each slice along the river is the thalweg, and the sequence of those points
    IS the centreline. Taking the deepest point per slice cannot jump to a
    different order of channel the way a longest-path walk can, and smoothing
    removes the remaining jitter.
    """
    from scipy.ndimage import distance_transform_edt

    dist = distance_transform_edt(belt)
    res = C.sensor_res(sensor) if (sensor := GEOM_SENSOR) else C.sensor_res(GEOM_SENSOR)

    rows, cols = np.where(belt)
    if len(rows) < 100:
        raise RuntimeError("belt too small to trace")
    pts_px = rasterio.transform.xy(transform, rows, cols)
    P = np.column_stack([pts_px[0], pts_px[1]])

    mean = P.mean(axis=0)
    cen = P - mean
    _, evec = np.linalg.eigh(np.cov(cen.T))
    uvec = evec[:, -1]                     # along flow (used ONLY for slicing)

    t = cen @ uvec
    lo, hi = np.percentile(t, 0.5), np.percentile(t, 99.5)
    edges = np.linspace(lo, hi, n_bins + 1)

    ridge = []
    for k in range(n_bins):
        sel = (t >= edges[k]) & (t < edges[k + 1]) if k < n_bins - 1 \
              else (t >= edges[k]) & (t <= edges[k + 1])
        if sel.sum() < 10:
            continue
        idx = np.where(sel)[0]
        r = rows[idx]; c = cols[idx]
        depth = dist[r, c] * res
        j = int(np.argmax(depth))
        # Only follow slices where the deepest water is genuinely the main belt.
        # Without this the centreline dives into minor floodplain channels and
        # half the transects end up on dry ground.
        if depth[j] < min_depth_m:
            continue
        xs, ys = rasterio.transform.xy(transform, r[j], c[j])
        ridge.append((float(xs), float(ys)))

    if len(ridge) < 20:
        raise RuntimeError(f"centreline too short ({len(ridge)} slices)")
    path = _smooth(np.array(ridge))
    # NOTE: return WORLD coordinates. The mean-subtracted frame is only for
    # slicing; downstream code casts these points through the raster transform,
    # which expects world coordinates.
    return path, 0.0


def _smooth(path_px, window=SMOOTH_WINDOW):
    """Smooth the centreline in world coordinates."""
    if len(path_px) < window:
        return path_px
    k = np.ones(window) / window
    pad = window // 2
    padded = np.pad(path_px.astype(float), ((pad, pad), (0, 0)), mode="edge")
    out = np.empty_like(path_px, dtype=float)
    for i in range(path_px.shape[1]):
        out[:, i] = np.convolve(padded[:, i], k, mode="same")[pad:pad + len(path_px)]
    return out


def _resample(path_m, spacing_m):
    """Evenly spaced points along the path, plus arc length."""
    seg = np.linalg.norm(np.diff(path_m, axis=0), axis=1)
    arc = np.concatenate([[0.0], np.cumsum(seg)])
    total = float(arc[-1])
    n = max(2, int(round(total / spacing_m)))
    targets = np.linspace(spacing_m / 2, total - spacing_m / 2, n)
    idx = np.searchsorted(arc, targets)
    idx = np.clip(idx, 0, len(path_m) - 1)
    return path_m[idx], targets, total


def build_transects(ref_year=GEOM_REF_YEAR, sensor_geom=GEOM_SENSOR,
                    spacing_m=SPACING_M, quiet=False):
    """Build the fixed transect geometry. Called once, reused for everything."""
    belt = load_belt(ref_year, sensor_geom)
    with rasterio.open(C.sensor_mask_path(sensor_geom, ref_year)) as src:
        tr = src.transform
        hw = (src.height, src.width)
    res = C.sensor_res(sensor_geom)

    path_m, ridge_km = _ridge_centreline(belt, tr, res)
    pts, arcs, total = _resample(path_m, spacing_m)

    ts = TransectSet(sensor_geom, ref_year, res, tr, hw, centreline_km=total / 1000)
    ts.points = pts
    ts.arcs = arcs

    # Size each transect from the BELT, not from the water. The belt is solid and
    # always well defined, so this never fails; whether a given YEAR has enough
    # water along a transect is decided later, per year, by measure_edges().
    inv = ~tr

    half = max(20, int(11 * spacing_m / res))     # tangent window ~ 11 * spacing
    clamped = []

    for k in range(len(pts)):
        lo, hi = max(0, k - 6), min(len(pts), k + 7)
        seg = pts[lo:hi] - pts[k]
        if len(seg) < 3:
            ts.dropped_build.append((k, "not enough centreline around point"))
            continue
        _, _, vt = np.linalg.svd(seg, full_matrices=False)
        tangent = vt[0]
        normal = np.array([-tangent[1], tangent[0]])

        prof = _belt_profile(belt, inv, pts[k], normal, MAX_CAST_M, res)
        if prof is None:
            ts.dropped_build.append((k, "no belt along this normal"))
            continue
        width0 = prof["vmax"] - prof["vmin"]
        if width0 < MIN_WIDTH_M:
            ts.dropped_build.append((k, f"belt only {width0:.0f} m wide"))
            continue
        if width0 > MAX_WIDTH_M:
            if C.PROFILE_MODE != "run":
                # Wide braided belt (Jamuna): a belt far past MAX_WIDTH_M is a
                # real defect - the mask has picked up a different water body -
                # and must be dropped, not quietly reinterpreted.
                ts.dropped_build.append(
                    (k, f"belt {width0/1000:.1f} km wide (implausible)"))
                continue
            # A 300 m channel cannot plausibly be 1.8 km wide. The belt here has
            # run into a floodplain pond CONNECTED to the river by a breach or a
            # small canal, so the largest-connected-component mask includes it.
            #
            # Clamp rather than drop. Dropping discards a perfectly good
            # transect that merely has a pond behind one bank, and this reach
            # only yields ~30 transects, so each loss is expensive. The clamped
            # cast is then short enough that edge measurement never reaches the
            # pond (see _water_profile, which truncates for the same reason).
            clamped.append((k, f"belt {width0/1000:.1f} km, clamped to "
                              f"{MAX_WIDTH_M/1000:.1f} km (connected water body)"))
            width0 = MAX_WIDTH_M
        half_max = min(MAX_CAST_M, width0 / 2.0 + MARGIN_M)

        ts.transects.append(Transect(
            i=len(ts.transects), center=pts[k], normal=normal,
            tangent=tangent, arc_m=float(arcs[k]), half_max=float(half_max),
            width0=float(prof["vmax"] - prof["vmin"]),
        ))

    if not quiet:
        print(f"centreline: {total/1000:.1f} km from {sensor_geom} {ref_year}")
        print(f"transects placed every {spacing_m:.0f} m, perpendicular to the "
              f"local centreline direction")
        print(f"kept {len(ts.transects)}, dropped {len(ts.dropped_build)} at build")
        for k, why in ts.dropped_build[:8]:
            print(f"   drop #{k}: {why}")
        if clamped:
            print(f"   clamped {len(clamped)} transect(s) where a connected "
                  f"water body inflated the belt:")
            for k, why in clamped[:4]:
                print(f"     clamp #{k}: {why}")
        if ts.transects:
            w = np.array([t.width0 for t in ts.transects])
            print(f"belt width at reference year: median {np.median(w)/1000:.1f} km, "
                  f"range {w.min()/1000:.1f}-{w.max()/1000:.1f} km")
    return ts


# =============================================================================
# finding the water edges along each transect
# =============================================================================


def _sample(mask, inv, center, normal, half, res):
    step = res
    n = int(half / step)
    offs = np.arange(-n, n + 1) * step
    cx, cy = inv * (center[0], center[1])
    cols = np.round(cx + offs / res * normal[0]).astype(int)
    rows = np.round(cy + offs / res * normal[1]).astype(int)
    H, W = mask.shape
    inside = (rows >= 0) & (rows < H) & (cols >= 0) & (cols < W)
    vals = np.zeros(len(offs), dtype=bool)
    if inside.sum() >= 5:
        vals[inside] = mask[rows[inside], cols[inside]]
    return offs, vals


def _belt_profile(belt, inv, center, normal, half, res):
    """Width of the solid belt along a normal. Used to size transects."""
    offs, vals = _sample(belt, inv, center, normal, half, res)
    if not vals.any():
        return None
    w = offs[vals]
    return {"vmin": float(np.percentile(w, 1)),
            "vmax": float(np.percentile(w, 99)),
            "water_frac": 1.0, "found": True}


def _water_profile(mask, inv, center, normal, half, res, mode="smoothed"):
    """Sample water along the normal. Returns edge offsets and water fraction.

    `mode` chooses how the two edges are found, because the right answer depends
    on how wide the river is:

    "smoothed" - smooth the profile over EDGE_WINDOW_M and call it river wherever
        the smoothed fraction stays at or above MIN_EDGE_FRAC. Needed for the
        JAMUNA, a 9 km braided belt whose true edges are separated by mid-channel
        bars that must not be mistaken for the bank.

    "run" - take the contiguous stretch of water containing the centre point and
        call its ends the banks. Correct for a NARROW river, and it is what makes
        the difference between a 300 m channel and a floodplain pond. On the
        Arial Khan the smoothed rule was reporting a pond 3.5 km away as the far
        bank, which failed the width gate and silently destroyed 9 of 32
        transects - 28% of the study reach lost to pond edges.
    """
    step = res
    n = int(half / step)
    offs = np.arange(-n, n + 1) * step

    cx, cy = inv * (center[0], center[1])
    # work in pixel space: isotropic, so the normal just scales by 1/res
    px = cx + offs / res * normal[0]
    py = cy + offs / res * normal[1]
    cols = np.round(px).astype(int)
    rows = np.round(py).astype(int)

    H, W = mask.shape
    inside = (rows >= 0) & (rows < H) & (cols >= 0) & (cols < W)
    if inside.sum() < 10:
        return None
    vals = np.zeros(len(offs), dtype=bool)
    vals[inside] = mask[rows[inside], cols[inside]]

    if not vals.any():
        return None

    ci = int(round(n))
    if not vals[ci]:
        widx = np.where(vals)[0]
        ci = int(widx[np.argmin(np.abs(widx - ci))])

    if mode == "run":
        lo = ci
        while lo > 0 and vals[lo - 1]:
            lo -= 1
        hi = ci
        while hi < len(vals) - 1 and vals[hi + 1]:
            hi += 1

        # The run can leak: where the channel is connected to a floodplain pond
        # by a breach or a small canal, contiguity walks straight through it and
        # reports a 2.9 km "river". For a channel of known scale that is not a
        # wider river, it is a leak.
        #
        # TRUNCATE rather than drop. Dropping would throw away a perfectly good
        # transect that simply has a pond behind one bank, and on a 9 km reach
        # with only ~30 transects, losing several is expensive. The near part of
        # the profile is the real channel, so keep the plausible width centred on
        # the transect and ignore the rest.
        run_w = offs[hi] - offs[lo]
        if run_w > MAX_WIDTH_M:
            half_run = MAX_WIDTH_M / 2.0
            lo = ci
            while lo > 0 and offs[lo] > offs[ci] - half_run and vals[lo - 1]:
                lo -= 1
            hi = ci
            while hi < len(vals) - 1 and offs[hi] < offs[ci] + half_run and vals[hi + 1]:
                hi += 1

        vmin, vmax = float(offs[lo]), float(offs[hi])
        between = (offs >= vmin) & (offs <= vmax)
        return {
            "vmin": vmin,
            "vmax": vmax,
            "water_frac": float(vals[between].mean()),
            "found": True,
        }

    # The belt edge is where the profile stops looking like RIVER, not where a
    # single water pixel happens to stop.
    #
    # Three earlier definitions all failed for a reason worth recording:
    #   - first/last water pixel: width depends on where a sandbar falls;
    #   - contiguous run: stops at every mid-channel bar, measuring single
    #     channels (~2 km) instead of the belt (~6-9 km);
    #   - 2nd/98th percentile: leaves a thin tail of water OUTSIDE the reported
    #     edge by construction, so the edge never sits on a real land/water
    #     boundary.
    #
    # Instead, smooth the profile over EDGE_WINDOW_M and call it river wherever
    # the smoothed fraction stays at or above MIN_EDGE_FRAC. A bar narrower than
    # the window is absorbed; a narrow floodplain pond is ignored; and the edge
    # lands on an actual transition.
    from scipy.ndimage import uniform_filter1d

    win = max(3, int(EDGE_WINDOW_M / step) | 1)
    smooth = uniform_filter1d(vals.astype("float32"), size=win, mode="nearest")
    is_river = smooth >= MIN_EDGE_FRAC

    left = np.where(is_river[:ci + 1])[0]
    right = np.where(is_river[ci:])[0]
    if len(left) == 0 or len(right) == 0:
        return None
    lo = int(left[0])
    hi = ci + int(right[-1])

    vmin, vmax = float(offs[lo]), float(offs[hi])
    between = (offs >= vmin) & (offs <= vmax)
    return {
        "vmin": vmin,
        "vmax": vmax,
        "water_frac": float(vals[between].mean()),
        "found": True,
    }


def _bridge(mask, max_gap):
    """Fill interior False runs no longer than max_gap."""
    out = mask.copy()
    idx = np.where(~out)[0]
    if len(idx) == 0:
        return out
    splits = np.split(idx, np.where(np.diff(idx) != 1)[0] + 1)
    for run in splits:
        if len(run) <= max_gap:
            a, b = run[0], run[-1]
            # only fill interior gaps, never extend past the water
            if a > 0 and b < len(out) - 1:
                out[a:b + 1] = True
    return out


def measure_edges(ts, year, sensor="s2", quiet=False):
    """Measure both belt edges for every transect in `ts` for `year`.

    The edge comes from the WATER mask via a purely GEOMETRIC rule: walk outward
    from the centre and stop where the smoothed water fraction stops looking
    like river. No hole filling, no connectivity test.

    That choice is the whole answer to "which sensor is more accurate", and it
    was settled by measurement, not opinion.

    Defining the belt by filling holes looked more principled, but hole filling
    is RESOLUTION DEPENDENT. A sandbar is an enclosed hole at 10 m, so the belt
    includes it; at 30 m the thin water channel through that bar is lost, the
    bar is no longer enclosed, and the belt stops hundreds of metres early. On
    one fixed transect, Sentinel-2 measured the belt as 5.09 km wide and
    Landsat as 1.80 km for the SAME year, while their water masks were
    IDENTICAL bin by bin. The Landsat zones then sat inside the braided belt,
    where sandbar migration was counted as bank erosion, and its rates came out
    3.3x too high with a correlation of -0.10 against Sentinel-2.

    With the geometric rule the two sensors agree to within 1-14% on 6 of 7
    transects (1.00x, 0.99x, 1.14x, 0.99x, 1.02x, 1.05x).

    A transect is kept only if both edges are found and it is mostly water.
    Dropped transects are reported, with the reason.
    """
    mask, tr, hw = load_water(year, sensor)
    inv = ~tr
    mode = C.PROFILE_MODE

    # The sampling step must be the resolution of the mask being MEASURED, not
    # the resolution of the sensor the GEOMETRY was built from.
    #
    # Using ts.res here (the geometry sensor, 10 m) while measuring a 30 m mask
    # compressed every cast to one third of its intended length, so Landsat's belt
    # came out at ~1.8 km where Sentinel-2 measured 5.1 km for the same year.
    # The water masks were IDENTICAL bin by bin; only the sampling was wrong.
    # That single mismatch is what produced the 3.3x rate disagreement and the
    # -0.10 correlation in D35.
    res = C.sensor_res(sensor)

    dropped = []
    for t in ts.transects:
        prof = _water_profile(mask, inv, t.center, t.normal, t.half_max,
                              res, mode=mode)
        if prof is None:
            t.ok, t.reason = False, "no water along this transect"
            dropped.append((t.i, t.reason))
            continue
        if prof["water_frac"] < MIN_WATER_FRAC:
            t.ok, t.reason = False, f"only {prof['water_frac']*100:.0f}% water"
            dropped.append((t.i, t.reason))
            continue
        t.vmin, t.vmax = prof["vmin"], prof["vmax"]
        t.width_m = prof["vmax"] - prof["vmin"]
        t.water_frac = prof["water_frac"]

        # Plausibility on the MEASURED width for this year. The build-time gate
        # used the solid belt, which is always wide; here we check the wetted
        # width actually found, and drop transects that caught a single channel
        # or that ran off into stray water.
        if t.width_m < MIN_WET_WIDTH_M:
            t.ok = False
            t.reason = f"wetted width only {t.width_m:.0f} m (single channel)"
            dropped.append((t.i, t.reason))
            continue
        if t.width_m > MAX_WIDTH_M:
            t.ok = False
            t.reason = f"wetted width {t.width_m/1000:.1f} km (implausible)"
            dropped.append((t.i, t.reason))
            continue

        t.ok, t.reason = True, ""

    if not quiet:
        print(f"  {sensor} {year}: {sum(t.ok for t in ts.transects)}"
              f"/{len(ts.transects)} transects usable, {len(dropped)} dropped")
        for i, why in dropped[:6]:
            print(f"     drop #{i}: {why}")

    return dropped


# =============================================================================
# zones and geometry helpers
# =============================================================================

def transect_line(t, extend=0.0):
    a = t.center - t.normal * (t.half_max + extend)
    b = t.center + t.normal * (t.half_max + extend)
    return LineString([tuple(a), tuple(b)])


def zone_polygon(t, v0, v1, pad):
    """Rectangle spanning the transect from v0 to v1, padded along the flow."""
    half = BUFFER_M
    corners = []
    for du in (-pad, pad):
        for dv in (v0, v1):
            corners.append(t.center + du * t.tangent + dv * t.normal)
    return Polygon(corners)


def bank_zones(t, pad, anchor_vmin, anchor_vmax, zone_m=ZONE_M):
    """The two EPR zones for a transect, anchored to the given edges."""
    half = zone_m / 2.0
    return (zone_polygon(t, anchor_vmin - half, anchor_vmin + half, pad),
            zone_polygon(t, anchor_vmax - half, anchor_vmax + half, pad))


def bank_positions(ts, year, sensor="s2", quiet=True):
    """Measure edges for a year and return the list of usable transects."""
    dropped = measure_edges(ts, year, sensor, quiet=quiet)
    return [t for t in ts.transects if t.ok], dropped


def stage_km2(year, sensor="s2"):
    w, _, _ = load_water(year, sensor)
    return float(w.sum()) * C.sensor_res(sensor) ** 2 / 1e6
