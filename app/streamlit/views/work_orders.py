"""Work Orders View & Closed-Loop Verification Workspace.

Follows Sections 24, 25, 26, & 27 of AGENT.md:
- Work orders inventory with status filtering
- Work order detail card with state machine timeline
- Controlled technician execution simulation (Start Work -> Sign Off)
- Post-maintenance physical verification panel (Before vs After delta table)
- Supports both nominal recovery and failed repair simulation paths
"""

from __future__ import annotations

import streamlit as st

from app.streamlit.components.tables import render_work_orders_table
from app.streamlit.components.verification import render_verification_panel
from app.streamlit.components.work_orders import render_work_order_card
from app.streamlit.services.view_service import CommandCenterFacade
from domain.enums import WorkOrderStatus


def render_work_orders_view(facade: CommandCenterFacade) -> None:
    """Render the work orders and verification screen."""
    st.markdown(
        """
        <div style="margin-bottom: 14px;">
            <div style="font-size: 20px; font-weight: 800; color: #f8fafc; letter-spacing: -0.02em;">
                MAINTENANCE WORK ORDERS & VERIFICATION
            </div>
            <div style="font-size: 12px; color: #94a3b8;">
                Governed work order lifecycle, technician execution tracking, and post-repair physical telemetry verification.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    all_wos = facade.get_work_orders()
    wo_ids = [w.work_order_id for w in all_wos]

    cur_wo_id = st.session_state.get("selected_work_order_id")
    if cur_wo_id not in wo_ids:
        cur_wo_id = wo_ids[0] if wo_ids else None

    # Work Order Selector & Filters
    col_sel, col_flt = st.columns([3, 1])
    with col_sel:
        if wo_ids:
            chosen_wo_id = st.selectbox(
                "Select Work Order:",
                wo_ids,
                index=wo_ids.index(cur_wo_id) if cur_wo_id in wo_ids else 0,
                format_func=lambda x: f"{x} — {facade.get_work_order_detail(x)['work_order'].title if facade.get_work_order_detail(x) else x}",
                key="wo_dropdown_selector",
            )
            if chosen_wo_id != cur_wo_id:
                st.session_state.selected_work_order_id = chosen_wo_id
                st.rerun()
        else:
            st.info("No work orders created yet. Authorize an investigation recommendation to generate a work order.")
            return

    detail = facade.get_work_order_detail(chosen_wo_id)
    if not detail:
        st.error(f"Work order '{chosen_wo_id}' not found.")
        return

    wo = detail["work_order"]
    maint_event = detail["maintenance_event"]
    verif = detail["verification"]

    # 1. Work Order Detail & Technician Simulation
    render_work_order_card(
        work_order=wo,
        on_start_work=lambda wo_id, tech: facade.start_work_order(wo_id, tech),
        on_complete_work=lambda wo_id, tech, dur, notes, acts: facade.complete_work_order(wo_id, tech, dur, notes, acts),
    )

    st.markdown("<hr style='border: none; border-bottom: 1px solid #1f2430; margin: 16px 0;'/>", unsafe_allow_html=True)

    # 2. Closed-Loop Verification Panel
    render_verification_panel(
        verification=verif,
        work_order=wo,
        on_run_verification=lambda wo_id, verifier, fail_mode: facade.run_verification(wo_id, verifier, fail_mode),
    )

    st.markdown("<hr style='border: none; border-bottom: 1px solid #1f2430; margin: 16px 0;'/>", unsafe_allow_html=True)

    # 3. All Work Orders Table
    render_work_orders_table(
        work_orders=all_wos,
        on_select_work_order=lambda wid: setattr(st.session_state, "selected_work_order_id", wid),
    )
