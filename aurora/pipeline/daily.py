"""
Daily pipeline for AURORA BMI.

Orchestrates the full daily calculation:
1. Fetch data from APIs
2. Extract features
3. Normalize with rolling baselines
4. Calculate composite score
5. Generate explanation
6. Persist results
"""

import asyncio
import logging
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from aurora.core.config import Settings, get_settings
from aurora.core.types import BMIResult, FeatureSet
from aurora.explain.generator import ExplanationGenerator
from aurora.features.aggregator import FeatureAggregator
from aurora.features.ma_breadth import calculate_ma_breadth
from aurora.ingest.fmp import FMPClient
from aurora.ingest.polygon import PolygonClient
from aurora.ingest.unusual_whales import UnusualWhalesClient
from aurora.normalization.pipeline import NormalizationPipeline
from aurora.scoring.engine import BMIEngine


logger = logging.getLogger(__name__)


class DailyPipeline:
    """
    Daily AURORA BMI calculation pipeline.

    This is the main entry point for daily BMI calculations.
    Orchestrates data fetching, feature extraction, normalization,
    scoring, and persistence.
    """

    def __init__(
        self,
        settings: Settings | None = None,
        output_dir: Path | None = None,
    ) -> None:
        """
        Initialize daily pipeline.

        Args:
            settings: Application settings
            output_dir: Directory for output files
        """
        self.settings = settings or get_settings()
        self.output_dir = output_dir or self.settings.processed_data_dir / "bmi"
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Initialize components
        self.feature_aggregator = FeatureAggregator()
        self.normalization = NormalizationPipeline(
            history_dir=self.output_dir,
        )
        self.explanation_gen = ExplanationGenerator()
        self.engine = BMIEngine(normalization_pipeline=self.normalization)

    async def run(
        self,
        trade_date: date | None = None,
        force_refresh: bool = False,
    ) -> BMIResult:
        """
        Run the daily BMI calculation.

        Args:
            trade_date: Date to calculate for (default: today)
            force_refresh: Force data refresh even if cached

        Returns:
            BMIResult with score, band, and explanation
        """
        trade_date = trade_date or date.today()
        logger.info(f"Starting AURORA BMI calculation for {trade_date}")

        # Load historical data for baselines
        self.normalization.load_history(up_to_date=trade_date)

        # Fetch raw data
        raw_data = await self._fetch_data(trade_date)

        # Extract features
        features = self._extract_features(trade_date, raw_data)

        # Calculate BMI
        result = self.engine.calculate(
            features=features,
            explanation_generator=self.explanation_gen,
        )

        # Persist result
        self._save_result(result)

        logger.info(
            f"AURORA BMI for {trade_date}: {result.score:.1f} ({result.band.value})"
        )

        return result

    async def _fetch_data(self, trade_date: date) -> dict[str, Any]:
        """
        Fetch data from all sources.

        Args:
            trade_date: Date to fetch data for

        Returns:
            Dict with raw data from each source
        """
        data: dict[str, Any] = {
            "polygon_breadth": None,
            "ma_breadth": None,
            "volume_data": None,
        }

        # Fetch from Polygon
        try:
            async with PolygonClient(settings=self.settings) as polygon:
                # Get grouped daily data
                # Try trade_date first, fall back to previous day if no results
                grouped = await polygon.get_grouped_daily(trade_date)
                results_count = grouped.get("resultsCount", 0)

                # If no results for today, try yesterday (market not closed yet)
                if results_count == 0:
                    from datetime import timedelta
                    prev_date = trade_date - timedelta(days=1)
                    # Skip weekends
                    while prev_date.weekday() >= 5:  # Saturday=5, Sunday=6
                        prev_date -= timedelta(days=1)
                    logger.info(f"No data for {trade_date}, trying {prev_date}")
                    grouped = await polygon.get_grouped_daily(prev_date)

                breadth = polygon.calculate_breadth_from_grouped(grouped)
                data["polygon_breadth"] = breadth
                logger.info(f"Polygon breadth: {breadth}")

                # Calculate SBC proxy from grouped daily data
                # Use advance/decline ratio as structural breadth indicator
                results = grouped.get("results", [])
                if results:
                    # Count stocks up vs down (structural measure)
                    stocks_up = 0
                    stocks_down = 0
                    for ticker in results:
                        # Compare close to open for daily direction
                        open_price = ticker.get("o", 0)
                        close_price = ticker.get("c", 0)
                        if close_price > open_price:
                            stocks_up += 1
                        elif close_price < open_price:
                            stocks_down += 1

                    total = stocks_up + stocks_down
                    if total > 0:
                        # pct_ma50 proxy: % of stocks closing higher
                        # pct_ma200 proxy: same (we use advance ratio as structural indicator)
                        pct_up = (stocks_up / total) * 100
                        data["ma_breadth"] = {
                            "pct_ma50": pct_up,
                            "pct_ma200": pct_up,  # Use same value as proxy
                        }
                        logger.info(f"SBC proxy: {pct_up:.1f}% stocks up ({stocks_up}/{total})")
        except Exception as e:
            logger.error(f"Failed to fetch Polygon data: {e}")

        # Try to get real MA breadth data (enhances SBC accuracy)
        # Results are cached per day to avoid repeated API calls
        try:
            ma_result = await calculate_ma_breadth(
                settings=self.settings,
                sample_size=20,  # Top 20 stocks - balance speed vs accuracy
                trade_date=trade_date,
                use_cache=True,
            )
            if ma_result.is_valid:
                data["ma_breadth"] = {
                    "pct_ma50": ma_result.pct_above_ma50,
                    "pct_ma200": ma_result.pct_above_ma200,
                }
                logger.info(
                    f"Real MA Breadth: {ma_result.pct_above_ma50:.1f}% > MA50, "
                    f"{ma_result.pct_above_ma200:.1f}% > MA200 "
                    f"({ma_result.stocks_checked} stocks)"
                )
        except Exception as e:
            logger.debug(f"Real MA breadth skipped: {e}")

        # Fetch from FMP as backup if Polygon failed
        if data["polygon_breadth"] is None or all(
            v is None for v in data["polygon_breadth"].values()
        ):
            try:
                async with FMPClient(settings=self.settings) as fmp:
                    # Get gainers and losers
                    gainers = await fmp.get_market_gainers()
                    losers = await fmp.get_market_losers()

                    # Get volume data via bulk quotes
                    gainer_symbols = [g["symbol"] for g in gainers if "symbol" in g]
                    loser_symbols = [l["symbol"] for l in losers if "symbol" in l]

                    gainer_quotes = await fmp.get_bulk_quotes(gainer_symbols[:25])
                    loser_quotes = await fmp.get_bulk_quotes(loser_symbols[:25])

                    # Calculate volume-weighted breadth
                    v_adv = sum(q.get("volume", 0) or 0 for q in gainer_quotes)
                    v_dec = sum(q.get("volume", 0) or 0 for q in loser_quotes)

                    breadth = {
                        "v_adv": v_adv if v_adv > 0 else None,
                        "v_dec": v_dec if v_dec > 0 else None,
                        "n_adv": len(gainers) if gainers else None,
                        "n_dec": len(losers) if losers else None,
                    }
                    data["polygon_breadth"] = breadth
                    logger.info(f"FMP breadth (backup): {breadth}")

                    # Calculate SBC proxy from gainers/losers ratio
                    n_adv = len(gainers) if gainers else 0
                    n_dec = len(losers) if losers else 0
                    total_fmp = n_adv + n_dec
                    if total_fmp > 0 and data.get("ma_breadth") is None:
                        pct_up = (n_adv / total_fmp) * 100
                        data["ma_breadth"] = {
                            "pct_ma50": pct_up,
                            "pct_ma200": pct_up,
                        }
                        logger.info(f"SBC proxy (FMP): {pct_up:.1f}%")
            except Exception as e:
                logger.error(f"Failed to fetch FMP data: {e}")

        # Fetch unusual volume data from Unusual Whales (lit flow)
        try:
            async with UnusualWhalesClient(settings=self.settings) as uw:
                # Use lit_flow_recent for IPO calculation (primary data source)
                lit_flow = await uw.get_lit_flow_recent(trade_date, limit=200)

                if lit_flow:
                    # Calculate relative volumes from lit flow
                    rel_vol_values = []
                    for trade in lit_flow:
                        # Extract volume metrics from lit flow
                        volume = trade.get("volume") or trade.get("size") or 0
                        avg_volume = trade.get("avg_volume") or trade.get("avgVolume") or 1
                        if avg_volume > 0 and volume > 0:
                            rel_vol = volume / avg_volume
                            rel_vol_values.append(rel_vol)

                    if rel_vol_values:
                        data["volume_data"] = {
                            "rel_vol_values": rel_vol_values,
                            "universe_median": sorted(rel_vol_values)[len(rel_vol_values) // 2],
                        }
                        logger.info(f"UW lit flow: {len(rel_vol_values)} stocks with volume data")
                    else:
                        logger.info("UW lit flow: no volume data extracted")
                else:
                    # Fallback to flow_alerts if lit_flow is empty
                    flow_alerts = await uw.get_flow_alerts(trade_date)
                    volume_data = uw.calculate_relative_volume_spikes(flow_alerts)
                    data["volume_data"] = volume_data
                    logger.info(
                        f"UW flow alerts (fallback): {len(volume_data.get('rel_vol_values', []))} stocks"
                    )
        except Exception as e:
            logger.warning(f"Failed to fetch UW data: {e}")

        return data

    def _extract_features(
        self,
        trade_date: date,
        raw_data: dict[str, Any],
    ) -> FeatureSet:
        """
        Extract features from raw data.

        Args:
            trade_date: Date for features
            raw_data: Dict with raw API data

        Returns:
            FeatureSet with calculated features
        """
        return self.feature_aggregator.from_raw_data(
            trade_date=trade_date,
            polygon_breadth=raw_data.get("polygon_breadth"),
            ma_breadth=raw_data.get("ma_breadth"),
            volume_data=raw_data.get("volume_data"),
        )

    def _save_result(self, result: BMIResult) -> Path:
        """
        Save result to Parquet file.

        Args:
            result: BMIResult to save

        Returns:
            Path to saved file
        """
        # Convert to dict
        data = result.to_dict()

        # Flatten components for DataFrame
        row = {
            "date": result.trade_date.isoformat(),
            "score": result.score,
            "band": result.band.value,
            "raw_composite": result.raw_composite,
            "status": result.status.value,
            "explanation": result.explanation,
        }

        # Add component z-scores AND raw values for rolling calculator
        for comp in result.components:
            # Raw value under feature name (for rolling calculator baseline)
            row[comp.name] = comp.raw_value
            # Z-score and contribution (for dashboard display)
            row[f"{comp.name}_zscore"] = comp.zscore
            row[f"{comp.name}_raw"] = comp.raw_value
            row[f"{comp.name}_contribution"] = comp.contribution

        # Create or append to history file
        history_file = self.output_dir / "bmi_history.parquet"

        if history_file.exists():
            df = pd.read_parquet(history_file)
            new_row = pd.DataFrame([row])
            df = pd.concat([df, new_row], ignore_index=True)
            # Remove duplicates by date
            df = df.drop_duplicates(subset=["date"], keep="last")
        else:
            df = pd.DataFrame([row])

        df.to_parquet(history_file, index=False)
        logger.info(f"Saved BMI result to {history_file}")

        # Also save daily file
        daily_file = self.output_dir / f"{result.trade_date.isoformat()}.parquet"
        pd.DataFrame([row]).to_parquet(daily_file, index=False)

        return history_file

    def get_history(
        self,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> pd.DataFrame:
        """
        Load historical BMI results.

        Args:
            start_date: Start of date range
            end_date: End of date range

        Returns:
            DataFrame with historical results
        """
        history_file = self.output_dir / "bmi_history.parquet"

        if not history_file.exists():
            return pd.DataFrame()

        df = pd.read_parquet(history_file)
        df["date"] = pd.to_datetime(df["date"]).dt.date

        if start_date:
            df = df[df["date"] >= start_date]
        if end_date:
            df = df[df["date"] <= end_date]

        return df.sort_values("date")


def run_daily_sync(
    trade_date: date | None = None,
    force_refresh: bool = False,
) -> BMIResult:
    """
    Synchronous wrapper for daily pipeline.

    Args:
        trade_date: Date to calculate for
        force_refresh: Force data refresh

    Returns:
        BMIResult
    """
    pipeline = DailyPipeline()
    return asyncio.run(pipeline.run(trade_date, force_refresh))
