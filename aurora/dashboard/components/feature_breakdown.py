"""
Feature breakdown component for AURORA BMI dashboard.

Displays component z-scores and contributions as a bar chart.
"""

from typing import Any

import plotly.graph_objects as go
import streamlit as st

FEATURE_NAMES_FULL = {
    "VPB": "Volume Participation Breadth",
    "IPB": "Issue Participation Breadth",
    "SBC": "Structural Breadth Confirmation",
    "IPO": "Institutional Participation Overlay",
}

FEATURE_WEIGHTS = {
    "VPB": 0.30,
    "IPB": 0.25,
    "SBC": 0.25,
    "IPO": 0.20,
}


def render_feature_breakdown(components: list[dict[str, Any]]) -> None:
    """
    Render feature breakdown chart.

    Args:
        components: List of component dicts with name, zscore, contribution
    """
    if not components:
        st.info("No component data available.")
        return

    # Create bar chart
    names = [c["name"] for c in components]
    zscores = [c["zscore"] for c in components]
    contributions = [c.get("contribution", 0) for c in components]

    # Color based on z-score direction
    colors = ["#22c55e" if z > 0 else "#ef4444" for z in zscores]

    fig = go.Figure()

    # Z-score bars
    fig.add_trace(
        go.Bar(
            name="Z-Score",
            x=names,
            y=zscores,
            marker_color=colors,
            text=[f"{z:+.2f}σ" for z in zscores],
            textposition="outside",
        )
    )

    fig.update_layout(
        title="Component Z-Scores (NOT clipped - tail information preserved)",
        yaxis_title="Z-Score",
        showlegend=False,
        height=300,
        margin=dict(l=0, r=0, t=50, b=0),
    )

    st.plotly_chart(fig, width="stretch")

    # Component details table
    cols = st.columns(len(components))

    for i, comp in enumerate(components):
        with cols[i]:
            name = comp["name"]
            zscore = comp["zscore"]
            weight = FEATURE_WEIGHTS.get(name, 0)
            contribution = comp.get("contribution", zscore * weight)

            # Direction indicator
            if zscore > 0.5:
                indicator = "🔼"
                status = "Elevated"
            elif zscore < -0.5:
                indicator = "🔽"
                status = "Depressed"
            else:
                indicator = "➡️"
                status = "Neutral"

            st.markdown(
                f"""
                <div style="
                    background: #f9fafb;
                    padding: 0.75rem;
                    border-radius: 0.25rem;
                    text-align: center;
                ">
                    <div style="font-weight: bold;">{name}</div>
                    <div style="font-size: 1.5rem;">{indicator}</div>
                    <div style="font-size: 0.875rem; color: #6b7280;">{status}</div>
                    <div style="font-size: 0.75rem; color: #9ca3af;">
                        z={zscore:+.2f} | w={weight:.0%}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    # Explanation of components
    with st.expander("Component Definitions"):
        st.markdown(
            """
            **VPB (Volume Participation Breadth)**: Dollar-weighted participation.
            Measures where the money is flowing. High VPB = volume in advances.

            **IPB (Issue Participation Breadth)**: Count-weighted participation.
            Measures breadth of participation. High IPB = many stocks advancing.

            **SBC (Structural Breadth Confirmation)**: Slow structural metrics.
            Average of % above MA50 and MA200. Confirms underlying structure.

            **IPO (Institutional Participation Overlay)**: Volume spike detection.
            Identifies unusual volume on lit exchanges (dual filter applied).

            ---

            **VPB/IPB Divergence** is a monitored diagnostic:
            - VPB high + IPB low = Narrow, mega-cap leadership
            - IPB high + VPB low = Broad but weak participation
            """
        )
