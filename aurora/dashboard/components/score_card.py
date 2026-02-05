"""
Score card component for AURORA BMI dashboard.

Displays the main BMI score with visual styling.
"""

import streamlit as st


BAND_COLORS = {
    "GREEN": "#22c55e",
    "LIGHT_GREEN": "#84cc16",
    "YELLOW": "#eab308",
    "RED": "#ef4444",
}

BAND_DESCRIPTIONS = {
    "GREEN": "Healthy Breadth",
    "LIGHT_GREEN": "Moderate Breadth",
    "YELLOW": "Weakening Breadth",
    "RED": "Poor Breadth",
}


def render_score_card(
    score: float,
    band: str,
    date_str: str,
) -> None:
    """
    Render the main score card.

    Args:
        score: AURORA BMI score (0-100)
        band: Band classification
        date_str: Date string for display
    """
    color = BAND_COLORS.get(band, "#6b7280")
    description = BAND_DESCRIPTIONS.get(band, "Unknown")

    st.markdown(
        f"""
        <div style="
            background: linear-gradient(135deg, {color}20, {color}10);
            border-left: 4px solid {color};
            padding: 1.5rem;
            border-radius: 0.5rem;
            margin-bottom: 1rem;
        ">
            <div style="font-size: 0.875rem; color: #6b7280; margin-bottom: 0.5rem;">
                AURORA BMI - {date_str}
            </div>
            <div style="display: flex; align-items: baseline; gap: 0.5rem;">
                <span style="font-size: 3rem; font-weight: bold; color: {color};">
                    {score:.1f}
                </span>
                <span style="font-size: 1.25rem; color: #6b7280;">
                    / 100
                </span>
            </div>
            <div style="font-size: 1rem; color: {color}; margin-top: 0.5rem;">
                {description}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
