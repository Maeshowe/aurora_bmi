"""
AURORA BMI - Baseline-normalized Market Breadth Index.

A daily diagnostic system measuring market participation health.

Outputs:
    - AURORA_BMI score in [0, 100]
    - Interpretation band: GREEN / LIGHT_GREEN / YELLOW / RED
    - Human-readable explanation of drivers

Design Philosophy:
    - Measures PARTICIPATION, not price direction
    - No ML, no prediction, no smoothing beyond rolling baseline
    - Breadth != Price, Participation != Direction
"""

from aurora.core.types import (
    Band,
    BaselineStatus,
    BMIResult,
    FeatureSet,
    ScoreComponent,
)

__version__ = "1.0.0"

__all__ = [
    "Band",
    "BaselineStatus",
    "BMIResult",
    "FeatureSet",
    "ScoreComponent",
    "__version__",
]
