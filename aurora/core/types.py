"""
Core type definitions for AURORA BMI.

Defines enums, dataclasses, and type aliases for the breadth index system.
"""

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import TypeAlias


class Band(str, Enum):
    """
    AURORA BMI interpretation bands.

    These represent participation health, NOT price outlook.

    Band Thresholds:
        - GREEN (0-25): Healthy, broad participation
        - LIGHT_GREEN (25-50): Moderate participation
        - YELLOW (50-75): Weakening participation
        - RED (75-100): Poor, narrow participation

    Note: Lower score = healthier breadth.
    """

    GREEN = "GREEN"
    LIGHT_GREEN = "LIGHT_GREEN"
    YELLOW = "YELLOW"
    RED = "RED"

    @classmethod
    def from_score(cls, score: float) -> "Band":
        """
        Convert AURORA score to band.

        Args:
            score: AURORA score in [0, 100]

        Returns:
            Corresponding band
        """
        if score <= 25:
            return cls.GREEN
        elif score <= 50:
            return cls.LIGHT_GREEN
        elif score <= 75:
            return cls.YELLOW
        else:
            return cls.RED

    @property
    def description(self) -> str:
        """Human-readable description of the band."""
        descriptions = {
            Band.GREEN: "Healthy, broad participation",
            Band.LIGHT_GREEN: "Moderate participation",
            Band.YELLOW: "Weakening participation",
            Band.RED: "Poor, narrow participation",
        }
        return descriptions[self]


class BaselineStatus(str, Enum):
    """
    Status of baseline normalization.

    GUARDRAIL: INSUFFICIENT is assigned when critical data is missing.
    Better to report uncertainty than to guess.
    """

    COMPLETE = "COMPLETE"  # All features have sufficient history (n >= N_min)
    PARTIAL = "PARTIAL"  # Some features excluded (n < N_min)
    INSUFFICIENT = "INSUFFICIENT"  # Critical features missing, cannot compute


@dataclass(frozen=True)
class ScoreComponent:
    """
    A component of the BMI composite score.

    Each component represents one breadth dimension with its weight,
    raw value, z-score, and contribution to the final score.
    """

    name: str
    weight: float
    raw_value: float
    zscore: float  # NOT clipped - preserves tail information
    contribution: float  # weight * zscore

    @property
    def contribution_pct(self) -> float:
        """Contribution as percentage (for display)."""
        return abs(self.contribution) * 100

    @property
    def direction(self) -> str:
        """Direction indicator based on z-score."""
        if self.zscore > 0.5:
            return "elevated"
        elif self.zscore < -0.5:
            return "depressed"
        else:
            return "neutral"


@dataclass(frozen=True)
class BMIResult:
    """
    Result of AURORA BMI calculation for a single trading day.

    This is the primary output of the AURORA BMI engine.

    Design Notes:
        - score is bounded [0, 100] via percentile ranking (the ONLY bounding mechanism)
        - z-scores in components are NOT clipped to preserve tail information
        - Lower score = healthier breadth (GREEN)
        - Higher score = weaker breadth (RED)
    """

    trade_date: date
    score: float  # AURORA score in [0, 100], bounded by percentile ranking
    band: Band  # Interpretation band
    explanation: str  # Human-readable explanation
    components: tuple[ScoreComponent, ...]  # Individual component scores
    raw_composite: float  # S_BMI before percentile transformation
    status: BaselineStatus  # Baseline completeness status
    excluded_features: tuple[str, ...]  # Features with n < N_min

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "date": self.trade_date.isoformat(),
            "score": round(self.score, 1),
            "band": self.band.value,
            "explanation": self.explanation,
            "components": [
                {
                    "name": c.name,
                    "weight": c.weight,
                    "raw_value": round(c.raw_value, 4),
                    "zscore": round(c.zscore, 2),  # NOT clipped
                    "contribution": round(c.contribution, 4),
                    "direction": c.direction,
                }
                for c in self.components
            ],
            "raw_composite": round(self.raw_composite, 4),
            "status": self.status.value,
            "excluded_features": list(self.excluded_features),
        }

    @property
    def is_healthy(self) -> bool:
        """Whether breadth indicates healthy participation."""
        return self.band in (Band.GREEN, Band.LIGHT_GREEN)

    @property
    def vpb_ipb_divergence(self) -> float | None:
        """
        VPB vs IPB divergence (diagnostic property).

        Positive = VPB > IPB (narrow, mega-cap driven)
        Negative = IPB > VPB (broad but weak)
        Near zero = aligned

        This is a MONITORED DIAGNOSTIC PROPERTY, not an error.
        VPB and IPB correlate but measure different dimensions:
        - VPB: dollar-weighted (where is capital flowing?)
        - IPB: count-weighted (how broad is participation?)
        """
        vpb_z = None
        ipb_z = None
        for c in self.components:
            if c.name == "VPB":
                vpb_z = c.zscore
            elif c.name == "IPB":
                ipb_z = c.zscore
        if vpb_z is not None and ipb_z is not None:
            return vpb_z - ipb_z
        return None


@dataclass
class FeatureSet:
    """
    Raw and computed features for BMI calculation.

    Contains inputs from data sources and computed breadth metrics.
    """

    trade_date: date

    # Volume Participation Breadth inputs
    v_adv: float | None = None  # Advancing volume
    v_dec: float | None = None  # Declining volume

    # Issue Participation Breadth inputs
    n_adv: int | None = None  # Advancing issues count
    n_dec: int | None = None  # Declining issues count

    # Structural Breadth Confirmation inputs
    pct_ma50: float | None = None  # % of stocks above 50-day MA
    pct_ma200: float | None = None  # % of stocks above 200-day MA

    # Institutional Participation Overlay inputs
    rel_vol_values: list[float] | None = None  # Per-stock relative volumes
    universe_median_relvol: float | None = None  # Universe median for dual filter

    # Computed breadth metrics
    vpb: float | None = None  # Volume Participation Breadth
    ipb: float | None = None  # Issue Participation Breadth
    sbc: float | None = None  # Structural Breadth Confirmation
    ipo: float | None = None  # Institutional Participation Overlay

    # Normalized z-scores (NOT clipped)
    normalized: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "date": self.trade_date.isoformat(),
            "v_adv": self.v_adv,
            "v_dec": self.v_dec,
            "n_adv": self.n_adv,
            "n_dec": self.n_dec,
            "pct_ma50": self.pct_ma50,
            "pct_ma200": self.pct_ma200,
            "vpb": self.vpb,
            "ipb": self.ipb,
            "sbc": self.sbc,
            "ipo": self.ipo,
            "normalized": self.normalized,
        }


# Type aliases for clarity
ZScore: TypeAlias = float  # NOT clipped - preserves tail information
Percentile: TypeAlias = float  # 0-100, the ONLY bounding mechanism
TradeDate: TypeAlias = date


# =============================================================================
# UNIVERSE TYPES
# =============================================================================


@dataclass(frozen=True)
class UniverseConfig:
    """
    Configuration for AURORA universe construction.

    CRITERIA (STRICT):
    - Market Cap > $2B
    - Price > $5
    - Average Daily Volume (20D) > 1M shares
    - Listed on NYSE or NASDAQ
    - (Optional) Free Float Market Cap > $1B if data available

    Design Rule:
        If universe quality is uncertain, reduce universe.
        Better to be slightly narrow than slightly wrong.
    """

    min_market_cap: int = 2_000_000_000  # $2B
    min_price: float = 5.0
    min_volume: int = 1_000_000  # 1M shares
    exchanges: tuple[str, ...] = ("NYSE", "NASDAQ")
    min_free_float_cap: int | None = 1_000_000_000  # $1B (optional)
    max_results: int = 2000
    size_change_warn_pct: float = 0.10  # Warn if ±10% day-over-day


@dataclass(frozen=True)
class UniverseSnapshot:
    """
    Daily universe snapshot for AURORA BMI.

    Immutable once written. Downstream components must only read.
    """

    trade_date: date
    tickers: tuple[str, ...]
    count: int
    median_market_cap: float | None
    median_volume: float | None
    previous_count: int | None = None

    @property
    def size_change_pct(self) -> float | None:
        """Percentage change from previous day's universe size."""
        if self.previous_count is None or self.previous_count == 0:
            return None
        return (self.count - self.previous_count) / self.previous_count

    @property
    def size_change_warning(self) -> bool:
        """True if size changed by more than 10%."""
        change = self.size_change_pct
        return change is not None and abs(change) > 0.10

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "date": self.trade_date.isoformat(),
            "tickers": list(self.tickers),
            "count": self.count,
            "median_market_cap": self.median_market_cap,
            "median_volume": self.median_volume,
            "previous_count": self.previous_count,
            "size_change_pct": self.size_change_pct,
        }
