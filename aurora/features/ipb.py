"""
Issue Participation Breadth (IPB) calculator.

IPB measures the count-weighted participation in market direction.
It answers: "How BROAD is participation?"

Formula:
    IPB_t = N_adv / (N_adv + N_dec)

Where:
    N_adv = Number of advancing stocks
    N_dec = Number of declining stocks

Interpretation:
    - IPB > 0.5: More stocks advancing than declining
    - IPB < 0.5: More stocks declining than advancing
    - IPB = 0.5: Equal number of advancers and decliners

Design Note:
    IPB correlates with VPB but measures a different dimension.
    IPB is count-weighted (breadth), VPB is dollar-weighted (money flow).

    VPB/IPB Divergence is a MONITORED DIAGNOSTIC PROPERTY:
    - VPB high + IPB low = Narrow leadership (mega-cap driven rally)
    - VPB low + IPB high = Broad but weak participation
    - Both high = Healthy broad rally
    - Both low = Broad weakness
"""

import logging
from dataclasses import dataclass


logger = logging.getLogger(__name__)


@dataclass
class IPBResult:
    """Result of IPB calculation."""

    value: float | None
    n_adv: int
    n_dec: int
    total_issues: int
    is_valid: bool
    message: str = ""


class IssueParticipationBreadth:
    """
    Issue Participation Breadth calculator.

    Measures count-weighted market participation (breadth).
    """

    NAME = "IPB"

    def calculate(
        self,
        n_adv: int | None,
        n_dec: int | None,
    ) -> IPBResult:
        """
        Calculate Issue Participation Breadth.

        Args:
            n_adv: Number of advancing issues
            n_dec: Number of declining issues

        Returns:
            IPBResult with calculated value or None if invalid
        """
        # Handle missing data
        if n_adv is None or n_dec is None:
            return IPBResult(
                value=None,
                n_adv=0,
                n_dec=0,
                total_issues=0,
                is_valid=False,
                message="Missing advancing or declining issue counts",
            )

        # Handle negative values (data error)
        if n_adv < 0 or n_dec < 0:
            logger.warning(f"Negative count detected: n_adv={n_adv}, n_dec={n_dec}")
            return IPBResult(
                value=None,
                n_adv=n_adv,
                n_dec=n_dec,
                total_issues=n_adv + n_dec,
                is_valid=False,
                message="Negative issue counts detected",
            )

        total_issues = n_adv + n_dec

        # Handle zero total issues (market closed or no data)
        if total_issues == 0:
            return IPBResult(
                value=None,
                n_adv=0,
                n_dec=0,
                total_issues=0,
                is_valid=False,
                message="Total issue count is zero",
            )

        # Calculate IPB
        ipb = n_adv / total_issues

        return IPBResult(
            value=ipb,
            n_adv=n_adv,
            n_dec=n_dec,
            total_issues=total_issues,
            is_valid=True,
        )

    def interpret(self, ipb: float) -> str:
        """
        Provide interpretation of IPB value.

        Args:
            ipb: IPB value in [0, 1]

        Returns:
            Human-readable interpretation
        """
        if ipb > 0.7:
            return "Strongly broad participation (many more advancers)"
        elif ipb > 0.55:
            return "Moderately broad participation"
        elif ipb > 0.45:
            return "Balanced breadth"
        elif ipb > 0.3:
            return "Moderately narrow participation"
        else:
            return "Strongly narrow participation (many more decliners)"

    def calculate_divergence(
        self,
        ipb: float,
        vpb: float,
    ) -> tuple[float, str]:
        """
        Calculate VPB/IPB divergence.

        This is a diagnostic property, not an error.

        Args:
            ipb: Issue Participation Breadth value
            vpb: Volume Participation Breadth value

        Returns:
            Tuple of (divergence value, interpretation)
        """
        divergence = vpb - ipb

        if divergence > 0.1:
            interpretation = (
                "VPB > IPB: Volume breadth exceeds issue breadth. "
                "Suggests mega-cap driven, narrow leadership."
            )
        elif divergence < -0.1:
            interpretation = (
                "IPB > VPB: Issue breadth exceeds volume breadth. "
                "Suggests broad but weak participation."
            )
        else:
            interpretation = "VPB ≈ IPB: Volume and issue breadth aligned."

        return divergence, interpretation
