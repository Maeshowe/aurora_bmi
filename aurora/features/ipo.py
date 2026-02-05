"""
Institutional Participation Overlay (IPO) calculator.

IPO detects institutional participation via relative volume spikes
on LIT exchanges (NOT dark pools - those belong to OBSIDIAN).

Formula (Dual Filter):
    IPO_t = count(RelVol_i > Q90(RelVol_i) AND RelVol_i > median(universe)) / N

Where:
    RelVol_i = Vol_i / SMA_20(Vol_i) for stock i
    Q90(RelVol_i) = 90th percentile of stock i's historical relative volume
    median(universe) = Cross-sectional median relative volume

Dual Filter Rationale:
    A stock must satisfy BOTH conditions to count:
    1. RelVol > Q90(own history) - unusual FOR THAT STOCK
    2. RelVol > median(universe) - unusual RELATIVE TO MARKET

    This prevents:
    - Small-cap noise (stock-specific Q90 alone is heterogeneous)
    - Crisis-mode saturation (during market stress, everyone is "abnormal")

Interpretation:
    - IPO high: Many stocks showing institutional-level activity
    - IPO low: Normal retail-dominated activity levels

GUARDRAIL: This uses LIT exchange data only. Dark pool analysis
belongs to OBSIDIAN, not AURORA.
"""

import logging
from dataclasses import dataclass


logger = logging.getLogger(__name__)


@dataclass
class IPOResult:
    """Result of IPO calculation."""

    value: float | None
    spike_count: int
    total_stocks: int
    universe_median: float | None
    is_valid: bool
    message: str = ""


class InstitutionalParticipationOverlay:
    """
    Institutional Participation Overlay calculator.

    Detects institutional participation via relative volume spikes
    using a DUAL FILTER approach on LIT exchange data only.

    GUARDRAIL: No dark pool data. That belongs to OBSIDIAN.
    """

    NAME = "IPO"
    DEFAULT_PERCENTILE = 90.0

    def __init__(self, percentile_threshold: float = 90.0) -> None:
        """
        Initialize IPO calculator.

        Args:
            percentile_threshold: Percentile threshold for "unusual" (default Q90)
        """
        self.percentile_threshold = percentile_threshold

    def calculate(
        self,
        rel_vol_values: list[float] | None,
        rel_vol_thresholds: list[float] | None = None,
        universe_median: float | None = None,
    ) -> IPOResult:
        """
        Calculate Institutional Participation Overlay using DUAL FILTER.

        A stock counts as having institutional participation if:
        1. Its relative volume exceeds its own Q90 threshold
        2. Its relative volume exceeds the universe median

        Args:
            rel_vol_values: List of relative volume values for each stock
            rel_vol_thresholds: Per-stock Q90 thresholds (same order as rel_vol_values)
            universe_median: Cross-sectional median relative volume

        Returns:
            IPOResult with calculated value or None if invalid
        """
        # Handle missing data
        if rel_vol_values is None or len(rel_vol_values) == 0:
            return IPOResult(
                value=None,
                spike_count=0,
                total_stocks=0,
                universe_median=None,
                is_valid=False,
                message="Missing relative volume data",
            )

        n = len(rel_vol_values)

        # If thresholds not provided, use a simple heuristic
        # (in practice, these should come from historical data)
        if rel_vol_thresholds is None:
            # Default: consider 2.0x relative volume as "unusual"
            rel_vol_thresholds = [2.0] * n
            logger.debug("Using default Q90 threshold of 2.0 for all stocks")

        if len(rel_vol_thresholds) != n:
            return IPOResult(
                value=None,
                spike_count=0,
                total_stocks=n,
                universe_median=universe_median,
                is_valid=False,
                message="Mismatch between rel_vol_values and thresholds lengths",
            )

        # Calculate universe median if not provided
        if universe_median is None:
            sorted_vals = sorted(rel_vol_values)
            if n % 2 == 0:
                universe_median = (sorted_vals[n // 2 - 1] + sorted_vals[n // 2]) / 2
            else:
                universe_median = sorted_vals[n // 2]

        # Apply DUAL FILTER
        spike_count = 0
        for i, rel_vol in enumerate(rel_vol_values):
            threshold = rel_vol_thresholds[i]

            # DUAL FILTER: Must satisfy BOTH conditions
            exceeds_own_q90 = rel_vol > threshold
            exceeds_universe_median = rel_vol > universe_median

            if exceeds_own_q90 and exceeds_universe_median:
                spike_count += 1

        # Calculate IPO as fraction of stocks showing institutional activity
        ipo = spike_count / n

        return IPOResult(
            value=ipo,
            spike_count=spike_count,
            total_stocks=n,
            universe_median=universe_median,
            is_valid=True,
        )

    def calculate_simple(
        self,
        rel_vol_values: list[float] | None,
        threshold: float = 2.0,
    ) -> IPOResult:
        """
        Simplified IPO calculation using a fixed threshold.

        This is a fallback when per-stock Q90 data is unavailable.

        Args:
            rel_vol_values: List of relative volume values
            threshold: Fixed threshold for "unusual" (default 2.0x)

        Returns:
            IPOResult with calculated value
        """
        if rel_vol_values is None or len(rel_vol_values) == 0:
            return IPOResult(
                value=None,
                spike_count=0,
                total_stocks=0,
                universe_median=None,
                is_valid=False,
                message="Missing relative volume data",
            )

        n = len(rel_vol_values)

        # Calculate universe median
        sorted_vals = sorted(rel_vol_values)
        if n % 2 == 0:
            universe_median = (sorted_vals[n // 2 - 1] + sorted_vals[n // 2]) / 2
        else:
            universe_median = sorted_vals[n // 2]

        # Use fixed threshold and universe median as dual filter
        spike_count = sum(
            1 for v in rel_vol_values
            if v > threshold and v > universe_median
        )

        ipo = spike_count / n

        return IPOResult(
            value=ipo,
            spike_count=spike_count,
            total_stocks=n,
            universe_median=universe_median,
            is_valid=True,
            message="Using simplified calculation with fixed threshold",
        )

    def interpret(self, ipo: float) -> str:
        """
        Provide interpretation of IPO value.

        Args:
            ipo: IPO value in [0, 1]

        Returns:
            Human-readable interpretation
        """
        pct = ipo * 100

        if pct > 20:
            return "High institutional participation (many stocks with volume spikes)"
        elif pct > 10:
            return "Elevated institutional participation"
        elif pct > 5:
            return "Moderate institutional participation"
        elif pct > 2:
            return "Low institutional participation"
        else:
            return "Minimal institutional participation (retail-dominated)"

    @staticmethod
    def calculate_relative_volume(
        current_volume: float,
        avg_volume: float,
    ) -> float | None:
        """
        Calculate relative volume for a single stock.

        Args:
            current_volume: Today's volume
            avg_volume: Average volume (e.g., 20-day SMA)

        Returns:
            Relative volume or None if invalid
        """
        if avg_volume <= 0:
            return None
        return current_volume / avg_volume
