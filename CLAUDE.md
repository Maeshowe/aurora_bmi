# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AURORA BMI (Baseline-normalized Market Breadth Index) is a deterministic, rule-based diagnostic system measuring market participation health. It produces a daily AURORA Score (0-100) and Band classification (GREEN/LIGHT_GREEN/YELLOW/RED). Part of the OBSIDIAN MM ecosystem but operates independently.

## Commands

```bash
# Install dependencies
uv sync
uv sync --extra dev  # Include dev dependencies

# Run daily calculation
uv run python scripts/run_daily.py

# Check API connectivity
uv run python scripts/diagnose_api.py

# Run tests
uv run pytest                                    # All tests
uv run pytest tests/unit/test_normalization.py  # Single file
uv run pytest -k "test_no_clipping"             # By name pattern
uv run pytest -m unit                           # By marker (unit, integration, slow, api)

# Linting and type checking
uv run ruff check aurora/                       # Lint
uv run ruff check aurora/ --fix                 # Lint with auto-fix
uv run mypy aurora/                             # Type check

# Launch dashboard
uv run streamlit run aurora/dashboard/app.py --server.port 8503
```

## Critical Design Decisions (DO NOT CHANGE)

### 1. NO Z-SCORE CLIPPING
Z-scores are NOT clipped at feature level. Extreme values (tail information) MUST be preserved.
- Percentile ranking is the ONLY bounding mechanism (applied to final composite)
- Crisis signals live in the tails
- See: `aurora/normalization/methods.py`

### 2. VPB/IPB DIVERGENCE IS A FEATURE
VPB (dollar-weighted) and IPB (count-weighted) measure different dimensions:
- High VPB + Low IPB = Narrow leadership (mega-cap driven)
- Low VPB + High IPB = Broad but weak participation
Their divergence is a MONITORED DIAGNOSTIC, not an error.

### 3. IPO DUAL FILTER
Stocks must satisfy BOTH conditions:
- `RelVol > Q90(own history)`
- `RelVol > median(universe)`

### 4. NO DARK POOL DATA
Dark pool analysis belongs to OBSIDIAN, not AURORA. See guardrail in `aurora/ingest/unusual_whales.py`.

### 5. Weights and Thresholds are FROZEN
```python
WEIGHTS = {"VPB": 0.30, "IPB": 0.25, "SBC": 0.25, "IPO": 0.20}
```
Do NOT tune these weights or band thresholds (0-25 GREEN, 25-50 LIGHT_GREEN, 50-75 YELLOW, 75-100 RED).

## Guardrails

- No ML or prediction logic
- No price trend logic
- No smoothing beyond rolling baseline (W=63, N_min=21)
- No combining with OBSIDIAN
- No future-looking logic

## Data Flow

```
Sources (Polygon/FMP/UW) → Async Ingest → Feature Extraction (VPB,IPB,SBC,IPO)
→ Z-score Normalization (63d rolling, NO clipping) → Composite Score
→ Percentile Rank → INVERT → Band Classification + Explanation → Dashboard
```

Score inversion: High composite (good breadth) → LOW score → GREEN

## Key Files

| Purpose | File |
|---------|------|
| Core types & enums | `aurora/core/types.py` |
| Constants (weights, thresholds) | `aurora/core/constants.py` |
| Z-score/percentile (NO clipping) | `aurora/normalization/methods.py` |
| Scoring engine | `aurora/scoring/engine.py` |
| Base API client | `aurora/ingest/base.py` |

## Adding a New Data Source

1. Create client in `aurora/ingest/` inheriting from `BaseAPIClient`
2. Implement `_auth_headers()` and `_auth_params()` methods
3. Add to feature aggregator if needed
4. NO dark pool endpoints

## Performance Notes

Current implementation is optimized for daily batch runs (~200-1000 stocks):
- Median calculations use `sorted()` - acceptable for N<1000
- Percentile rank is O(n) - acceptable for 63-day rolling window
- No N² loops over symbols

**If scaling beyond 10K symbols:** Consider numpy vectorization for median/percentile operations.

**Clarity beats cleverness:** Prefer readable code over micro-optimizations.

## Required API Keys

Set in `.env` file: `POLYGON_API_KEY`, `FMP_API_KEY`, `UW_API_KEY`
