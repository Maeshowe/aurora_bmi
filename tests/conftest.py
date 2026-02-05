"""
Pytest configuration and fixtures for AURORA BMI tests.
"""

from datetime import date

import pytest


@pytest.fixture
def trade_date() -> date:
    """Standard test trade date."""
    return date(2024, 1, 15)


@pytest.fixture
def healthy_market_features() -> dict:
    """Features indicating healthy breadth (should be GREEN)."""
    return {
        "v_adv": 3_000_000_000,
        "v_dec": 1_000_000_000,
        "n_adv": 400,
        "n_dec": 100,
        "pct_ma50": 75.0,
        "pct_ma200": 80.0,
        "rel_vol_values": [2.1, 2.5, 2.8, 3.0, 2.2] * 20,
    }


@pytest.fixture
def poor_market_features() -> dict:
    """Features indicating poor breadth (should be RED)."""
    return {
        "v_adv": 800_000_000,
        "v_dec": 3_200_000_000,
        "n_adv": 80,
        "n_dec": 420,
        "pct_ma50": 25.0,
        "pct_ma200": 30.0,
        "rel_vol_values": [0.8, 0.9, 0.7, 0.6, 0.8] * 20,
    }


@pytest.fixture
def neutral_market_features() -> dict:
    """Features indicating neutral breadth (should be YELLOW/LIGHT_GREEN)."""
    return {
        "v_adv": 2_000_000_000,
        "v_dec": 2_000_000_000,
        "n_adv": 250,
        "n_dec": 250,
        "pct_ma50": 50.0,
        "pct_ma200": 50.0,
        "rel_vol_values": [1.0, 1.1, 0.9, 1.2, 0.8] * 20,
    }


@pytest.fixture
def narrow_leadership_features() -> dict:
    """Features showing VPB/IPB divergence (narrow leadership)."""
    return {
        "v_adv": 3_500_000_000,  # High VPB
        "v_dec": 500_000_000,
        "n_adv": 200,  # Lower IPB relative
        "n_dec": 300,
        "pct_ma50": 60.0,
        "pct_ma200": 65.0,
        "rel_vol_values": [1.5, 1.8, 1.6, 1.7, 1.9] * 20,
    }


@pytest.fixture
def insufficient_history() -> list[dict]:
    """Only 15 days of history (< N_min=21)."""
    return [
        {"date": f"2024-01-{i:02d}", "VPB": 0.5 + i * 0.01, "IPB": 0.5}
        for i in range(1, 16)
    ]


@pytest.fixture
def sufficient_history() -> list[dict]:
    """63 days of history (> N_min=21)."""
    return [
        {
            "date": f"2024-{(i // 28) + 1:02d}-{(i % 28) + 1:02d}",
            "VPB": 0.5 + (i % 10) * 0.02,
            "IPB": 0.5 + (i % 10) * 0.015,
            "SBC": 0.55 + (i % 5) * 0.01,
            "IPO": 0.1 + (i % 8) * 0.02,
        }
        for i in range(63)
    ]


@pytest.fixture
def sample_z_scores() -> dict[str, float]:
    """Sample z-scores for testing."""
    return {
        "VPB": 1.5,
        "IPB": 1.0,
        "SBC": -0.5,
        "IPO": 0.8,
    }


@pytest.fixture
def extreme_z_scores() -> dict[str, float]:
    """Extreme z-scores (should NOT be clipped)."""
    return {
        "VPB": 4.5,  # Would be clipped to 3 if clipping was applied
        "IPB": -5.0,  # Would be clipped to -3 if clipping was applied
        "SBC": 0.0,
        "IPO": 2.0,
    }
