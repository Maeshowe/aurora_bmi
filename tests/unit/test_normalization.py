"""
Tests for normalization methods.

CRITICAL: These tests verify that z-scores are NOT clipped.
Extreme values must be preserved for proper tail detection.
"""

import pytest

from aurora.normalization.methods import (
    percentile_rank,
    zscore_normalize,
)
from aurora.normalization.rolling import RollingStats


class TestZScoreNormalization:
    """Tests for z-score normalization."""

    def test_basic_zscore(self):
        """Test basic z-score calculation."""
        z = zscore_normalize(value=75, mean=50, std=10)
        assert z == pytest.approx(2.5)

    def test_zero_std(self):
        """Test handling of zero standard deviation."""
        z = zscore_normalize(value=50, mean=50, std=0)
        assert z == 0.0

    def test_no_clipping_positive(self):
        """CRITICAL: Verify z-scores are NOT clipped at +3σ."""
        z = zscore_normalize(value=100, mean=50, std=10)
        # Should be 5.0, NOT clipped to 3.0
        assert z == pytest.approx(5.0)
        assert z > 3.0  # Explicitly verify no clipping

    def test_no_clipping_negative(self):
        """CRITICAL: Verify z-scores are NOT clipped at -3σ."""
        z = zscore_normalize(value=0, mean=50, std=10)
        # Should be -5.0, NOT clipped to -3.0
        assert z == pytest.approx(-5.0)
        assert z < -3.0  # Explicitly verify no clipping

    def test_extreme_positive_preserved(self):
        """CRITICAL: Extreme positive z-scores preserved."""
        z = zscore_normalize(value=150, mean=50, std=10)
        assert z == pytest.approx(10.0)
        # This would be clipped to 3.0 if clipping was applied
        assert z > 9.0

    def test_extreme_negative_preserved(self):
        """CRITICAL: Extreme negative z-scores preserved."""
        z = zscore_normalize(value=-50, mean=50, std=10)
        assert z == pytest.approx(-10.0)
        # This would be clipped to -3.0 if clipping was applied
        assert z < -9.0


class TestPercentileRank:
    """Tests for percentile ranking (ONLY bounding mechanism)."""

    def test_basic_percentile(self):
        """Test basic percentile ranking."""
        history = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        p = percentile_rank(5.5, history)
        # 5.5 is greater than 5 values
        assert p == pytest.approx(50.0)

    def test_percentile_minimum(self):
        """Test percentile at minimum."""
        history = [5, 6, 7, 8, 9, 10]
        p = percentile_rank(4, history)
        # 4 is less than all values
        assert p == pytest.approx(0.0)

    def test_percentile_maximum(self):
        """Test percentile at maximum."""
        history = [1, 2, 3, 4, 5]
        p = percentile_rank(6, history)
        # 6 is greater than all values
        assert p == pytest.approx(100.0)

    def test_empty_history(self):
        """Test percentile with empty history."""
        p = percentile_rank(5, [])
        # Should return middle value as fallback
        assert p == pytest.approx(50.0)

    def test_bounds_0_to_100(self):
        """Test that percentile is always in [0, 100]."""
        history = list(range(100))

        p_low = percentile_rank(-100, history)
        assert 0 <= p_low <= 100

        p_high = percentile_rank(200, history)
        assert 0 <= p_high <= 100


class TestRollingStats:
    """Tests for rolling statistics."""

    def test_insufficient_data(self):
        """Test that insufficient data is flagged."""
        stats = RollingStats(feature_name="test", min_observations=21)

        for i in range(15):
            stats.add(float(i), None)

        assert not stats.is_ready
        assert stats.count == 15
        assert stats.mean is None
        assert stats.std is None

    def test_sufficient_data(self):
        """Test calculation with sufficient data."""
        stats = RollingStats(feature_name="test", min_observations=21)

        for i in range(30):
            stats.add(float(i), None)

        assert stats.is_ready
        assert stats.count == 30
        assert stats.mean is not None
        assert stats.std is not None

    def test_rolling_window(self):
        """Test that rolling window is respected."""
        stats = RollingStats(feature_name="test", window=10, min_observations=5)

        for i in range(20):
            stats.add(float(i), None)

        # Should only keep last 10 values
        assert stats.count == 10
        # Mean of 10-19 is 14.5
        assert stats.mean == pytest.approx(14.5)
