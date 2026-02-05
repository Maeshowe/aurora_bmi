# CLAUDE.md - AURORA BMI Project Guidance

## Project Overview

AURORA BMI (Baseline-normalized Market Breadth Index) is a daily diagnostic system measuring market participation health. It is part of the OBSIDIAN MM ecosystem but operates independently.

## Key Commands

```bash
# Run daily calculation
python scripts/run_daily.py

# Check API connectivity
python scripts/diagnose_api.py

# Run tests
pytest

# Launch dashboard
streamlit run aurora/dashboard/app.py
```

## Architecture

```
aurora_bmi/
├── aurora/
│   ├── core/           # Types, constants, config
│   ├── ingest/         # API clients (Polygon, FMP, UW)
│   ├── features/       # VPB, IPB, SBC, IPO calculators
│   ├── normalization/  # Z-score (NO clipping), percentile
│   ├── scoring/        # Composite score, engine
│   ├── explain/        # Human-readable output
│   ├── pipeline/       # Daily orchestration
│   └── dashboard/      # Streamlit UI
├── config/             # YAML configs
├── data/               # Parquet storage
├── scripts/            # CLI tools
└── tests/              # Unit tests
```

## Critical Design Decisions (DO NOT CHANGE)

### 1. NO Z-SCORE CLIPPING
Z-scores are NOT clipped at feature level. Extreme values (tail information) MUST be preserved.
- Percentile ranking is the ONLY bounding mechanism
- Crisis signals live in the tails
- See: `aurora/normalization/methods.py`

### 2. VPB/IPB DIVERGENCE IS A FEATURE
VPB and IPB are correlated but measure different dimensions:
- VPB: dollar-weighted
- IPB: count-weighted
Their divergence is a MONITORED DIAGNOSTIC, not an error.

### 3. IPO DUAL FILTER
Stocks must satisfy BOTH conditions:
- `RelVol > Q90(own history)`
- `RelVol > median(universe)`

### 4. NO DARK POOL DATA
Dark pool analysis belongs to OBSIDIAN, not AURORA.
See: `aurora/ingest/unusual_whales.py` for guardrail.

## Weights (FROZEN)

```python
WEIGHTS = {
    "VPB": 0.30,  # Volume Participation Breadth
    "IPB": 0.25,  # Issue Participation Breadth
    "SBC": 0.25,  # Structural Breadth Confirmation
    "IPO": 0.20,  # Institutional Participation Overlay
}
```

**Do NOT tune these weights.** They are conceptual allocations.

## Band Thresholds (FROZEN)

| Score | Band |
|-------|------|
| 0-25 | GREEN |
| 25-50 | LIGHT_GREEN |
| 50-75 | YELLOW |
| 75-100 | RED |

## Guardrails

- No ML
- No price trend logic
- No smoothing beyond rolling baseline
- No combining with OBSIDIAN
- No future-looking logic
- Minimum observations: N_min = 21
- Rolling window: W = 63

## Key Files

| Purpose | File |
|---------|------|
| Core types | `aurora/core/types.py` |
| Constants | `aurora/core/constants.py` |
| Normalization | `aurora/normalization/methods.py` |
| Scoring | `aurora/scoring/engine.py` |
| Daily pipeline | `aurora/pipeline/daily.py` |

## Testing

```bash
# Run all tests
pytest

# Verify no clipping
pytest tests/unit/test_normalization.py -v

# Verify scoring bounds
pytest tests/unit/test_scoring.py -v
```

## Common Tasks

### Add new data source
1. Create client in `aurora/ingest/`
2. Inherit from `BaseAPIClient`
3. Add to feature aggregator if needed
4. NO dark pool endpoints

### Modify explanation output
1. Edit templates in `aurora/explain/templates.py`
2. Update generator in `aurora/explain/generator.py`

### Update dashboard
1. Components in `aurora/dashboard/components/`
2. Main app in `aurora/dashboard/app.py`

## DO NOT

- Clip z-scores at feature level
- Add ML or prediction logic
- Tune weights or thresholds
- Import dark pool data
- Mix with OBSIDIAN code
- Add price trend logic
