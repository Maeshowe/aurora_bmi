"""
Structural Breadth Confirmation (SBC) calculator.

SBC uses slow structural metrics to confirm breadth conditions.
It answers: "Is the breadth structurally sound?"

Formula:
    SBC_t = (pct_MA50 + pct_MA200) / 2

Where:
    pct_MA50 = Percentage of stocks above their 50-day MA
    pct_MA200 = Percentage of stocks above their 200-day MA

Interpretation:
    - SBC > 60%: Strong structural breadth
    - SBC 40-60%: Moderate structural breadth
    - SBC < 40%: Weak structural breadth

Design Note:
    SBC is a "slow" indicator compared to VPB/IPB.
    It confirms whether the underlying structure supports
    the current participation levels.
"""

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class SBCResult:
    """Result of SBC calculation."""

    value: float | None
    pct_ma50: float | None
    pct_ma200: float | None
    is_valid: bool
    message: str = ""


class StructuralBreadthConfirmation:
    """
    Structural Breadth Confirmation calculator.

    Uses slow structural metrics (% above moving averages)
    to confirm market breadth conditions.
    """

    NAME = "SBC"

    def calculate(
        self,
        pct_ma50: float | None,
        pct_ma200: float | None,
    ) -> SBCResult:
        """
        Calculate Structural Breadth Confirmation.

        Args:
            pct_ma50: Percentage of stocks above 50-day MA (0-100)
            pct_ma200: Percentage of stocks above 200-day MA (0-100)

        Returns:
            SBCResult with calculated value or None if invalid
        """
        # Handle missing data
        if pct_ma50 is None and pct_ma200 is None:
            return SBCResult(
                value=None,
                pct_ma50=None,
                pct_ma200=None,
                is_valid=False,
                message="Missing both MA50 and MA200 breadth data",
            )

        # Handle partial data - use what's available
        if pct_ma50 is None:
            logger.info("MA50 breadth missing, using MA200 only")
            return SBCResult(
                value=pct_ma200 / 100.0 if pct_ma200 else None,  # Normalize to [0, 1]
                pct_ma50=None,
                pct_ma200=pct_ma200,
                is_valid=pct_ma200 is not None,
                message="Using MA200 breadth only (MA50 missing)",
            )

        if pct_ma200 is None:
            logger.info("MA200 breadth missing, using MA50 only")
            return SBCResult(
                value=pct_ma50 / 100.0 if pct_ma50 else None,  # Normalize to [0, 1]
                pct_ma50=pct_ma50,
                pct_ma200=None,
                is_valid=pct_ma50 is not None,
                message="Using MA50 breadth only (MA200 missing)",
            )

        # Validate ranges
        if not (0 <= pct_ma50 <= 100) or not (0 <= pct_ma200 <= 100):
            logger.warning(
                f"MA breadth out of range: pct_ma50={pct_ma50}, pct_ma200={pct_ma200}"
            )
            return SBCResult(
                value=None,
                pct_ma50=pct_ma50,
                pct_ma200=pct_ma200,
                is_valid=False,
                message="MA breadth values out of expected range [0, 100]",
            )

        # Calculate SBC (average of both, normalized to [0, 1])
        sbc = ((pct_ma50 + pct_ma200) / 2) / 100.0

        return SBCResult(
            value=sbc,
            pct_ma50=pct_ma50,
            pct_ma200=pct_ma200,
            is_valid=True,
        )

    def interpret(self, sbc: float) -> str:
        """
        Provide interpretation of SBC value.

        Args:
            sbc: SBC value in [0, 1]

        Returns:
            Human-readable interpretation
        """
        pct = sbc * 100  # Convert to percentage for interpretation

        if pct > 70:
            return "Strong structural breadth (majority above both MAs)"
        elif pct > 55:
            return "Moderately strong structural breadth"
        elif pct > 45:
            return "Neutral structural breadth"
        elif pct > 30:
            return "Moderately weak structural breadth"
        else:
            return "Weak structural breadth (minority above MAs)"

    def assess_ma_divergence(
        self,
        pct_ma50: float,
        pct_ma200: float,
    ) -> tuple[float, str]:
        """
        Assess divergence between MA50 and MA200 breadth.

        Large divergence can indicate market transition.

        Args:
            pct_ma50: % above 50-day MA
            pct_ma200: % above 200-day MA

        Returns:
            Tuple of (divergence, interpretation)
        """
        divergence = pct_ma50 - pct_ma200

        if divergence > 15:
            interpretation = (
                "MA50 > MA200 breadth: Short-term breadth improving. "
                "Possible early recovery or momentum building."
            )
        elif divergence < -15:
            interpretation = (
                "MA200 > MA50 breadth: Short-term breadth deteriorating. "
                "Possible distribution or weakening momentum."
            )
        else:
            interpretation = "MA50 ≈ MA200 breadth: Structural breadth aligned."

        return divergence, interpretation
