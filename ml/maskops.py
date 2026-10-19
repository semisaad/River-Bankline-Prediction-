"""Operations on a prepared water mask, shared by both prepare scripts.

These live here rather than in `01_prepare.py` because `01_prepare.py` starts
with a digit and cannot be imported. The Sentinel-2 and Landsat paths must apply
exactly the same rule, or the two sensors stop being comparable, which is the
whole point of running both.
"""

import numpy as np
from scipy import ndimage


def river_body(arr, px_m, min_km2):
    """Keep only water bodies at least `min_km2` in size; discard the rest.

    WHY THIS EXISTS (D77, D79). The exporters carry a connected-component filter,
    but it did not reach the files that were actually downloaded: 27-56% of every
    mask was ponds - 1,053 to 2,370 separate bodies per year, 33.1 of 79.9 km2
    across the 8 Sentinel-2 years. The live transect builder copes by clamping a
    belt that a connected body has inflated, but 10 of its 63 transects hit the
    1.2 km ceiling on the pond-contaminated masks.

    The river here is a single thread, so it is ONE body. Measured across all 45
    exported masks it is 5.32-8.23 km2 while the second-largest body never
    exceeded 1.48 km2, so the 2.0 km2 default sits in an empty gap rather than
    near a boundary where a wet year could tip it.

    Returns (filtered, dropped) where `dropped` lists discarded bodies as
    (km2, fraction of total water), largest first, so that a discarded river
    section is visible rather than silent.
    """
    if min_km2 <= 0 or not arr.any():
        return arr, []

    binary = arr > 0
    labels, n = ndimage.label(binary)
    if n <= 1:
        return arr, []

    areas = ndimage.sum(binary, labels, range(1, n + 1)) * (px_m ** 2) / 1e6
    total = float(areas.sum())
    keep = areas >= min_km2

    out = np.where(keep[labels - 1], arr, 0).astype(arr.dtype)
    dropped = sorted(((float(a), float(a / total) if total else 0.0)
                      for a, k in zip(areas, keep) if not k), reverse=True)
    return out, dropped


def summarise(ponds, min_km2):
    """Total up what the filter did across the whole run."""
    if not ponds:
        return
    lost = sum(raw - k for _, raw, k in ponds)
    kept = sum(k for _, _, k in ponds)
    worst = max(d[0][0] for d, _, _ in ponds)
    print(f"\npond filter (>= {min_km2} km2): dropped {lost:.1f} km2 of "
          f"{lost + kept:.1f} km2 ({lost / (lost + kept) * 100:.0f}%) over "
          f"{len(ponds)} years; largest single body discarded {worst:.2f} km2")
    if worst > 1.5:
        print("\n" + "=" * 66)
        print("WARNING: the filter discarded a body of river scale.")
        print("A pond is not this big - this is a second channel or a real")
        print("section of the river that would now be measured as bank.")
        print(f"Lower river_body_min_km2 in config.py (now {min_km2}), or")
        print("inspect those years, before trusting any bankline derived from them.")
        print("=" * 66)
    print()
