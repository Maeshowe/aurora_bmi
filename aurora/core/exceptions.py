"""
Custom exceptions for AURORA BMI.

All exceptions inherit from AuroraError for easy catching.
"""


class AuroraError(Exception):
    """Base exception for all AURORA BMI errors."""

    pass


class ConfigurationError(AuroraError):
    """Raised when configuration is invalid or missing."""

    def __init__(self, message: str, config_key: str | None = None):
        self.config_key = config_key
        super().__init__(message)


class DataFetchError(AuroraError):
    """Raised when data fetching from an API fails."""

    def __init__(
        self,
        message: str,
        source: str | None = None,
        status_code: int | None = None,
    ):
        self.source = source
        self.status_code = status_code
        super().__init__(message)


class InsufficientDataError(AuroraError):
    """
    Raised when there is insufficient data for calculation.

    This is a GUARDRAIL: better to report uncertainty than to guess.
    """

    def __init__(
        self,
        message: str,
        feature: str | None = None,
        available: int | None = None,
        required: int | None = None,
    ):
        self.feature = feature
        self.available = available
        self.required = required
        super().__init__(message)


class NormalizationError(AuroraError):
    """Raised when normalization fails."""

    def __init__(self, message: str, feature: str | None = None):
        self.feature = feature
        super().__init__(message)


class RateLimitError(AuroraError):
    """Raised when API rate limit is exceeded."""

    def __init__(
        self,
        message: str,
        source: str | None = None,
        retry_after: int | None = None,
    ):
        self.source = source
        self.retry_after = retry_after
        super().__init__(message)


class CacheError(AuroraError):
    """Raised when cache operations fail."""

    pass
