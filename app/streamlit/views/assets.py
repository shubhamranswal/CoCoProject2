"""Assets View & M204 Machine Workspace.

Follows Sections 12, 13, 14, & 15 of AGENT.md:
- Fleet asset selector
- Asset workspace with real-time operational status
- Telemetry trend charts (Vibration RMS, RTD Temperature)
- Synchronized 3-Signal Correlation View (Vibration + Temperature + Risk)
- Subassembly components, calibrated sensors, anomalies, and maintenance history
- Theme CSS variable styling and zero emojis
"""

from __future__ import annotations

import streamlit as st

from app.streamlit.components.charts import (
    render_signal_correlation_chart,
    render_temperature_trend_chart,
    render_vibration_trend_chart,
)
from app.streamlit.components.pagination import paginate_items
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
            format_func=lambda x: f"{x} - {facade.repo.get_machine(x).name if facade.repo.get_machine(x) else x}",
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
        <div class="ind-card" style="border-left: 4px solid {'#dc2626' if mach.health_status == HealthStatus.CRITICAL else '#16a34a'};">
            <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                <div>
                    {health_badge}
                    <span class="badge badge-neutral" style="margin-left: 6px;">{mach.line_id}</span>
                    <span class="badge badge-info" style="margin-left: 6px;">STATE: {mach.state.value}</span>
                    <div style="font-size: 18px; font-weight: 700; color: var(--text-primary); margin-top: 6px;">
                        {mach.machine_id} - {mach.name}
                    </div>
                    <div style="font-size: 12px; color: var(--text-muted); margin-top: 2px;">
                        Model: <b>{mach.model}</b> &nbsp;|&nbsp; Manufacturer: <b>{mach.manufacturer}</b> &nbsp;|&nbsp; Serial: <code>{mach.serial_number}</code>
                    </div>
                </div>
                <div style="text-align: right;">
                    <div style="font-size: 10px; color: var(--text-muted); font-weight: 600; text-transform: uppercase;">Failure Risk Score</div>
                    <div style="font-size: 26px; font-weight: 700; color: {'#dc2626' if risk_score > 70 else '#16a34a'}; line-height: 1;">
                        {risk_score:.0f}%
                    </div>
                    <div style="font-size: 11px; color: var(--text-muted);">Criticality: {mach.criticality}</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Telemetry Visualizations
    telemetry_data = facade.get_telemetry_history(cur_mach_id)

    tab_charts, tab_corr, tab_prod, tab_comp, tab_maint = st.tabs([
        "Telemetry Trends",
        "Signal Correlation (Vib + Temp + Risk)",
        "Production Orders",
        "Components & Sensors",
        "Maintenance & Failure History",
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

    with tab_prod:
        st.markdown(f"<b>Active Production Orders on Asset {cur_mach_id}:</b>", unsafe_allow_html=True)
        prod_orders = []
        try:
            prod_out = facade.tool_registry.execute_tool("get_production_context", machine_id=cur_mach_id)
            if prod_out and getattr(prod_out, "orders", None):
                prod_orders = prod_out.orders
        except Exception:
            pass

        if prod_orders:
            page_orders, _, _ = paginate_items(
                items=prod_orders,
                page_size=5,
                state_key=f"pagination_assets_prod_{cur_mach_id}",
                item_label="orders",
            )
            order_rows = []
            for o in page_orders:
                order_rows.append({
                    "Order ID": o.order_id,
                    "Product": o.product_name or o.product_id,
                    "Planned Qty": o.planned_qty,
                    "Produced Qty": o.produced_qty,
                    "Remaining Qty": o.remaining_qty,
                    "Unit Price": f"INR {o.unit_price_inr:,.0f}",
                    "Revenue Exposure": f"INR {o.unfulfilled_revenue_exposure_inr:,.0f}",
                    "Status": o.status.upper(),
                })
            st.dataframe(order_rows, width="stretch", hide_index=True)
        else:
            st.info(f"No active production orders currently allocated to machine {cur_mach_id}.")

    with tab_comp:
        col_c, col_s = st.columns(2)
        with col_c:
            st.markdown("<b>Subassembly Components:</b>", unsafe_allow_html=True)
            comps = detail.get("components", [])
            page_comps, _, _ = paginate_items(
                items=comps,
                page_size=6,
                state_key=f"pagination_assets_comp_{cur_mach_id}",
                item_label="components",
            )
            for c in page_comps:
                st.markdown(
                    f"- <b>{c.name}</b> (<code>{c.component_id}</code>) - Type: <code>{c.component_type}</code> | Health: <code>{c.health_status.value}</code>",
                    unsafe_allow_html=True,
                )
        with col_s:
            st.markdown("<b>Calibrated Sensors:</b>", unsafe_allow_html=True)
            sensors = detail.get("sensors", [])
            page_sensors, _, _ = paginate_items(
                items=sensors,
                page_size=6,
                state_key=f"pagination_assets_sens_{cur_mach_id}",
                item_label="sensors",
            )
            for s in page_sensors:
                st.markdown(
                    f"- <b>{s.name}</b> (<code>{s.sensor_id}</code>) - Type: <code>{s.sensor_type.value}</code> | Unit: <code>{s.unit}</code> | Sample Rate: {s.sampling_rate_hz}Hz",
                    unsafe_allow_html=True,
                )

    with tab_maint:
        st.markdown("<b>Past Maintenance Events:</b>", unsafe_allow_html=True)
        maint_events = detail.get("maintenance", [])
        if maint_events:
            page_maint, _, _ = paginate_items(
                items=maint_events,
                page_size=5,
                state_key=f"pagination_assets_maint_{cur_mach_id}",
                item_label="maintenance events",
            )
            for m in page_maint:
                st.markdown(
                    f"- <b>{m.performed_at.strftime('%Y-%m-%d')}</b>: {m.maintenance_type} by <b>{m.technician_name}</b> ({m.duration_hours}h) - {m.notes}",
                    unsafe_allow_html=True,
                )
        else:
            st.caption("No historical maintenance events logged.")

        st.markdown("<br><b>Past Failure Incidents:</b>", unsafe_allow_html=True)
        failure_events = detail.get("failures", [])
        if failure_events:
            page_fails, _, _ = paginate_items(
                items=failure_events,
                page_size=5,
                state_key=f"pagination_assets_fail_{cur_mach_id}",
                item_label="failure incidents",
            )
            for f in page_fails:
                st.markdown(
                    f"- <b>{f.occurred_at.strftime('%Y-%m-%d')}</b>: {f.failure_mode.value} - Cause: {f.root_cause} (Downtime: {f.downtime_hours}h)",
                    unsafe_allow_html=True,
                )
        else:
            st.caption("No historical failure records.")
