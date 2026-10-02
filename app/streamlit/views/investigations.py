"""AI Investigations Workspace View.

Follows Sections 16, 17, 18, 19, 20, 21, 22, & 23 of AGENT.md:
- Investigation Workspace header
- Investigation progression timeline
- Evidence Panel (typed facts & sources)
- Hypothesis Comparison (Supported vs Refuted)
- Finding Panel (Observed Facts vs Historical Facts vs Inferences)
- Recommendation Panel (Action Scope & Replacement Parts)
- Human Approval Gateway (Policy Enforcement & Work Order Generation)
- Theme CSS variable styling and zero emojis
"""

from __future__ import annotations

import streamlit as st

from app.streamlit.components.approvals import render_approval_panel
from app.streamlit.components.evidence import render_evidence_panel
from app.streamlit.components.timelines import render_investigation_timeline
from app.streamlit.services.view_service import CommandCenterFacade
from app.streamlit.state import navigate_to


def render_investigations_view(facade: CommandCenterFacade) -> None:
    """Render the autonomous reliability investigation workspace."""
    investigations = facade.get_investigations()

    if not investigations:
        st.warning("No investigations found in repository.")
        st.caption("Trigger an investigation using the demo controls or run the scenario pipeline.")
        return

    inv_ids = [i.investigation_id for i in investigations]
    cur_inv_id = st.session_state.get("selected_investigation_id")
    if cur_inv_id not in inv_ids:
        cur_inv_id = inv_ids[0]

    # Investigation Selector
    col_sel, col_act = st.columns([3, 1])
    with col_sel:
        chosen_inv_id = st.selectbox(
            "Select Investigation Case:",
            inv_ids,
            index=inv_ids.index(cur_inv_id) if cur_inv_id in inv_ids else 0,
            format_func=lambda x: f"{x} — Machine {facade.get_investigation_detail(x)['investigation'].machine_id if facade.get_investigation_detail(x) else x}",
            key="inv_case_selector",
        )
        if chosen_inv_id != cur_inv_id:
            st.session_state.selected_investigation_id = chosen_inv_id
            st.rerun()

    detail = facade.get_investigation_detail(chosen_inv_id)
    if not detail:
        st.error(f"Investigation '{chosen_inv_id}' not found.")
        return

    inv = detail["investigation"]
    evidence = detail["evidence"]
    hypotheses = detail["hypotheses"]
    findings = detail.get("findings") or ([detail["finding"]] if detail.get("finding") else [])
    recommendations = detail.get("recommendations") or ([detail["recommendation"]] if detail.get("recommendation") else [])
    provenance = detail.get("provenance") or getattr(inv, "provenance", {}) or {}
    tool_calls = detail.get("tool_calls", [])
    machine_name = detail.get("machine_name") or inv.machine_id
    action_proposal = detail.get("action_proposal")
    app = detail.get("approval")
    wo = detail.get("work_order")

    # Header Card (Dynamic Asset, Trigger, Timestamps)
    conf_pct = (inv.confidence * 100) if inv.confidence else 92.0
    trigger_str = inv.trigger_type.value if hasattr(inv.trigger_type, "value") else str(inv.trigger_type or "ANOMALY")
    trigger_ref = getattr(inv, "prediction_id", None) or getattr(inv, "alert_id", None) or getattr(inv, "trigger_id", None) or "N/A"
    completed_dt = getattr(inv, "completed_at", None) or getattr(inv, "created_at", None)
    completed_str = completed_dt.strftime("%Y-%m-%d %H:%M:%S UTC") if completed_dt else "N/A"

    st.markdown(
        f"""
        <div class="ind-card" style="border-left: 4px solid var(--primary-accent);">
            <div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 8px;">
                <div>
                    <span class="badge badge-info">{inv.status.value}</span>
                    <span class="badge badge-neutral" style="margin-left: 6px;">ASSET: {inv.machine_id}</span>
                    <span class="badge badge-critical" style="margin-left: 6px;">{inv.failure_mode.value}</span>
                    <div style="font-size: 18px; font-weight: 700; color: var(--text-primary); margin-top: 6px;">
                        Reliability Investigation — {inv.investigation_id}
                    </div>
                    <div style="font-size: 12px; color: var(--text-muted); margin-top: 2px;">
                        Target Equipment: <b>{inv.machine_id} ({machine_name})</b> &nbsp;|&nbsp; Trigger: <b>{trigger_str}</b> (<code>{trigger_ref}</code>) &nbsp;|&nbsp; Completed: <b>{completed_str}</b>
                    </div>
                </div>
                <div style="text-align: right;">
                    <div style="font-size: 10px; color: var(--text-muted); text-transform: uppercase;">Diagnosis Confidence</div>
                    <div style="font-size: 26px; font-weight: 700; color: var(--primary-accent); line-height: 1;">
                        {conf_pct:.0f}%
                    </div>
                    <div style="font-size: 11px; color: var(--text-muted);">Evidence Base: {len(evidence)} items</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Provenance & Execution Card
    exec_mode = provenance.get("execution_mode", "DETERMINISTIC_FALLBACK")
    adapter_name = provenance.get("adapter", "N/A")
    model_name = provenance.get("model", "N/A")
    ev_count = provenance.get("evidence_count", len(evidence))
    call_count = provenance.get("tool_count", len(tool_calls))
    st.markdown(
        f"""
        <div class="ind-card" style="margin-top: 8px; padding: 10px 14px; background: var(--bg-card); border: 1px solid var(--border-subtle); border-radius: 6px;">
            <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px; font-size: 11px;">
                <div>
                    <span style="color: var(--text-muted); text-transform: uppercase; font-weight: 700; letter-spacing: 0.04em;">Provenance & Execution:</span>
                    <span class="badge badge-info" style="margin-left: 6px;">{exec_mode}</span>
                    <span style="color: var(--text-secondary); margin-left: 10px;">Adapter: <b>{adapter_name}</b></span>
                    <span style="color: var(--text-secondary); margin-left: 10px;">Model: <code>{model_name}</code></span>
                </div>
                <div>
                    <span style="color: var(--text-secondary);">Evidence Base: <b>{ev_count}</b></span>
                    <span style="color: var(--text-muted); margin: 0 6px;">|</span>
                    <span style="color: var(--text-secondary);">Governed Read Tools: <b>{call_count}</b></span>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Progression Timeline
    render_investigation_timeline(inv, detail=detail)

    st.markdown("<hr style='border: none; border-bottom: 1px solid var(--border-subtle); margin: 16px 0;'/>", unsafe_allow_html=True)

    # 1. Evidence Repository Panel
    render_evidence_panel(evidence)

    st.markdown("<hr style='border: none; border-bottom: 1px solid var(--border-subtle); margin: 16px 0;'/>", unsafe_allow_html=True)

    # 2. Hypothesis Comparison
    st.markdown(
        """
        <div style="font-size: 13px; font-weight: 700; color: var(--text-primary); text-transform: uppercase; letter-spacing: 0.04em; margin-bottom: 8px;">
            Hypothesis Evaluation & Differential Diagnosis
        </div>
        """,
        unsafe_allow_html=True,
    )
    if hypotheses:
        h_cols = st.columns(len(hypotheses))
        for col, h in zip(h_cols, hypotheses):
            with col:
                is_supported = (h.status == "SUPPORTED")
                badge_type = "badge-critical" if is_supported else "badge-neutral"
                border_col = "#dc2626" if is_supported else "var(--border-subtle)"

                sup_badges = "".join([f'<span class="badge badge-healthy" style="margin-right: 4px; font-size: 10px;">SUPPORTS: {eid}</span>' for eid in (h.supporting_evidence_ids or [])])
                con_badges = "".join([f'<span class="badge badge-critical" style="margin-right: 4px; font-size: 10px;">CONTRADICTS: {eid}</span>' for eid in (h.contradicting_evidence_ids or [])])
                evidence_markup = ""
                if sup_badges or con_badges:
                    evidence_markup = f"""
                    <div style="margin-top: 8px; border-top: 1px solid var(--border-subtle); padding-top: 6px;">
                        <span style="font-size: 10px; color: var(--text-muted); text-transform: uppercase;">Evidence Grounding:</span>
                        <div style="margin-top: 4px; display: flex; flex-wrap: wrap; gap: 4px;">{sup_badges}{con_badges}</div>
                    </div>
                    """

                statement_markup = ""
                if getattr(h, "statement", None):
                    statement_markup = f"""
                    <div style="font-size: 12px; color: var(--text-primary); font-weight: 500; margin-top: 4px;">
                        {h.statement}
                    </div>
                    """

                st.markdown(
                    f"""
                    <div class="ind-card" style="border: 1px solid {border_col};">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <span class="badge {badge_type}">{h.status}</span>
                            <span style="font-size: 11px; color: var(--text-muted);">{h.confidence * 100:.0f}% conf</span>
                        </div>
                        <div style="font-size: 13px; font-weight: 700; color: var(--text-primary); margin-top: 6px;">
                            {h.hypothesis_name}
                        </div>
                        {statement_markup}
                        <div style="font-size: 11px; color: var(--text-secondary); margin-top: 6px;">
                            {h.rationale}
                        </div>
                        {evidence_markup}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
    else:
        st.info("No hypothesis records attached.")

    st.markdown("<hr style='border: none; border-bottom: 1px solid var(--border-subtle); margin: 16px 0;'/>", unsafe_allow_html=True)

    # 3. Finding Panel (Multi-Finding: Root Cause, Operational Impact, Inventory Risk)
    if findings:
        st.markdown(
            f"""
            <div style="font-size: 13px; font-weight: 700; color: var(--text-primary); text-transform: uppercase; letter-spacing: 0.04em; margin-bottom: 8px;">
                Synthesized Investigation Findings ({len(findings)} Findings)
            </div>
            """,
            unsafe_allow_html=True,
        )
        for idx, f in enumerate(findings):
            is_primary = (idx == 0)
            card_class = "ind-card-hero" if is_primary else "ind-card"
            title_prefix = "ROOT CAUSE FINDING" if is_primary else f"FINDING #{idx + 1}"
            border_style = "border-left: 4px solid #dc2626;" if is_primary else "border-left: 4px solid var(--primary-accent);"

            statement_html = ""
            if getattr(f, "statement", None):
                statement_html = f"<div style='font-size: 12px; color: var(--text-secondary); margin-top: 4px; font-style: italic;'>{f.statement}</div>"

            refs = getattr(f, "evidence_refs", []) or getattr(f, "supporting_evidence_ids", [])
            refs_badges = "".join([f"<span class='badge badge-neutral' style='font-size: 10px; margin-right: 4px;'>{r}</span>" for r in refs])
            refs_html = f"<div style='margin-top: 6px;'><span style='font-size: 10px; color: var(--text-muted); text-transform: uppercase;'>Evidence Grounding: </span>{refs_badges}</div>" if refs_badges else ""

            st.markdown(
                f"""
                <div class="{card_class}" style="{border_style} margin-bottom: 12px;">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <span style="font-size: 11px; font-weight: 700; color: #dc2626; text-transform: uppercase; letter-spacing: 0.05em;">
                            {title_prefix} (CONFIDENCE: {f.confidence * 100:.0f}%)
                        </span>
                        <span class="badge badge-neutral">ID: {f.finding_id}</span>
                    </div>
                    <div style="font-size: 15px; font-weight: 700; color: var(--text-primary); margin-top: 6px;">
                        {f.summary}
                    </div>
                    {statement_html}
                    {refs_html}
                </div>
                """,
                unsafe_allow_html=True,
            )

            col_f1, col_f2, col_f3 = st.columns(3)
            with col_f1:
                st.markdown("<b>Observed Sensor Facts:</b>", unsafe_allow_html=True)
                if f.observed_facts:
                    for fact in f.observed_facts:
                        st.markdown(f"- <span style='font-size: 12px; color: var(--text-secondary);'>{fact}</span>", unsafe_allow_html=True)
                else:
                    st.caption("None reported.")
            with col_f2:
                st.markdown("<b>Historical Precedents:</b>", unsafe_allow_html=True)
                if f.historical_facts:
                    for hfact in f.historical_facts:
                        st.markdown(f"- <span style='font-size: 12px; color: var(--text-secondary);'>{hfact}</span>", unsafe_allow_html=True)
                else:
                    st.caption("None reported.")
            with col_f3:
                st.markdown("<b>Correlated Inferences:</b>", unsafe_allow_html=True)
                if f.inferences:
                    for inf in f.inferences:
                        st.markdown(f"- <span style='font-size: 12px; color: var(--text-secondary);'>{inf}</span>", unsafe_allow_html=True)
                else:
                    st.caption("None reported.")

            if idx < len(findings) - 1:
                st.markdown("<div style='margin-bottom: 12px;'></div>", unsafe_allow_html=True)

    st.markdown("<hr style='border: none; border-bottom: 1px solid var(--border-subtle); margin: 16px 0;'/>", unsafe_allow_html=True)

    # 4. Recommendation Panel (Strictly ADVISORY & NON-EXECUTABLE)
    if recommendations:
        st.markdown(
            f"""
            <div style="font-size: 13px; font-weight: 700; color: var(--text-primary); text-transform: uppercase; letter-spacing: 0.04em; margin-bottom: 8px;">
                Advisory Recommendations ({len(recommendations)} Items)
            </div>
            """,
            unsafe_allow_html=True,
        )
        for rec in recommendations:
            priority_val = rec.priority.value if hasattr(rec.priority, "value") else str(rec.priority)
            parts_str = ", ".join(rec.suggested_parts) if rec.suggested_parts else "None required"
            next_step_html = (
                f"<div style='font-size: 12px; color: var(--text-primary); margin-top: 6px;'><b>Suggested Next Step:</b> {rec.suggested_next_step}</div>"
                if getattr(rec, "suggested_next_step", None) else ""
            )
            checklist_items = "".join([f"<li><span style='font-size: 12px; color: var(--text-secondary);'>{item}</span></li>" for item in getattr(rec, "suggested_checklist", [])])
            checklist_html = (
                f"<div style='margin-top: 8px;'><span style='font-size: 11px; font-weight: 600; color: var(--text-primary); text-transform: uppercase;'>Suggested Procedure Checklist:</span><ul style='margin-top: 4px; padding-left: 20px;'>{checklist_items}</ul></div>"
                if checklist_items else ""
            )
            rec_evidence = getattr(rec, "evidence_refs", []) or getattr(rec, "evidence_ids", [])
            rec_ev_badges = "".join([f"<span class='badge badge-neutral' style='font-size: 10px; margin-right: 4px;'>{reid}</span>" for reid in rec_evidence])
            rec_ev_html = (
                f"<div style='margin-top: 6px;'><span style='font-size: 10px; color: var(--text-muted); text-transform: uppercase;'>Evidence: </span>{rec_ev_badges}</div>"
                if rec_ev_badges else ""
            )

            # Status badge logic based on governed proposal state
            is_proposed = action_proposal and (
                getattr(action_proposal, "recommendation_id", None) == rec.recommendation_id
                or len(recommendations) == 1
            )
            if is_proposed and action_proposal.status == "PENDING_APPROVAL":
                status_badge = '<span class="badge badge-warning" style="font-weight: 700;">PENDING HUMAN APPROVAL</span>'
            elif is_proposed and action_proposal.status == "APPROVED":
                status_badge = '<span class="badge badge-healthy" style="font-weight: 700;">APPROVED — READY FOR SEPARATE GOVERNED EXECUTION</span>'
            elif is_proposed and action_proposal.status == "REJECTED":
                status_badge = '<span class="badge badge-critical" style="font-weight: 700;">PROPOSAL REJECTED</span>'
            else:
                status_badge = '<span class="badge badge-info" style="font-weight: 700;">STATUS: ADVISORY (NON-EXECUTABLE)</span>'

            st.markdown(
                f"""
                <div class="ind-card" style="border-left: 4px solid #0284c7;">
                    <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 6px;">
                        <div>
                            {status_badge}
                            <span class="badge badge-critical" style="margin-left: 6px;">PRIORITY: {priority_val}</span>
                            <span class="badge badge-neutral" style="margin-left: 6px;">ACTION: {rec.action_type}</span>
                        </div>
                        <div style="font-size: 11px; color: var(--text-muted);">
                            Est. Downtime: <b>{rec.estimated_downtime_hours}h</b>
                        </div>
                    </div>
                    <div style="font-size: 16px; font-weight: 700; color: var(--text-primary); margin-top: 8px;">
                        {rec.title}
                    </div>
                    <div style="font-size: 12px; color: var(--text-secondary); margin-top: 4px;">
                        {rec.action_description}
                    </div>
                    {next_step_html}
                    <div style="font-size: 11px; color: var(--primary-accent); margin-top: 6px;">
                        Required / Suggested Parts: <b>{parts_str}</b>
                    </div>
                    {checklist_html}
                    {rec_ev_html}
                </div>
                """,
                unsafe_allow_html=True,
            )

            # Explicit human submission button when no proposal exists yet
            if not is_proposed:
                col_btn, col_info = st.columns([1, 2])
                with col_btn:
                    if st.button(
                        "Submit for Human Approval",
                        key=f"submit_proposal_btn_{rec.recommendation_id}",
                        type="primary",
                        help="Submit this advisory recommendation to the Human Approval Gateway. Does NOT execute actions or dispatch work orders.",
                    ):
                        facade.submit_action_proposal_for_recommendation(
                            investigation_id=inv.investigation_id,
                            recommendation_id=rec.recommendation_id,
                        )
                        st.session_state.last_action_message = f"Action proposal submitted for {rec.recommendation_id}. Awaiting human authorization."
                        st.rerun()
                with col_info:
                    st.caption("Advisory recommendation. Submitting creates a governed action proposal requiring explicit operator authorization.")

    # 5. Governed Tool Audit Ledger Expander
    if tool_calls:
        with st.expander(f"Governed Read Tool Audit Ledger ({len(tool_calls)} Invocations)", expanded=False):
            audit_rows = []
            for t in tool_calls:
                mode = getattr(t, "tool_mode", None) or (t.arguments.get("tool_mode") if isinstance(t.arguments, dict) else None) or "READ"
                status_str = "PASS" if t.is_success else f"FAIL ({t.error_message or 'Error'})"
                ts_str = t.started_at.strftime("%Y-%m-%d %H:%M:%S UTC") if t.started_at else "N/A"
                audit_rows.append({
                    "Tool": t.tool_name,
                    "Mode": mode,
                    "Status": status_str,
                    "Duration": f"{t.duration_ms:.1f} ms",
                    "Timestamp": ts_str,
                })
            st.dataframe(audit_rows, use_container_width=True, hide_index=True)

    # 5. Human Approval Gateway Panel
    render_approval_panel(
        approval=app,
        investigation=inv,
        action_proposal=action_proposal,
        on_approve=lambda a_id, actor, r: facade.approve_action(a_id, actor, r),
        on_reject=lambda a_id, actor, r: facade.reject_action(a_id, actor, r),
    )

    # If work order already created, show link button to navigate
    if wo:
        st.markdown("<hr style='border: none; border-bottom: 1px solid var(--border-subtle); margin: 16px 0;'/>", unsafe_allow_html=True)
        st.success(f"Dispatched Work Order: {wo.work_order_id} ({wo.status.value})")
        if st.button("Go to Work Order Management", key="nav_to_wo_btn", type="primary", use_container_width=True):
            navigate_to("Work Orders", work_order_id=wo.work_order_id)
            st.rerun()
