"""
BMI scoring engine for AURORA.

Orchestrates the full scoring process:
1. Calculate composite score (S_BMI)
2. Apply percentile ranking (ONLY bounding mechanism)
3. Classify band
4. Return BMIResult
"""

import logging
from datetime import date

from aurora.core.constants import VPB_IPB_DIVERGENCE_WARN
from aurora.core.types import Band, BaselineStatus, BMIResult, FeatureSet, ScoreComponent
from aurora.normalization.pipeline import NormalizationPipeline
from aurora.scoring.composite import (
    assess_vpb_ipb_divergence,
    calculate_composite,
    get_top_drivers,
)


logger = logging.getLogger(__name__)


class BMIEngine:
    """
    AURORA BMI scoring engine.

    Transforms normalized features into the final AURORA score.

    Output:
        - AURORA score in [0, 100] (via percentile ranking)
        - Band classification
        - Component breakdown
        - VPB/IPB divergence diagnostics
    """

    def __init__(
        self,
        normalization_pipeline: NormalizationPipeline | None = None,
    ) -> None:
        """
        Initialize BMI engine.

        Args:
            normalization_pipeline: Pipeline for normalization (created if not provided)
        """
        self.pipeline = normalization_pipeline or NormalizationPipeline()

    def calculate(
        self,
        features: FeatureSet,
        explanation_generator: any = None,
    ) -> BMIResult:
        """
        Calculate AURORA BMI from features.

        Args:
            features: FeatureSet with raw feature values
            explanation_generator: Optional ExplanationGenerator for text output

        Returns:
            BMIResult with score, band, and explanation
        """
        trade_date = features.trade_date

        # Step 1: Normalize features (z-scores, NO clipping)
        z_scores, excluded, status = self.pipeline.normalize(features)

        # Step 2: Calculate composite score
        composite, components = calculate_composite(z_scores)

        # Update components with raw values from features
        components = self._enrich_components(components, features)

        # Step 3: Percentile ranking (ONLY bounding mechanism)
        aurora_score = self.pipeline.calculate_percentile(composite)

        # Step 4: Classify band
        band = Band.from_score(aurora_score)

        # Step 5: Generate explanation
        if explanation_generator:
            explanation = explanation_generator.generate(
                band=band,
                components=components,
                excluded=excluded,
                status=status,
            )
        else:
            explanation = self._default_explanation(band, components, excluded)

        # Step 6: Check VPB/IPB divergence (diagnostic)
        divergence, div_interpretation = assess_vpb_ipb_divergence(components)
        if divergence is not None and abs(divergence) > VPB_IPB_DIVERGENCE_WARN:
            logger.info(f"VPB/IPB divergence flagged: {divergence:.2f}")
            explanation += f" {div_interpretation}"

        # Step 7: Add observation to history for future baselines
        self.pipeline.add_observation(features)
        self.pipeline.add_composite_to_history(composite)

        return BMIResult(
            trade_date=trade_date,
            score=aurora_score,
            band=band,
            explanation=explanation,
            components=tuple(components),
            raw_composite=composite,
            status=status,
            excluded_features=tuple(excluded),
        )

    def _enrich_components(
        self,
        components: list[ScoreComponent],
        features: FeatureSet,
    ) -> list[ScoreComponent]:
        """
        Add raw values to score components.

        Args:
            components: List of ScoreComponents
            features: FeatureSet with raw values

        Returns:
            Updated components with raw_value filled
        """
        feature_map = {
            "VPB": features.vpb,
            "IPB": features.ipb,
            "SBC": features.sbc,
            "IPO": features.ipo,
        }

        enriched = []
        for c in components:
            raw_value = feature_map.get(c.name, 0.0) or 0.0
            enriched.append(
                ScoreComponent(
                    name=c.name,
                    weight=c.weight,
                    raw_value=raw_value,
                    zscore=c.zscore,
                    contribution=c.contribution,
                )
            )

        return enriched

    def _default_explanation(
        self,
        band: Band,
        components: list[ScoreComponent],
        excluded: list[str],
    ) -> str:
        """
        Generate default explanation text.

        Args:
            band: Classification band
            components: Score components
            excluded: Excluded feature names

        Returns:
            Human-readable explanation
        """
        base = band.description

        # Get top drivers
        top = get_top_drivers(components, n=2)
        if top:
            drivers = ", ".join(
                f"{c.name} ({c.zscore:+.1f}σ)" for c in top
            )
            base += f" Primary drivers: {drivers}."

        # Note excluded features
        if excluded:
            base += f" Excluded (insufficient history): {', '.join(excluded)}."

        return base

    def classify_band(self, score: float) -> Band:
        """
        Classify score into band.

        Args:
            score: AURORA score in [0, 100]

        Returns:
            Band classification
        """
        return Band.from_score(score)

    def get_diagnostics(
        self,
        result: BMIResult,
    ) -> dict:
        """
        Get diagnostic information from result.

        Args:
            result: BMIResult

        Returns:
            Dict with diagnostic metrics
        """
        divergence, div_msg = assess_vpb_ipb_divergence(list(result.components))

        return {
            "score": result.score,
            "band": result.band.value,
            "raw_composite": result.raw_composite,
            "status": result.status.value,
            "excluded_features": list(result.excluded_features),
            "vpb_ipb_divergence": divergence,
            "vpb_ipb_interpretation": div_msg,
            "component_zscores": {c.name: c.zscore for c in result.components},
            "component_contributions": {c.name: c.contribution for c in result.components},
        }
