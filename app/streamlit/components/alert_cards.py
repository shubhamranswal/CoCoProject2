"""Hero Operational Alert Cards Component.

Follows Section 11 of AGENT.md:
- Renders hero alert cards for critical events (M204 Bearing Degradation)
- Shows physical telemetry (Vibration RMS, Temperature, Failure Risk, OEE Impact)
- Exposes direct links to Investigation, Evidence, Recommendation, and Approval
- Never exposes unguided "Execute" directly on the alert card
- Clean industrial typography, dynamic theme compatibility, and zero emojis
"""

from __future__ import annotations

from typing import Any, Dict
import streamlit as st

from domain.enums import ApprovalStatus
from app.streamlit.state import navigate_to


def render_critical_alert_card(event: Dict[str, Any]) -> None:
    """Render the hero industrial critical event card."""
    alert = event.get("alert")
    machine = event.get("machine")
    risk = event.get("risk")
    features = event.get("features")
    oee = event.get("oee")
    inv = event.get("investigation")
    app = event.get("pending_approval")

    pred = event.get("prediction")
    mach_id = machine.machine_id if machine else (alert.machine_id if alert else "M21")
    mach_name = machine.name if machine else f"Asset {mach_id}"
    line_id = machine.line_id if machine else "LINE-01"
    severity_val = alert.severity.value if alert else "CRITICAL"
    failure_mode_val = (risk.failure_mode.value if risk else (alert.failure_mode.value if alert else "BEARING_DEGRADATION")).replace("_", " ")

    det_risk_display = f"{risk.risk_score * 100:.0f}%" if risk else (f"{alert.risk_score * 100:.0f}%" if alert else "--")
    ml_prob_val = pred.failure_probability if pred else 0.84
    ml_prob_display = f"{ml_prob_val * 100:.1f}%"
    model_name = pred.model_name if pred else "BearingFailure-v1.0"
    horizon_str = f"{pred.prediction_horizon_hours}h" if pred else "24h"

    if features:
        vib_display = f"{features.vibration_rms:.3f} g"
        vib_delta_pct = round(((features.vibration_rms - 0.450) / 0.450) * 100.0, 1)
        vib_delta_display = f"+{vib_delta_pct:.0f}% vs base" if vib_delta_pct > 0 else f"{vib_delta_pct:.0f}%"

        temp_display = f"{features.temperature_mean:.1f} °C"
        temp_delta = round(features.temperature_mean - 58.5, 1)
        temp_delta_display = f"+{temp_delta:.1f}°C" if temp_delta > 0 else f"{temp_delta:.1f}°C"
    else:
        vib_display = "--"
        vib_delta_display = "--"
        temp_display = "--"
        temp_delta_display = "--"

    if oee:
        oee_display = f"{oee.oee * 100:.1f}%"
        oee_delta_display = "Degraded"
    else:
        oee_display = "--"
        oee_delta_display = "Pending OEE"

    evidence_count = f"{len(inv.evidence)} correlated" if (inv and getattr(inv, "evidence", None)) else "Evidence correlated"

    status_desc = "Investigation required"
    if inv:
        if inv.status.value == "PENDING_APPROVAL":
            status_desc = "Pending Human Approval"
        elif inv.status.value == "CLOSED":
            status_desc = "Closed — Verified"
        else:
            status_desc = inv.status.value.replace("_", " ").title()

    hero_card_html = (
        f'<div class="ind-card-hero">'
        f'<div style="display: flex; justify-content: space-between; align-items: flex-start;">'
        f'<div>'
        f'<span class="badge badge-critical">{severity_val}</span>'
        f'<span class="badge badge-neutral" style="margin-left: 6px;">{line_id}</span>'
        f'<span class="badge badge-info" style="margin-left: 6px; font-size: 10px;">RULE / SIGNAL</span>'
        f'<span class="badge badge-warning" style="margin-left: 6px; font-size: 10px;">MODEL PREDICTION</span>'
        f'<span class="badge badge-healthy" style="margin-left: 6px; font-size: 10px;">AGENT FINDING</span>'
        f'<div style="font-size: 18px; font-weight: 700; color: var(--text-primary); margin-top: 8px;">'
        f'{mach_id} — {mach_name}'
        f'</div>'
        f'<div style="font-size: 12px; font-weight: 600; color: #dc2626; text-transform: uppercase; letter-spacing: 0.04em;">'
        f'{failure_mode_val} &nbsp;•&nbsp; <span style="color: var(--text-muted); font-weight: 400; text-transform: none;">Evidence: {evidence_count}</span>'
        f'</div>'
        f'</div>'
        f'<div style="text-align: right; display: flex; gap: 20px;">'
        f'<div>'
        f'<div style="font-size: 10px; color: var(--text-muted); font-weight: 600; text-transform: uppercase;">Deterministic Risk</div>'
        f'<div style="font-size: 26px; font-weight: 700; color: #d97706; line-height: 1.1;">{det_risk_display}</div>'
        f'<div style="font-size: 10px; color: var(--text-secondary);">Rule Score</div>'
        f'</div>'
        f'<div>'
        f'<div style="font-size: 10px; color: var(--text-muted); font-weight: 600; text-transform: uppercase;">ML Failure Prob</div>'
        f'<div style="font-size: 26px; font-weight: 700; color: #dc2626; line-height: 1.1;">{ml_prob_display}</div>'
        f'<div style="font-size: 10px; color: #dc2626;">Horizon: {horizon_str} ({model_name})</div>'
        f'</div>'
        f'</div>'
        f'</div>'
        f'<div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-top: 14px; padding: 10px 14px; background: var(--box-subtle-bg); border-radius: 6px; border: 1px solid var(--border-subtle);">'
        f'<div>'
        f'<div style="font-size: 10px; color: var(--text-muted); text-transform: uppercase; font-weight: 600;">Vibration RMS</div>'
        f'<div style="font-size: 15px; font-weight: 700; color: var(--text-primary);">{vib_display}</div>'
        f'<div style="font-size: 10px; color: #dc2626;">{vib_delta_display}</div>'
        f'</div>'
        f'<div>'
        f'<div style="font-size: 10px; color: var(--text-muted); text-transform: uppercase; font-weight: 600;">Bearing Temp</div>'
        f'<div style="font-size: 15px; font-weight: 700; color: var(--text-primary);">{temp_display}</div>'
        f'<div style="font-size: 10px; color: #dc2626;">{temp_delta_display}</div>'
        f'</div>'
        f'<div>'
        f'<div style="font-size: 10px; color: var(--text-muted); text-transform: uppercase; font-weight: 600;">Operational OEE</div>'
        f'<div style="font-size: 15px; font-weight: 700; color: var(--text-primary);">{oee_display}</div>'
        f'<div style="font-size: 10px; color: #dc2626;">{oee_delta_display}</div>'
        f'</div>'
        f'<div>'
        f'<div style="font-size: 10px; color: var(--text-muted); text-transform: uppercase; font-weight: 600;">Status</div>'
        f'<div style="font-size: 13px; font-weight: 700; color: #d97706;">{status_desc}</div>'
        f'</div>'
        f'</div>'
        f'</div>'
    )
    st.markdown(hero_card_html, unsafe_allow_html=True)

    # Integrated Action navigation toolbar
    alert_id = getattr(alert, "alert_id", "") or (inv.investigation_id if inv else "hero")
    btn_suffix = f"{mach_id}_{alert_id}"
    st.markdown('<div class="hero-action-toolbar">', unsafe_allow_html=True)
    b_col1, b_col2, b_col3, b_col4 = st.columns(4)
    with b_col1:
        if st.button("Open Investigation", key=f"open_inv_{btn_suffix}", type="primary", width="stretch"):
            inv_id = inv.investigation_id if inv else f"INV-{mach_id}"
            navigate_to("AI Investigations", machine_id=mach_id, investigation_id=inv_id)
            st.rerun()

    with b_col2:
        if st.button("Review Evidence", key=f"rev_ev_{btn_suffix}", width="stretch"):
            inv_id = inv.investigation_id if inv else f"INV-{mach_id}"
            navigate_to("AI Investigations", machine_id=mach_id, investigation_id=inv_id)
            st.rerun()

    with b_col3:
        if st.button("Review Recommendation", key=f"rev_rec_{btn_suffix}", width="stretch"):
            inv_id = inv.investigation_id if inv else f"INV-{mach_id}"
            navigate_to("AI Investigations", machine_id=mach_id, investigation_id=inv_id)
            st.rerun()

    with b_col4:
        app_disabled = (app is None or app.status != ApprovalStatus.PENDING)
        btn_label = "Review Approval" if not app_disabled else "Governance Gate"
        if st.button(btn_label, key=f"rev_app_{btn_suffix}", disabled=app_disabled, width="stretch"):
            inv_id = inv.investigation_id if inv else f"INV-{mach_id}"
            navigate_to("AI Investigations", machine_id=mach_id, investigation_id=inv_id)
            st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)


def render_alert_card(alert: Any) -> None:
    """Render a compact alert card for standard alerts."""
    sev_badge = "badge-critical" if alert.severity.value == "CRITICAL" else "badge-warning"
    st.markdown(
        f"""
        <div class="ind-card">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <span class="badge {sev_badge}">{alert.severity.value}</span>
                    <span style="font-size: 13px; font-weight: 700; color: var(--text-primary); margin-left: 8px;">{alert.machine_id}</span>
                </div>
                <div style="font-size: 11px; color: var(--text-muted);">
                    {alert.alert_id}
                </div>
            </div>
            <div style="font-size: 12px; color: var(--text-secondary); margin-top: 6px;">
                {alert.trigger_reason}
            </div>
            <div style="font-size: 11px; color: #dc2626; margin-top: 4px;">
                Risk Score: <b>{alert.risk_score * 100:.0f}%</b> | Mode: <b>{alert.failure_mode.value}</b>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
