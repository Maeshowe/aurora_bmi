"""
Unusual Whales API client for lit exchange data.

IMPORTANT: This client ONLY accesses lit exchange endpoints.
Dark pool data belongs to OBSIDIAN and is explicitly excluded.
"""

import logging
from datetime import date
from typing import Any

from aurora.core.config import Settings, get_settings
from aurora.ingest.base import BaseAPIClient
from aurora.ingest.cache import CacheManager
from aurora.ingest.rate_limiter import TokenBucketLimiter

logger = logging.getLogger(__name__)


class UnusualWhalesClient(BaseAPIClient):
    """
    Unusual Whales API client for lit exchange data.

    GUARDRAIL: This client explicitly EXCLUDES dark pool endpoints.
    Dark pool analysis belongs to OBSIDIAN, not AURORA.

    Provides:
    - Lit exchange flow alerts
    - Unusual volume detection (lit exchanges only)
    - Block trade activity (lit exchanges only)
    """

    SOURCE_NAME = "unusual_whales"
    BASE_URL = "https://api.unusualwhales.com"

    # Endpoint mappings (from UW_Original_export.yaml)
    ENDPOINTS = {
        # Lit flow endpoints (primary for AURORA)
        "lit_flow_recent": "/api/lit-flow/recent",
        "lit_flow_ticker": "/api/lit-flow/{ticker}",
        # Options flow endpoints
        "flow_alerts": "/api/option-trades/flow-alerts",
        "stock_flow_recent": "/api/stock/{ticker}/flow-recent",
        "stock_flow_alerts": "/api/stock/{ticker}/flow-alerts",
        # Market endpoints
        "market_tide": "/api/market/market-tide",
        "market_spike": "/api/market/spike",
        "total_options_volume": "/api/market/total-options-volume",
    }

    # GUARDRAIL: Explicitly excluded endpoints (dark pool belongs to OBSIDIAN)
    EXCLUDED_ENDPOINTS = frozenset([
        "/api/darkpool",
        "/api/darkpool/",
        "/api/darkpool/recent",
        "/darkpool",
    ])

    def __init__(
        self,
        api_key: str | None = None,
        rate_limiter: TokenBucketLimiter | None = None,
        cache: CacheManager | None = None,
        settings: Settings | None = None,
    ) -> None:
        """
        Initialize Unusual Whales client.

        Args:
            api_key: UW API key (from env if not provided)
            rate_limiter: Rate limiter (created if not provided)
            cache: Cache manager (created if not provided)
            settings: Settings object
        """
        settings = settings or get_settings()
        api_key = api_key or settings.unusual_whales_api_key

        if not api_key:
            logger.warning(
                "Unusual Whales API key not configured. "
                "IPO calculations will use fallback methods."
            )

        if rate_limiter is None:
            # UW: 60 requests/minute
            rate_limiter = TokenBucketLimiter.from_rpm(60, burst_size=10)

        if cache is None:
            cache = CacheManager(settings.raw_data_dir / "unusual_whales")

        super().__init__(
            api_key=api_key or "",
            base_url=self.BASE_URL,
            rate_limiter=rate_limiter,
            cache=cache,
        )

    def _auth_headers(self) -> dict[str, str]:
        """UW uses Bearer token auth."""
        if not self.api_key:
            return {}
        return {"Authorization": f"Bearer {self.api_key}"}

    def _auth_params(self) -> dict[str, str]:
        """UW uses header auth, not query params."""
        return {}

    def _validate_endpoint(self, endpoint: str) -> None:
        """
        GUARDRAIL: Ensure endpoint is not a dark pool endpoint.

        Raises:
            ValueError: If endpoint is a dark pool endpoint
        """
        endpoint_lower = endpoint.lower()
        for excluded in self.EXCLUDED_ENDPOINTS:
            if endpoint_lower.startswith(excluded):
                raise ValueError(
                    f"Dark pool endpoints are not allowed in AURORA. "
                    f"Endpoint '{endpoint}' is excluded. "
                    f"Dark pool analysis belongs to OBSIDIAN."
                )

    async def _get(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
        cache_key_parts: tuple[str, str | None, date] | None = None,
    ) -> dict[str, Any]:
        """Override to add endpoint validation."""
        self._validate_endpoint(endpoint)
        return await super()._get(endpoint, params, cache_key_parts)

    async def get_lit_flow_recent(
        self,
        trade_date: date | None = None,
        limit: int = 200,
        min_premium: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        Get recent lit exchange trades.

        This is the PRIMARY endpoint for AURORA BMI lit exchange data.

        Args:
            trade_date: Date to fetch (default: today)
            limit: Maximum trades to return (max 200)
            min_premium: Minimum premium filter

        Returns:
            List of lit exchange trades
        """
        if not self.api_key:
            logger.debug("UW API key not configured, returning empty lit flow")
            return []

        endpoint = self.ENDPOINTS["lit_flow_recent"]
        params: dict[str, Any] = {"limit": min(limit, 200)}

        if trade_date:
            params["date"] = trade_date.strftime("%Y-%m-%d")
        if min_premium is not None:
            params["min_premium"] = min_premium

        result = await self._get(
            endpoint,
            params,
            cache_key_parts=("lit_flow_recent", None, trade_date or date.today()),
        )

        if isinstance(result, dict):
            return result.get("data", [])
        return result if isinstance(result, list) else []

    async def get_lit_flow_ticker(
        self,
        ticker: str,
        trade_date: date | None = None,
    ) -> list[dict[str, Any]]:
        """
        Get lit exchange trades for a specific ticker.

        Args:
            ticker: Stock ticker
            trade_date: Date to fetch (default: today)

        Returns:
            List of lit exchange trades for ticker
        """
        if not self.api_key:
            logger.debug("UW API key not configured, returning empty lit flow")
            return []

        endpoint = self.ENDPOINTS["lit_flow_ticker"].format(ticker=ticker)
        params: dict[str, Any] = {}

        if trade_date:
            params["date"] = trade_date.strftime("%Y-%m-%d")

        result = await self._get(
            endpoint,
            params,
            cache_key_parts=("lit_flow_ticker", ticker, trade_date or date.today()),
        )

        if isinstance(result, dict):
            return result.get("data", [])
        return result if isinstance(result, list) else []

    async def get_flow_alerts(
        self,
        trade_date: date | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Get unusual options flow alerts (lit exchanges only).

        Args:
            trade_date: Date to fetch (default: today)
            limit: Maximum alerts to return

        Returns:
            List of flow alerts
        """
        if not self.api_key:
            logger.debug("UW API key not configured, returning empty flow alerts")
            return []

        endpoint = self.ENDPOINTS["flow_alerts"]
        params: dict[str, Any] = {"limit": limit}

        if trade_date:
            params["date"] = trade_date.strftime("%Y-%m-%d")

        result = await self._get(
            endpoint,
            params,
            cache_key_parts=("flow_alerts", None, trade_date or date.today()),
        )

        if isinstance(result, dict):
            return result.get("data", [])
        return result if isinstance(result, list) else []

    async def get_stock_flow(
        self,
        ticker: str,
        trade_date: date | None = None,
    ) -> dict[str, Any]:
        """
        Get flow data for a specific stock (lit exchanges only).

        Args:
            ticker: Stock ticker
            trade_date: Date to fetch (default: today)

        Returns:
            Stock flow data
        """
        if not self.api_key:
            logger.debug("UW API key not configured, returning empty stock flow")
            return {}

        endpoint = self.ENDPOINTS["stock_flow_recent"].format(ticker=ticker)
        params: dict[str, Any] = {}

        if trade_date:
            params["date"] = trade_date.strftime("%Y-%m-%d")

        return await self._get(
            endpoint,
            params,
            cache_key_parts=("stock_flow", ticker, trade_date or date.today()),
        )

    async def get_market_tide(
        self,
        trade_date: date | None = None,
        interval_5m: bool = False,
    ) -> dict[str, Any]:
        """
        Get market-wide options flow sentiment.

        Market Tide is a proprietary tool that examines market-wide options
        activity and filters out noise.

        Args:
            trade_date: Date to fetch (default: today)
            interval_5m: Return data in 5-minute intervals (default: 1-minute)

        Returns:
            Market tide data (call/put ratios, premium flow)
        """
        if not self.api_key:
            return {}

        endpoint = self.ENDPOINTS["market_tide"]
        params: dict[str, Any] = {}

        if trade_date:
            params["date"] = trade_date.strftime("%Y-%m-%d")
        if interval_5m:
            params["interval_5m"] = "true"

        return await self._get(
            endpoint,
            params,
            cache_key_parts=("market_tide", None, trade_date or date.today()),
        )

    async def get_market_spike(
        self,
        trade_date: date | None = None,
    ) -> dict[str, Any]:
        """
        Get SPIKE values for the given date.

        SPIKE is a volatility indicator.

        Args:
            trade_date: Date to fetch (default: today)

        Returns:
            SPIKE value data
        """
        if not self.api_key:
            return {}

        endpoint = self.ENDPOINTS["market_spike"]
        params: dict[str, Any] = {}

        if trade_date:
            params["date"] = trade_date.strftime("%Y-%m-%d")

        return await self._get(
            endpoint,
            params,
            cache_key_parts=("market_spike", None, trade_date or date.today()),
        )

    def calculate_relative_volume_spikes(
        self,
        flow_alerts: list[dict[str, Any]],
        percentile_threshold: float = 90.0,
    ) -> dict[str, Any]:
        """
        Calculate relative volume spikes from flow alerts.

        This identifies institutional participation via lit exchange
        activity that shows unusual volume relative to historical norms.

        Args:
            flow_alerts: List of flow alerts
            percentile_threshold: Threshold for "unusual" (default Q90)

        Returns:
            Dict with rel_vol_values and universe_median
        """
        if not flow_alerts:
            return {
                "rel_vol_values": [],
                "universe_median": None,
            }

        # Extract volume metrics
        volumes = []
        for alert in flow_alerts:
            vol = alert.get("volume", 0)
            avg_vol = alert.get("avg_volume", 0) or alert.get("average_volume", 0)

            if vol > 0 and avg_vol > 0:
                rel_vol = vol / avg_vol
                volumes.append(rel_vol)

        if not volumes:
            return {
                "rel_vol_values": [],
                "universe_median": None,
            }

        # Calculate universe median
        sorted_volumes = sorted(volumes)
        n = len(sorted_volumes)
        if n % 2 == 0:
            median = (sorted_volumes[n // 2 - 1] + sorted_volumes[n // 2]) / 2
        else:
            median = sorted_volumes[n // 2]

        return {
            "rel_vol_values": volumes,
            "universe_median": median,
        }

    async def health_check(self) -> bool:
        """Check UW API connectivity."""
        if not self.api_key:
            logger.info("UW API key not configured, health check skipped")
            return True  # Not an error, just not configured

        try:
            tide = await self.get_market_tide()
            return bool(tide)
        except Exception as e:
            logger.error(f"UW health check failed: {e}")
            return False
