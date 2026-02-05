"""
Normalization pipeline for AURORA BMI.

Orchestrates the full normalization process:
1. Load historical data
2. Calculate z-scores (NO CLIPPING)
3. Track baseline status
4. Return normalized features with excluded list
"""

import logging
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from aurora.core.constants import FEATURE_NAMES, MIN_OBSERVATIONS, ROLLING_WINDOW
from aurora.core.types import BaselineStatus, FeatureSet
from aurora.normalization.methods import percentile_rank, zscore_normalize
from aurora.normalization.rolling import MultiFeatureRollingCalculator

logger = logging.getLogger(__name__)


class NormalizationPipeline:
    """
    Feature normalization pipeline with rolling baselines.

    CRITICAL DESIGN DECISIONS:
    1. Z-scores are NOT clipped at feature level
    2. Percentile ranking is the ONLY bounding mechanism
    3. Features with n < N_min are excluded, not imputed
    """

    def __init__(
        self,
        window: int = ROLLING_WINDOW,
        min_observations: int = MIN_OBSERVATIONS,
        history_dir: Path | None = None,
    ) -> None:
        """
        Initialize normalization pipeline.

        Args:
            window: Rolling window size (default 63)
            min_observations: Minimum for valid baseline (default 21)
            history_dir: Directory containing historical data
        """
        self.window = window
        self.min_observations = min_observations
        self.history_dir = history_dir

        # Initialize rolling calculator for all features
        self._calculator = MultiFeatureRollingCalculator(
            feature_names=FEATURE_NAMES,
            window=window,
            min_observations=min_observations,
        )

        # Track composite score history for percentile ranking
        self._composite_history: list[float] = []

    def load_history(self, up_to_date: date | None = None) -> int:
        """
        Load historical data from files.

        Args:
            up_to_date: Only load data up to this date

        Returns:
            Number of observations loaded
        """
        if self.history_dir is None:
            logger.warning("No history directory configured")
            return 0

        history_file = self.history_dir / "bmi_history.parquet"
        if not history_file.exists():
            logger.info(f"No history file found at {history_file}")
            return 0

        try:
            df = pd.read_parquet(history_file)

            # Filter by date if specified
            if up_to_date is not None:
                df = df[df["date"] <= up_to_date.isoformat()]

            # Sort by date
            df = df.sort_values("date")

            # Load into rolling calculator
            records = df.to_dict("records")
            count = self._calculator.load_from_history(records)

            # Load composite history for percentile ranking
            if "raw_composite" in df.columns:
                self._composite_history = df["raw_composite"].tolist()

            logger.info(f"Loaded {count} historical observations from {history_file}")
            return count

        except Exception as e:
            logger.error(f"Failed to load history: {e}")
            return 0

    def load_from_records(self, records: list[dict[str, Any]]) -> int:
        """
        Load historical data from a list of records.

        Args:
            records: List of dicts with date and feature values

        Returns:
            Number of observations loaded
        """
        count = self._calculator.load_from_history(records)

        # Extract composite history if present
        for record in records:
            if "raw_composite" in record:
                self._composite_history.append(record["raw_composite"])

        return count

    def normalize(
        self,
        features: FeatureSet,
    ) -> tuple[dict[str, float], list[str], BaselineStatus]:
        """
        Normalize features and return z-scores.

        IMPORTANT: Z-scores are NOT clipped. Extreme values preserved.

        Args:
            features: FeatureSet with raw feature values

        Returns:
            Tuple of:
            - z_scores dict (feature name -> z-score)
            - excluded features list
            - baseline status
        """
        z_scores: dict[str, float] = {}
        excluded: list[str] = []

        # Map feature names to values
        feature_values = {
            "VPB": features.vpb,
            "IPB": features.ipb,
            "SBC": features.sbc,
            "IPO": features.ipo,
        }

        # Normalize each feature
        for name, value in feature_values.items():
            if value is None:
                excluded.append(name)
                logger.debug(f"Feature {name} is None, excluding")
                continue

            stats = self._calculator.get_stats(name)

            if stats is None or not stats.is_ready:
                excluded.append(name)
                logger.debug(
                    f"Feature {name} has insufficient history "
                    f"({stats.count if stats else 0} < {self.min_observations})"
                )
                continue

            # Calculate z-score (NO CLIPPING)
            z = zscore_normalize(value, stats.mean, stats.std)
            z_scores[name] = z

        # Determine baseline status
        if len(excluded) == 0:
            status = BaselineStatus.COMPLETE
        elif len(z_scores) > 0:
            status = BaselineStatus.PARTIAL
        else:
            status = BaselineStatus.INSUFFICIENT

        logger.info(
            f"Normalization complete: {len(z_scores)} features normalized, "
            f"{len(excluded)} excluded, status={status.value}"
        )

        return z_scores, excluded, status

    def add_observation(self, features: FeatureSet) -> None:
        """
        Add current observation to rolling history.

        Call this AFTER normalization to include in future baselines.

        Args:
            features: FeatureSet with raw values
        """
        feature_values = {
            "VPB": features.vpb,
            "IPB": features.ipb,
            "SBC": features.sbc,
            "IPO": features.ipo,
        }

        # Filter out None values
        valid_features = {k: v for k, v in feature_values.items() if v is not None}

        self._calculator.add_observation(features.trade_date, valid_features)

    def add_composite_to_history(self, composite: float) -> None:
        """
        Add composite score to history for percentile ranking.

        Args:
            composite: Raw composite score (S_BMI)
        """
        self._composite_history.append(composite)

        # Keep only window size
        if len(self._composite_history) > self.window:
            self._composite_history = self._composite_history[-self.window:]

    def calculate_percentile(self, composite: float) -> float:
        """
        Calculate AURORA score from composite.

        This is the ONLY bounding mechanism in AURORA BMI.
        Maps any composite score to [0, 100].

        IMPORTANT: Score is INVERTED so that:
        - High composite (good breadth) → LOW score → GREEN
        - Low composite (poor breadth) → HIGH score → RED

        Args:
            composite: Raw composite score (S_BMI)

        Returns:
            AURORA score in [0, 100] (inverted percentile)
        """
        if len(self._composite_history) < 10:
            # Fallback for insufficient history
            # Use sigmoid scaling centered at 0
            logger.warning(
                f"Insufficient composite history ({len(self._composite_history)}), "
                "using sigmoid fallback"
            )
            from aurora.normalization.methods import sigmoid_scale
            # Invert: high composite → low score
            return 100 - (sigmoid_scale(composite, midpoint=0.0, steepness=0.5) * 100)

        # Calculate percentile
        pct = percentile_rank(composite, self._composite_history)

        # Handle edge cases: when composite is outside historical range,
        # use sigmoid blending to give meaningful values (not hard 0/100)
        if pct <= 1.0 or pct >= 99.0:
            import numpy as np

            from aurora.normalization.methods import sigmoid_scale

            # Calculate historical mean and std for sigmoid scaling
            hist_mean = float(np.mean(self._composite_history))
            hist_std = float(np.std(self._composite_history))

            if hist_std > 0:
                # Sigmoid scale with historical parameters
                sigmoid_pct = sigmoid_scale(
                    composite,
                    midpoint=hist_mean,
                    steepness=1.0 / hist_std
                ) * 100

                # Blend: use sigmoid when at extremes, clamped to [1, 99]
                if pct <= 1.0:
                    pct = max(1.0, min(25.0, sigmoid_pct))
                else:
                    pct = min(99.0, max(75.0, sigmoid_pct))

                logger.info(
                    f"Extreme composite {composite:.4f}, "
                    f"percentile adjusted to {pct:.1f}%"
                )

        # INVERT: high composite (good) → low score (GREEN)
        return 100 - pct

    def get_summary(self) -> dict[str, Any]:
        """
        Get summary of pipeline state.

        Returns:
            Dict with status of each feature
        """
        return {
            "feature_stats": self._calculator.summary(),
            "ready_features": self._calculator.get_ready_features(),
            "not_ready_features": self._calculator.get_not_ready_features(),
            "composite_history_count": len(self._composite_history),
        }
