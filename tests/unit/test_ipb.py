"""Tests for Issue Participation Breadth (IPB) calculator."""

import pytest

from aurora.features.ipb import IssueParticipationBreadth


class TestIPB:
    """Tests for IPB calculation."""

    def test_basic_calculation(self):
        """Test basic IPB calculation."""
        ipb = IssueParticipationBreadth()
        result = ipb.calculate(n_adv=300, n_dec=200)

        assert result.is_valid
        assert result.value == pytest.approx(0.6)
        assert result.n_adv == 300
        assert result.n_dec == 200
        assert result.total_issues == 500

    def test_zero_issues(self):
        """Test handling of zero total issues."""
        ipb = IssueParticipationBreadth()
        result = ipb.calculate(n_adv=0, n_dec=0)

        assert not result.is_valid
        assert result.value is None

    def test_all_advancing(self):
        """Test when all issues are advancing."""
        ipb = IssueParticipationBreadth()
        result = ipb.calculate(n_adv=500, n_dec=0)

        assert result.is_valid
        assert result.value == 1.0

    def test_all_declining(self):
        """Test when all issues are declining."""
        ipb = IssueParticipationBreadth()
        result = ipb.calculate(n_adv=0, n_dec=500)

        assert result.is_valid
        assert result.value == 0.0

    def test_divergence_calculation(self):
        """Test VPB/IPB divergence calculation."""
        ipb = IssueParticipationBreadth()

        # VPB high, IPB low (narrow leadership)
        divergence, interpretation = ipb.calculate_divergence(
            ipb=0.4, vpb=0.7
        )
        assert divergence == pytest.approx(0.3)
        assert "mega-cap" in interpretation.lower()

        # IPB high, VPB low (broad but weak)
        divergence, interpretation = ipb.calculate_divergence(
            ipb=0.7, vpb=0.4
        )
        assert divergence == pytest.approx(-0.3)
        assert "broad" in interpretation.lower()

        # Aligned
        divergence, interpretation = ipb.calculate_divergence(
            ipb=0.5, vpb=0.5
        )
        assert abs(divergence) < 0.11
        assert "aligned" in interpretation.lower()
