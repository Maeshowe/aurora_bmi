"""
Explanation templates for AURORA BMI.

These templates provide human-readable interpretations
of the BMI score and its components.
"""

from aurora.core.types import Band


# Base explanation templates by band
BAND_TEMPLATES: dict[Band, str] = {
    Band.GREEN: "Market breadth is healthy with strong, broad-based participation.",
    Band.LIGHT_GREEN: "Market breadth shows moderate participation.",
    Band.YELLOW: "Market breadth is weakening, participation declining.",
    Band.RED: "Market breadth is poor with narrow participation.",
}

# Component-specific templates
DRIVER_TEMPLATES: dict[str, dict[str, str]] = {
    "VPB": {
        "elevated": "volume participation is elevated (money flowing into advances)",
        "depressed": "volume participation is weak (money flowing into declines)",
        "neutral": "volume participation is neutral",
    },
    "IPB": {
        "elevated": "issue breadth is strong (many stocks advancing)",
        "depressed": "issue breadth is weak (many stocks declining)",
        "neutral": "issue breadth is neutral",
    },
    "SBC": {
        "elevated": "structural breadth is strong (majority above key MAs)",
        "depressed": "structural breadth is weak (minority above key MAs)",
        "neutral": "structural breadth is neutral",
    },
    "IPO": {
        "elevated": "institutional participation is elevated (volume spikes detected)",
        "depressed": "institutional participation is minimal",
        "neutral": "institutional participation is normal",
    },
}

# VPB/IPB divergence templates
DIVERGENCE_TEMPLATES: dict[str, str] = {
    "narrow_leadership": (
        "VPB/IPB divergence indicates narrow, mega-cap driven leadership. "
        "Volume concentrated in few names while broader market participation lags."
    ),
    "broad_weak": (
        "VPB/IPB divergence indicates broad but weak participation. "
        "Many stocks participating but with relatively low volume."
    ),
    "aligned": "Volume and issue breadth are aligned.",
}

# Status templates
STATUS_TEMPLATES: dict[str, str] = {
    "COMPLETE": "",  # No additional text needed
    "PARTIAL": "Note: Some features excluded due to insufficient baseline history.",
    "INSUFFICIENT": "Warning: Insufficient data for reliable calculation.",
}

# Feature descriptions for education
FEATURE_DESCRIPTIONS: dict[str, str] = {
    "VPB": (
        "Volume Participation Breadth (VPB) measures where the money is flowing. "
        "It's dollar-weighted, showing whether volume is concentrated in "
        "advancing or declining stocks."
    ),
    "IPB": (
        "Issue Participation Breadth (IPB) measures how broad participation is. "
        "It's count-weighted, showing whether more stocks are advancing or declining, "
        "regardless of their volume."
    ),
    "SBC": (
        "Structural Breadth Confirmation (SBC) uses slow moving average metrics "
        "to confirm whether the underlying market structure supports the current "
        "participation levels."
    ),
    "IPO": (
        "Institutional Participation Overlay (IPO) detects unusual volume spikes "
        "on lit exchanges that suggest institutional activity. Uses a dual filter "
        "requiring both stock-specific and market-relative thresholds."
    ),
}

# Design documentation as template
DESIGN_NOTES: str = """
AURORA BMI Design Notes:

1. Z-scores are NOT clipped at feature level. Extreme values (tail information)
   are preserved because crisis signals live in the tails.

2. Percentile ranking is the ONLY bounding mechanism. It naturally maps any
   composite score to [0, 100] while preserving relative ordering.

3. VPB and IPB correlate but measure different dimensions:
   - VPB: dollar-weighted (where is capital flowing?)
   - IPB: count-weighted (how broad is participation?)
   Their divergence is a MONITORED DIAGNOSTIC PROPERTY, not an error.

4. IPO uses a dual filter: stocks must exceed both their own Q90 threshold
   AND the universe median. This prevents small-cap noise and crisis saturation.

5. Lower score = healthier breadth (GREEN)
   Higher score = weaker breadth (RED)
"""
