"""
Financial Modeling Prep (FMP) API client.

Provides backup market breadth data and sector-level metrics.
"""

import logging
from datetime import date
from typing import Any

from aurora.core.config import Settings, get_settings
from aurora.ingest.base import BaseAPIClient
from aurora.ingest.cache import CacheManager
from aurora.ingest.rate_limiter import TokenBucketLimiter


logger = logging.getLogger(__name__)


class FMPClient(BaseAPIClient):
    """
    FMP API client.

    Provides backup data for market breadth calculations.

    Uses the /stable/ endpoint convention from MoneyFlows 2026.
    """

    SOURCE_NAME = "fmp"
    BASE_URL = "https://financialmodelingprep.com"

    # Stable API endpoint mappings (MoneyFlows 2026 convention)
    # All endpoints now use the /stable/ prefix
    STABLE_ENDPOINTS = {
        # Core data endpoints
        "screener": "/stable/company-screener",
        "profile": "/stable/profile",
        "historical_price": "/stable/historical-price-eod/full",
        "quote": "/stable/quote",
        "ratios": "/stable/ratios",
        "growth": "/stable/financial-growth",
        # Market movement endpoints
        "actives": "/stable/most-actives",
        "gainers": "/stable/biggest-gainers",
        "losers": "/stable/biggest-losers",
        # Sector endpoints
        "sector_performance": "/stable/sector-performance-snapshot",
        "historical_sector": "/stable/historical-sector-performance",
        # Technical indicators
        "technical_indicator": "/stable/technical-indicators",
    }

    # Available technical indicators
    TECHNICAL_INDICATORS = frozenset([
        "sma",              # Simple Moving Average
        "ema",              # Exponential Moving Average
        "wma",              # Weighted Moving Average
        "dema",             # Double Exponential Moving Average
        "tema",             # Triple Exponential Moving Average
        "rsi",              # Relative Strength Index
        "standarddeviation",  # Standard Deviation
        "williams",         # Williams %R
        "adx",              # Average Directional Index
    ])

    def __init__(
        self,
        api_key: str | None = None,
        rate_limiter: TokenBucketLimiter | None = None,
        cache: CacheManager | None = None,
        settings: Settings | None = None,
    ) -> None:
        """
        Initialize FMP client.

        Args:
            api_key: FMP API key (from env if not provided)
            rate_limiter: Rate limiter (created if not provided)
            cache: Cache manager (created if not provided)
            settings: Settings object
        """
        settings = settings or get_settings()
        api_key = api_key or settings.fmp_key

        if rate_limiter is None:
            # FMP free tier: ~250 calls/day, be conservative
            rate_limiter = TokenBucketLimiter.from_rpm(10, burst_size=5)

        if cache is None:
            cache = CacheManager(settings.raw_data_dir / "fmp")

        super().__init__(
            api_key=api_key,
            base_url=self.BASE_URL,
            rate_limiter=rate_limiter,
            cache=cache,
        )

    def _auth_headers(self) -> dict[str, str]:
        """FMP uses query param auth."""
        return {}

    def _auth_params(self) -> dict[str, str]:
        """FMP API key as query parameter."""
        return {"apikey": self.api_key}

    async def get_stock_screener(
        self,
        market_cap_more_than: int | None = None,
        market_cap_less_than: int | None = None,
        sector: str | None = None,
        industry: str | None = None,
        exchange: str | None = None,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        """
        Get stocks matching criteria.

        Useful for building universe for breadth calculations.

        Args:
            market_cap_more_than: Minimum market cap
            market_cap_less_than: Maximum market cap
            sector: Sector filter
            industry: Industry filter
            exchange: Exchange filter (NYSE, NASDAQ)
            limit: Maximum results

        Returns:
            List of matching stocks
        """
        params: dict[str, Any] = {"limit": limit}

        if market_cap_more_than:
            params["marketCapMoreThan"] = market_cap_more_than
        if market_cap_less_than:
            params["marketCapLessThan"] = market_cap_less_than
        if sector:
            params["sector"] = sector
        if industry:
            params["industry"] = industry
        if exchange:
            params["exchange"] = exchange

        endpoint = self.STABLE_ENDPOINTS["screener"]
        result = await self._get(endpoint, params)
        return result if isinstance(result, list) else []

    async def get_bulk_quotes(
        self,
        symbols: list[str],
    ) -> list[dict[str, Any]]:
        """
        Get quotes for multiple symbols.

        The quote endpoint includes volume data.
        Note: Stable API requires individual calls per symbol.

        Args:
            symbols: List of ticker symbols

        Returns:
            List of quote data with volume
        """
        import asyncio

        if not symbols:
            return []

        async def get_single_quote(symbol: str) -> dict[str, Any] | None:
            """Get quote for a single symbol."""
            endpoint = self.STABLE_ENDPOINTS["quote"]
            params = {"symbol": symbol}
            try:
                result = await self._get(endpoint, params)
                if isinstance(result, list) and result:
                    return result[0]
            except Exception:
                pass
            return None

        # Fetch quotes in parallel (limit to 20 to respect rate limits)
        limited_symbols = symbols[:20]
        tasks = [get_single_quote(s) for s in limited_symbols]
        results = await asyncio.gather(*tasks)

        # Filter out None results
        return [r for r in results if r is not None]

    async def get_market_most_active(self) -> list[dict[str, Any]]:
        """
        Get most active stocks by volume.

        Useful for identifying high-activity stocks for IPO calculation.

        Returns:
            List of most active stocks
        """
        endpoint = self.STABLE_ENDPOINTS["actives"]
        result = await self._get(endpoint)
        return result if isinstance(result, list) else []

    async def get_market_gainers(self) -> list[dict[str, Any]]:
        """
        Get top gaining stocks.

        Returns:
            List of top gainers
        """
        endpoint = self.STABLE_ENDPOINTS["gainers"]
        result = await self._get(endpoint)
        return result if isinstance(result, list) else []

    async def get_market_losers(self) -> list[dict[str, Any]]:
        """
        Get top losing stocks.

        Returns:
            List of top losers
        """
        endpoint = self.STABLE_ENDPOINTS["losers"]
        result = await self._get(endpoint)
        return result if isinstance(result, list) else []

    async def get_sector_performance(
        self,
        trade_date: date | None = None,
    ) -> list[dict[str, Any]]:
        """
        Get sector performance snapshot.

        Args:
            trade_date: Date for snapshot (default: today)

        Returns:
            List of sector performance metrics
        """
        endpoint = self.STABLE_ENDPOINTS["sector_performance"]
        # Date is required for this endpoint
        target_date = trade_date or date.today()
        params = {"date": target_date.strftime("%Y-%m-%d")}

        result = await self._get(endpoint, params)
        return result if isinstance(result, list) else []

    async def get_historical_sector_performance(
        self,
        sector: str,
    ) -> list[dict[str, Any]]:
        """
        Get historical performance for a specific sector.

        Args:
            sector: Sector name (e.g., "Energy", "Technology")

        Returns:
            List of historical sector performance data
        """
        endpoint = self.STABLE_ENDPOINTS["historical_sector"]
        params = {"sector": sector}

        result = await self._get(endpoint, params)
        return result if isinstance(result, list) else []

    async def get_historical_price(
        self,
        symbol: str,
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> list[dict[str, Any]]:
        """
        Get historical daily prices for a symbol.

        Args:
            symbol: Stock ticker
            from_date: Start date
            to_date: End date

        Returns:
            List of daily price data
        """
        # Using stable API endpoint (MoneyFlows 2026 convention)
        endpoint = f"{self.STABLE_ENDPOINTS['historical_price']}/{symbol}"
        params: dict[str, Any] = {}

        if from_date:
            params["from"] = from_date.strftime("%Y-%m-%d")
        if to_date:
            params["to"] = to_date.strftime("%Y-%m-%d")

        result = await self._get(
            endpoint,
            params,
            cache_key_parts=("historical", symbol, to_date or date.today()),
        )

        # FMP returns {"symbol": "X", "historical": [...]}
        if isinstance(result, dict) and "historical" in result:
            return result["historical"]
        return []

    async def get_technical_indicator(
        self,
        symbol: str,
        indicator: str = "sma",
        period: int = 50,
        timeframe: str = "1day",
    ) -> list[dict[str, Any]]:
        """
        Get technical indicator data.

        Args:
            symbol: Stock ticker
            indicator: Indicator type. Available options:
                - sma: Simple Moving Average
                - ema: Exponential Moving Average
                - wma: Weighted Moving Average
                - dema: Double Exponential Moving Average
                - tema: Triple Exponential Moving Average
                - rsi: Relative Strength Index
                - standarddeviation: Standard Deviation
                - williams: Williams %R
                - adx: Average Directional Index
            period: Indicator period length
            timeframe: Data timeframe (1min, 5min, 15min, 30min, 1hour, 4hour, 1day)

        Returns:
            List of indicator values
        """
        # Stable API endpoint: /stable/technical-indicators/{indicator}
        endpoint = f"{self.STABLE_ENDPOINTS['technical_indicator']}/{indicator}"
        params = {
            "symbol": symbol,
            "periodLength": period,
            "timeframe": timeframe,
        }

        result = await self._get(endpoint, params)
        return result if isinstance(result, list) else []

    async def get_market_breadth_data(
        self,
        min_market_cap: int = 100_000_000,  # $100M minimum
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        """
        Get broad market data with volume for breadth calculations.

        Uses the screener endpoint which includes volume data.

        Args:
            min_market_cap: Minimum market cap filter
            limit: Maximum results

        Returns:
            List of stocks with price, volume, and change data
        """
        endpoint = self.STABLE_ENDPOINTS["screener"]
        params = {
            "marketCapMoreThan": min_market_cap,
            "limit": limit,
            "isActivelyTrading": True,
        }

        result = await self._get(endpoint, params)
        return result if isinstance(result, list) else []

    def calculate_breadth_from_screener(
        self,
        gainers: list[dict[str, Any]],
        losers: list[dict[str, Any]],
        actives: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        Calculate breadth metrics from FMP data.

        This is a backup method when Polygon data is unavailable.

        Args:
            gainers: List from get_market_gainers()
            losers: List from get_market_losers()
            actives: List from get_market_most_active()

        Returns:
            Dict with approximate v_adv, v_dec, n_adv, n_dec
        """
        # Approximate from gainers/losers counts
        n_adv = len(gainers)
        n_dec = len(losers)

        # Approximate volume from actives
        v_adv = 0.0
        v_dec = 0.0

        for stock in actives:
            volume = stock.get("volume", 0) or 0
            change_pct = stock.get("changesPercentage", 0) or 0

            if change_pct > 0:
                v_adv += volume
            elif change_pct < 0:
                v_dec += volume

        return {
            "v_adv": v_adv if v_adv > 0 else None,
            "v_dec": v_dec if v_dec > 0 else None,
            "n_adv": n_adv if n_adv > 0 else None,
            "n_dec": n_dec if n_dec > 0 else None,
        }

    def calculate_breadth_from_universe(
        self,
        stocks: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        Calculate breadth metrics from screener universe data.

        Uses volume data from the screener endpoint.

        Args:
            stocks: List from get_market_breadth_data() or get_stock_screener()

        Returns:
            Dict with v_adv, v_dec, n_adv, n_dec
        """
        v_adv = 0.0
        v_dec = 0.0
        n_adv = 0
        n_dec = 0

        for stock in stocks:
            volume = stock.get("volume", 0) or 0
            # Screener uses 'price' and we need to compare with previous
            # Since we don't have previous close, use beta as proxy for direction
            # Or check if there's a change field
            change = stock.get("change", 0) or stock.get("changesPercentage", 0) or 0

            # If no change data, use beta sign as rough proxy
            if change == 0:
                beta = stock.get("beta", 1.0) or 1.0
                # Skip if we can't determine direction
                continue

            if change > 0:
                v_adv += volume
                n_adv += 1
            elif change < 0:
                v_dec += volume
                n_dec += 1

        return {
            "v_adv": v_adv if v_adv > 0 else None,
            "v_dec": v_dec if v_dec > 0 else None,
            "n_adv": n_adv if n_adv > 0 else None,
            "n_dec": n_dec if n_dec > 0 else None,
        }

    async def health_check(self) -> bool:
        """Check FMP API connectivity."""
        try:
            # Use most-actives endpoint (no required parameters)
            actives = await self.get_market_most_active()
            return len(actives) > 0
        except Exception as e:
            logger.error(f"FMP health check failed: {e}")
            return False
