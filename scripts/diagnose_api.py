#!/usr/bin/env python3
"""
API diagnostics script for AURORA BMI.

Checks connectivity and health of all data sources.

Usage:
    python scripts/diagnose_api.py
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from aurora.core.config import get_settings
from aurora.ingest.fmp import FMPClient
from aurora.ingest.polygon import PolygonClient
from aurora.ingest.unusual_whales import UnusualWhalesClient


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def check_polygon() -> dict:
    """Check Polygon API connectivity."""
    result = {
        "name": "Polygon.io",
        "status": "unknown",
        "message": "",
        "endpoints_tested": [],
    }

    try:
        settings = get_settings()
        async with PolygonClient(settings=settings) as client:
            # Test market status endpoint
            result["endpoints_tested"].append("/v1/marketstatus/now")
            healthy = await client.health_check()
            if healthy:
                result["status"] = "ok"
                result["message"] = "Connected successfully"

                # Try to get market status
                status = await client.get_market_status()
                result["market_status"] = status.get("market", "unknown")

                # Log tested endpoints
                result["endpoints_tested"].append(
                    "/v2/snapshot/locale/us/markets/stocks/tickers"
                )
            else:
                result["status"] = "error"
                result["message"] = "Health check failed"
    except Exception as e:
        result["status"] = "error"
        result["message"] = str(e)

    return result


async def check_fmp() -> dict:
    """Check FMP API connectivity."""
    result = {
        "name": "Financial Modeling Prep",
        "status": "unknown",
        "message": "",
        "endpoints_tested": [],
    }

    try:
        settings = get_settings()
        async with FMPClient(settings=settings) as client:
            # Test most-actives endpoint (stable API, no required params)
            result["endpoints_tested"].append(client.STABLE_ENDPOINTS["actives"])
            healthy = await client.health_check()
            if healthy:
                result["status"] = "ok"
                result["message"] = "Connected successfully"

                # Log stable API endpoints available
                result["endpoints_tested"].extend([
                    client.STABLE_ENDPOINTS["gainers"],
                    client.STABLE_ENDPOINTS["losers"],
                ])
            else:
                result["status"] = "error"
                result["message"] = "Health check failed"
    except Exception as e:
        result["status"] = "error"
        result["message"] = str(e)

    return result


async def check_unusual_whales() -> dict:
    """Check Unusual Whales API connectivity."""
    result = {
        "name": "Unusual Whales",
        "status": "unknown",
        "message": "",
        "endpoints_tested": [],
    }

    try:
        settings = get_settings()

        if not settings.unusual_whales_api_key:
            result["status"] = "skipped"
            result["message"] = "API key not configured (optional)"
            return result

        async with UnusualWhalesClient(settings=settings) as client:
            # Test market tide endpoint
            result["endpoints_tested"].append(client.ENDPOINTS["market_tide"])
            healthy = await client.health_check()
            if healthy:
                result["status"] = "ok"
                result["message"] = "Connected successfully"

                # Log available lit flow endpoints
                result["endpoints_tested"].extend([
                    client.ENDPOINTS["lit_flow_recent"],
                    client.ENDPOINTS["market_spike"],
                ])
            else:
                result["status"] = "error"
                result["message"] = "Health check failed"
    except Exception as e:
        result["status"] = "error"
        result["message"] = str(e)

    return result


async def main_async() -> int:
    """Run all diagnostics."""
    print("\n" + "=" * 60)
    print("AURORA BMI - API DIAGNOSTICS")
    print("=" * 60 + "\n")

    # Check all APIs
    results = await asyncio.gather(
        check_polygon(),
        check_fmp(),
        check_unusual_whales(),
    )

    # Display results
    all_ok = True
    for result in results:
        status = result["status"]
        name = result["name"]
        message = result["message"]

        if status == "ok":
            icon = "✅"
        elif status == "skipped":
            icon = "⏭️"
        else:
            icon = "❌"
            all_ok = False

        print(f"{icon} {name}")
        print(f"   Status: {status}")
        print(f"   Message: {message}")
        if "market_status" in result:
            print(f"   Market: {result['market_status']}")
        if "endpoints_tested" in result and result["endpoints_tested"]:
            print(f"   Endpoints: {', '.join(result['endpoints_tested'][:2])}")
        print()

    # Summary
    print("-" * 60)
    if all_ok:
        print("✅ All required APIs are operational")
    else:
        print("⚠️  Some APIs have issues. Check configuration.")
        print()
        print("Required environment variables:")
        print("  POLYGON_KEY")
        print("  FMP_KEY")
        print()
        print("Optional:")
        print("  UW_API_KEY")
        print("  FRED_KEY")

    print("=" * 60 + "\n")

    return 0 if all_ok else 1


def main() -> int:
    """Main entry point."""
    return asyncio.run(main_async())


if __name__ == "__main__":
    sys.exit(main())
