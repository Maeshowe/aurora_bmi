"""Tests for Institutional Participation Overlay (IPO) calculator."""

import pytest

from aurora.features.ipo import InstitutionalParticipationOverlay


class TestIPO:
    """Tests for IPO calculation with dual filter."""

    def test_dual_filter_both_conditions(self):
        """Test that dual filter requires BOTH conditions."""
        ipo = InstitutionalParticipationOverlay()

        # Values: [3.0, 1.5, 2.5, 0.8, 1.2]
        # Thresholds: [2.0, 2.0, 2.0, 2.0, 2.0]
        # Median: 1.5
        # Stock 0: 3.0 > 2.0 AND 3.0 > 1.5 -> counts
        # Stock 1: 1.5 < 2.0 -> doesn't count
        # Stock 2: 2.5 > 2.0 AND 2.5 > 1.5 -> counts
        # Stock 3: 0.8 < 2.0 -> doesn't count
        # Stock 4: 1.2 < 2.0 -> doesn't count

        result = ipo.calculate(
            rel_vol_values=[3.0, 1.5, 2.5, 0.8, 1.2],
            rel_vol_thresholds=[2.0, 2.0, 2.0, 2.0, 2.0],
            universe_median=1.5,
        )

        assert result.is_valid
        assert result.spike_count == 2
        assert result.value == pytest.approx(2 / 5)

    def test_exceeds_threshold_but_not_median(self):
        """Test stock exceeding threshold but not median doesn't count."""
        ipo = InstitutionalParticipationOverlay()

        # Stock has high threshold-relative volume but below median
        result = ipo.calculate(
            rel_vol_values=[2.5],  # Exceeds threshold (2.0)
            rel_vol_thresholds=[2.0],
            universe_median=3.0,  # But below median
        )

        assert result.is_valid
        assert result.spike_count == 0
        assert result.value == 0.0

    def test_exceeds_median_but_not_threshold(self):
        """Test stock exceeding median but not threshold doesn't count."""
        ipo = InstitutionalParticipationOverlay()

        # Stock has high median-relative volume but not threshold
        result = ipo.calculate(
            rel_vol_values=[1.8],  # Exceeds median
            rel_vol_thresholds=[2.0],  # But below threshold
            universe_median=1.5,
        )

        assert result.is_valid
        assert result.spike_count == 0
        assert result.value == 0.0

    def test_empty_values(self):
        """Test handling of empty values."""
        ipo = InstitutionalParticipationOverlay()

        result = ipo.calculate(
            rel_vol_values=[],
            rel_vol_thresholds=[],
        )

        assert not result.is_valid
        assert result.value is None

    def test_none_values(self):
        """Test handling of None values."""
        ipo = InstitutionalParticipationOverlay()

        result = ipo.calculate(
            rel_vol_values=None,
            rel_vol_thresholds=None,
        )

        assert not result.is_valid
        assert result.value is None

    def test_calculate_simple(self):
        """Test simplified calculation with fixed threshold."""
        ipo = InstitutionalParticipationOverlay()

        # Values: [3.0, 2.5, 1.5, 0.8, 1.2]
        # Fixed threshold: 2.0
        # Median will be calculated: 1.5
        # Stock 0: 3.0 > 2.0 AND 3.0 > 1.5 -> counts
        # Stock 1: 2.5 > 2.0 AND 2.5 > 1.5 -> counts
        # Stock 2: 1.5 < 2.0 -> doesn't count
        # Stock 3: 0.8 < 2.0 -> doesn't count
        # Stock 4: 1.2 < 2.0 -> doesn't count

        result = ipo.calculate_simple(
            rel_vol_values=[3.0, 2.5, 1.5, 0.8, 1.2],
            threshold=2.0,
        )

        assert result.is_valid
        assert result.spike_count == 2
        assert result.value == pytest.approx(0.4)
        assert result.universe_median == pytest.approx(1.5)

    def test_high_spike_ratio(self):
        """Test stocks with high values - dual filter limits max spike ratio.

        Note: With dual filter (must exceed BOTH threshold AND median),
        at most ~half the stocks can ever spike since by definition,
        half are below or equal to median.
        """
        ipo = InstitutionalParticipationOverlay()

        # Values: [6.0, 5.5, 5.0, 4.5, 4.0] - median = 5.0
        # All exceed threshold (2.0), but only 2 exceed median (5.0)
        result = ipo.calculate_simple(
            rel_vol_values=[6.0, 5.5, 5.0, 4.5, 4.0],
            threshold=2.0,
        )

        assert result.is_valid
        assert result.universe_median == pytest.approx(5.0)
        # Dual filter: 6.0 > 5.0 ✓, 5.5 > 5.0 ✓, rest ✗
        assert result.spike_count == 2
        assert result.value == pytest.approx(0.4)

    def test_no_stocks_spike(self):
        """Test when no stocks have spikes."""
        ipo = InstitutionalParticipationOverlay()

        result = ipo.calculate_simple(
            rel_vol_values=[0.5, 0.6, 0.7, 0.8, 0.9],
            threshold=2.0,
        )

        assert result.is_valid
        assert result.spike_count == 0
        assert result.value == 0.0
