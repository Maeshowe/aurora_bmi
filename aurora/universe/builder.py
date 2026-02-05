"""
AURORA Universe Builder.

Builds daily universe snapshots for AURORA BMI calculations.
Universe building is SEPARATE from feature computation.

CRITERIA (STRICT):
- Market Cap > $2B
- Price > $5
- Average Daily Volume (20D) > 1M shares
- Listed on NYSE or NASDAQ
- (Optional) Free Float Market Cap > $1B if data available

DESIGN RULES:
- Universe snapshot is IMMUTABLE once written
- Downstream components must only READ, never modify
- If quality is uncertain, REDUCE universe (never expand with noisy names)
- Better to be slightly narrow than slightly wrong

Output: data/universe/aurora/YYYY-MM-DD.parquet
"""

import asyncio
import logging
import statistics
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from aurora.core.config import Settings, get_settings
from aurora.core.types import UniverseConfig, UniverseSnapshot
from aurora.ingest.fmp import FMPClient

logger = logging.getLogger(__name__)


class UniverseBuilder:
    """
    AURORA Universe Builder.

    Constructs daily universe snapshots using FMP screener API.
    Uses parallel API calls with rate limiting and aggressive caching.

    Usage:
        builder = UniverseBuilder()
        async with builder:
            snapshot = await builder.build_universe(date.today())

    Design Principles:
        1. Universe building is SEPARATE from feature computation
        2. Snapshots are IMMUTABLE once written
        3. If quality uncertain: reduce, never expand
        4. Log size daily, warn on ±10% day-over-day change
    """

    SNAPSHOT_DIR = "data/universe/aurora"

    def __init__(
        self,
        config: UniverseConfig | None = None,
        fmp_client: FMPClient | None = None,
        settings: Settings | None = None,
    ) -> None:
        """
        Initialize Universe Builder.

        Args:
            config: Universe construction config (defaults used if not provided)
            fmp_client: FMP API client (created if not provided)
            settings: Settings object
        """
        self.settings = settings or get_settings()
        self.config = config or UniverseConfig()

        # FMP client for screener API
        self._fmp_client = fmp_client
        self._owns_client = fmp_client is None

        # Ensure snapshot directory exists
        self._snapshot_dir = Path(self.SNAPSHOT_DIR)
        self._snapshot_dir.mkdir(parents=True, exist_ok=True)

        # Track client state for context manager
        self._client_entered = False

    async def __aenter__(self) -> "UniverseBuilder":
        """Async context manager entry."""
        if self._owns_client and self._fmp_client is None:
            self._fmp_client = FMPClient(settings=self.settings)

        if self._fmp_client and hasattr(self._fmp_client, "__aenter__"):
            await self._fmp_client.__aenter__()
            self._client_entered = True

        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        if self._client_entered and self._fmp_client:
            await self._fmp_client.__aexit__(exc_type, exc_val, exc_tb)
            self._client_entered = False

    def _get_snapshot_path(self, trade_date: date) -> Path:
        """
        Get snapshot file path for a given date.

        Format: data/universe/aurora/YYYY-MM-DD.parquet
        """
        return self._snapshot_dir / f"{trade_date.isoformat()}.parquet"

    def _load_previous_count(self, trade_date: date) -> int | None:
        """
        Load previous trading day's universe count for validation.

        Returns None if no previous snapshot exists.
        """
        # Check previous few days (weekends, holidays)
        for days_back in range(1, 5):
            prev_date = trade_date - timedelta(days=days_back)
            prev_path = self._get_snapshot_path(prev_date)

            if prev_path.exists():
                try:
                    df = pd.read_parquet(prev_path)
                    return len(df)
                except Exception as e:
                    logger.warning(f"Could not read previous snapshot: {e}")
                    return None

        return None

    async def build_universe(
        self,
        trade_date: date | None = None,
        force_rebuild: bool = False,
    ) -> UniverseSnapshot:
        """
        Build daily universe snapshot.

        Uses FMP screener API with parallel calls for each exchange.
        Saves immutable parquet snapshot.

        Args:
            trade_date: Date for snapshot (default: today)
            force_rebuild: Rebuild even if snapshot exists

        Returns:
            UniverseSnapshot with validated results
        """
        trade_date = trade_date or date.today()
        snapshot_path = self._get_snapshot_path(trade_date)

        # Check for existing snapshot
        if not force_rebuild and snapshot_path.exists():
            logger.info(f"Universe snapshot exists: {snapshot_path}")
            return self._load_snapshot(trade_date)

        logger.info(f"Building AURORA universe for {trade_date}...")

        # Fetch candidates from FMP screener (parallel by exchange)
        all_candidates = await self._fetch_candidates()

        if not all_candidates:
            logger.error("No candidates returned from FMP screener")
            return self._create_empty_snapshot(trade_date)

        # Apply filters and deduplicate
        filtered = self._apply_filters(all_candidates)
        unique_tickers = self._deduplicate(filtered)

        # Calculate summary statistics
        market_caps = [c.get("marketCap", 0) for c in filtered if c.get("marketCap")]
        volumes = [c.get("volume", 0) for c in filtered if c.get("volume")]

        median_market_cap = statistics.median(market_caps) if market_caps else None
        median_volume = statistics.median(volumes) if volumes else None

        # Load previous count for validation
        previous_count = self._load_previous_count(trade_date)

        # Create snapshot
        snapshot = UniverseSnapshot(
            trade_date=trade_date,
            tickers=tuple(sorted(unique_tickers)),
            count=len(unique_tickers),
            median_market_cap=median_market_cap,
            median_volume=median_volume,
            previous_count=previous_count,
        )

        # Validate and warn
        self._validate_snapshot(snapshot)

        # Save immutable snapshot
        self._save_snapshot(snapshot)

        return snapshot

    async def _fetch_candidates(self) -> list[dict[str, Any]]:
        """
        Fetch candidates from FMP screener API.

        Uses parallel calls for each exchange to maximize throughput.
        """
        if not self._fmp_client:
            raise RuntimeError("FMP client not initialized. Use 'async with' context.")

        # Parallel fetch for each exchange
        tasks = []
        for exchange in self.config.exchanges:
            tasks.append(
                self._fmp_client.get_stock_screener(
                    market_cap_more_than=self.config.min_market_cap,
                    limit=self.config.max_results,
                    exchange=exchange,
                )
            )

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Combine results
        all_candidates: list[dict[str, Any]] = []
        for i, result in enumerate(results):
            exchange = self.config.exchanges[i]
            if isinstance(result, BaseException):
                logger.warning(f"Screener failed for {exchange}: {result}")
                continue
            if result:
                logger.info(f"Fetched {len(result)} candidates from {exchange}")
                all_candidates.extend(result)

        return all_candidates

    def _apply_filters(self, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Apply strict AURORA universe filters.

        Filters:
        - Market Cap > $2B (already applied in screener)
        - Price > $5
        - Volume > 1M shares
        - (Optional) Free Float > $1B
        """
        filtered = []

        for stock in candidates:
            symbol = stock.get("symbol", "")
            price = stock.get("price", 0) or 0
            volume = stock.get("volume", 0) or 0
            market_cap = stock.get("marketCap", 0) or 0

            # Skip if no symbol
            if not symbol:
                continue

            # Price filter
            if price < self.config.min_price:
                continue

            # Volume filter
            if volume < self.config.min_volume:
                continue

            # Market cap redundant check (screener already filtered)
            if market_cap < self.config.min_market_cap:
                continue

            # Optional: Free float filter (if data available)
            if self.config.min_free_float_cap:
                free_float = stock.get("freeFloat")
                if free_float is not None:
                    free_float_cap = market_cap * (free_float / 100)
                    if free_float_cap < self.config.min_free_float_cap:
                        continue

            filtered.append(stock)

        logger.info(
            f"Filtered universe: {len(candidates)} -> {len(filtered)} "
            f"(Price>${self.config.min_price}, Vol>{self.config.min_volume/1e6:.0f}M)"
        )

        return filtered

    def _deduplicate(self, candidates: list[dict[str, Any]]) -> list[str]:
        """
        Deduplicate tickers from multiple exchanges.

        Returns sorted list of unique tickers.
        """
        seen = set()
        unique = []

        for stock in candidates:
            symbol = stock.get("symbol", "").upper()
            if symbol and symbol not in seen:
                seen.add(symbol)
                unique.append(symbol)

        return sorted(unique)

    def _validate_snapshot(self, snapshot: UniverseSnapshot) -> None:
        """
        Validate snapshot and log warnings.

        Checks:
        - Universe size > 0
        - Size change within ±10% day-over-day
        """
        # Log universe size
        logger.info(
            f"AURORA Universe: {snapshot.count} stocks | "
            f"Median MCap: ${snapshot.median_market_cap/1e9:.1f}B | "
            f"Median Vol: {snapshot.median_volume/1e6:.1f}M"
            if snapshot.median_market_cap and snapshot.median_volume
            else f"AURORA Universe: {snapshot.count} stocks"
        )

        # Warn if empty
        if snapshot.count == 0:
            logger.error("AURORA Universe is EMPTY - check API connectivity")
            return

        # Warn if size changed significantly
        if snapshot.size_change_warning:
            change_pct = snapshot.size_change_pct or 0
            direction = "increased" if change_pct > 0 else "decreased"
            logger.warning(
                f"AURORA Universe size {direction} by {abs(change_pct)*100:.1f}% "
                f"({snapshot.previous_count} -> {snapshot.count})"
            )

    def _save_snapshot(self, snapshot: UniverseSnapshot) -> Path:
        """
        Save immutable universe snapshot to parquet.

        Returns path to saved file.
        """
        path = self._get_snapshot_path(snapshot.trade_date)

        # Create DataFrame
        df = pd.DataFrame({
            "ticker": snapshot.tickers,
            "date": snapshot.trade_date.isoformat(),
        })

        # Add metadata columns
        df["count"] = snapshot.count
        df["median_market_cap"] = snapshot.median_market_cap
        df["median_volume"] = snapshot.median_volume

        # Save atomically
        temp_path = path.with_suffix(".tmp")
        try:
            df.to_parquet(temp_path, index=False, compression="snappy")
            temp_path.rename(path)
            logger.info(f"Saved universe snapshot: {path}")
        except Exception:
            if temp_path.exists():
                temp_path.unlink()
            raise

        return path

    def _load_snapshot(self, trade_date: date) -> UniverseSnapshot:
        """
        Load existing universe snapshot from parquet.

        Args:
            trade_date: Date of snapshot to load

        Returns:
            UniverseSnapshot from saved data
        """
        path = self._get_snapshot_path(trade_date)

        if not path.exists():
            raise FileNotFoundError(f"No snapshot for {trade_date}")

        df = pd.read_parquet(path)

        # Extract tickers
        tickers = tuple(df["ticker"].tolist())

        # Extract metadata (same for all rows)
        count = int(df["count"].iloc[0]) if "count" in df.columns else len(tickers)
        median_market_cap = (
            float(df["median_market_cap"].iloc[0])
            if "median_market_cap" in df.columns and pd.notna(df["median_market_cap"].iloc[0])
            else None
        )
        median_volume = (
            float(df["median_volume"].iloc[0])
            if "median_volume" in df.columns and pd.notna(df["median_volume"].iloc[0])
            else None
        )

        # Load previous count for validation
        previous_count = self._load_previous_count(trade_date)

        return UniverseSnapshot(
            trade_date=trade_date,
            tickers=tickers,
            count=count,
            median_market_cap=median_market_cap,
            median_volume=median_volume,
            previous_count=previous_count,
        )

    def _create_empty_snapshot(self, trade_date: date) -> UniverseSnapshot:
        """Create empty snapshot for error cases."""
        return UniverseSnapshot(
            trade_date=trade_date,
            tickers=(),
            count=0,
            median_market_cap=None,
            median_volume=None,
        )

    def load_snapshot(self, trade_date: date) -> UniverseSnapshot | None:
        """
        Public method to load existing snapshot.

        Returns None if no snapshot exists for the date.
        """
        path = self._get_snapshot_path(trade_date)
        if not path.exists():
            return None
        return self._load_snapshot(trade_date)

    def list_available_snapshots(self) -> list[date]:
        """
        List all available snapshot dates.

        Returns:
            Sorted list of dates with snapshots
        """
        dates = []
        for path in self._snapshot_dir.glob("*.parquet"):
            try:
                date_str = path.stem  # YYYY-MM-DD
                d = date.fromisoformat(date_str)
                dates.append(d)
            except ValueError:
                continue

        return sorted(dates)

    def get_universe_stats(self) -> dict[str, Any]:
        """
        Get statistics about available universe snapshots.

        Returns:
            Dict with snapshot statistics
        """
        dates = self.list_available_snapshots()

        if not dates:
            return {
                "snapshot_count": 0,
                "date_range": (None, None),
                "snapshot_dir": str(self._snapshot_dir),
            }

        return {
            "snapshot_count": len(dates),
            "date_range": (dates[0], dates[-1]),
            "snapshot_dir": str(self._snapshot_dir),
            "latest_date": dates[-1],
        }
