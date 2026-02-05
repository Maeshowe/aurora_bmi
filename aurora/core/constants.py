"""
Constants for AURORA BMI.

These values are FROZEN and must not be tuned or optimized.
They represent conceptual design choices, not fitted parameters.
"""

from typing import Final

# =============================================================================
# COMPONENT WEIGHTS (FROZEN)
# =============================================================================
# These weights are conceptual allocations, NOT optimized parameters.
# Do not tune these values.

WEIGHTS: Final[dict[str, float]] = {
    "VPB": 0.30,  # Volume Participation Breadth (dollar-weighted)
    "IPB": 0.25,  # Issue Participation Breadth (count-weighted)
    "SBC": 0.25,  # Structural Breadth Confirmation (MA50/200)
    "IPO": 0.20,  # Institutional Participation Overlay
}

# Verify weights sum to 1.0
assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9, "Weights must sum to 1.0"

# =============================================================================
# NORMALIZATION PARAMETERS (FROZEN)
# =============================================================================

ROLLING_WINDOW: Final[int] = 63  # Trading days (~3 months)
MIN_OBSERVATIONS: Final[int] = 21  # Minimum for valid baseline (~1 month)

# =============================================================================
# BAND THRESHOLDS (FROZEN)
# =============================================================================
# Lower score = healthier breadth

BAND_THRESHOLDS: Final[dict[str, tuple[float, float]]] = {
    "GREEN": (0, 25),  # Healthy, broad participation
    "LIGHT_GREEN": (25, 50),  # Moderate participation
    "YELLOW": (50, 75),  # Weakening participation
    "RED": (75, 100),  # Poor, narrow participation
}

# =============================================================================
# IPO DUAL FILTER THRESHOLD
# =============================================================================
# Stock must exceed BOTH its own Q90 AND universe median

IPO_PERCENTILE_THRESHOLD: Final[float] = 90.0  # Q90 for stock-specific threshold

# =============================================================================
# DIAGNOSTIC THRESHOLDS
# =============================================================================
# VPB/IPB divergence monitoring (not used in scoring, only for diagnostics)

VPB_IPB_DIVERGENCE_WARN: Final[float] = 1.0  # Flag if |VPB_z - IPB_z| > 1.0

# =============================================================================
# FEATURE NAMES
# =============================================================================

FEATURE_NAMES: Final[tuple[str, ...]] = ("VPB", "IPB", "SBC", "IPO")

# =============================================================================
# DESIGN DOCUMENTATION
# =============================================================================
# These constants encode the following design decisions:
#
# 1. NO Z-SCORE CLIPPING: Feature-level z-scores are NOT clipped.
#    Extreme values are preserved. Percentile ranking is the ONLY
#    bounding mechanism applied to the final score.
#
# 2. VPB/IPB CORRELATION: VPB and IPB are correlated but measure
#    different dimensions (dollar-weighted vs count-weighted).
#    Their divergence is a MONITORED DIAGNOSTIC PROPERTY, not an error.
#    - VPB high + IPB low = narrow leadership (mega-cap driven)
#    - VPB low + IPB high = broad but weak participation
#
# 3. IPO DUAL FILTER: A stock counts toward IPO only if:
#    - RelVol > Q90(own history) - unusual for that stock
#    - RelVol > median(universe) - unusual relative to market
#    This prevents small-cap noise and crisis-mode saturation.
