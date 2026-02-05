"""
Volume Participation Breadth (VPB) calculator.

VPB measures the dollar-weighted participation in market direction.
It answers: "Where is the MONEY going?"

Formula:
    VPB_t = V_adv / (V_adv + V_dec)

Where:
    V_adv = Total volume of advancing stocks
    V_dec = Total volume of declining stocks

Interpretation:
    - VPB > 0.5: More volume in advancing stocks
    - VPB < 0.5: More volume in declining stocks
    - VPB = 0.5: Equal volume distribution

Design Note:
    VPB correlates with IPB but measures a different dimension.
    VPB is dollar-weighted, IPB is count-weighted.
    Divergence (VPB high, IPB low) indicates narrow, mega-cap leadership.
    This is a MONITORED DIAGNOSTIC PROPERTY, not an error.
"""

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class VPBResult:
    """Result of VPB calculation."""

    value: float | None
    v_adv: float
    v_dec: float
    total_volume: float
    is_valid: bool
    message: str = ""


class VolumeParticipationBreadth:
    """
    Volume Participation Breadth calculator.

    Measures dollar-weighted market participation.
    """

    NAME = "VPB"

    def calculate(
        self,
        v_adv: float | None,
        v_dec: float | None,
    ) -> VPBResult:
        """
        Calculate Volume Participation Breadth.

        Args:
            v_adv: Advancing volume (total volume of advancing stocks)
            v_dec: Declining volume (total volume of declining stocks)

        Returns:
            VPBResult with calculated value or None if invalid
        """
        # Handle missing data
        if v_adv is None or v_dec is None:
            return VPBResult(
                value=None,
                v_adv=0.0,
                v_dec=0.0,
                total_volume=0.0,
                is_valid=False,
                message="Missing advancing or declining volume data",
            )

        # Handle negative values (data error)
        if v_adv < 0 or v_dec < 0:
            logger.warning(f"Negative volume detected: v_adv={v_adv}, v_dec={v_dec}")
            return VPBResult(
                value=None,
                v_adv=v_adv,
                v_dec=v_dec,
                total_volume=v_adv + v_dec,
                is_valid=False,
                message="Negative volume values detected",
            )

        total_volume = v_adv + v_dec

        # Handle zero total volume (market closed or no data)
        if total_volume == 0:
            return VPBResult(
                value=None,
                v_adv=0.0,
                v_dec=0.0,
                total_volume=0.0,
                is_valid=False,
                message="Total volume is zero",
            )

        # Calculate VPB
        vpb = v_adv / total_volume

        return VPBResult(
            value=vpb,
            v_adv=v_adv,
            v_dec=v_dec,
            total_volume=total_volume,
            is_valid=True,
        )

    def interpret(self, vpb: float) -> str:
        """
        Provide interpretation of VPB value.

        Args:
            vpb: VPB value in [0, 1]

        Returns:
            Human-readable interpretation
        """
        if vpb > 0.7:
            return "Strong volume participation in advancing stocks"
        elif vpb > 0.55:
            return "Moderate volume participation favoring advances"
        elif vpb > 0.45:
            return "Balanced volume participation"
        elif vpb > 0.3:
            return "Moderate volume participation favoring declines"
        else:
            return "Strong volume participation in declining stocks"
