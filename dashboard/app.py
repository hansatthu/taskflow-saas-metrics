"""
Step 4 — Dashboard.

Streamlit app with three views over the Step 3 metric outputs:
  Growth Overview   - MRR trend + MRR waterfall
  Retention Health  - churn trend, NRR trend, cohort retention heatmap
  Unit Economics    - LTV:CAC by channel, CAC/LTV by channel

Run with:  streamlit run dashboard/app.py
"""

from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# ----------------------------------------------------------------------
# Palette (validated categorical / sequential / status colors)
# ----------------------------------------------------------------------
INK = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"
GRID = "#e1e0d9"
BASELINE = "#c3c2b7"
SURFACE = "#fcfcfb"

CAT = {
    "blue": "#2a78d6",
    "orange": "#eb6834",
    "aqua": "#1baf7a",
    "yellow": "#eda100",
    "magenta": "#e87ba4",
}
SEQ_BLUE = ["#cde2fb", "#9ec5f4", "#5598e7", "#2a78d6", "#184f95"]
GOOD = "#0ca30c"
CRITICAL = "#d03b3b"

# Fixed channel -> color mapping, reused across every chart on the page.
CHANNEL_COLOR = {
    "Paid Ads": CAT["blue"],
    "Organic Search": CAT["orange"],
    "Referral": CAT["aqua"],
    "Content Marketing": CAT["yellow"],
    "Outbound Sales": CAT["magenta"],
}
WATERFALL_COLOR = {
    "New": CAT["blue"],
    "Expansion": CAT["orange"],
    "Contraction": CAT["aqua"],
    "Churned": CAT["yellow"],
}

FONT = dict(family="Segoe UI, system-ui, -apple-system, sans-serif", color=INK, size=13)

st.set_page_config(page_title="TaskFlow — SaaS Metrics", layout="wide")

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "output"


@st.cache_data
def load(name, date_cols=None):
    return pd.read_csv(OUTPUT / name, parse_dates=date_cols or [])


def style(fig, y_title="", x_title="", legend=True):
    fig.update_layout(
        template="plotly_white",
        font=FONT,
        paper_bgcolor=SURFACE,
        plot_bgcolor=SURFACE,
        margin=dict(l=10, r=10, t=30, b=10),
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0,
            font=dict(color=INK_SECONDARY, size=12),
        ) if legend else None,
        showlegend=legend,
        hoverlabel=dict(bgcolor=SURFACE, font=FONT, bordercolor=BASELINE),
    )
    fig.update_xaxes(
        title=dict(text=x_title, font=dict(color=INK_MUTED, size=12)),
        showgrid=False, linecolor=BASELINE, tickfont=dict(color=INK_MUTED),
    )
    fig.update_yaxes(
        title=dict(text=y_title, font=dict(color=INK_MUTED, size=12)),
        showgrid=True, gridcolor=GRID, zeroline=True, zerolinecolor=BASELINE,
        tickfont=dict(color=INK_MUTED),
    )
    return fig


st.title("TaskFlow — SaaS Metrics")
st.caption(
    "Jan 2023 – Dec 2024 · reconstructed from the subscription event ledger · "
    "gross margin assumption: 80%"
)

tab_growth, tab_retention, tab_unit = st.tabs(
    ["Growth Overview", "Retention Health", "Unit Economics"]
)

# ========================================================================
# TAB 1 — Growth Overview
# ========================================================================
with tab_growth:
    mrr = load("mrr_by_month.csv", ["month"])
    waterfall = load("mrr_waterfall.csv", ["month"])
    nrr = load("nrr_by_month.csv", ["month"])
    snapshot_last = pd.read_csv(OUTPUT / "monthly_snapshot.csv")
    last_month = snapshot_last.month.max()
    active_paying = (
        (snapshot_last.month == last_month) & (snapshot_last.plan != "Free")
    ).sum()

    current_mrr = mrr.mrr.iloc[-1]
    prev_mrr = mrr.mrr.iloc[-2]
    mom_growth = (current_mrr - prev_mrr) / prev_mrr
    latest_nrr = nrr.nrr.dropna().iloc[-1]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("MRR (Dec 2024)", f"${current_mrr:,.0f}", f"{mom_growth:+.1%} MoM")
    c2.metric("MRR growth, 24 mo", f"{(current_mrr / mrr.mrr.iloc[0] - 1):,.0%}")
    c3.metric("NRR (latest month)", f"{latest_nrr:.1%}")
    c4.metric("Active paying customers", f"{active_paying:,}")

    st.subheader("MRR over time")
    fig = go.Figure(
        go.Scatter(
            x=mrr.month, y=mrr.mrr, mode="lines", line=dict(color=CAT["blue"], width=2.5),
            fill="tozeroy", fillcolor="rgba(42,120,214,0.10)", name="MRR",
            hovertemplate="%{x|%b %Y}<br>$%{y:,.0f}<extra></extra>",
        )
    )
    st.plotly_chart(style(fig, y_title="MRR (USD)"), use_container_width=True)

    st.subheader("MRR waterfall — New / Expansion / Contraction / Churned")
    fig = go.Figure()
    for col, label in [
        ("new_mrr", "New"), ("expansion_mrr", "Expansion"),
        ("contraction_mrr", "Contraction"), ("churned_mrr", "Churned"),
    ]:
        fig.add_bar(
            x=waterfall.month, y=waterfall[col], name=label,
            marker_color=WATERFALL_COLOR[label],
            hovertemplate="%{x|%b %Y}<br>" + label + ": $%{y:,.0f}<extra></extra>",
        )
    fig.update_layout(barmode="relative")
    st.plotly_chart(style(fig, y_title="MRR movement (USD)"), use_container_width=True)

    st.caption(
        "Ending MRR each month = starting MRR + New + Expansion + Contraction + "
        "Churned. Growth over the full period is driven almost entirely by New "
        "MRR — see the Retention tab for what that implies about NRR."
    )

# ========================================================================
# TAB 2 — Retention Health
# ========================================================================
with tab_retention:
    churn = load("churn_rate_by_month.csv", ["month"])
    nrr = load("nrr_by_month.csv", ["month"])
    cohort = load("cohort_retention.csv", ["cohort_month"])

    avg_logo_churn = churn.logo_churn_rate.mean()
    avg_rev_churn = churn.revenue_churn_rate.mean()
    avg_nrr = nrr.nrr.dropna().mean()
    m1_retention = cohort[cohort.months_since_signup == 1].retention_rate.mean()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Avg. logo churn / mo", f"{avg_logo_churn:.1%}")
    c2.metric("Avg. revenue churn / mo", f"{avg_rev_churn:.1%}")
    c3.metric("Avg. NRR", f"{avg_nrr:.1%}", "below 100%" if avg_nrr < 1 else "above 100%")
    c4.metric("Retention, 1 month after signup", f"{m1_retention:.1%}")

    st.subheader("Logo churn vs. revenue churn")
    fig = go.Figure()
    fig.add_scatter(
        x=churn.month, y=churn.logo_churn_rate, mode="lines+markers", name="Logo churn",
        line=dict(color=CAT["blue"], width=2.5), marker=dict(size=6),
        hovertemplate="%{x|%b %Y}<br>Logo churn: %{y:.1%}<extra></extra>",
    )
    fig.add_scatter(
        x=churn.month, y=churn.revenue_churn_rate, mode="lines+markers", name="Revenue churn",
        line=dict(color=CAT["orange"], width=2.5), marker=dict(size=6),
        hovertemplate="%{x|%b %Y}<br>Revenue churn: %{y:.1%}<extra></extra>",
    )
    fig.update_yaxes(tickformat=".0%")
    st.plotly_chart(style(fig, y_title="Monthly churn rate"), use_container_width=True)
    st.caption(
        "Revenue churn running below logo churn means churn is concentrated "
        "among lower-value accounts — higher-paying customers are comparatively sticky."
    )

    st.subheader("Net Revenue Retention")
    fig = go.Figure()
    fig.add_scatter(
        x=nrr.month, y=nrr.nrr, mode="lines+markers", name="NRR",
        line=dict(color=CAT["blue"], width=2.5), marker=dict(size=6),
        hovertemplate="%{x|%b %Y}<br>NRR: %{y:.1%}<extra></extra>",
    )
    fig.add_hline(y=1.0, line_dash="dash", line_color=BASELINE, annotation_text="100%",
                   annotation_font=dict(color=INK_MUTED))
    fig.update_yaxes(tickformat=".0%")
    st.plotly_chart(style(fig, y_title="NRR", legend=False), use_container_width=True)

    st.subheader("Cohort retention — % of signup cohort still active, by month since signup")
    pivot = cohort.pivot(index="cohort_month", columns="months_since_signup", values="retention_rate")
    fig = go.Figure(
        go.Heatmap(
            z=pivot.values, x=pivot.columns, y=pivot.index.strftime("%b %Y"),
            colorscale=[[i / (len(SEQ_BLUE) - 1), c] for i, c in enumerate(SEQ_BLUE)],
            zmin=0, zmax=1, colorbar=dict(title="Retention", tickformat=".0%"),
            hovertemplate="Cohort %{y}<br>Month +%{x}: %{z:.0%}<extra></extra>",
        )
    )
    st.plotly_chart(
        style(fig, y_title="Signup cohort", x_title="Months since signup", legend=False),
        use_container_width=True,
    )

# ========================================================================
# TAB 3 — Unit Economics
# ========================================================================
with tab_unit:
    ltv_cac = load("ltv_cac_by_channel.csv")
    ltv_cac = ltv_cac.sort_values("ltv_cac_ratio", ascending=True)

    best = ltv_cac.iloc[-1]
    worst = ltv_cac.iloc[0]
    blended_ltv_cac = ltv_cac.ltv_usd.sum() / ltv_cac.cac_usd.sum()

    c1, c2, c3 = st.columns(3)
    c1.metric("Best channel", best.acquisition_channel, f"{best.ltv_cac_ratio:.1f}:1")
    c2.metric("Weakest channel", worst.acquisition_channel, f"{worst.ltv_cac_ratio:.1f}:1")
    c3.metric("Blended LTV:CAC (all channels)", f"{blended_ltv_cac:.1f}:1")

    st.subheader("LTV:CAC ratio by channel")
    colors = [GOOD if r >= 3 else CRITICAL for r in ltv_cac.ltv_cac_ratio]
    fig = go.Figure(
        go.Bar(
            x=ltv_cac.ltv_cac_ratio, y=ltv_cac.acquisition_channel, orientation="h",
            marker_color=colors,
            text=[f"{r:.1f}:1" for r in ltv_cac.ltv_cac_ratio], textposition="outside",
            hovertemplate="%{y}<br>LTV:CAC %{x:.1f}:1<extra></extra>",
        )
    )
    fig.add_vline(x=3, line_dash="dash", line_color=INK_MUTED,
                   annotation_text="3:1 benchmark", annotation_font=dict(color=INK_MUTED))
    fig.update_layout(
        legend=dict(orientation="h", y=1.08, x=0),
        showlegend=True,
    )
    fig.add_bar(x=[None], y=[None], marker_color=GOOD, name="≥ 3:1 (healthy)")
    fig.add_bar(x=[None], y=[None], marker_color=CRITICAL, name="< 3:1 (below benchmark)")
    st.plotly_chart(style(fig, x_title="LTV : CAC"), use_container_width=True)

    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("LTV by channel")
        d = ltv_cac.sort_values("ltv_usd")
        fig = go.Figure(
            go.Bar(
                x=d.ltv_usd, y=d.acquisition_channel, orientation="h",
                marker_color=[CHANNEL_COLOR[c] for c in d.acquisition_channel],
                text=[f"${v:,.0f}" for v in d.ltv_usd], textposition="outside",
                hovertemplate="%{y}<br>LTV $%{x:,.0f}<extra></extra>",
            )
        )
        st.plotly_chart(style(fig, x_title="LTV (USD)", legend=False), use_container_width=True)
    with col_b:
        st.subheader("CAC by channel")
        d = ltv_cac.sort_values("cac_usd")
        fig = go.Figure(
            go.Bar(
                x=d.cac_usd, y=d.acquisition_channel, orientation="h",
                marker_color=[CHANNEL_COLOR[c] for c in d.acquisition_channel],
                text=[f"${v:,.0f}" for v in d.cac_usd], textposition="outside",
                hovertemplate="%{y}<br>CAC $%{x:,.0f}<extra></extra>",
            )
        )
        st.plotly_chart(style(fig, x_title="CAC (USD)", legend=False), use_container_width=True)

    st.caption(
        "LTV = (blended ARPU of currently-active paying customers x 80% gross "
        "margin) / average monthly logo churn rate. CAC is blended spend / new "
        "customers per channel over the full 24 months."
    )
