"""Post-Maintenance Verification Panel Component.

Follows Sections 26 & 27 of AGENT.md:
- Renders before/after physical metrics comparison: Vibration RMS, Temperature, Failure Risk, Anomalies, OEE
- Distinctly displays VERIFIED vs FAILED outcomes calculated by VerificationService
- Never displays SUCCESS when verification failed
- Exposes interactive controls to run nominal verification or simulate failed maintenance
- Theme-aware styling and zero emojis
"""

from __future__ import annotations

from typing import Callable, Optional
import streamlit as st

from domain.enums import VerificationStatus
from domain.models import Verification, WorkOrder


def render_verification_panel(
    verification: Optional[Verification],
    work_order: Optional[WorkOrder],
    on_run_verification: Callable[[str, str, bool], None],
) -> None:
    """Render the closed-loop verification results and before/after metrics table."""
    st.markdown(
        """
        <div style="font-size: 13px; font-weight: 700; color: var(--text-primary); text-transform: uppercase; letter-spacing: 0.04em; margin-bottom: 8px;">
            Closed-Loop Physical Verification
        </div>
        """,
        unsafe_allow_html=True,
    )

    if not work_order:
        st.info("No work order associated with this investigation.")
        return

    # Trigger control if work order is completed or verified
    if work_order.status.value in ("COMPLETED", "VERIFIED") or verification is not None:
        with st.expander("Run Verification Evaluation", expanded=(verification is None)):
            st.caption("Ingest post-maintenance telemetry from restarted equipment and evaluate against VerificationPolicy:")
            verifier_id = st.text_input("Lead Reliability Engineer / Verifier ID:", value="lead.engineer.david", key="verifier_id_input")

            col_v1, col_v2 = st.columns(2)
            with col_v1:
                if st.button("Ingest Telemetry & Run Verification", type="primary", use_container_width=True):
                    on_run_verification(work_order.work_order_id, verifier_id, False)
                    st.session_state.last_action_message = "Post-maintenance telemetry verified successfully."
                    st.rerun()
            with col_v2:
                if st.button("Simulate Improper Repair (Fail Path)", type="secondary", use_container_width=True, help="Simulate wrong bearing / high vibration persisting"):
                    on_run_verification(work_order.work_order_id, verifier_id, True)
                    st.session_state.last_action_message = "Post-maintenance verification failed: signals abnormal."
                    st.rerun()

    if not verification:
        st.info("Awaiting physical work order completion to ingest post-maintenance sensor telemetry.")
        return

    # Render Verification Outcome
    if verification.verification_status == VerificationStatus.VERIFIED:
        st.markdown(
            f"""
            <div class="ind-card-success">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <div>
                        <span class="badge badge-healthy">PHYSICAL VERIFICATION PASSED</span>
                        <span style="font-size: 12px; color: var(--text-muted); margin-left: 8px;">ID: <code>{verification.verification_id}</code></span>
                    </div>
                    <div style="font-size: 11px; color: #16a34a; font-weight: 600;">
                        Status: <b>VERIFIED (100% Deterministic)</b>
                    </div>
                </div>
                <div style="font-size: 13px; color: var(--text-secondary); margin-top: 8px;">
                    <b>Evaluation:</b> {verification.verification_reason}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    elif verification.verification_status == VerificationStatus.FAILED:
        st.markdown(
            f"""
            <div class="ind-card-hero">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <div>
                        <span class="badge badge-critical">VERIFICATION FAILED</span>
                        <span style="font-size: 12px; color: #dc2626; margin-left: 8px;">ID: <code>{verification.verification_id}</code></span>
                    </div>
                    <div style="font-size: 11px; color: #dc2626; font-weight: 600;">
                        Status: <b>MACHINE RECOVERY NOT CONFIRMED</b>
                    </div>
                </div>
                <div style="font-size: 13px; color: #dc2626; margin-top: 8px;">
                    <b>Finding:</b> {verification.verification_reason}
                </div>
                <div style="font-size: 11px; color: var(--text-muted); margin-top: 6px;">
                    Work order remains <b>COMPLETED</b> (technician signed off, but telemetry failed). Investigation remains <b>OPEN</b> for follow-up root cause analysis.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Before / After Metrics Comparison Table
    st.markdown("<div style='font-size: 11px; font-weight: 700; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em; margin-top: 14px; margin-bottom: 6px;'>MEASURED BEFORE & AFTER DELTAS</div>", unsafe_allow_html=True)

    vib_delta = verification.post_vibration_rms - verification.pre_vibration_rms
    vib_pct = (vib_delta / max(verification.pre_vibration_rms, 0.0001)) * 100
    temp_delta = verification.post_temperature_c - verification.pre_temperature_c
    risk_delta = verification.post_risk_score - verification.pre_risk_score
    risk_pct = (risk_delta / max(verification.pre_risk_score, 0.0001)) * 100
    pre_oee_pct = verification.pre_oee * 100
    post_oee_pct = verification.post_oee * 100
    oee_delta = post_oee_pct - pre_oee_pct

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        st.metric(
            label="Vibration RMS",
            value=f"{verification.post_vibration_rms:.3f} g",
            delta=f"{vib_pct:+.1f}% ({vib_delta:+.3f}g)",
            delta_color="normal" if vib_delta < 0 else "inverse",
        )
    with c2:
        st.metric(
            label="Bearing Temp",
            value=f"{verification.post_temperature_c:.1f} °C",
            delta=f"{temp_delta:+.1f} °C",
            delta_color="normal" if temp_delta < 0 else "inverse",
        )
    with c3:
        st.metric(
            label="Failure Risk",
            value=f"{verification.post_risk_score:.2f}",
            delta=f"{risk_pct:+.1f}%",
            delta_color="normal" if risk_delta < 0 else "inverse",
        )
    with c4:
        st.metric(
            label="Active Anomalies",
            value=f"{verification.anomalies_after}",
            delta=f"{verification.anomalies_after - verification.anomalies_before}",
            delta_color="normal" if verification.anomalies_after < verification.anomalies_before else "inverse",
        )
    with c5:
        st.metric(
            label="OEE Impact",
            value=f"{post_oee_pct:.1f}%",
            delta=f"{oee_delta:+.1f}%",
            delta_color="normal" if oee_delta > 0 else "inverse",
        )
