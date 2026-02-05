"""
Polygon.io API client for market breadth data.

Provides:
- Advancing/declining volume and issues
- Market snapshot data
- Per-stock aggregate data for MA calculations
"""

import logging
from datetime import date
from typing import Any

from aurora.core.config import Settings, get_settings
from aurora.ingest.base import BaseAPIClient
from aurora.ingest.cache import CacheManager
from aurora.ingest.rate_limiter import TokenBucketLimiter

logger = logging.getLogger(__name__)


class PolygonClient(BaseAPIClient):
    """
    Polygon.io API client.

    Fetches market breadth data including:
    - Market snapshot (advancing/declining volume and issues)
    - Grouped daily aggregates
    - Per-ticker aggregates for MA calculations
    """

    SOURCE_NAME = "polygon"
    BASE_URL = "https://api.polygon.io"

    def __init__(
        self,
        api_key: str | None = None,
        rate_limiter: TokenBucketLimiter | None = None,
        cache: CacheManager | None = None,
        settings: Settings | None = None,
    ) -> None:
        """
        Initialize Polygon client.

        Args:
            api_key: Polygon API key (from env if not provided)
            rate_limiter: Rate limiter (created if not provided)
            cache: Cache manager (created if not provided)
            settings: Settings object
        """
        settings = settings or get_settings()
        api_key = api_key or settings.polygon_key

        if rate_limiter is None:
            # Free tier: 5 requests/minute
            rate_limiter = TokenBucketLimiter.from_rpm(5, burst_size=5)

        if cache is None:
            cache = CacheManager(settings.raw_data_dir / "polygon")

        super().__init__(
            api_key=api_key,
            base_url=self.BASE_URL,
            rate_limiter=rate_limiter,
            cache=cache,
        )

    def _auth_headers(self) -> dict[str, str]:
        """Polygon uses query param auth."""
        return {}

    def _auth_params(self) -> dict[str, str]:
        """Polygon API key as query parameter."""
        return {"apiKey": self.api_key}

    async def get_grouped_daily(self, trade_date: date) -> dict[str, Any]:
        """
        Get grouped daily aggregates for all tickers.

        This provides OHLCV data for all tickers on a given date,
        useful for calculating advancing/declining statistics.

        Args:
            trade_date: Date to fetch data for

        Returns:
            Grouped daily aggregate data
        """
        date_str = trade_date.strftime("%Y-%m-%d")
        endpoint = f"/v2/aggs/grouped/locale/us/market/stocks/{date_str}"

        return await self._get(
            endpoint,
            params={"adjusted": "true"},
            cache_key_parts=("grouped_daily", None, trade_date),
        )

    async def get_market_snapshot(self) -> dict[str, Any]:
        """
        Get current market snapshot.

        Returns snapshot of all tickers including:
        - Current day's aggregate
        - Previous day's aggregate
        - Today's change

        Note: This is a heavy endpoint, use sparingly.

        Returns:
            Market snapshot data
        """
        endpoint = "/v2/snapshot/locale/us/markets/stocks/tickers"

        # Don't cache snapshots (real-time data)
        return await self._get(endpoint)

    async def get_ticker_aggregates(
        self,
        ticker: str,
        from_date: date,
        to_date: date,
        timespan: str = "day",
    ) -> dict[str, Any]:
        """
        Get aggregate bars for a specific ticker.

        Args:
            ticker: Stock ticker symbol
            from_date: Start date
            to_date: End date
            timespan: Bar timespan (day, minute, etc.)

        Returns:
            Aggregate bar data
        """
        from_str = from_date.strftime("%Y-%m-%d")
        to_str = to_date.strftime("%Y-%m-%d")
        endpoint = f"/v2/aggs/ticker/{ticker}/range/1/{timespan}/{from_str}/{to_str}"

        return await self._get(
            endpoint,
            params={"adjusted": "true", "sort": "asc"},
            cache_key_parts=("ticker_aggs", ticker, to_date),
        )

    async def get_market_status(self) -> dict[str, Any]:
        """
        Get current market status.

        Returns:
            Market status (open, closed, early_hours, etc.)
        """
        endpoint = "/v1/marketstatus/now"
        return await self._get(endpoint)

    def calculate_breadth_from_grouped(
        self,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Calculate breadth metrics from grouped daily data.

        Args:
            data: Response from get_grouped_daily()

        Returns:
            Dict with v_adv, v_dec, n_adv, n_dec
        """
        results = data.get("results", [])

        if not results:
            return {
                "v_adv": None,
                "v_dec": None,
                "n_adv": None,
                "n_dec": None,
            }

        v_adv = 0.0
        v_dec = 0.0
        n_adv = 0
        n_dec = 0

        for ticker_data in results:
            # Skip if missing required fields
            if "v" not in ticker_data or "c" not in ticker_data or "o" not in ticker_data:
                continue

            volume = ticker_data["v"]
            close = ticker_data["c"]
            open_price = ticker_data["o"]

            # Determine direction (advancing if close > open)
            if close > open_price:
                v_adv += volume
                n_adv += 1
            elif close < open_price:
                v_dec += volume
                n_dec += 1
            # Unchanged not counted in either

        return {
            "v_adv": v_adv,
            "v_dec": v_dec,
            "n_adv": n_adv,
            "n_dec": n_dec,
        }

    def calculate_ma_breadth(
        self,
        ticker_histories: dict[str, list[dict[str, Any]]],
    ) -> dict[str, float | None]:
        """
        Calculate % of stocks above MA50 and MA200.

        Args:
            ticker_histories: Dict of ticker -> list of OHLCV bars

        Returns:
            Dict with pct_ma50 and pct_ma200
        """
        if not ticker_histories:
            return {"pct_ma50": None, "pct_ma200": None}

        above_ma50 = 0
        above_ma200 = 0
        valid_tickers = 0

        for ticker, bars in ticker_histories.items():
            if len(bars) < 200:
                continue

            closes = [b["c"] for b in bars if "c" in b]

            if len(closes) < 200:
                continue

            current_price = closes[-1]
            ma50 = sum(closes[-50:]) / 50
            ma200 = sum(closes[-200:]) / 200

            valid_tickers += 1

            if current_price > ma50:
                above_ma50 += 1
            if current_price > ma200:
                above_ma200 += 1

        if valid_tickers == 0:
            return {"pct_ma50": None, "pct_ma200": None}

        return {
            "pct_ma50": (above_ma50 / valid_tickers) * 100,
            "pct_ma200": (above_ma200 / valid_tickers) * 100,
        }

    async def health_check(self) -> bool:
        """Check Polygon API connectivity."""
        try:
            status = await self.get_market_status()
            return "market" in status or "serverTime" in status
        except Exception as e:
            logger.error(f"Polygon health check failed: {e}")
            return False
