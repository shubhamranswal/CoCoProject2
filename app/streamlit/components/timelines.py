"""Timeline Visualization Components.

Follows Sections 17 & 24 of AGENT.md:
- Investigation Step Timeline: Alert -> Telemetry -> Anomalies -> History -> Manual -> Hypotheses -> Finding -> Recommendation -> Approval
- Work Order State Machine Timeline: Approved -> Open -> In Progress -> Completed -> Verified
- Clean industrial styling and theme variable compatibility
"""

from __future__ import annotations

from typing import Optional
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
        ("Technical Manual Consulted", "DRV-5000 Manual Section 4.2: Maximum vibration RMS limit is 0.70g.", True),
        ("Hypotheses Evaluated", "Bearing Degradation (Supported), Thermal Overload (Refuted).", True),
        ("Finding Generated", "M204 Conveyor Motor undergoing progressive bearing raceway degradation.", True),
        ("Recommendation Formed", "Perform LOTO and emergency bearing assembly replacement.", True),
        ("Governance Approval Requested", "Approval request APP-M204 dispatched for human authorization.", bool(investigation and investigation.action_proposal)),
    ]

    st.markdown("<div style='font-size: 13px; font-weight: 700; color: var(--text-primary); letter-spacing: 0.04em; margin-bottom: 8px;'>INVESTIGATION PROGRESSION</div>", unsafe_allow_html=True)

    for title, desc, is_completed in steps:
        status_class = "completed" if is_completed else ""
        icon = "[DONE]" if is_completed else "[PENDING]"
        icon_color = "#16a34a" if is_completed else "var(--text-muted)"
        st.markdown(
            f"""
            <div class="timeline-step {status_class}">
                <div style="font-size: 12px; font-weight: 700; color: var(--text-primary);">
                    <span style="font-size: 10px; color: {icon_color}; margin-right: 4px;">{icon}</span> {title}
                </div>
                <div style="font-size: 11px; color: var(--text-muted); margin-top: 2px;">
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
            color = "#16a34a" if is_done else ("#0284c7" if is_active else "var(--border-strong)")
            badge_class = "badge-healthy" if is_done else ("badge-info" if is_active else "badge-neutral")
            status_text = "COMPLETED" if is_done else ("ACTIVE" if is_active else "QUEUED")

            st.markdown(
                f"""
                <div style="text-align: center; padding: 8px 6px; border-radius: 8px; background: var(--bg-card); border: 1px solid {color}; box-shadow: var(--card-shadow);">
                    <div style="margin-bottom: 4px;"><span class="badge {badge_class}" style="font-size: 9px;">{status_text}</span></div>
                    <div style="font-size: 11px; font-weight: 700; color: var(--text-primary); text-transform: uppercase;">
                        {st_name.value}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
