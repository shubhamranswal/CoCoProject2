"""Human Approval Governance Component.

Follows Milestone 5 & Milestone 6.5.5.3A Zero-Trust Governance:
- Human-in-the-loop authorization gateway
- Requires explicit authenticated human approver identity and justification
- Autonomous agents strictly barred from self-approval
- Clear separation between approval state and execution
- Professional industrial styling and zero emojis
"""

from __future__ import annotations

from typing import Callable, Optional
import streamlit as st

from domain.enums import ApprovalStatus
from domain.models import ActionProposal, Approval, Investigation


def render_approval_panel(
    approval: Optional[Approval],
    investigation: Optional[Investigation],
    on_approve: Callable[[str, str, str], None],
    on_reject: Callable[[str, str, str], None],
    on_create_work_order: Optional[Callable[[str, str], None]] = None,
    action_proposal: Optional[ActionProposal] = None,
) -> None:
    """Render the governed human approval action panel."""
    if not approval and not action_proposal:
        st.info("No action proposals currently require human approval.")
        return

    st.markdown(
        """
        <div style="font-size: 13px; font-weight: 700; color: var(--text-primary); text-transform: uppercase; letter-spacing: 0.04em; margin-bottom: 8px;">
            Human-in-the-Loop Governance Gateway
        </div>
        """,
        unsafe_allow_html=True,
    )

    # 1. Resolve entity fields
    prop_id = (
        action_proposal.proposal_id
        if action_proposal
        else (
            approval.action_proposal_id
            if approval and approval.action_proposal_id
            else (
                approval.approval_id.replace("APP-", "PROP-")
                if approval and approval.approval_id.startswith("APP-")
                else "N/A"
            )
        )
    )

    inv_id = (
        action_proposal.investigation_id
        if action_proposal
        else (
            approval.investigation_id
            if approval
            else (investigation.investigation_id if investigation else "N/A")
        )
    )

    machine_id = (
        action_proposal.machine_id
        if action_proposal
        else (
            approval.machine_id
            if approval
            else (investigation.machine_id if investigation else "N/A")
        )
    )

    action_type = (
        action_proposal.action_type
        if action_proposal
        else (approval.requested_action if approval else "INSPECT_BEARING_ASSEMBLY")
    )

    params = (
        action_proposal.parameters
        if action_proposal and isinstance(action_proposal.parameters, dict)
        else (
            approval.authorization_context.get("parameters", {})
            if approval
            and approval.authorization_context
            and isinstance(approval.authorization_context.get("parameters"), dict)
            else {}
        )
    )

    rec_title = params.get("title") or (
        investigation.recommendation.title
        if investigation and getattr(investigation, "recommendation", None)
        else "Inspect Drive-End Bearing Assembly"
    )

    rec_id = (
        action_proposal.recommendation_id
        if action_proposal
        else (getattr(approval, "recommendation_id", "REC-ADVISORY") if approval else "REC-ADVISORY")
    )

    rationale = (
        action_proposal.reason
        if action_proposal
        else (
            approval.authorization_context.get("reason")
            if approval and approval.authorization_context
            else ""
        )
    ) or (
        investigation.recommendation.rationale
        if investigation and getattr(investigation, "recommendation", None)
        else "Operational recommendation from investigation."
    )

    evidence_refs = (
        action_proposal.evidence_ids
        if action_proposal and action_proposal.evidence_ids
        else (
            investigation.recommendation.evidence_refs
            if investigation and getattr(investigation, "recommendation", None)
            else []
        )
    )

    if action_proposal and hasattr(action_proposal.priority, "value"):
        priority_str = action_proposal.priority.value
    elif action_proposal:
        priority_str = str(action_proposal.priority)
    elif approval and approval.authorization_context and "priority" in approval.authorization_context:
        p = approval.authorization_context["priority"]
        priority_str = p.value if hasattr(p, "value") else str(p)
    else:
        priority_str = "HIGH"

    suggested_parts = params.get("suggested_parts") or (
        investigation.recommendation.suggested_parts
        if investigation and getattr(investigation, "recommendation", None)
        else []
    )
    suggested_checklist = params.get("suggested_checklist") or (
        investigation.recommendation.suggested_checklist
        if investigation and getattr(investigation, "recommendation", None)
        else []
    )
    estimated_downtime = params.get("estimated_downtime_hours") or (
        investigation.recommendation.estimated_downtime_hours
        if investigation and getattr(investigation, "recommendation", None)
        else 2.0
    )

    proposal_status = (
        action_proposal.status
        if action_proposal
        else (
            "PENDING_APPROVAL"
            if approval and approval.status == ApprovalStatus.PENDING
            else "UNKNOWN"
        )
    )
    approval_status_val = approval.status.value if approval else "PENDING"
    approval_record_id = approval.approval_id if approval else f"APP-{prop_id}"

    # 2. Render Review Surface based on Status
    is_pending = (
        (approval and approval.status == ApprovalStatus.PENDING)
        or proposal_status == "PENDING_APPROVAL"
    )
    is_approved = (
        (approval and approval.status == ApprovalStatus.APPROVED)
        or proposal_status == "APPROVED"
    )
    is_rejected = (
        (approval and approval.status == ApprovalStatus.REJECTED)
        or proposal_status == "REJECTED"
    )

    checklist_html = ""
    if suggested_checklist:
        items = "".join([f"<li style='margin-bottom: 2px;'>{item}</li>" for item in suggested_checklist])
        checklist_html = f"<div style='margin-top: 6px;'><span style='font-size: 11px; color: var(--text-muted); font-weight: 600;'>Suggested Checklist:</span><ul style='font-size: 12px; color: var(--text-secondary); margin: 4px 0 0 16px; padding: 0;'>{items}</ul></div>"

    parts_html = ""
    if suggested_parts:
        parts_str = ", ".join(suggested_parts)
        parts_html = f"<div style='font-size: 11px; color: var(--primary-accent); margin-top: 4px;'>Suggested Parts: <b>{parts_str}</b></div>"

    ev_badges = "".join([f"<span class='badge badge-neutral' style='font-size: 10px; margin-right: 4px;'>{reid}</span>" for reid in evidence_refs])
    ev_html = f"<div style='margin-top: 6px;'><span style='font-size: 10px; color: var(--text-muted); text-transform: uppercase;'>Evidence Grounding: </span>{ev_badges}</div>" if ev_badges else ""

    if is_pending:
        st.markdown(
            f"""
            <div class="ind-card-warning">
                <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px;">
                    <div>
                        <span class="badge badge-warning">AUTHORIZATION REQUIRED</span>
                        <span style="font-size: 12px; color: var(--text-muted); margin-left: 8px;">Proposal: <code>{prop_id}</code></span>
                        <span style="font-size: 12px; color: var(--text-muted); margin-left: 6px;">Approval: <code>{approval_record_id}</code></span>
                    </div>
                    <div style="font-size: 11px; color: #d97706; font-weight: 600;">
                        Policy: Operational action proposals require verified human authorization
                    </div>
                </div>

                <div style="font-size: 16px; font-weight: 700; color: var(--text-primary); margin-top: 10px;">
                    {rec_title}
                </div>
                <div style="font-size: 12px; color: var(--text-secondary); margin-top: 4px;">
                    Target Machine: <b>{machine_id}</b> &nbsp;|&nbsp; Action: <b>{action_type}</b> &nbsp;|&nbsp; Priority: <span class="badge badge-critical" style="font-size: 10px;">{priority_str}</span> &nbsp;|&nbsp; Est. Downtime: <b>{estimated_downtime}h</b>
                </div>
                <div style="font-size: 12px; color: var(--text-muted); margin-top: 6px;">
                    <b>Rationale:</b> {rationale}
                </div>
                {parts_html}
                {checklist_html}
                {ev_html}
                <div style="margin-top: 8px; font-size: 11px; color: var(--text-muted);">
                    Status: Proposal: <span class="badge badge-warning">{proposal_status}</span> &nbsp;|&nbsp; Approval: <span class="badge badge-warning">{approval_status_val}</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        with st.expander("Authorize / Reject Action", expanded=True):
            operator_name = st.text_input(
                "Authorized Operator ID:",
                value=st.session_state.get("active_user", "operator.shubham"),
                key="approval_operator_input",
                help="Only authenticated human personnel may grant approval. Autonomous agents cannot self-approve.",
            )
            justification = st.text_area(
                "Decision Justification / Notes:",
                value="Reviewed physical telemetry harmonics and thermal runaway. Authorized operational action proposal.",
                key="approval_justification_input",
            )

            col_app, col_rej = st.columns([2, 1])

            with col_app:
                if st.button("Confirm & Grant Approval", type="primary", width="stretch"):
                    if not operator_name.strip():
                        st.error("Operator identity cannot be empty.")
                    else:
                        try:
                            on_approve(approval_record_id, operator_name.strip(), justification.strip())
                            st.session_state.last_action_message = f"Approval {approval_record_id} granted by {operator_name}."
                            st.rerun()
                        except PermissionError as p_err:
                            st.error(str(p_err))
                        except Exception as exc:
                            st.error(f"Approval failed: {exc}")

            with col_rej:
                if st.button("Reject Proposal", type="secondary", width="stretch"):
                    if not operator_name.strip():
                        st.error("Operator identity cannot be empty.")
                    else:
                        try:
                            on_reject(approval_record_id, operator_name.strip(), justification.strip())
                            st.session_state.last_action_message = f"Approval {approval_record_id} rejected by {operator_name}."
                            st.rerun()
                        except PermissionError as p_err:
                            st.error(str(p_err))
                        except Exception as exc:
                            st.error(f"Rejection failed: {exc}")

    elif is_approved:
        decision_by = (
            approval.decision_by or approval.reviewed_by
            if approval
            else "operator.shubham"
        )
        decision_reason = (
            approval.decision_reason
            if approval and approval.decision_reason
            else "Authorized by human operator."
        )

        st.markdown(
            f"""
            <div class="ind-card-success">
                <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px;">
                    <div>
                        <span class="badge badge-healthy">ACTION AUTHORIZED</span>
                        <span style="font-size: 12px; color: var(--text-muted); margin-left: 8px;">Proposal: <code>{prop_id}</code></span>
                        <span style="font-size: 12px; color: var(--text-muted); margin-left: 6px;">Approval: <code>{approval_record_id}</code></span>
                    </div>
                    <div style="font-size: 11px; color: #16a34a; font-weight: 600;">
                        Authorized by: <b>{decision_by}</b>
                    </div>
                </div>
                <div style="font-size: 13px; color: var(--text-secondary); margin-top: 8px;">
                    <b>Action:</b> {action_type} on machine <b>{machine_id}</b>
                </div>
                <div style="font-size: 13px; color: var(--text-secondary); margin-top: 4px;">
                    <b>Reason:</b> {decision_reason}
                </div>
                <div style="margin-top: 10px; padding: 10px; background: rgba(34, 197, 94, 0.08); border: 1px solid #16a34a; border-radius: 6px;">
                    <div style="font-weight: 700; color: #16a34a; font-size: 12px; letter-spacing: 0.03em;">
                        APPROVED — READY FOR SEPARATE GOVERNED EXECUTION
                    </div>
                    <div style="font-size: 12px; color: var(--text-muted); margin-top: 3px;">
                        Action execution is a separate governed step. Operational dispatch requires independent execution authorization.
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    elif is_rejected:
        rejection_reason = (
            approval.decision_reason
            if approval and approval.decision_reason
            else "Rejected by human operator."
        )
        st.markdown(
            f"""
            <div class="ind-card">
                <span class="badge badge-critical">PROPOSAL REJECTED</span>
                <span style="font-size: 12px; color: var(--text-secondary); margin-left: 8px;">
                    Proposal <code>{prop_id}</code> was rejected. Reason: {rejection_reason}
                </span>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f"""
            <div class="ind-card">
                <span class="badge badge-info">{proposal_status}</span>
                <span style="font-size: 12px; color: var(--text-secondary); margin-left: 8px;">
                    Proposal <code>{prop_id}</code> status: {proposal_status}
                </span>
            </div>
            """,
            unsafe_allow_html=True,
        )
