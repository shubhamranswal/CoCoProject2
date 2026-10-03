"""Industrial KPI Metric Cards Component.

Follows Section 12 of DeRule Product Specification:
- Key Signals: Critical Alerts, Machines At Risk, Open Work Orders, Production Exposure
- Reliability Overview: Overall OEE, Availability, Performance, Quality
- Semantic color coding and delta targets
- Zero emojis and clean enterprise styling
"""

from __future__ import annotations

from typing import Any, Dict
import streamlit as st


def render_key_signals(kpis: Dict[str, Any]) -> None:
    """Render the 4 DeRule Key Operational Signals."""
    c1, c2, c3, c4 = st.columns(4)

    alerts_cnt = kpis.get("active_alerts", 0)
    crit_cnt = kpis.get("critical_assets", 0)
    wo_cnt = kpis.get("open_work_orders", 0)
    app_cnt = kpis.get("pending_approvals", 0)

    alert_color = "#dc2626" if alerts_cnt > 0 else "#16a34a"
    crit_color = "#dc2626" if crit_cnt > 0 else "#16a34a"

    with c1:
        st.markdown(
            f"""
            <div class="ind-card">
                <div class="metric-label">Critical Alerts</div>
                <div class="metric-value" style="color: {alert_color};">{alerts_cnt}</div>
                <div class="metric-delta" style="color: var(--text-muted);">
                    {'Action required' if alerts_cnt > 0 else 'All nominal'}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with c2:
        st.markdown(
            f"""
            <div class="ind-card">
                <div class="metric-label">Machines At Risk</div>
                <div class="metric-value" style="color: {crit_color};">{crit_cnt}</div>
                <div class="metric-delta" style="color: var(--text-muted);">
                    {f'{crit_cnt} asset requiring review' if crit_cnt > 0 else '0 at risk'}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with c3:
        st.markdown(
            f"""
            <div class="ind-card">
                <div class="metric-label">Open Work Orders</div>
                <div class="metric-value">{wo_cnt}</div>
                <div class="metric-delta" style="color: var(--primary-accent); font-weight: 600;">
                    CMMS Dispatched
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with c4:
        exposure_label = f"{crit_cnt} Production Line Affected" if crit_cnt > 0 else "Nominal Line Schedule"
        st.markdown(
            f"""
            <div class="ind-card">
                <div class="metric-label">Production Exposure</div>
                <div class="metric-value" style="font-size: 16px; margin-top: 4px; color: {'#d97706' if crit_cnt > 0 else '#16a34a'};">
                    {exposure_label}
                </div>
                <div class="metric-delta" style="color: var(--text-muted);">
                    {'Mitigation required' if crit_cnt > 0 else 'Zero bottleneck'}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_reliability_overview(kpis: Dict[str, Any]) -> None:
    """Render the Reliability Overview metrics grid."""
    c1, c2, c3, c4 = st.columns(4)

    oee_pct = kpis.get("oee", 0.0) * 100
    avail_pct = kpis.get("availability", 0.0) * 100
    perf_pct = kpis.get("performance", 0.95) * 100
    qual_pct = kpis.get("quality", 0.98) * 100

    with c1:
        st.markdown(
            f"""
            <div class="ind-card">
                <div class="metric-label">Overall Fleet OEE</div>
                <div class="metric-value">{oee_pct:.1f}%</div>
                <div class="metric-delta" style="color: {'#16a34a' if oee_pct >= 85 else '#d97706'}; font-weight: 600;">
                    Target: 85.0%
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with c2:
        st.markdown(
            f"""
            <div class="ind-card">
                <div class="metric-label">Availability</div>
                <div class="metric-value">{avail_pct:.1f}%</div>
                <div class="metric-delta" style="color: {'#16a34a' if avail_pct >= 90 else '#dc2626'}; font-weight: 600;">
                    Target: 92.0%
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with c3:
        st.markdown(
            f"""
            <div class="ind-card">
                <div class="metric-label">Performance</div>
                <div class="metric-value">{perf_pct:.1f}%</div>
                <div class="metric-delta" style="color: {'#16a34a' if perf_pct >= 90 else '#d97706'}; font-weight: 600;">
                    Target: 90.0%
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with c4:
        st.markdown(
            f"""
            <div class="ind-card">
                <div class="metric-label">Quality</div>
                <div class="metric-value">{qual_pct:.1f}%</div>
                <div class="metric-delta" style="color: {'#16a34a' if qual_pct >= 95 else '#d97706'}; font-weight: 600;">
                    Target: 95.0%
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_kpi_row(kpis: Dict[str, Any]) -> None:
    """Render the top-level factory KPI grid (retained for backward compatibility)."""
    render_key_signals(kpis)
