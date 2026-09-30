"""Reliability View — Fleet Risk & Failure Analysis.

Follows Section 28 of AGENT.md:
- Fleet health distribution
- Risk score distribution across assets
- Active reliability alerts
- Failure modes taxonomy
- Historical failure records
"""

from __future__ import annotations

import streamlit as st
import plotly.graph_objects as go

from app.streamlit.services.view_service import CommandCenterFacade
from domain.enums import HealthStatus


def render_reliability_view(facade: CommandCenterFacade) -> None:
    """Render fleet reliability and risk analysis view."""
    st.markdown(
        """
        <div style="margin-bottom: 14px;">
            <div style="font-size: 20px; font-weight: 800; color: #f8fafc; letter-spacing: -0.02em;">
                FLEET RELIABILITY & FAILURE RISK
            </div>
            <div style="font-size: 12px; color: #94a3b8;">
                Fleet health monitoring, predictive failure risk distributions, and historical failure analysis.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    machines = facade.repo.list_machines()
    alerts = facade.repo.list_alerts()
    failures = facade.repo.get_failure_history("M204")

    # Fleet Health Breakdown
    col_h1, col_h2, col_h3 = st.columns(3)
    healthy_cnt = sum(1 for m in machines if m.health_status == HealthStatus.HEALTHY)
    warning_cnt = sum(1 for m in machines if m.health_status == HealthStatus.DEGRADING)
    critical_cnt = sum(1 for m in machines if m.health_status == HealthStatus.CRITICAL)

    with col_h1:
        st.markdown(
            f"""
            <div class="ind-card">
                <div class="metric-label">Healthy Assets</div>
                <div class="metric-value" style="color: #10b981;">{healthy_cnt} / {len(machines)}</div>
                <div class="metric-delta" style="color: #10b981;">Nominal vibration & temp</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col_h2:
        st.markdown(
            f"""
            <div class="ind-card">
                <div class="metric-label">Degrading / Warning</div>
                <div class="metric-value" style="color: #f59e0b;">{warning_cnt}</div>
                <div class="metric-delta" style="color: #f59e0b;">Precursor drift observed</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col_h3:
        st.markdown(
            f"""
            <div class="ind-card">
                <div class="metric-label">Critical High-Risk</div>
                <div class="metric-value" style="color: #ef4444;">{critical_cnt}</div>
                <div class="metric-delta" style="color: #ef4444;">Intervention required</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("<hr style='border: none; border-bottom: 1px solid #1f2430; margin: 16px 0;'/>", unsafe_allow_html=True)

    # Risk Distribution Bar Chart
    col_chart, col_fail = st.columns([3, 2])

    with col_chart:
        st.markdown("<b>Fleet Failure Risk Scores:</b>", unsafe_allow_html=True)
        mach_names = []
        risk_scores = []
        colors = []

        for m in machines:
            mach_names.append(m.machine_id)
            r = facade.repo.get_latest_failure_risk(m.machine_id)
            score = (r.risk_score * 100) if r else 10.0
            risk_scores.append(score)
            colors.append("#ef4444" if score > 70 else ("#f59e0b" if score > 40 else "#10b981"))

        fig = go.Figure(
            go.Bar(
                x=mach_names,
                y=risk_scores,
                marker_color=colors,
                text=[f"{s:.0f}%" for s in risk_scores],
                textposition="auto",
            )
        )
        fig.update_layout(
            paper_bgcolor="#12151c",
            plot_bgcolor="#161922",
            font=dict(color="#cbd5e1", size=11),
            yaxis=dict(title="Failure Risk (%)", range=[0, 100], gridcolor="#232936"),
            xaxis=dict(gridcolor="#232936"),
            margin=dict(l=30, r=20, t=25, b=20),
            height=300,
        )
        st.plotly_chart(fig, use_container_width=True)

    with col_fail:
        st.markdown("<b>Active Fleet Alerts:</b>", unsafe_allow_html=True)
        if alerts:
            for a in alerts:
                st.markdown(
                    f"""
                    <div class="ind-card" style="margin-bottom: 8px;">
                        <span class="badge badge-critical">{a.severity.value}</span>
                        <span style="font-size: 12px; font-weight: 700; color: #f8fafc; margin-left: 6px;">{a.machine_id} — {a.title}</span>
                        <div style="font-size: 11px; color: #94a3b8; margin-top: 2px;">{a.description}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
        else:
            st.info("No active alerts.")

    st.markdown("<hr style='border: none; border-bottom: 1px solid #1f2430; margin: 16px 0;'/>", unsafe_allow_html=True)

    # Historical Failures
    st.markdown("<b>Precedent Failure Incidents:</b>", unsafe_allow_html=True)
    if failures:
        for f in failures:
            st.markdown(
                f"- **{f.occurred_at.strftime('%Y-%m-%d')}** (`{f.machine_id}`): **{f.failure_mode.value}** — Root Cause: {f.root_cause} | Downtime: {f.downtime_hours}h | Action: {f.maintenance_action_taken}",
                unsafe_allow_html=True,
            )
    else:
        st.caption("No historical failure records found.")
