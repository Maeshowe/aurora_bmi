"""
AURORA BMI Streamlit Dashboard.

Main entry point for the dashboard application.
Run with: streamlit run aurora/dashboard/app.py
"""

import streamlit as st

from aurora.dashboard.components.band_indicator import render_band_indicator
from aurora.dashboard.components.feature_breakdown import render_feature_breakdown
from aurora.dashboard.components.score_card import render_score_card
from aurora.pipeline.daily import DailyPipeline
from aurora.universe import UniverseBuilder


def main() -> None:
    """Main dashboard application."""
    st.set_page_config(
        page_title="AURORA BMI",
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    st.title("AURORA BMI")
    st.markdown("**Baseline-normalized Market Breadth Index**")

    # Sidebar
    with st.sidebar:
        st.header("About AURORA BMI")
        st.markdown(
            """
            AURORA BMI measures market participation health.

            **Bands:**
            - 🟢 GREEN (0-25): Healthy breadth
            - 🟡 LIGHT GREEN (25-50): Moderate
            - 🟠 YELLOW (50-75): Weakening
            - 🔴 RED (75-100): Poor breadth

            **Components:**
            - VPB: Volume Participation
            - IPB: Issue Participation
            - SBC: Structural Breadth
            - IPO: Institutional Overlay
            """
        )

        st.divider()

        st.markdown(
            """
            **Design Notes:**
            - Lower score = healthier breadth
            - Z-scores NOT clipped (tails preserved)
            - Percentile ranking is ONLY bounding
            """
        )

    # Load pipeline
    pipeline = DailyPipeline()

    # Get historical data
    history = pipeline.get_history()

    if history.empty:
        st.warning(
            "No historical data available. Run the daily pipeline first:\n"
            "```\npython scripts/run_daily.py\n```"
        )
        return

    # Get latest result
    latest = history.iloc[-1]

    # Main content
    col1, col2 = st.columns([2, 1])

    with col1:
        # Score card
        render_score_card(
            score=latest["score"],
            band=latest["band"],
            date_str=str(latest["date"]),
        )

    with col2:
        # Band indicator (semicircular gauge)
        render_band_indicator(latest["band"], score=latest["score"])

    # Universe Statistics
    st.markdown("### AURORA Universe")
    universe_builder = UniverseBuilder()
    try:
        from datetime import date
        latest_date = date.fromisoformat(str(latest["date"]))
        universe = universe_builder.load_snapshot(latest_date)
        if universe:
            ucol1, ucol2, ucol3, ucol4 = st.columns(4)
            with ucol1:
                st.metric("Stocks", f"{universe.count:,}")
            with ucol2:
                if universe.median_market_cap:
                    st.metric("Median MCap", f"${universe.median_market_cap/1e9:.1f}B")
                else:
                    st.metric("Median MCap", "N/A")
            with ucol3:
                if universe.median_volume:
                    st.metric("Median Volume", f"{universe.median_volume/1e6:.1f}M")
                else:
                    st.metric("Median Volume", "N/A")
            with ucol4:
                if universe.size_change_pct is not None:
                    delta_str = f"{universe.size_change_pct*100:+.1f}%"
                    st.metric(
                        "Size Change",
                        delta_str,
                        delta=delta_str if universe.size_change_warning else None,
                        delta_color="inverse" if universe.size_change_warning else "off",
                    )
                else:
                    st.metric("Size Change", "N/A")

            if universe.size_change_warning:
                st.warning(
                    f"Universe size changed significantly: "
                    f"{universe.previous_count} → {universe.count} "
                    f"({universe.size_change_pct*100:+.1f}%)"
                )
        else:
            st.info("No universe snapshot available for this date.")
    except Exception as e:
        st.warning(f"Could not load universe data: {e}")

    # Explanation
    st.markdown("### Interpretation")
    st.info(latest.get("explanation", "No explanation available."))

    # Feature breakdown
    st.markdown("### Component Breakdown")

    # Extract component data
    components = []
    for name in ["VPB", "IPB", "SBC", "IPO"]:
        zscore_col = f"{name}_zscore"
        raw_col = f"{name}_raw"
        contrib_col = f"{name}_contribution"

        if zscore_col in latest:
            components.append({
                "name": name,
                "zscore": latest[zscore_col],
                "raw_value": latest.get(raw_col, 0),
                "contribution": latest.get(contrib_col, 0),
            })

    if components:
        render_feature_breakdown(components)
    else:
        st.warning("No component data available.")

    # Historical chart
    st.markdown("### Historical Trend")

    if len(history) > 1:
        import plotly.graph_objects as go

        fig = go.Figure()

        # Score line
        fig.add_trace(
            go.Scatter(
                x=history["date"].astype(str),
                y=history["score"],
                mode="lines+markers",
                name="AURORA BMI",
                line=dict(color="#3b82f6", width=2),
                marker=dict(size=6),
            )
        )

        # Band zones
        fig.add_hrect(y0=0, y1=25, fillcolor="green", opacity=0.1, line_width=0)
        fig.add_hrect(y0=25, y1=50, fillcolor="lightgreen", opacity=0.1, line_width=0)
        fig.add_hrect(y0=50, y1=75, fillcolor="yellow", opacity=0.1, line_width=0)
        fig.add_hrect(y0=75, y1=100, fillcolor="red", opacity=0.1, line_width=0)

        fig.update_layout(
            yaxis_title="AURORA BMI Score",
            xaxis_title="Date",
            yaxis_range=[0, 100],
            height=400,
            margin=dict(l=0, r=0, t=30, b=0),
        )

        st.plotly_chart(fig, use_container_width=True, key="historical_chart")
    else:
        st.info("Need more data points for historical chart.")

    # VPB/IPB Divergence
    if "VPB_zscore" in latest and "IPB_zscore" in latest:
        vpb_z = latest["VPB_zscore"]
        ipb_z = latest["IPB_zscore"]
        divergence = vpb_z - ipb_z

        st.markdown("### VPB/IPB Divergence")
        st.markdown(
            f"**Divergence:** {divergence:+.2f}σ "
            f"(VPB: {vpb_z:+.2f}σ, IPB: {ipb_z:+.2f}σ)"
        )

        if abs(divergence) > 1.0:
            if divergence > 0:
                st.warning(
                    "VPB > IPB: Narrow, mega-cap driven leadership detected. "
                    "Volume concentrated in few names."
                )
            else:
                st.warning(
                    "IPB > VPB: Broad but weak participation detected. "
                    "Many stocks participating with low volume."
                )
        else:
            st.success("VPB and IPB are aligned.")

    # Data table
    with st.expander("Raw Data"):
        st.dataframe(history.tail(20))


if __name__ == "__main__":
    main()
