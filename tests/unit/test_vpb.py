"""Tests for Volume Participation Breadth (VPB) calculator."""

import pytest

from aurora.features.vpb import VolumeParticipationBreadth


class TestVPB:
    """Tests for VPB calculation."""

    def test_basic_calculation(self):
        """Test basic VPB calculation."""
        vpb = VolumeParticipationBreadth()
        result = vpb.calculate(v_adv=3_000, v_dec=1_000)

        assert result.is_valid
        assert result.value == pytest.approx(0.75)
        assert result.v_adv == 3_000
        assert result.v_dec == 1_000
        assert result.total_volume == 4_000

    def test_zero_volume(self):
        """Test handling of zero total volume."""
        vpb = VolumeParticipationBreadth()
        result = vpb.calculate(v_adv=0, v_dec=0)

        assert not result.is_valid
        assert result.value is None
        assert "zero" in result.message.lower()

    def test_all_advancing(self):
        """Test when all volume is advancing."""
        vpb = VolumeParticipationBreadth()
        result = vpb.calculate(v_adv=1_000, v_dec=0)

        assert result.is_valid
        assert result.value == 1.0

    def test_all_declining(self):
        """Test when all volume is declining."""
        vpb = VolumeParticipationBreadth()
        result = vpb.calculate(v_adv=0, v_dec=1_000)

        assert result.is_valid
        assert result.value == 0.0

    def test_equal_volume(self):
        """Test when advancing equals declining."""
        vpb = VolumeParticipationBreadth()
        result = vpb.calculate(v_adv=500, v_dec=500)

        assert result.is_valid
        assert result.value == 0.5

    def test_missing_data(self):
        """Test handling of missing data."""
        vpb = VolumeParticipationBreadth()

        result1 = vpb.calculate(v_adv=None, v_dec=1_000)
        assert not result1.is_valid

        result2 = vpb.calculate(v_adv=1_000, v_dec=None)
        assert not result2.is_valid

    def test_negative_volume(self):
        """Test handling of negative volume (data error)."""
        vpb = VolumeParticipationBreadth()
        result = vpb.calculate(v_adv=-100, v_dec=1_000)

        assert not result.is_valid
        assert "negative" in result.message.lower()

    def test_interpretation(self):
        """Test VPB interpretation."""
        vpb = VolumeParticipationBreadth()

        assert "strong" in vpb.interpret(0.8).lower()
        assert "moderate" in vpb.interpret(0.6).lower()
        assert "balanced" in vpb.interpret(0.5).lower()
        assert "declining" in vpb.interpret(0.3).lower()
