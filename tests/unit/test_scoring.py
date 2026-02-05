"""Tests for scoring module."""

import pytest

from aurora.core.types import Band
from aurora.scoring.composite import calculate_composite, get_top_drivers


class TestCompositeScore:
    """Tests for composite score calculation."""

    def test_basic_composite(self, sample_z_scores):
        """Test basic composite calculation."""
        composite, components = calculate_composite(sample_z_scores)

        # Expected: 0.30*1.5 + 0.25*1.0 + 0.25*(-0.5) + 0.20*0.8
        # = 0.45 + 0.25 - 0.125 + 0.16 = 0.735
        assert composite == pytest.approx(0.735)
        assert len(components) == 4

    def test_missing_features(self):
        """Test composite with missing features."""
        z_scores = {"VPB": 1.0, "IPB": 0.5}  # SBC and IPO missing

        composite, components = calculate_composite(z_scores)

        assert len(components) == 2
        # Only VPB and IPB contribute
        assert composite == pytest.approx(0.30 * 1.0 + 0.25 * 0.5)

    def test_no_clipping_in_composite(self, extreme_z_scores):
        """CRITICAL: Verify extreme z-scores flow through to composite."""
        composite, components = calculate_composite(extreme_z_scores)

        # Verify extreme z-scores are preserved in components
        vpb_comp = next(c for c in components if c.name == "VPB")
        ipb_comp = next(c for c in components if c.name == "IPB")

        assert vpb_comp.zscore == pytest.approx(4.5)  # NOT clipped
        assert ipb_comp.zscore == pytest.approx(-5.0)  # NOT clipped

    def test_top_drivers(self, sample_z_scores):
        """Test identification of top drivers."""
        _, components = calculate_composite(sample_z_scores)
        top = get_top_drivers(components, n=2)

        # VPB (1.5) and IPB (1.0) should be top by |zscore|
        assert len(top) == 2
        assert top[0].name == "VPB"  # Highest |zscore|
        assert top[1].name == "IPB"  # Second highest


class TestBandClassification:
    """Tests for band classification."""

    def test_green_band(self):
        """Test GREEN band (0-25)."""
        assert Band.from_score(0) == Band.GREEN
        assert Band.from_score(12.5) == Band.GREEN
        assert Band.from_score(25) == Band.GREEN

    def test_light_green_band(self):
        """Test LIGHT_GREEN band (25-50)."""
        assert Band.from_score(26) == Band.LIGHT_GREEN
        assert Band.from_score(37.5) == Band.LIGHT_GREEN
        assert Band.from_score(50) == Band.LIGHT_GREEN

    def test_yellow_band(self):
        """Test YELLOW band (50-75)."""
        assert Band.from_score(51) == Band.YELLOW
        assert Band.from_score(62.5) == Band.YELLOW
        assert Band.from_score(75) == Band.YELLOW

    def test_red_band(self):
        """Test RED band (75-100)."""
        assert Band.from_score(76) == Band.RED
        assert Band.from_score(87.5) == Band.RED
        assert Band.from_score(100) == Band.RED

    def test_boundary_conditions(self):
        """Test exact boundary values."""
        # At boundaries, should be in lower band
        assert Band.from_score(25) == Band.GREEN
        assert Band.from_score(50) == Band.LIGHT_GREEN
        assert Band.from_score(75) == Band.YELLOW

        # Just above boundaries
        assert Band.from_score(25.01) == Band.LIGHT_GREEN
        assert Band.from_score(50.01) == Band.YELLOW
        assert Band.from_score(75.01) == Band.RED
