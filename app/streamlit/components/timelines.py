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


def render_investigation_timeline(
    investigation: Optional[Investigation],
    detail: Optional[dict] = None,
) -> None:
    """Render the dynamic step-by-step investigation timeline."""
    if investigation:
        machine_id = getattr(investigation, "machine_id", "Unknown")
        machine_name = (detail.get("machine_name") if detail else None) or machine_id
        trigger_type = getattr(investigation, "trigger_type", None)
        trigger_str = trigger_type.value if hasattr(trigger_type, "value") else str(trigger_type or "ANOMALY")
        trigger_ref = (
            getattr(investigation, "prediction_id", None)
            or getattr(investigation, "alert_id", None)
            or getattr(investigation, "trigger_id", None)
            or f"TRG-{machine_id}"
        )
        evidence_count = (
            len(detail.get("evidence", []))
            if detail and "evidence" in detail
            else len(getattr(investigation, "evidence", []) or [])
        )
        hypotheses = (detail.get("hypotheses") if detail else None) or getattr(investigation, "hypotheses", []) or []
        findings = (detail.get("findings") if detail else None) or getattr(investigation, "findings", []) or ([investigation.finding] if getattr(investigation, "finding", None) else [])
        recommendations = (detail.get("recommendations") if detail else None) or getattr(investigation, "recommendations", []) or ([investigation.recommendation] if getattr(investigation, "recommendation", None) else [])
        action_proposal = (detail.get("action_proposal") if detail else None) or getattr(investigation, "action_proposal", None)
        rec_type = recommendations[0].action_type if recommendations else "INSPECTION"

        steps = [
            ("Trigger Event Detected", f"{trigger_str} identified for asset {machine_id} ({machine_name}). Ref: {trigger_ref}.", True),
            ("Evidence Base Ingestion", f"Ingested and verified {evidence_count} evidence records across telemetry, failure history, inventory, and technical manuals.", True),
            ("Hypothesis Evaluation", f"Evaluated {len(hypotheses)} diagnostic hypotheses against verified sensor and operational evidence.", True),
            ("Root Cause Synthesis", f"Synthesized {len(findings)} findings establishing mechanical failure mechanism and operational impacts.", True),
            ("Advisory Recommendations", f"Formed {len(recommendations)} advisory recommendations ({rec_type}). Strictly non-executable.", True),
            ("Governance & Policy Gate", f"Governance Policy: {'Action proposal dispatched for authorization' if action_proposal else 'Advisory state maintained. Human approval required prior to operational proposal.'}", bool(action_proposal)),
        ]
    else:
        steps = [
            ("Trigger Event Detected", "System anomaly or risk prediction identified for target equipment.", False),
            ("Evidence Base Ingestion", "Gathering sensor telemetry, maintenance logs, and asset manuals.", False),
            ("Hypothesis Evaluation", "Formulating and testing failure mode hypotheses.", False),
            ("Root Cause Synthesis", "Synthesizing evidence-grounded findings.", False),
            ("Advisory Recommendations", "Drafting advisory maintenance recommendations.", False),
            ("Governance & Policy Gate", "Evaluating human authorization and governance policy.", False),
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
