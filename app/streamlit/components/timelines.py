"""Timeline Visualization Components.

Follows Sections 17 & 24 of AGENT.md:
- Investigation Step Timeline: Alert -> Telemetry -> Anomalies -> History -> Manual -> Hypotheses -> Finding -> Recommendation -> Approval
- Work Order State Machine Timeline: Approved -> Open -> In Progress -> Completed -> Verified
"""

from __future__ import annotations

from typing import List, Optional
import streamlit as st

from domain.enums import WorkOrderStatus
from domain.models import Investigation, WorkOrder


def render_investigation_timeline(investigation: Optional[Investigation]) -> None:
    """Render the high-level step-by-step investigation timeline."""
    steps = [
        ("Alert Detected", "ALT-M204: Critical vibration & temperature threshold crossed.", True),
        ("Telemetry Reviewed", "FeatureExtractor calculated Vibration RMS (0.919g) and thermal slope.", True),
        ("Anomalies Correlated", "Dual-signal anomaly active on drive-end bearing sensors.", True),
        ("Failure History Queried", "Retrieved 2025-04 bearing inner-race spalling precedent.", True),
        ("Maintenance History Queried", "Last grease replenishment performed 48 days ago.", True),
        ("Technical Manual Consulted", "DRV-5000 Manual §4.2: Maximum vibration RMS limit is 0.70g.", True),
        ("Hypotheses Evaluated", "Bearing Degradation (Supported), Thermal Overload (Refuted).", True),
        ("Finding Generated", "M204 Conveyor Motor undergoing progressive bearing raceway degradation.", True),
        ("Recommendation Formed", "Perform LOTO and emergency bearing assembly replacement.", True),
        ("Governance Approval Requested", "Approval request APP-M204 dispatched for human authorization.", bool(investigation and investigation.action_proposal)),
    ]

    st.markdown("<div style='font-size: 13px; font-weight: 700; color: #f8fafc; margin-bottom: 8px;'>INVESTIGATION PROGRESSION</div>", unsafe_allow_html=True)

    for title, desc, is_completed in steps:
        status_class = "completed" if is_completed else ""
        icon = "✓" if is_completed else "○"
        st.markdown(
            f"""
            <div class="timeline-step {status_class}">
                <div style="font-size: 12px; font-weight: 700; color: #f1f5f9;">
                    {icon} {title}
                </div>
                <div style="font-size: 11px; color: #94a3b8; margin-top: 2px;">
                    {desc}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_work_order_timeline(work_order: Optional[WorkOrder]) -> None:
    """Render the governed work order lifecycle state machine."""
    stages = [
        WorkOrderStatus.APPROVED,
        WorkOrderStatus.OPEN,
        WorkOrderStatus.IN_PROGRESS,
        WorkOrderStatus.COMPLETED,
        WorkOrderStatus.VERIFIED,
    ]

    cur_status = work_order.status if work_order else WorkOrderStatus.APPROVED
    cur_idx = 0
    try:
        cur_idx = stages.index(cur_status)
    except ValueError:
        cur_idx = 0

    cols = st.columns(len(stages))
    for idx, (col, st_name) in enumerate(zip(cols, stages)):
        with col:
            is_active = (idx == cur_idx)
            is_done = (idx < cur_idx)
            color = "#10b981" if is_done else ("#3b82f6" if is_active else "#475569")
            symbol = "✓" if is_done else ("●" if is_active else "○")

            st.markdown(
                f"""
                <div style="text-align: center; padding: 6px; border-radius: 4px; background: rgba(0,0,0,0.2); border: 1px solid {color};">
                    <div style="font-size: 14px; color: {color}; font-weight: 800;">{symbol}</div>
                    <div style="font-size: 11px; font-weight: 700; color: #f8fafc; text-transform: uppercase; margin-top: 2px;">
                        {st_name.value}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
