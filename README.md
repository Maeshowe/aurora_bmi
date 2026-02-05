# AURORA BMI v1.0

**Baseline-normalized Market Breadth Index**

A daily diagnostic system measuring market participation health. Part of the OBSIDIAN MM ecosystem but operates as an independent subsystem.

## Overview

AURORA BMI answers the question: **"Is the current market move supported by broad, organized participation?"**

### Output

- **AURORA_BMI score**: 0-100 (lower = healthier breadth)
- **Interpretation band**: GREEN / LIGHT_GREEN / YELLOW / RED
- **Human-readable explanation** of drivers

### Key Principle

**Breadth ≠ Price. Participation ≠ Direction.**

AURORA measures participation health, NOT price outlook.

## Interpretation Bands

| Score | Band | Meaning |
|-------|------|---------|
| 0-25 | GREEN | Healthy, broad participation |
| 25-50 | LIGHT_GREEN | Moderate participation |
| 50-75 | YELLOW | Weakening participation |
| 75-100 | RED | Poor, narrow participation |

## Components

### 1. Volume Participation Breadth (VPB) - Weight: 30%
```
VPB_t = V_adv / (V_adv + V_dec)
```
**Measures**: Where is the MONEY going? (dollar-weighted)

### 2. Issue Participation Breadth (IPB) - Weight: 25%
```
IPB_t = N_adv / (N_adv + N_dec)
```
**Measures**: How BROAD is participation? (count-weighted)

### 3. Structural Breadth Confirmation (SBC) - Weight: 25%
```
SBC_t = (pct_MA50 + pct_MA200) / 2
```
**Measures**: Is the breadth structurally sound?

### 4. Institutional Participation Overlay (IPO) - Weight: 20%
```
IPO_t = count(RelVol_i > Q90(RelVol_i) AND RelVol_i > median(universe)) / N
```
**Measures**: Are institutions participating? (dual filter, lit exchange only)

## Quick Start

### Installation

```bash
# Clone the repository
cd aurora_bmi

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or: venv\Scripts\activate  # Windows

# Install dependencies
pip install -e ".[dev]"
```

### Configuration

1. Copy the environment template:
```bash
cp .env.example .env
```

2. Add your API keys to `.env`:
```
POLYGON_KEY=your_key_here
FMP_KEY=your_key_here
UW_API_KEY=your_key_here  # Optional
```

### Usage

```bash
# Check API connectivity
python scripts/diagnose_api.py

# Run daily calculation
python scripts/run_daily.py

# Run for specific date
python scripts/run_daily.py --date 2024-01-15

# Launch dashboard
streamlit run aurora/dashboard/app.py
```

## Design Decisions

### 1. No Z-score Clipping

**Z-scores are NOT clipped at the feature level.**

Breadth distributions have fat tails, and crisis signals live in those tails. Clipping at ±3σ would mask exactly the events we want to detect.

**Percentile ranking is the ONLY bounding mechanism**, applied to the final composite score.

### 2. VPB/IPB Correlation

VPB and IPB are correlated but measure different dimensions:
- **VPB**: Dollar-weighted (where is capital flowing?)
- **IPB**: Count-weighted (how broad is participation?)

Their divergence is a **monitored diagnostic property**:
- **VPB high + IPB low**: Narrow, mega-cap driven leadership
- **VPB low + IPB high**: Broad but weak participation

### 3. IPO Dual Filter

A stock counts toward IPO only if it satisfies BOTH:
1. `RelVol > Q90(own history)` - unusual for that stock
2. `RelVol > median(universe)` - unusual relative to market

This prevents small-cap noise and crisis-mode saturation.

## Architecture

```
aurora_bmi/
├── aurora/
│   ├── core/           # Types, constants, config, exceptions
│   ├── ingest/         # API clients (async)
│   ├── features/       # VPB, IPB, SBC, IPO calculators
│   ├── normalization/  # Z-score, percentile, rolling stats
│   ├── scoring/        # Composite score, BMI engine
│   ├── explain/        # Human-readable explanations
│   ├── pipeline/       # Daily orchestration
│   └── dashboard/      # Streamlit UI
├── config/             # YAML configuration files
├── data/               # Parquet data storage
├── scripts/            # CLI entry points
└── tests/              # Unit and integration tests
```

## Guardrails

| Rule | Enforcement |
|------|-------------|
| No ML | Pure arithmetic formulas only |
| No price trend logic | VPB/IPB use volume/count, not prices |
| No smoothing | Only rolling z-score normalization |
| No OBSIDIAN crosstalk | Completely separate codebase |
| No future-looking | All windows backward-only |
| Minimum observations | N_min=21 required for baseline |
| Explicit uncertainty | PARTIAL/INSUFFICIENT status flags |

## API Reference

### Python API

```python
from aurora.pipeline.daily import DailyPipeline
import asyncio

# Initialize pipeline
pipeline = DailyPipeline()

# Run calculation
result = asyncio.run(pipeline.run())

# Access result
print(f"Score: {result.score}")
print(f"Band: {result.band.value}")
print(f"Explanation: {result.explanation}")
```

### CLI

```bash
# Daily calculation
python scripts/run_daily.py [--date YYYY-MM-DD] [--force] [--verbose]

# API diagnostics
python scripts/diagnose_api.py

# Dashboard
streamlit run aurora/dashboard/app.py
```

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=aurora

# Run specific test file
pytest tests/unit/test_normalization.py

# Run only fast tests
pytest -m "not slow"
```

## Data Sources

- **Polygon.io**: Advancing/declining volume & issues, MA breadth
- **FMP**: Backup market internals
- **Unusual Whales**: Lit exchange volume (NO dark pool - that's OBSIDIAN)

## License

MIT

## Contributing

1. Fork the repository
2. Create a feature branch
3. Write tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

---

**AURORA BMI** - Measuring participation, not predicting price.
