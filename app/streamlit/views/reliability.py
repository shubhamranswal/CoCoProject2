"""Reliability View — Fleet Risk & Failure Analysis.

Follows Section 28 of AGENT.md:
- Fleet health distribution
- Risk score distribution across assets
- Active reliability alerts
- Failure modes taxonomy
- Historical failure records
- Theme CSS variable styling and zero emojis
"""

from __future__ import annotations

import streamlit as st
import plotly.graph_objects as go

from app.streamlit.components.charts import get_plotly_layout
from app.streamlit.services.view_service import CommandCenterFacade
from domain.enums import HealthStatus


def render_reliability_view(facade: CommandCenterFacade) -> None:
    """Render fleet reliability and risk analysis view."""
    st.markdown(
        """
        <div style="margin-bottom: 14px;">
            <div style="font-size: 18px; font-weight: 700; color: var(--text-primary); letter-spacing: -0.02em;">
                FLEET RELIABILITY & FAILURE RISK
            </div>
            <div style="font-size: 12px; color: var(--text-muted);">
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
                <div class="metric-value" style="color: #16a34a;">{healthy_cnt} / {len(machines)}</div>
                <div class="metric-delta" style="color: #16a34a;">Nominal vibration & temp</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col_h2:
        st.markdown(
            f"""
            <div class="ind-card">
                <div class="metric-label">Degrading / Warning</div>
                <div class="metric-value" style="color: #d97706;">{warning_cnt}</div>
                <div class="metric-delta" style="color: #d97706;">Precursor drift observed</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col_h3:
        st.markdown(
            f"""
            <div class="ind-card">
                <div class="metric-label">Critical High-Risk</div>
                <div class="metric-value" style="color: #dc2626;">{critical_cnt}</div>
                <div class="metric-delta" style="color: #dc2626;">Intervention required</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("<hr style='border: none; border-bottom: 1px solid var(--border-subtle); margin: 16px 0;'/>", unsafe_allow_html=True)

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
            colors.append("#dc2626" if score > 70 else ("#d97706" if score > 40 else "#16a34a"))

        fig = go.Figure(
            go.Bar(
                x=mach_names,
                y=risk_scores,
                marker_color=colors,
                text=[f"{s:.0f}%" for s in risk_scores],
                textposition="auto",
            )
        )
        layout = get_plotly_layout()
        layout.update(
            yaxis=dict(title="Failure Risk (%)", range=[0, 100]),
            margin=dict(l=30, r=20, t=25, b=20),
            height=300,
        )
        fig.update_layout(**layout)
        st.plotly_chart(fig, width="stretch")

    with col_fail:
        st.markdown("<b>Active Fleet Alerts:</b>", unsafe_allow_html=True)
        if alerts:
            for a in alerts:
                st.markdown(
                    f"""
                    <div class="ind-card" style="margin-bottom: 8px;">
                        <span class="badge badge-critical">{a.severity.value}</span>
                        <span style="font-size: 12px; font-weight: 700; color: var(--text-primary); margin-left: 6px;">{a.machine_id} — {a.alert_id}</span>
                        <div style="font-size: 11px; color: var(--text-muted); margin-top: 2px;">{a.trigger_reason}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
        else:
            st.info("No active alerts.")

    st.markdown("<hr style='border: none; border-bottom: 1px solid var(--border-subtle); margin: 16px 0;'/>", unsafe_allow_html=True)

    # Predictive Risk Timeline (Deterministic vs ML)
    st.markdown("<b>Predictive Risk Timeline (M204 Degradation Dynamics):</b>", unsafe_allow_html=True)
    st.caption("Compares Rule-Based Deterministic Risk (yellow dashed) with Calibrated ML Failure Probability P(failure within 24h) (red solid).")

    timeline_pts = facade.get_predictive_timeline("M204")
    times = [p["time"] for p in timeline_pts]
    det_risks = [p["deterministic_risk"] * 100 for p in timeline_pts]
    ml_probs = [p["ml_probability"] * 100 for p in timeline_pts]

    fig_timeline = go.Figure()
    fig_timeline.add_trace(go.Scatter(
        x=times, y=det_risks,
        name="Deterministic Risk (Rule)",
        line=dict(color="#d97706", width=2, dash="dash"),
        mode="lines+markers"
    ))
    fig_timeline.add_trace(go.Scatter(
        x=times, y=ml_probs,
        name="ML Failure Probability (24h)",
        line=dict(color="#dc2626", width=3),
        mode="lines+markers"
    ))
    fig_timeline.add_hline(y=50, line_dash="dot", line_color="#d97706", annotation_text="ML Warning (50%)")
    fig_timeline.add_hline(y=70, line_dash="dot", line_color="#dc2626", annotation_text="Critical Threshold (70%)")

    timeline_layout = get_plotly_layout()
    timeline_layout.update(
        yaxis=dict(title="Probability / Risk (%)", range=[0, 105]),
        xaxis=dict(title="Timeline (HH:MM)"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=30, r=20, t=30, b=30),
        height=320,
    )
    fig_timeline.update_layout(**timeline_layout)
    st.plotly_chart(fig_timeline, width="stretch")

    st.markdown("<hr style='border: none; border-bottom: 1px solid var(--border-subtle); margin: 16px 0;'/>", unsafe_allow_html=True)

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
