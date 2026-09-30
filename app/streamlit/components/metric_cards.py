"""Industrial KPI Metric Cards Component.

Follows Section 10 of AGENT.md:
- Renders deterministic operational metrics: Overall OEE, Availability, Active Alerts, Critical Assets, Open Work Orders, Pending Approvals
- Semantic color coding and delta percentages
"""

from __future__ import annotations

from typing import Any, Dict
import streamlit as st


def render_kpi_row(kpis: Dict[str, Any]) -> None:
    """Render the top-level factory KPI grid."""
    c1, c2, c3, c4, c5, c6 = st.columns(6)

    oee_pct = kpis.get("oee", 0.0) * 100
    avail_pct = kpis.get("availability", 0.0) * 100
    alerts_cnt = kpis.get("active_alerts", 0)
    crit_cnt = kpis.get("critical_assets", 0)
    wo_cnt = kpis.get("open_work_orders", 0)
    app_cnt = kpis.get("pending_approvals", 0)

    with c1:
        st.markdown(
            f"""
            <div class="ind-card">
                <div class="metric-label">Overall OEE</div>
                <div class="metric-value">{oee_pct:.1f}%</div>
                <div class="metric-delta" style="color: {'#10b981' if oee_pct >= 85 else '#f59e0b'};">
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
                <div class="metric-delta" style="color: {'#10b981' if avail_pct >= 90 else '#ef4444'};">
                    Target: 92.0%
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with c3:
        alert_color = "#ef4444" if alerts_cnt > 0 else "#10b981"
        st.markdown(
            f"""
            <div class="ind-card">
                <div class="metric-label">Active Alerts</div>
                <div class="metric-value" style="color: {alert_color};">{alerts_cnt}</div>
                <div class="metric-delta" style="color: #94a3b8;">
                    {'Action required' if alerts_cnt > 0 else 'All assets nominal'}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with c4:
        crit_color = "#ef4444" if crit_cnt > 0 else "#10b981"
        st.markdown(
            f"""
            <div class="ind-card">
                <div class="metric-label">Critical Assets</div>
                <div class="metric-value" style="color: {crit_color};">{crit_cnt}</div>
                <div class="metric-delta" style="color: #94a3b8;">
                    {'M204 At-Risk' if crit_cnt > 0 else '0 at risk'}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with c5:
        st.markdown(
            f"""
            <div class="ind-card">
                <div class="metric-label">Open Work Orders</div>
                <div class="metric-value">{wo_cnt}</div>
                <div class="metric-delta" style="color: #38bdf8;">
                    CMMS Dispatched
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with c6:
        app_color = "#f59e0b" if app_cnt > 0 else "#94a3b8"
        st.markdown(
            f"""
            <div class="ind-card">
                <div class="metric-label">Pending Approvals</div>
                <div class="metric-value" style="color: {app_color};">{app_cnt}</div>
                <div class="metric-delta" style="color: {'#f59e0b' if app_cnt > 0 else '#94a3b8'};">
                    {'Human Review Req.' if app_cnt > 0 else 'None pending'}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
