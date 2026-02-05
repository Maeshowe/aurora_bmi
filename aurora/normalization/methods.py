"""
Normalization methods for AURORA BMI.

CRITICAL DESIGN DECISION:
Z-scores are NOT clipped at the feature level.
Extreme values (tail information) must be preserved.
Percentile ranking is the ONLY bounding mechanism,
applied to the final composite score.

Rationale:
- Breadth distributions have fat tails
- Crisis signals live in the tails
- Clipping would mask exactly the events we want to detect
"""

import logging
from collections.abc import Sequence

import numpy as np

logger = logging.getLogger(__name__)


def zscore_normalize(
    value: float,
    mean: float,
    std: float,
) -> float:
    """
    Calculate z-score normalization.

    IMPORTANT: This function does NOT clip the z-score.
    Extreme values are preserved to capture tail information.

    Args:
        value: The value to normalize
        mean: The rolling mean
        std: The rolling standard deviation

    Returns:
        Z-score (unbounded - NOT clipped)
    """
    if std == 0 or std is None or np.isnan(std):
        # If no variance, return 0 (value equals mean)
        logger.debug(f"Zero std for value={value}, mean={mean}, returning 0.0")
        return 0.0

    z = (value - mean) / std

    # NO CLIPPING - preserve tail information
    # Extreme z-scores (e.g., -5, +7) indicate crisis conditions
    # and should be preserved for proper percentile ranking

    return float(z)


def percentile_rank(
    value: float,
    history: Sequence[float],
) -> float:
    """
    Calculate percentile rank of a value within historical distribution.

    This is the ONLY bounding mechanism in AURORA BMI.
    It naturally maps any z-score (including extremes) to [0, 100].

    Args:
        value: The value to rank
        history: Historical values to compare against

    Returns:
        Percentile rank in [0, 100]
    """
    if not history:
        # No history - return middle value
        return 50.0

    n = len(history)

    # Count how many historical values are less than current
    count_less = sum(1 for h in history if h < value)

    # Percentile rank formula
    percentile = (count_less / n) * 100

    return float(percentile)


def percentile_rank_with_ties(
    value: float,
    history: Sequence[float],
) -> float:
    """
    Calculate percentile rank handling ties.

    Uses the midpoint method for ties: if a value ties with
    k values, it gets rank as if it were in the middle.

    Args:
        value: The value to rank
        history: Historical values to compare against

    Returns:
        Percentile rank in [0, 100]
    """
    if not history:
        return 50.0

    n = len(history)

    count_less = sum(1 for h in history if h < value)
    count_equal = sum(1 for h in history if h == value)

    # Midpoint method for ties
    rank = count_less + (count_equal / 2)
    percentile = (rank / n) * 100

    return float(percentile)


def calculate_rolling_mean(
    values: Sequence[float],
    window: int,
) -> float | None:
    """
    Calculate rolling mean from recent values.

    Args:
        values: Sequence of historical values (oldest to newest)
        window: Number of values to include

    Returns:
        Rolling mean or None if insufficient data
    """
    if len(values) < window:
        return None

    recent = values[-window:]
    return float(np.mean(recent))


def calculate_rolling_std(
    values: Sequence[float],
    window: int,
    ddof: int = 1,
) -> float | None:
    """
    Calculate rolling standard deviation from recent values.

    Args:
        values: Sequence of historical values (oldest to newest)
        window: Number of values to include
        ddof: Delta degrees of freedom (default 1 for sample std)

    Returns:
        Rolling std or None if insufficient data
    """
    if len(values) < window:
        return None

    recent = values[-window:]
    return float(np.std(recent, ddof=ddof))


def sigmoid_scale(
    value: float,
    midpoint: float = 0.0,
    steepness: float = 1.0,
) -> float:
    """
    Scale a value to [0, 1] using sigmoid function.

    This is a FALLBACK method when insufficient history
    prevents percentile ranking. Not used in normal operation.

    Args:
        value: Value to scale
        midpoint: Sigmoid midpoint (where output = 0.5)
        steepness: Controls steepness of transition

    Returns:
        Scaled value in [0, 1]
    """
    return 1.0 / (1.0 + np.exp(-steepness * (value - midpoint)))
