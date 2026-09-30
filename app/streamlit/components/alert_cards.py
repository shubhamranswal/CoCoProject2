"""Hero Operational Alert Cards Component.

Follows Section 11 of AGENT.md:
- Renders hero alert cards for critical events (M204 Bearing Degradation)
- Shows physical telemetry (Vibration RMS, Temperature, Failure Risk, OEE Impact)
- Exposes direct links to Investigation, Evidence, Recommendation, and Approval
- Never exposes unguided "Execute" directly on the alert card
"""

from __future__ import annotations

from typing import Any, Dict
import streamlit as st

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

    mach_id = machine.machine_id if machine else (alert.machine_id if alert else "M204")
    mach_name = machine.name if machine else "Conveyor Drive Motor"
    line_id = machine.line_id if machine else "LINE-B"
    severity_val = alert.severity.value if alert else "CRITICAL"
    failure_mode_val = (risk.failure_mode.value if risk else "BEARING_DEGRADATION").replace("_", " ")

    risk_score = (risk.risk_score * 100) if risk else 86.0
    vib_rms = features.vibration_rms if features else 0.919
    temp_c = features.temperature_mean if features else 84.1
    oee_pct = (oee.oee * 100) if oee else 59.3

    status_desc = "Investigation required"
    if inv:
        if inv.status.value == "PENDING_APPROVAL":
            status_desc = "Investigation complete — Human Approval required"
        elif inv.status.value == "CLOSED":
            status_desc = "Investigation Closed — Maintenance Verified"
        else:
            status_desc = f"Investigation {inv.status.value}"

    st.markdown(
        f"""
        <div class="ind-card-hero">
            <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                <div>
                    <span class="badge badge-critical">{severity_val}</span>
                    <span class="badge badge-neutral" style="margin-left: 6px;">{line_id}</span>
                    <div style="font-size: 20px; font-weight: 800; color: #f8fafc; margin-top: 6px;">
                        {mach_id} — {mach_name}
                    </div>
                    <div style="font-size: 13px; font-weight: 700; color: #fca5a5; text-transform: uppercase; letter-spacing: 0.05em;">
                        {failure_mode_val}
                    </div>
                </div>
                <div style="text-align: right;">
                    <div style="font-size: 11px; color: #94a3b8; font-weight: 600; text-transform: uppercase;">Predicted Failure Risk</div>
                    <div style="font-size: 32px; font-weight: 800; color: #ef4444; line-height: 1;">
                        {risk_score:.0f}%
                    </div>
                    <div style="font-size: 11px; color: #fca5a5;">Horizon: 72 Hours</div>
                </div>
            </div>

            <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-top: 16px; padding: 10px 14px; background: rgba(0,0,0,0.25); border-radius: 4px; border: 1px solid rgba(255,255,255,0.06);">
                <div>
                    <div style="font-size: 10px; color: #94a3b8; text-transform: uppercase;">Vibration RMS</div>
                    <div style="font-size: 16px; font-weight: 700; color: #f8fafc;">{vib_rms:.3f} g</div>
                    <div style="font-size: 10px; color: #ef4444;">+104% vs baseline (0.450g)</div>
                </div>
                <div>
                    <div style="font-size: 10px; color: #94a3b8; text-transform: uppercase;">Bearing Temp</div>
                    <div style="font-size: 16px; font-weight: 700; color: #f8fafc;">{temp_c:.1f} °C</div>
                    <div style="font-size: 10px; color: #ef4444;">+25.6°C thermal rise</div>
                </div>
                <div>
                    <div style="font-size: 10px; color: #94a3b8; text-transform: uppercase;">Operational OEE</div>
                    <div style="font-size: 16px; font-weight: 700; color: #f8fafc;">{oee_pct:.1f}%</div>
                    <div style="font-size: 10px; color: #ef4444;">Degraded by line downtime</div>
                </div>
                <div>
                    <div style="font-size: 10px; color: #94a3b8; text-transform: uppercase;">Status</div>
                    <div style="font-size: 13px; font-weight: 700; color: #fbbf24;">{status_desc}</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Action navigation buttons
    b_col1, b_col2, b_col3, b_col4 = st.columns(4)
    with b_col1:
        if st.button("🔍 Open Investigation", key=f"open_inv_{mach_id}", type="primary", use_container_width=True):
            inv_id = inv.investigation_id if inv else f"INV-{mach_id}"
            navigate_to("AI Investigations", machine_id=mach_id, investigation_id=inv_id)
            st.rerun()

    with b_col2:
        if st.button("📊 Review Evidence", key=f"rev_ev_{mach_id}", use_container_width=True):
            inv_id = inv.investigation_id if inv else f"INV-{mach_id}"
            navigate_to("AI Investigations", machine_id=mach_id, investigation_id=inv_id)
            st.rerun()

    with b_col3:
        if st.button("📋 Review Recommendation", key=f"rev_rec_{mach_id}", use_container_width=True):
            inv_id = inv.investigation_id if inv else f"INV-{mach_id}"
            navigate_to("AI Investigations", machine_id=mach_id, investigation_id=inv_id)
            st.rerun()

    with b_col4:
        app_disabled = (app is None or app.status != ApprovalStatus.PENDING)
        btn_label = "✅ Review Approval" if not app_disabled else "⚖️ Governance Gate"
        if st.button(btn_label, key=f"rev_app_{mach_id}", disabled=app_disabled, use_container_width=True):
            inv_id = inv.investigation_id if inv else f"INV-{mach_id}"
            navigate_to("AI Investigations", machine_id=mach_id, investigation_id=inv_id)
            st.rerun()


def render_alert_card(alert: Any) -> None:
    """Render a compact alert card for standard alerts."""
    sev_badge = "badge-critical" if alert.severity.value == "CRITICAL" else "badge-warning"
    st.markdown(
        f"""
        <div class="ind-card">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <span class="badge {sev_badge}">{alert.severity.value}</span>
                    <span style="font-size: 13px; font-weight: 700; color: #f8fafc; margin-left: 8px;">{alert.machine_id}</span>
                </div>
                <div style="font-size: 11px; color: #94a3b8;">
                    {alert.alert_id}
                </div>
            </div>
            <div style="font-size: 12px; color: #cbd5e1; margin-top: 6px;">
                {alert.trigger_reason}
            </div>
            <div style="font-size: 11px; color: #fca5a5; margin-top: 4px;">
                Risk Score: <b>{alert.risk_score * 100:.0f}%</b> | Mode: <b>{alert.failure_mode.value}</b>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
