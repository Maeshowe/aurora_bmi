"""
Configuration management for AURORA BMI.

Loads settings from environment variables and YAML config files.
Uses Pydantic for validation.
"""

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from aurora.core.exceptions import ConfigurationError


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.

    API keys and paths are loaded from .env file or environment.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # API Keys (matching MoneyFlows 2026 convention)
    polygon_key: str = Field(
        ...,
        validation_alias="POLYGON_KEY",
        description="Polygon.io API key",
    )
    fmp_key: str = Field(
        ...,
        validation_alias="FMP_KEY",
        description="Financial Modeling Prep API key",
    )
    unusual_whales_api_key: str = Field(
        default="",
        validation_alias="UW_API_KEY",
        description="Unusual Whales API key (optional)",
    )
    fred_key: str = Field(
        default="",
        validation_alias="FRED_KEY",
        description="FRED API key (optional)",
    )

    # Paths
    data_dir: Path = Field(
        default=Path("data"),
        description="Root directory for data storage",
    )
    config_dir: Path = Field(
        default=Path("config"),
        description="Directory containing YAML config files",
    )

    # Logging
    log_level: str = Field(
        default="INFO",
        description="Logging level",
    )

    @field_validator("data_dir", "config_dir", mode="before")
    @classmethod
    def resolve_path(cls, v: str | Path) -> Path:
        """Convert string to Path and resolve."""
        return Path(v).resolve()

    @field_validator("log_level", mode="before")
    @classmethod
    def uppercase_log_level(cls, v: str) -> str:
        """Ensure log level is uppercase."""
        return v.upper()

    @property
    def raw_data_dir(self) -> Path:
        """Directory for raw API responses."""
        path = self.data_dir / "raw"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def processed_data_dir(self) -> Path:
        """Directory for processed data."""
        path = self.data_dir / "processed"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def baselines_dir(self) -> Path:
        """Directory for baseline statistics."""
        path = self.data_dir / "baselines"
        path.mkdir(parents=True, exist_ok=True)
        return path


class SourcesConfig:
    """Configuration for API sources loaded from settings.yaml."""

    def __init__(self, config_path: Path):
        self._config = self._load_yaml(config_path)

    @staticmethod
    def _load_yaml(path: Path) -> dict[str, Any]:
        """Load and parse YAML file."""
        if not path.exists():
            raise ConfigurationError(f"Config file not found: {path}")

        with open(path) as f:
            return yaml.safe_load(f) or {}

    @property
    def polygon(self) -> dict[str, Any]:
        """Polygon API configuration."""
        return self._config.get("api_sources", {}).get("polygon", {})

    @property
    def fmp(self) -> dict[str, Any]:
        """FMP API configuration."""
        return self._config.get("api_sources", {}).get("fmp", {})

    @property
    def unusual_whales(self) -> dict[str, Any]:
        """Unusual Whales API configuration."""
        return self._config.get("api_sources", {}).get("unusual_whales", {})

    @property
    def cache_config(self) -> dict[str, Any]:
        """Cache configuration."""
        return self._config.get("cache", {})


class NormalizationConfig:
    """
    Configuration for normalization loaded from normalization.yaml.

    DESIGN NOTE: Z-scores are NOT clipped at feature level.
    Percentile ranking is the ONLY bounding mechanism.
    """

    def __init__(self, config_path: Path):
        self._config = self._load_yaml(config_path)

    @staticmethod
    def _load_yaml(path: Path) -> dict[str, Any]:
        """Load and parse YAML file."""
        if not path.exists():
            raise ConfigurationError(f"Config file not found: {path}")

        with open(path) as f:
            return yaml.safe_load(f) or {}

    @property
    def default_window(self) -> int:
        """Default rolling window size."""
        return self._config.get("normalization", {}).get("default_window", 63)

    @property
    def min_observations(self) -> int:
        """Minimum observations required for valid baseline."""
        return self._config.get("normalization", {}).get("min_observations", 21)

    def get_feature_config(self, feature: str) -> dict[str, Any]:
        """Get configuration for a specific feature."""
        features = self._config.get("normalization", {}).get("features", {})
        default = {
            "method": "zscore",
            "window": self.default_window,
            "clip": False,  # NO CLIPPING - preserve tail information
        }
        config = features.get(feature, default)
        # Enforce no clipping
        config["clip"] = False
        return config


class BandsConfig:
    """Configuration for interpretation bands loaded from bands.yaml."""

    def __init__(self, config_path: Path):
        self._config = self._load_yaml(config_path)

    @staticmethod
    def _load_yaml(path: Path) -> dict[str, Any]:
        """Load and parse YAML file."""
        if not path.exists():
            raise ConfigurationError(f"Config file not found: {path}")

        with open(path) as f:
            return yaml.safe_load(f) or {}

    @property
    def thresholds(self) -> dict[str, tuple[float, float]]:
        """Band threshold ranges."""
        bands = self._config.get("bands", {})
        return {
            name: (band.get("min", 0), band.get("max", 100))
            for name, band in bands.items()
        }

    @property
    def descriptions(self) -> dict[str, str]:
        """Band descriptions."""
        bands = self._config.get("bands", {})
        return {
            name: band.get("description", "")
            for name, band in bands.items()
        }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Get cached application settings."""
    return Settings()


def load_config(
    config_type: str,
) -> SourcesConfig | NormalizationConfig | BandsConfig:
    """
    Load a specific configuration file.

    Args:
        config_type: One of "sources", "normalization", "bands"

    Returns:
        Appropriate config object
    """
    settings = get_settings()
    config_map: dict[str, tuple[Path, type]] = {
        "sources": (settings.config_dir / "settings.yaml", SourcesConfig),
        "normalization": (settings.config_dir / "normalization.yaml", NormalizationConfig),
        "bands": (settings.config_dir / "bands.yaml", BandsConfig),
    }

    if config_type not in config_map:
        raise ConfigurationError(
            f"Unknown config type: {config_type}. "
            f"Valid types: {list(config_map.keys())}"
        )

    path, config_class = config_map[config_type]
    return config_class(path)
