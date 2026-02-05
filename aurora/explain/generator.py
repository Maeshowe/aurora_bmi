"""
Explanation generator for AURORA BMI.

Generates human-readable explanations of BMI results.
"""

import logging
from typing import Sequence

from aurora.core.constants import VPB_IPB_DIVERGENCE_WARN
from aurora.core.types import Band, BaselineStatus, ScoreComponent
from aurora.explain.templates import (
    BAND_TEMPLATES,
    DIVERGENCE_TEMPLATES,
    DRIVER_TEMPLATES,
    STATUS_TEMPLATES,
)


logger = logging.getLogger(__name__)


class ExplanationGenerator:
    """
    Generates human-readable explanations for AURORA BMI results.

    Combines:
    - Band-level interpretation
    - Top driver analysis
    - VPB/IPB divergence diagnostics
    - Baseline status notes
    """

    def __init__(self, include_design_notes: bool = False) -> None:
        """
        Initialize explanation generator.

        Args:
            include_design_notes: Include educational design notes in output
        """
        self.include_design_notes = include_design_notes

    def generate(
        self,
        band: Band,
        components: Sequence[ScoreComponent],
        excluded: Sequence[str],
        status: BaselineStatus,
    ) -> str:
        """
        Generate complete explanation.

        Args:
            band: Classification band
            components: Score components
            excluded: Excluded feature names
            status: Baseline status

        Returns:
            Human-readable explanation (structured with newlines)
        """
        lines: list[str] = []

        # 1. Base band interpretation (headline)
        band_text = BAND_TEMPLATES.get(band, "")
        if band_text:
            lines.append(f"**Status:** {band_text}")

        # 2. Top drivers (bulleted list)
        driver_lines = self._format_drivers_structured(components)
        if driver_lines:
            lines.append("")
            lines.append("**Primary Drivers:**")
            lines.extend(driver_lines)

        # 3. VPB/IPB divergence if significant
        divergence_text = self._format_divergence(components)
        if divergence_text:
            lines.append("")
            lines.append(f"**Note:** {divergence_text}")

        # 4. Status notes / warnings
        status_text = STATUS_TEMPLATES.get(status.value, "")
        if status_text or excluded:
            lines.append("")
            if status_text:
                lines.append(f"**Warning:** {status_text}")
            if excluded:
                lines.append(f"**Excluded:** {', '.join(excluded)}")

        return "\n".join(lines)

    def _format_drivers_structured(
        self,
        components: Sequence[ScoreComponent],
        n: int = 2,
    ) -> list[str]:
        """
        Format top N drivers as bullet points.

        Args:
            components: Score components
            n: Number of drivers to include

        Returns:
            List of formatted driver lines
        """
        if not components:
            return []

        # Sort by absolute z-score
        sorted_comps = sorted(
            components,
            key=lambda c: abs(c.zscore),
            reverse=True,
        )[:n]

        lines = []
        for comp in sorted_comps:
            direction = comp.direction
            template = DRIVER_TEMPLATES.get(comp.name, {}).get(
                direction,
                f"{comp.name} is {direction}",
            )
            arrow = "↑" if comp.zscore > 0 else "↓" if comp.zscore < 0 else "→"
            lines.append(f"• {template} ({comp.zscore:+.1f}σ {arrow})")

        return lines

    def _format_drivers(
        self,
        components: Sequence[ScoreComponent],
        n: int = 2,
    ) -> str:
        """
        Format top N drivers.

        Args:
            components: Score components
            n: Number of drivers to include

        Returns:
            Formatted driver text
        """
        if not components:
            return ""

        # Sort by absolute z-score
        sorted_comps = sorted(
            components,
            key=lambda c: abs(c.zscore),
            reverse=True,
        )[:n]

        driver_parts = []
        for comp in sorted_comps:
            direction = comp.direction
            template = DRIVER_TEMPLATES.get(comp.name, {}).get(
                direction,
                f"{comp.name} is {direction}",
            )
            driver_parts.append(f"{template} ({comp.zscore:+.1f}σ)")

        if driver_parts:
            return "Primary drivers: " + "; ".join(driver_parts) + "."

        return ""

    def _format_divergence(
        self,
        components: Sequence[ScoreComponent],
    ) -> str:
        """
        Format VPB/IPB divergence if significant.

        Args:
            components: Score components

        Returns:
            Divergence text or empty string
        """
        vpb_z = None
        ipb_z = None

        for c in components:
            if c.name == "VPB":
                vpb_z = c.zscore
            elif c.name == "IPB":
                ipb_z = c.zscore

        if vpb_z is None or ipb_z is None:
            return ""

        divergence = vpb_z - ipb_z

        if abs(divergence) < VPB_IPB_DIVERGENCE_WARN:
            return ""

        if divergence > VPB_IPB_DIVERGENCE_WARN:
            return DIVERGENCE_TEMPLATES["narrow_leadership"]
        else:
            return DIVERGENCE_TEMPLATES["broad_weak"]

    def format_component_breakdown(
        self,
        components: Sequence[ScoreComponent],
    ) -> str:
        """
        Format detailed component breakdown.

        Args:
            components: Score components

        Returns:
            Multi-line breakdown text
        """
        lines = ["Component Breakdown:"]

        for comp in components:
            direction_symbol = "↑" if comp.zscore > 0 else "↓" if comp.zscore < 0 else "→"
            lines.append(
                f"  {comp.name}: {comp.raw_value:.4f} "
                f"(z={comp.zscore:+.2f} {direction_symbol}, "
                f"weight={comp.weight:.0%}, "
                f"contribution={comp.contribution:+.4f})"
            )

        return "\n".join(lines)

    def format_summary(
        self,
        score: float,
        band: Band,
        components: Sequence[ScoreComponent],
    ) -> str:
        """
        Format one-line summary.

        Args:
            score: AURORA score
            band: Classification band
            components: Score components

        Returns:
            One-line summary
        """
        top = max(components, key=lambda c: abs(c.zscore)) if components else None
        top_str = f", led by {top.name}" if top else ""

        return f"AURORA BMI: {score:.1f} ({band.value}){top_str}"
