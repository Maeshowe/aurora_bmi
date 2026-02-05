"""Core types, constants, configuration, and exceptions for AURORA BMI."""

from aurora.core.config import (
    BandsConfig,
    NormalizationConfig,
    Settings,
    get_settings,
    load_config,
)
from aurora.core.constants import (
    BAND_THRESHOLDS,
    MIN_OBSERVATIONS,
    ROLLING_WINDOW,
    WEIGHTS,
)
from aurora.core.exceptions import (
    AuroraError,
    ConfigurationError,
    DataFetchError,
    InsufficientDataError,
    NormalizationError,
)
from aurora.core.types import (
    Band,
    BaselineStatus,
    BMIResult,
    FeatureSet,
    ScoreComponent,
)

__all__ = [
    # Types
    "Band",
    "BaselineStatus",
    "BMIResult",
    "FeatureSet",
    "ScoreComponent",
    # Constants
    "BAND_THRESHOLDS",
    "MIN_OBSERVATIONS",
    "ROLLING_WINDOW",
    "WEIGHTS",
    # Config
    "BandsConfig",
    "NormalizationConfig",
    "Settings",
    "get_settings",
    "load_config",
    # Exceptions
    "AuroraError",
    "ConfigurationError",
    "DataFetchError",
    "InsufficientDataError",
    "NormalizationError",
]
