"""Work Order Detail and Technician Execution Component.

Follows Sections 24 & 25 of AGENT.md:
- Renders governed work order state, assigned crew, and execution parameters
- Provides controlled simulation of technician execution using the real WorkOrderService state machine
- Does not allow arbitrary status mutations
"""

from __future__ import annotations

from typing import Callable, Optional
import streamlit as st

from domain.enums import WorkOrderStatus
from domain.models import WorkOrder
from app.streamlit.components.timelines import render_work_order_timeline


def render_work_order_card(
    work_order: Optional[WorkOrder],
    on_start_work: Callable[[str, str], None],
    on_complete_work: Callable[[str, str, float, str, list[str]], None],
) -> None:
    """Render the work order details and maintenance simulation panel."""
    if not work_order:
        st.info("No work order found.")
        return

    st.markdown(
        f"""
        <div class="ind-card">
            <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                <div>
                    <span class="badge badge-info">WORK ORDER</span>
                    <span class="badge badge-warning" style="margin-left: 6px;">PRIORITY: {work_order.priority.value}</span>
                    <span class="badge badge-neutral" style="margin-left: 6px;">STATUS: {work_order.status.value}</span>
                    <div style="font-size: 18px; font-weight: 800; color: #f8fafc; margin-top: 6px;">
                        {work_order.work_order_id} — {work_order.title}
                    </div>
                    <div style="font-size: 12px; color: #94a3b8; margin-top: 2px;">
                        Machine: <b>{work_order.machine_id}</b> &nbsp;|&nbsp; Component: <b>{work_order.component_id}</b> &nbsp;|&nbsp; Assigned: <b>{work_order.assigned_to}</b>
                    </div>
                </div>
                <div style="text-align: right;">
                    <div style="font-size: 10px; color: #94a3b8; text-transform: uppercase;">Idempotency Key</div>
                    <div style="font-size: 11px; color: #cbd5e1; font-family: monospace;">{work_order.idempotency_key or 'N/A'}</div>
                </div>
            </div>

            <div style="font-size: 12px; color: #cbd5e1; margin-top: 10px; padding: 8px 12px; background: rgba(0,0,0,0.2); border-radius: 4px;">
                <b>Description:</b> {work_order.description}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Lifecycle state machine timeline
    st.markdown("<div style='margin-bottom: 12px;'>", unsafe_allow_html=True)
    render_work_order_timeline(work_order)
    st.markdown("</div>", unsafe_allow_html=True)

    # Technician Execution Controls
    if work_order.status in (WorkOrderStatus.APPROVED, WorkOrderStatus.OPEN, WorkOrderStatus.ASSIGNED):
        with st.expander("🛠️ Technician On-Site Dispatch", expanded=True):
            st.caption("Simulate maintenance technician arriving on site and commencing LOTO:")
            tech_id = st.text_input("Technician Name / ID:", value="tech.marcus", key=f"tech_start_{work_order.work_order_id}")
            if st.button("🚀 Start Maintenance (Set IN_PROGRESS)", type="primary", use_container_width=True):
                on_start_work(work_order.work_order_id, tech_id)
                st.session_state.last_action_message = f"Work order {work_order.work_order_id} marked IN_PROGRESS by {tech_id}."
                st.rerun()

    elif work_order.status == WorkOrderStatus.IN_PROGRESS:
        with st.expander("✅ Complete Maintenance Execution", expanded=True):
            st.caption("Technician logs completed physical tasks, duration, and replacement parts:")
            tech_id = st.text_input("Technician Name / ID:", value="tech.marcus", key=f"tech_comp_{work_order.work_order_id}")
            duration_val = st.number_input("Duration (Hours):", min_value=0.5, max_value=24.0, value=2.25, step=0.25)
            notes_val = st.text_area(
                "Maintenance Execution Notes:",
                value="Replaced drive-end bearing with new SKF 6205-2RSH. Packed with Mobil Polyrex EM. Laser realigned shaft.",
            )
            actions_list = [
                "Electrical LOTO completed",
                "Decoupled conveyor drive shaft",
                "Extracted defective bearing assembly",
                "Fitted replacement SKF 6205-2RSH",
                "Shaft laser realignment to 0.03mm",
            ]

            if st.button("🏁 Sign Off Work Order (Set COMPLETED)", type="primary", use_container_width=True):
                on_complete_work(work_order.work_order_id, tech_id, duration_val, notes_val, actions_list)
                st.session_state.last_action_message = f"Work order {work_order.work_order_id} signed off by {tech_id}. Ready for Verification."
                st.rerun()

    elif work_order.status == WorkOrderStatus.COMPLETED:
        st.markdown(
            f"""
            <div class="ind-card-warning">
                <div style="font-size: 13px; font-weight: 700; color: #fbbf24;">
                    ⏳ Physical Work Completed — Pending Telemetry Verification
                </div>
                <div style="font-size: 11px; color: #cbd5e1; margin-top: 4px;">
                    Work order is marked <b>COMPLETED</b> by technician. Final <b>VERIFIED</b> status requires post-restart sensor verification.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    elif work_order.status == WorkOrderStatus.VERIFIED:
        st.markdown(
            f"""
            <div class="ind-card-success">
                <div style="font-size: 13px; font-weight: 700; color: #34d399;">
                    ✓ Closed-Loop Verified
                </div>
                <div style="font-size: 11px; color: #cbd5e1; margin-top: 4px;">
                    Post-maintenance sensor telemetry confirmed physical vibration and temperature recovery.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
