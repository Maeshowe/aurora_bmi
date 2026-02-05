"""
Band indicator component for AURORA BMI dashboard.

Displays a semicircular gauge showing the current score.
"""

import plotly.graph_objects as go
import streamlit as st


def render_band_indicator(band: str, score: float = 50.0) -> None:
    """
    Render the semicircular gauge indicator.

    Args:
        band: Band classification (GREEN, LIGHT_GREEN, YELLOW, RED)
        score: BMI score (0-100)
    """
    # Create gauge chart
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=score,
            title={"text": "AURORA BMI Score", "font": {"size": 16, "color": "#6b7280"}},
            number={"font": {"size": 48, "color": "#1f2937"}, "suffix": ""},
            gauge={
                "axis": {
                    "range": [0, 100],
                    "tickwidth": 2,
                    "tickcolor": "#9ca3af",
                    "tickfont": {"color": "#6b7280", "size": 12},
                    "tickvals": [0, 20, 40, 60, 80, 100],
                },
                "bar": {"color": "rgba(0,0,0,0)"},  # Hide the bar, use threshold
                "bgcolor": "#f3f4f6",
                "borderwidth": 0,
                "steps": [
                    {"range": [0, 25], "color": "#22c55e"},      # GREEN
                    {"range": [25, 50], "color": "#84cc16"},     # LIGHT_GREEN
                    {"range": [50, 75], "color": "#eab308"},     # YELLOW
                    {"range": [75, 100], "color": "#ef4444"},    # RED
                ],
                "threshold": {
                    "line": {"color": "#1f2937", "width": 4},
                    "thickness": 0.8,
                    "value": score,
                },
            },
        )
    )

    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"color": "#374151"},
        height=280,
        margin=dict(l=30, r=30, t=50, b=20),
    )

    st.plotly_chart(fig, use_container_width=True)

    # Band label
    band_labels = {
        "GREEN": ("🟢", "Healthy Breadth"),
        "LIGHT_GREEN": ("🟡", "Moderate Breadth"),
        "YELLOW": ("🟠", "Weakening Breadth"),
        "RED": ("🔴", "Poor Breadth"),
    }
    emoji, label = band_labels.get(band, ("⚪", "Unknown"))
    st.markdown(f"<h3 style='text-align:center;'>{emoji} {label}</h3>", unsafe_allow_html=True)
