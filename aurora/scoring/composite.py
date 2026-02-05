"""
Composite score calculation for AURORA BMI.

Formula:
    S_BMI = 0.30 * Z_VPB + 0.25 * Z_IPB + 0.25 * Z_SBC + 0.20 * Z_IPO

These weights are FROZEN conceptual allocations, NOT optimized parameters.
Do not tune these values.
"""

import logging

from aurora.core.constants import WEIGHTS
from aurora.core.types import ScoreComponent

logger = logging.getLogger(__name__)


def calculate_composite(
    z_scores: dict[str, float],
) -> tuple[float, list[ScoreComponent]]:
    """
    Calculate composite BMI score from z-scores.

    Args:
        z_scores: Dict of feature name -> z-score (NOT clipped)

    Returns:
        Tuple of:
        - raw composite score (S_BMI)
        - list of ScoreComponents with contributions
    """
    components: list[ScoreComponent] = []
    total_weight = 0.0
    weighted_sum = 0.0

    for name, weight in WEIGHTS.items():
        z = z_scores.get(name)

        if z is None:
            # Feature excluded - skip but don't count toward total weight
            logger.debug(f"Feature {name} not in z_scores, skipping")
            continue

        contribution = weight * z
        weighted_sum += contribution
        total_weight += weight

        components.append(
            ScoreComponent(
                name=name,
                weight=weight,
                raw_value=0.0,  # Will be filled by caller if needed
                zscore=z,  # NOT clipped
                contribution=contribution,
            )
        )

    # If not all features present, scale by actual weight used
    if total_weight > 0 and total_weight < 1.0:
        logger.info(
            f"Scaling composite by actual weight used: {total_weight:.2f}"
        )
        # Don't rescale - use actual weighted sum
        # This means partial baselines result in lower absolute scores

    composite = weighted_sum

    logger.debug(
        f"Composite score: {composite:.4f} "
        f"(from {len(components)} features, total_weight={total_weight:.2f})"
    )

    return composite, components


def get_component_contributions(
    components: list[ScoreComponent],
) -> dict[str, float]:
    """
    Get contribution percentages for each component.

    Args:
        components: List of ScoreComponents

    Returns:
        Dict of feature name -> contribution percentage
    """
    total_abs_contribution = sum(abs(c.contribution) for c in components)

    if total_abs_contribution == 0:
        return {c.name: 0.0 for c in components}

    return {
        c.name: (abs(c.contribution) / total_abs_contribution) * 100
        for c in components
    }


def get_top_drivers(
    components: list[ScoreComponent],
    n: int = 2,
) -> list[ScoreComponent]:
    """
    Get top N driving components by absolute z-score.

    Args:
        components: List of ScoreComponents
        n: Number of top drivers to return

    Returns:
        List of top N ScoreComponents by |zscore|
    """
    sorted_components = sorted(
        components,
        key=lambda c: abs(c.zscore),
        reverse=True,
    )
    return sorted_components[:n]


def assess_vpb_ipb_divergence(
    components: list[ScoreComponent],
) -> tuple[float | None, str]:
    """
    Assess VPB/IPB divergence from components.

    This is a MONITORED DIAGNOSTIC PROPERTY.

    Args:
        components: List of ScoreComponents

    Returns:
        Tuple of (divergence value, interpretation)
    """
    vpb_z = None
    ipb_z = None

    for c in components:
        if c.name == "VPB":
            vpb_z = c.zscore
        elif c.name == "IPB":
            ipb_z = c.zscore

    if vpb_z is None or ipb_z is None:
        return None, "Cannot assess divergence: missing VPB or IPB"

    divergence = vpb_z - ipb_z

    if divergence > 1.0:
        interpretation = (
            "VPB >> IPB: Strong divergence indicating narrow, "
            "mega-cap driven leadership. Volume concentrated in few names."
        )
    elif divergence > 0.5:
        interpretation = (
            "VPB > IPB: Moderate divergence suggesting somewhat narrow breadth."
        )
    elif divergence < -1.0:
        interpretation = (
            "IPB >> VPB: Strong divergence indicating broad but weak participation. "
            "Many stocks participating but with low volume."
        )
    elif divergence < -0.5:
        interpretation = (
            "IPB > VPB: Moderate divergence suggesting broad but lighter participation."
        )
    else:
        interpretation = "VPB ≈ IPB: Volume and issue breadth aligned."

    return divergence, interpretation
