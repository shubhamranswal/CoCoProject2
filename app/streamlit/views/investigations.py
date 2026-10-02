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
    finding = detail["finding"]
    rec = detail["recommendation"]
    evidence = detail["evidence"]
    hypotheses = detail["hypotheses"]
    app = detail["approval"]
    wo = detail["work_order"]

    # Header Card
    conf_pct = (inv.confidence * 100) if inv.confidence else 92.0
    st.markdown(
        f"""
        <div class="ind-card" style="border-left: 4px solid var(--primary-accent);">
            <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                <div>
                    <span class="badge badge-info">{inv.status.value}</span>
                    <span class="badge badge-neutral" style="margin-left: 6px;">ASSET: {inv.machine_id}</span>
                    <span class="badge badge-critical" style="margin-left: 6px;">{inv.failure_mode.value}</span>
                    <div style="font-size: 18px; font-weight: 700; color: var(--text-primary); margin-top: 6px;">
                        Reliability Investigation — {inv.investigation_id}
                    </div>
                    <div style="font-size: 12px; color: var(--text-muted); margin-top: 2px;">
                        Target Equipment: <b>{inv.machine_id} (Conveyor Drive Motor)</b> &nbsp;|&nbsp; Alert Ref: <code>{inv.alert_id or 'ALT-M204'}</code>
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

    # Progression Timeline
    render_investigation_timeline(inv)

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
                        <div style="font-size: 11px; color: var(--text-secondary); margin-top: 4px;">
                            {h.rationale}
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
    else:
        st.info("No hypothesis records attached.")

    st.markdown("<hr style='border: none; border-bottom: 1px solid var(--border-subtle); margin: 16px 0;'/>", unsafe_allow_html=True)

    # 3. Finding Panel (Facts vs Historical vs Inferences)
    if finding:
        st.markdown(
            f"""
            <div class="ind-card-hero">
                <div style="font-size: 11px; font-weight: 700; color: #dc2626; text-transform: uppercase; letter-spacing: 0.05em;">
                    ROOT CAUSE FINDING (CONFIDENCE: {finding.confidence * 100:.0f}%)
                </div>
                <div style="font-size: 15px; font-weight: 700; color: var(--text-primary); margin-top: 6px;">
                    {finding.summary}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        col_f1, col_f2, col_f3 = st.columns(3)
        with col_f1:
            st.markdown("<b>Observed Sensor Facts:</b>", unsafe_allow_html=True)
            for fact in finding.observed_facts:
                st.markdown(f"- <span style='font-size: 12px; color: var(--text-secondary);'>{fact}</span>", unsafe_allow_html=True)
        with col_f2:
            st.markdown("<b>Historical Precedents:</b>", unsafe_allow_html=True)
            for hfact in finding.historical_facts:
                st.markdown(f"- <span style='font-size: 12px; color: var(--text-secondary);'>{hfact}</span>", unsafe_allow_html=True)
        with col_f3:
            st.markdown("<b>Correlated Inferences:</b>", unsafe_allow_html=True)
            for inf in finding.inferences:
                st.markdown(f"- <span style='font-size: 12px; color: var(--text-secondary);'>{inf}</span>", unsafe_allow_html=True)

    st.markdown("<hr style='border: none; border-bottom: 1px solid var(--border-subtle); margin: 16px 0;'/>", unsafe_allow_html=True)

    # 4. Recommendation Panel
    if rec:
        st.markdown(
            f"""
            <div class="ind-card">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <div>
                        <span class="badge badge-warning">RECOMMENDATION</span>
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
                <div style="font-size: 11px; color: var(--primary-accent); margin-top: 6px;">
                    Required Replacement Parts: <b>{', '.join(rec.suggested_parts)}</b>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # 5. Human Approval Gateway Panel
    render_approval_panel(
        approval=app,
        investigation=inv,
        on_approve=lambda a_id, actor, r: facade.approve_action(a_id, actor, r),
        on_reject=lambda a_id, actor, r: facade.reject_action(a_id, actor, r),
        on_create_work_order=lambda a_id, actor: facade.create_work_order_from_approval(a_id, actor),
    )

    # If work order already created, show link button to navigate
    if wo:
        st.markdown("<hr style='border: none; border-bottom: 1px solid var(--border-subtle); margin: 16px 0;'/>", unsafe_allow_html=True)
        st.success(f"Dispatched Work Order: {wo.work_order_id} ({wo.status.value})")
        if st.button("Go to Work Order Management", key="nav_to_wo_btn", type="primary", use_container_width=True):
            navigate_to("Work Orders", work_order_id=wo.work_order_id)
            st.rerun()
