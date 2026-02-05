"""
Moving Average Breadth Calculator for AURORA BMI.

Calculates the percentage of stocks trading above their
50-day and 200-day simple moving averages.

This is used for the SBC (Structural Breadth Confirmation) component.
"""

import asyncio
import json
import logging
from dataclasses import dataclass, asdict
from datetime import date
from pathlib import Path

from aurora.core.config import Settings, get_settings
from aurora.ingest.fmp import FMPClient

logger = logging.getLogger(__name__)

# Cache directory for MA breadth results
CACHE_DIR = Path("data/raw/ma_breadth")


def _get_cache_path(trade_date: date) -> Path:
    """Get cache file path for a given date."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR / f"{trade_date.isoformat()}.json"


def _load_cached_result(trade_date: date) -> "MABreadthResult | None":
    """Load cached MA breadth result for a date."""
    cache_path = _get_cache_path(trade_date)
    if not cache_path.exists():
        return None

    try:
        with open(cache_path, "r") as f:
            data = json.load(f)

        return MABreadthResult(
            pct_above_ma50=data.get("pct_above_ma50"),
            pct_above_ma200=data.get("pct_above_ma200"),
            stocks_checked=data.get("stocks_checked", 0),
            stocks_above_ma50=data.get("stocks_above_ma50", 0),
            stocks_above_ma200=data.get("stocks_above_ma200", 0),
            is_valid=data.get("is_valid", False),
            message=data.get("message", "Loaded from cache"),
        )
    except Exception as e:
        logger.debug(f"Failed to load cache for {trade_date}: {e}")
        return None


def _save_cached_result(trade_date: date, result: "MABreadthResult") -> None:
    """Save MA breadth result to cache."""
    cache_path = _get_cache_path(trade_date)

    try:
        data = {
            "pct_above_ma50": result.pct_above_ma50,
            "pct_above_ma200": result.pct_above_ma200,
            "stocks_checked": result.stocks_checked,
            "stocks_above_ma50": result.stocks_above_ma50,
            "stocks_above_ma200": result.stocks_above_ma200,
            "is_valid": result.is_valid,
            "message": result.message,
            "cached_at": date.today().isoformat(),
        }

        with open(cache_path, "w") as f:
            json.dump(data, f, indent=2)

        logger.debug(f"Cached MA breadth result for {trade_date}")
    except Exception as e:
        logger.warning(f"Failed to save cache for {trade_date}: {e}")


# Sample universe for MA breadth calculation
# Top market cap stocks for representative breadth
SAMPLE_UNIVERSE = [
    # Mega-cap tech
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA",
    # Financials
    "JPM", "BAC", "WFC", "GS", "MS", "C", "BLK",
    # Healthcare
    "UNH", "JNJ", "PFE", "ABBV", "MRK", "TMO", "ABT",
    # Consumer
    "WMT", "PG", "KO", "PEP", "COST", "HD", "MCD",
    # Industrials
    "CAT", "BA", "HON", "UPS", "RTX", "GE", "LMT",
    # Energy
    "XOM", "CVX", "COP", "SLB", "EOG",
    # Communications
    "DIS", "NFLX", "CMCSA", "VZ", "T",
    # Materials
    "LIN", "APD", "ECL", "NEM",
    # Utilities
    "NEE", "DUK", "SO", "D",
    # Real Estate
    "AMT", "PLD", "CCI", "EQIX",
]


@dataclass
class MABreadthResult:
    """Result of MA breadth calculation."""

    pct_above_ma50: float | None
    pct_above_ma200: float | None
    stocks_checked: int
    stocks_above_ma50: int
    stocks_above_ma200: int
    is_valid: bool
    message: str = ""


async def calculate_ma_breadth(
    settings: Settings | None = None,
    sample_size: int = 50,
    trade_date: date | None = None,
    use_cache: bool = True,
) -> MABreadthResult:
    """
    Calculate percentage of stocks above MA50 and MA200.

    Uses FMP technical indicators API to get real SMA values.
    Results are cached per day to avoid redundant API calls.

    Args:
        settings: Application settings
        sample_size: Number of stocks to sample (default 50)
        trade_date: Date for caching (default: today)
        use_cache: Whether to use cached results (default: True)

    Returns:
        MABreadthResult with percentages
    """
    settings = settings or get_settings()
    trade_date = trade_date or date.today()
    universe = SAMPLE_UNIVERSE[:sample_size]

    # Check cache first
    if use_cache:
        cached = _load_cached_result(trade_date)
        if cached and cached.is_valid:
            logger.info(
                f"Using cached MA breadth for {trade_date}: "
                f"{cached.pct_above_ma50:.1f}% > MA50, {cached.pct_above_ma200:.1f}% > MA200"
            )
            return cached

    above_ma50 = 0
    above_ma200 = 0
    checked = 0

    async with FMPClient(settings=settings) as fmp:
        # Get quotes for current prices
        quotes = await fmp.get_bulk_quotes(universe)
        quote_map = {q["symbol"]: q for q in quotes if q}

        # Check each stock's MA status
        tasks = []
        for symbol in universe:
            if symbol in quote_map:
                tasks.append(_check_ma_status(fmp, symbol, quote_map[symbol]))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, Exception):
                logger.debug(f"MA check failed: {result}")
                continue
            if result is None:
                continue

            checked += 1
            is_above_50, is_above_200 = result
            if is_above_50:
                above_ma50 += 1
            if is_above_200:
                above_ma200 += 1

    if checked == 0:
        return MABreadthResult(
            pct_above_ma50=None,
            pct_above_ma200=None,
            stocks_checked=0,
            stocks_above_ma50=0,
            stocks_above_ma200=0,
            is_valid=False,
            message="No stocks could be checked",
        )

    pct_ma50 = (above_ma50 / checked) * 100
    pct_ma200 = (above_ma200 / checked) * 100

    logger.info(
        f"MA Breadth: {pct_ma50:.1f}% above MA50, {pct_ma200:.1f}% above MA200 "
        f"({checked} stocks)"
    )

    result = MABreadthResult(
        pct_above_ma50=pct_ma50,
        pct_above_ma200=pct_ma200,
        stocks_checked=checked,
        stocks_above_ma50=above_ma50,
        stocks_above_ma200=above_ma200,
        is_valid=True,
    )

    # Cache the result for future use
    if use_cache:
        _save_cached_result(trade_date, result)

    return result


async def _check_ma_status(
    fmp: FMPClient,
    symbol: str,
    quote: dict,
) -> tuple[bool, bool] | None:
    """
    Check if a stock is above its MA50 and MA200.

    Args:
        fmp: FMP client
        symbol: Stock ticker
        quote: Current quote data

    Returns:
        Tuple of (above_ma50, above_ma200) or None if failed
    """
    try:
        current_price = quote.get("price") or quote.get("previousClose")
        if not current_price:
            return None

        # Get SMA50
        sma50_data = await fmp.get_technical_indicator(
            symbol=symbol,
            indicator="sma",
            period=50,
        )

        # Get SMA200
        sma200_data = await fmp.get_technical_indicator(
            symbol=symbol,
            indicator="sma",
            period=200,
        )

        # Extract latest values
        sma50 = None
        sma200 = None

        if sma50_data and len(sma50_data) > 0:
            sma50 = sma50_data[0].get("sma")

        if sma200_data and len(sma200_data) > 0:
            sma200 = sma200_data[0].get("sma")

        above_ma50 = sma50 is not None and current_price > sma50
        above_ma200 = sma200 is not None and current_price > sma200

        return (above_ma50, above_ma200)

    except Exception as e:
        logger.debug(f"Failed to check MA for {symbol}: {e}")
        return None


async def calculate_ma_breadth_fast(
    grouped_data: dict,
) -> MABreadthResult:
    """
    Fast MA breadth approximation from grouped daily data.

    Uses price vs previous close as a proxy when real MA data
    is not available or too slow to fetch.

    Args:
        grouped_data: Polygon grouped daily response

    Returns:
        MABreadthResult with approximated percentages
    """
    results = grouped_data.get("results", [])

    if not results:
        return MABreadthResult(
            pct_above_ma50=None,
            pct_above_ma200=None,
            stocks_checked=0,
            stocks_above_ma50=0,
            stocks_above_ma200=0,
            is_valid=False,
            message="No data available",
        )

    # Use close > open as proxy (same as before)
    stocks_up = 0
    stocks_down = 0

    for ticker in results:
        open_price = ticker.get("o", 0)
        close_price = ticker.get("c", 0)
        if close_price > open_price:
            stocks_up += 1
        elif close_price < open_price:
            stocks_down += 1

    total = stocks_up + stocks_down
    if total == 0:
        return MABreadthResult(
            pct_above_ma50=None,
            pct_above_ma200=None,
            stocks_checked=0,
            stocks_above_ma50=0,
            stocks_above_ma200=0,
            is_valid=False,
            message="No price data",
        )

    pct_up = (stocks_up / total) * 100

    return MABreadthResult(
        pct_above_ma50=pct_up,
        pct_above_ma200=pct_up,  # Same proxy for both
        stocks_checked=total,
        stocks_above_ma50=stocks_up,
        stocks_above_ma200=stocks_up,
        is_valid=True,
        message="Using intraday proxy (close > open)",
    )
