#!/usr/bin/env python3
"""
Daily AURORA BMI calculation script.

Usage:
    python scripts/run_daily.py
    python scripts/run_daily.py --date 2024-01-15
    python scripts/run_daily.py --force
"""

import argparse
import asyncio
import logging
import sys
from datetime import date, datetime
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from aurora.pipeline.daily import DailyPipeline


def setup_logging(verbose: bool = False) -> None:
    """Configure logging."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def parse_date(date_str: str | None) -> date | None:
    """Parse date string to date object."""
    if date_str is None:
        return None

    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        print(f"Error: Invalid date format '{date_str}'. Use YYYY-MM-DD.")
        sys.exit(1)


async def main_async(
    trade_date: date | None,
    force: bool,
) -> int:
    """Async main function."""
    pipeline = DailyPipeline()

    try:
        result = await pipeline.run(
            trade_date=trade_date,
            force_refresh=force,
        )

        # Print result
        print("\n" + "=" * 60)
        print("AURORA BMI RESULT")
        print("=" * 60)
        print(f"Date:       {result.trade_date}")
        print(f"Score:      {result.score:.1f}")
        print(f"Band:       {result.band.value}")
        print(f"Status:     {result.status.value}")
        print("-" * 60)
        print("Components:")
        for comp in result.components:
            direction = "↑" if comp.zscore > 0 else "↓" if comp.zscore < 0 else "→"
            print(
                f"  {comp.name}: z={comp.zscore:+.2f}{direction} "
                f"(weight={comp.weight:.0%}, contribution={comp.contribution:+.4f})"
            )
        print("-" * 60)
        print(f"Raw Composite: {result.raw_composite:.4f}")
        if result.excluded_features:
            print(f"Excluded:      {', '.join(result.excluded_features)}")
        print("-" * 60)
        print("Explanation:")
        print(f"  {result.explanation}")
        print("=" * 60 + "\n")

        # Check VPB/IPB divergence
        divergence = result.vpb_ipb_divergence
        if divergence is not None and abs(divergence) > 1.0:
            print("⚠️  VPB/IPB DIVERGENCE DETECTED")
            if divergence > 0:
                print("    Volume breadth > Issue breadth")
                print("    → Narrow, mega-cap driven leadership")
            else:
                print("    Issue breadth > Volume breadth")
                print("    → Broad but weak participation")
            print()

        return 0

    except Exception as e:
        logging.error(f"Pipeline failed: {e}")
        return 1


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Run AURORA BMI daily calculation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python scripts/run_daily.py              # Calculate for today
    python scripts/run_daily.py --date 2024-01-15  # Specific date
    python scripts/run_daily.py --force      # Force data refresh

AURORA BMI measures market participation health:
    GREEN (0-25):       Healthy, broad participation
    LIGHT_GREEN (25-50): Moderate participation
    YELLOW (50-75):     Weakening participation
    RED (75-100):       Poor, narrow participation
        """,
    )

    parser.add_argument(
        "--date",
        "-d",
        type=str,
        default=None,
        help="Date to calculate (YYYY-MM-DD format, default: today)",
    )

    parser.add_argument(
        "--force",
        "-f",
        action="store_true",
        help="Force data refresh (ignore cache)",
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    setup_logging(args.verbose)

    trade_date = parse_date(args.date)

    return asyncio.run(main_async(trade_date, args.force))


if __name__ == "__main__":
    sys.exit(main())
