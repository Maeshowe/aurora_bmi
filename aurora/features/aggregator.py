"""
Feature aggregator for AURORA BMI.

Combines all feature calculations into a unified FeatureSet.
"""

import logging
from datetime import date

from aurora.core.types import FeatureSet
from aurora.features.ipb import IssueParticipationBreadth
from aurora.features.ipo import InstitutionalParticipationOverlay
from aurora.features.sbc import StructuralBreadthConfirmation
from aurora.features.vpb import VolumeParticipationBreadth

logger = logging.getLogger(__name__)


class FeatureAggregator:
    """
    Aggregates all breadth features into a unified FeatureSet.

    This is the main entry point for feature extraction.
    """

    def __init__(self) -> None:
        """Initialize feature calculators."""
        self.vpb_calc = VolumeParticipationBreadth()
        self.ipb_calc = IssueParticipationBreadth()
        self.sbc_calc = StructuralBreadthConfirmation()
        self.ipo_calc = InstitutionalParticipationOverlay()

    def calculate(
        self,
        trade_date: date,
        v_adv: float | None = None,
        v_dec: float | None = None,
        n_adv: int | None = None,
        n_dec: int | None = None,
        pct_ma50: float | None = None,
        pct_ma200: float | None = None,
        rel_vol_values: list[float] | None = None,
        universe_median_relvol: float | None = None,
    ) -> FeatureSet:
        """
        Calculate all features and return a FeatureSet.

        Args:
            trade_date: Date for this calculation
            v_adv: Advancing volume
            v_dec: Declining volume
            n_adv: Advancing issues count
            n_dec: Declining issues count
            pct_ma50: % of stocks above 50-day MA
            pct_ma200: % of stocks above 200-day MA
            rel_vol_values: Per-stock relative volume values
            universe_median_relvol: Universe median relative volume

        Returns:
            FeatureSet with all calculated features
        """
        # Calculate VPB
        vpb_result = self.vpb_calc.calculate(v_adv, v_dec)
        vpb = vpb_result.value

        # Calculate IPB
        ipb_result = self.ipb_calc.calculate(n_adv, n_dec)
        ipb = ipb_result.value

        # Calculate SBC
        sbc_result = self.sbc_calc.calculate(pct_ma50, pct_ma200)
        sbc = sbc_result.value

        # Calculate IPO
        ipo_result = self.ipo_calc.calculate_simple(
            rel_vol_values,
            threshold=2.0,  # Default threshold
        )
        ipo = ipo_result.value

        # Log calculation status
        features_status = {
            "VPB": "OK" if vpb is not None else "MISSING",
            "IPB": "OK" if ipb is not None else "MISSING",
            "SBC": "OK" if sbc is not None else "MISSING",
            "IPO": "OK" if ipo is not None else "MISSING",
        }
        logger.info(f"Feature calculation status: {features_status}")

        # Create and return FeatureSet
        return FeatureSet(
            trade_date=trade_date,
            v_adv=v_adv,
            v_dec=v_dec,
            n_adv=n_adv,
            n_dec=n_dec,
            pct_ma50=pct_ma50,
            pct_ma200=pct_ma200,
            rel_vol_values=rel_vol_values,
            universe_median_relvol=universe_median_relvol or ipo_result.universe_median,
            vpb=vpb,
            ipb=ipb,
            sbc=sbc,
            ipo=ipo,
        )

    def from_raw_data(
        self,
        trade_date: date,
        polygon_breadth: dict | None = None,
        ma_breadth: dict | None = None,
        volume_data: dict | None = None,
    ) -> FeatureSet:
        """
        Create FeatureSet from raw API response data.

        Args:
            trade_date: Date for this calculation
            polygon_breadth: Dict with v_adv, v_dec, n_adv, n_dec
            ma_breadth: Dict with pct_ma50, pct_ma200
            volume_data: Dict with rel_vol_values, universe_median

        Returns:
            FeatureSet with all calculated features
        """
        polygon_breadth = polygon_breadth or {}
        ma_breadth = ma_breadth or {}
        volume_data = volume_data or {}

        # Cross-section sanity check: warn if distribution collapses
        if polygon_breadth:
            self._check_distribution_collapse(polygon_breadth)

        return self.calculate(
            trade_date=trade_date,
            v_adv=polygon_breadth.get("v_adv"),
            v_dec=polygon_breadth.get("v_dec"),
            n_adv=polygon_breadth.get("n_adv"),
            n_dec=polygon_breadth.get("n_dec"),
            pct_ma50=ma_breadth.get("pct_ma50"),
            pct_ma200=ma_breadth.get("pct_ma200"),
            rel_vol_values=volume_data.get("rel_vol_values"),
            universe_median_relvol=volume_data.get("universe_median"),
        )

    def get_valid_features(self, feature_set: FeatureSet) -> dict[str, float]:
        """
        Get dict of valid (non-None) features.

        Args:
            feature_set: FeatureSet to extract from

        Returns:
            Dict of feature name -> value for valid features
        """
        features = {
            "VPB": feature_set.vpb,
            "IPB": feature_set.ipb,
            "SBC": feature_set.sbc,
            "IPO": feature_set.ipo,
        }
        return {k: v for k, v in features.items() if v is not None}

    def get_missing_features(self, feature_set: FeatureSet) -> list[str]:
        """
        Get list of missing (None) features.

        Args:
            feature_set: FeatureSet to check

        Returns:
            List of missing feature names
        """
        features = {
            "VPB": feature_set.vpb,
            "IPB": feature_set.ipb,
            "SBC": feature_set.sbc,
            "IPO": feature_set.ipo,
        }
        return [k for k, v in features.items() if v is None]

    def calculate_vpb_ipb_divergence(
        self,
        feature_set: FeatureSet,
    ) -> tuple[float | None, str]:
        """
        Calculate VPB/IPB divergence.

        This is a MONITORED DIAGNOSTIC PROPERTY.

        Args:
            feature_set: FeatureSet with calculated features

        Returns:
            Tuple of (divergence value, interpretation)
        """
        if feature_set.vpb is None or feature_set.ipb is None:
            return None, "Cannot calculate divergence: missing VPB or IPB"

        return self.ipb_calc.calculate_divergence(feature_set.ipb, feature_set.vpb)

    def _check_distribution_collapse(self, breadth: dict) -> None:
        """
        Warn if breadth distribution collapses (crisis indicator).

        A collapse occurs when >90% or <10% of issues are advancing,
        indicating extreme one-sided market conditions.

        Args:
            breadth: Dict with n_adv and n_dec counts
        """
        n_adv = breadth.get("n_adv") or 0
        n_dec = breadth.get("n_dec") or 0
        total = n_adv + n_dec

        if total > 0:
            adv_ratio = n_adv / total
            # Collapse = extreme one-sided breadth (>90% or <10%)
            if adv_ratio > 0.90:
                logger.warning(
                    f"Distribution collapse detected: {adv_ratio*100:.1f}% advancing "
                    f"({n_adv}/{total}) - near-universal participation"
                )
            elif adv_ratio < 0.10:
                logger.warning(
                    f"Distribution collapse detected: {adv_ratio*100:.1f}% advancing "
                    f"({n_adv}/{total}) - near-universal non-participation"
                )
