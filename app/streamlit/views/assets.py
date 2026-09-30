"""Assets View & M204 Machine Workspace.

Follows Sections 12, 13, 14, & 15 of AGENT.md:
- Fleet asset selector
- Asset workspace with real-time operational status
- Telemetry trend charts (Vibration RMS, RTD Temperature)
- Synchronized 3-Signal Correlation View (Vibration + Temperature + Risk)
- Subassembly components, calibrated sensors, anomalies, and maintenance history
"""

from __future__ import annotations

import streamlit as st

from app.streamlit.components.charts import (
    render_signal_correlation_chart,
    render_temperature_trend_chart,
    render_vibration_trend_chart,
)
from app.streamlit.services.view_service import CommandCenterFacade
from domain.enums import HealthStatus


def render_assets_view(facade: CommandCenterFacade) -> None:
    """Render the asset workspace view."""
    machines = facade.repo.list_machines()
    mach_ids = [m.machine_id for m in machines]

    cur_mach_id = st.session_state.get("selected_machine_id", "M204")
    if cur_mach_id not in mach_ids:
        cur_mach_id = mach_ids[0] if mach_ids else "M204"

    # Asset selector bar
    col_sel, col_stat = st.columns([3, 1])
    with col_sel:
        chosen_id = st.selectbox(
            "Select Asset:",
            mach_ids,
            index=mach_ids.index(cur_mach_id) if cur_mach_id in mach_ids else 0,
            format_func=lambda x: f"{x} — {facade.repo.get_machine(x).name if facade.repo.get_machine(x) else x}",
            key="asset_machine_dropdown",
        )
        if chosen_id != cur_mach_id:
            st.session_state.selected_machine_id = chosen_id
            st.rerun()

    detail = facade.get_asset_detail(cur_mach_id)
    if not detail:
        st.error(f"Asset '{cur_mach_id}' not found.")
        return

    mach = detail["machine"]
    risk = detail["risk"]
    features = detail["features"]
    oee = detail["oee"]

    # Header Card
    health_badge = (
        "<span class='badge badge-critical'>CRITICAL</span>"
        if mach.health_status == HealthStatus.CRITICAL
        else ("<span class='badge badge-warning'>WARNING</span>" if mach.health_status == HealthStatus.DEGRADING else "<span class='badge badge-healthy'>HEALTHY</span>")
    )
    risk_score = (risk.risk_score * 100) if risk else 10.0

    st.markdown(
        f"""
        <div class="ind-card" style="border-left: 4px solid {'#ef4444' if mach.health_status == HealthStatus.CRITICAL else '#10b981'};">
            <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                <div>
                    {health_badge}
                    <span class="badge badge-neutral" style="margin-left: 6px;">{mach.line_id}</span>
                    <span class="badge badge-info" style="margin-left: 6px;">STATE: {mach.state.value}</span>
                    <div style="font-size: 20px; font-weight: 800; color: #f8fafc; margin-top: 6px;">
                        {mach.machine_id} — {mach.name}
                    </div>
                    <div style="font-size: 12px; color: #94a3b8; margin-top: 2px;">
                        Model: <b>{mach.model}</b> &nbsp;|&nbsp; Manufacturer: <b>{mach.manufacturer}</b> &nbsp;|&nbsp; Serial: <code>{mach.serial_number}</code>
                    </div>
                </div>
                <div style="text-align: right;">
                    <div style="font-size: 11px; color: #94a3b8; font-weight: 600; text-transform: uppercase;">Failure Risk Score</div>
                    <div style="font-size: 28px; font-weight: 800; color: {'#ef4444' if risk_score > 70 else '#10b981'}; line-height: 1;">
                        {risk_score:.0f}%
                    </div>
                    <div style="font-size: 11px; color: #94a3b8;">Criticality: {mach.criticality}</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Telemetry Visualizations
    telemetry_data = facade.get_telemetry_history(cur_mach_id)

    tab_charts, tab_corr, tab_comp, tab_maint = st.tabs([
        "📈 Telemetry Trends",
        "🔬 Signal Correlation (Vib + Temp + Risk)",
        "🔩 Components & Sensors",
        "🛠️ Maintenance & Failure History",
    ])

    with tab_charts:
        c_v, c_t = st.columns(2)
        with c_v:
            render_vibration_trend_chart(telemetry_data)
        with c_t:
            render_temperature_trend_chart(telemetry_data)

    with tab_corr:
        st.caption("Synchronous time-series analysis showing vibration harmonic spike coupled with thermal runaway and rising failure risk:")
        render_signal_correlation_chart(telemetry_data)

    with tab_comp:
        col_c, col_s = st.columns(2)
        with col_c:
            st.markdown("<b>Subassembly Components:</b>", unsafe_allow_html=True)
            for c in detail["components"]:
                st.markdown(
                    f"- <b>{c.name}</b> (<code>{c.component_id}</code>) — Type: <code>{c.component_type}</code> | Health: <code>{c.health_status.value}</code>",
                    unsafe_allow_html=True,
                )
        with col_s:
            st.markdown("<b>Calibrated Sensors:</b>", unsafe_allow_html=True)
            for s in detail["sensors"]:
                st.markdown(
                    f"- <b>{s.name}</b> (<code>{s.sensor_id}</code>) — Type: <code>{s.sensor_type.value}</code> | Unit: <code>{s.unit}</code> | Sample Rate: {s.sampling_rate_hz}Hz",
                    unsafe_allow_html=True,
                )

    with tab_maint:
        st.markdown("<b>Past Maintenance Events:</b>", unsafe_allow_html=True)
        if detail["maintenance"]:
            for m in detail["maintenance"]:
                st.markdown(
                    f"- <b>{m.performed_at.strftime('%Y-%m-%d')}</b>: {m.maintenance_type} by <b>{m.technician_name}</b> ({m.duration_hours}h) — {m.notes}",
                    unsafe_allow_html=True,
                )
        else:
            st.caption("No historical maintenance events logged.")

        st.markdown("<br><b>Past Failure Incidents:</b>", unsafe_allow_html=True)
        if detail["failures"]:
            for f in detail["failures"]:
                st.markdown(
                    f"- <b>{f.occurred_at.strftime('%Y-%m-%d')}</b>: {f.failure_mode.value} — Cause: {f.root_cause} (Downtime: {f.downtime_hours}h)",
                    unsafe_allow_html=True,
                )
        else:
            st.caption("No historical failure records.")
