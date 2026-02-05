# AURORA BMI

**Baseline-normalized Market Breadth Index**

| | |
|---|---|
| **Version** | 1.1 |
| **Classification** | Internal Technical Reference |
| **Scope** | Market Participation Health Diagnostic System |
| **Instrument Universe** | US Equity Market (aggregate breadth) |
| **Temporal Resolution** | Daily Aggregation (T+0 close) |

---

## 1. System Definition

AURORA BMI is a deterministic, rule-based diagnostic engine that measures the health of market participation. The system produces one output per trading day:

| Output | Type | Domain |
|--------|------|--------|
| **AURORA Score** | Continuous | U ∈ [0, 100] |
| **Band Classification** | Categorical | {GREEN, LIGHT_GREEN, YELLOW, RED} |

Both outputs are accompanied by a mandatory explainability vector identifying the top contributing features.

**Scope exclusions.** The system measures PARTICIPATION, not DIRECTION. It does not generate signals, forecasts, or trade recommendations. All outputs are descriptive and diagnostic.

---

## 2. Data Sources

| Domain | Provider | Data Type |
|--------|----------|-----------|
| Advancing/Declining volume | Polygon.io | Grouped daily breadth |
| Advancing/Declining issues | Polygon.io | Market internals |
| % above MA50/MA200 | FMP API | Technical indicators |
| Institutional lit flow | Unusual Whales | Volume spikes |

**Data quality rule.** If a source field is missing, the feature is excluded. No interpolation or imputation is applied.

---

## 3. Feature Definitions

### 3.1 Volume Participation Breadth (VPB)

Measures where the MONEY is going (dollar-weighted).

```
VPB_t = V_adv / (V_adv + V_dec)
```

- VPB > 0.5 → More volume in advancing stocks
- VPB < 0.5 → More volume in declining stocks

### 3.2 Issue Participation Breadth (IPB)

Measures how BROAD is participation (count-weighted).

```
IPB_t = N_adv / (N_adv + N_dec)
```

- IPB > 0.5 → More stocks advancing
- IPB < 0.5 → More stocks declining

**VPB vs IPB Divergence (Diagnostic):**
- VPB high + IPB low = Narrow leadership (mega-cap driven participation)
- VPB low + IPB high = Broad but weak participation
- Both high = Healthy broad participation
- Both low = Broad weakness

### 3.3 Structural Breadth Confirmation (SBC)

Measures underlying market structure.

```
SBC_t = (pct_MA50 + pct_MA200) / 2
```

Where:
- pct_MA50 = % of stocks trading above 50-day SMA
- pct_MA200 = % of stocks trading above 200-day SMA

Calculated from 50 stocks sampled from the AURORA Universe (quality-filtered NYSE/NASDAQ, $2B+ market cap) via FMP technical indicators API.

### 3.4 Institutional Participation Overlay (IPO)

Detects unusual institutional volume activity.

```
IPO_t = count(RelVol_i > Q90 AND RelVol_i > median) / N
```

Dual filter prevents:
- Small-cap noise (stock-specific Q90 not enough)
- Crisis saturation (universe median as floor)

Data source: Unusual Whales lit exchange volume (NO dark pool).

---

## 4. Baseline Framework

### 4.1 Parameters

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| Rolling window | W = 63 days | ~1 quarter |
| Minimum observations | N_min = 21 | ~1 month |

### 4.2 Normalization

Z-scores are calculated WITHOUT clipping (preserve tail information):

```
Z_X(t) = (X_t - μ_X) / σ_X
```

**Rationale:** Breadth distributions have fat tails. Crisis signals live in the tails. Percentile ranking naturally compresses outliers.

### 4.3 Baseline States

| State | Condition | Behavior |
|-------|-----------|----------|
| COMPLETE | All features have n ≥ 21 | Full diagnostic |
| PARTIAL | Some features have n < 21 | Partial diagnosis |
| INSUFFICIENT | All features have n < 21 | No diagnosis |

---

## 5. Composite Score

### 5.1 Formula

```
S_BMI = 0.30×Z_VPB + 0.25×Z_IPB + 0.25×Z_SBC + 0.20×Z_IPO
```

**Weights are FROZEN conceptual allocations. Do NOT tune.**

### 5.2 AURORA Score

```
AURORA = 100 - PercentileRank(S_BMI)
```

**INVERTED** so that:
- High composite (good breadth) → LOW score → GREEN
- Low composite (poor breadth) → HIGH score → RED

---

## 6. Interpretation Bands

| Score | Band | Meaning |
|-------|------|---------|
| 0-25 | GREEN | Healthy participation |
| 25-50 | LIGHT_GREEN | Moderate participation |
| 50-75 | YELLOW | Weakening participation |
| 75-100 | RED | Poor participation |

---

## 7. Architecture

```
Sources (Polygon / FMP / UW)
    │
    ▼
Async Ingest → Raw Cache
    │
    ▼
Feature Extraction (VPB, IPB, SBC, IPO)
    │
    ▼
Normalization (63d rolling z-score)
    │
    ▼
Composite Score → Percentile Rank → INVERT
    │
    ▼
Band Classification + Explanation
    │
    ▼
Dashboard (Streamlit)
```

---

## 8. Project Structure

```
aurora_bmi/
├── aurora/
│   ├── core/           # Types, config, constants
│   ├── ingest/         # API clients (Polygon, FMP, UW)
│   ├── features/       # Feature calculators
│   ├── normalization/  # Rolling z-score, percentile
│   ├── scoring/        # Composite, engine
│   ├── explain/        # Explanation generator
│   ├── pipeline/       # Daily orchestrator
│   ├── dashboard/      # Streamlit UI
│   └── universe/       # Quality-filtered stock universe
├── config/             # YAML configuration
├── data/
│   ├── raw/            # API cache
│   └── processed/      # BMI history
├── scripts/            # CLI entry points
└── tests/              # Unit tests
```

---

## 9. Quick Start

### Installation

```bash
cd aurora_bmi
uv sync

# Configure API keys
cp .env.example .env
nano .env
```

### Run Daily Pipeline

```bash
uv run python scripts/run_daily.py
```

### Launch Dashboard

```bash
uv run streamlit run aurora/dashboard/app.py --server.port 8503
```

---

## 10. API Keys Required

| Provider | Environment Variable |
|----------|---------------------|
| Polygon.io | POLYGON_API_KEY |
| FMP | FMP_API_KEY |
| Unusual Whales | UW_API_KEY |

---

## Disclaimer

This software is provided for **educational and diagnostic purposes only**. It measures market participation health, not price direction. It does not generate trading signals and should not be used to make investment decisions.
