#!/usr/bin/env python3
"""
Import legacy BMI baseline data into AURORA BMI format.

Converts secrets/bmi_history.parquet to the format expected by the dashboard.
"""

import sys
from pathlib import Path

import pandas as pd

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


def convert_baseline():
    """Convert legacy BMI data to AURORA format."""
    # Paths
    source = Path("secrets/bmi_history.parquet")
    target = Path("data/processed/bmi/bmi_history.parquet")

    if not source.exists():
        print(f"Source file not found: {source}")
        return 1

    # Read legacy format
    df = pd.read_parquet(source)
    print(f"Loaded {len(df)} rows from {source}")
    print(f"Columns: {df.columns.tolist()}")
    print(f"Date range: {df['Date'].min()} to {df['Date'].max()}")

    # Convert to AURORA BMI format
    # Legacy BMI is 0-1 scale, convert to 0-100 using percentile rank
    df["score"] = df["BMI"].rank(pct=True) * 100

    def assign_band(score: float) -> str:
        if score <= 25:
            return "GREEN"
        elif score <= 50:
            return "LIGHT_GREEN"
        elif score <= 75:
            return "YELLOW"
        else:
            return "RED"

    # Calculate z-scores for VPB proxy (Buying_Power)
    bp_mean = df["Buying_Power"].mean()
    bp_std = df["Buying_Power"].std()
    df["VPB_zscore"] = (df["Buying_Power"] - bp_mean) / bp_std

    # Calculate z-scores for IPB proxy (Buys/Total_Signals)
    ipb_raw = df["Buys"] / df["Total_Signals"]
    ipb_mean = ipb_raw.mean()
    ipb_std = ipb_raw.std()
    df["IPB_zscore"] = (ipb_raw - ipb_mean) / ipb_std

    # Create AURORA format DataFrame
    new_df = pd.DataFrame(
        {
            "date": df["Date"],
            "score": df["score"].round(1),
            "band": df["score"].apply(assign_band),
            "raw_composite": (df["BMI"] - 0.5) * 10,  # Approximate z-score scale
            "status": "BASELINE",
            "explanation": df.apply(
                lambda r: f"Historical baseline: BP={r['Buying_Power']:.1%}, "
                f"Buys={r['Buys']}, Sells={r['Sells']}",
                axis=1,
            ),
            # Feature RAW VALUES for rolling calculator (must match FEATURE_NAMES)
            "VPB": df["Buying_Power"],  # Raw VPB value for baseline
            "IPB": ipb_raw,              # Raw IPB value for baseline
            "SBC": 0.5,                  # Not available - use neutral
            "IPO": 0.0,                  # Not available - use zero
            # Component columns for dashboard display
            "VPB_zscore": df["VPB_zscore"],
            "VPB_raw": df["Buying_Power"],
            "VPB_contribution": df["VPB_zscore"] * 0.30,
            "IPB_zscore": df["IPB_zscore"],
            "IPB_raw": ipb_raw,
            "IPB_contribution": df["IPB_zscore"] * 0.25,
            "SBC_zscore": 0.0,
            "SBC_raw": 0.5,
            "SBC_contribution": 0.0,
            "IPO_zscore": 0.0,
            "IPO_raw": 0.0,
            "IPO_contribution": 0.0,
        }
    )

    # Ensure target directory exists
    target.parent.mkdir(parents=True, exist_ok=True)

    # Save
    new_df.to_parquet(target, index=False)
    print(f"\nSaved {len(new_df)} rows to {target}")

    # Show sample
    print("\nSample (last 5 rows):")
    print(
        new_df[["date", "score", "band", "VPB_zscore", "IPB_zscore"]].tail().to_string()
    )

    # Statistics
    print("\nScore distribution:")
    print(f"  Mean: {new_df['score'].mean():.1f}")
    print(f"  Std:  {new_df['score'].std():.1f}")
    print(f"  Min:  {new_df['score'].min():.1f}")
    print(f"  Max:  {new_df['score'].max():.1f}")

    return 0


if __name__ == "__main__":
    sys.exit(convert_baseline())
