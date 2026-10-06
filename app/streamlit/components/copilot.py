"""DeRule Copilot: Global Interactive AI Reliability Investigation Assistant Component.

Follows DeRule Governance and UX Architecture:
- Floating launcher at bottom-right of viewport ("Ask DeRule")
- Anchored compact chat panel with responsive layout
- Strictly read-only investigation interface (M4 tools only)
- Real-time display of OBSERVED FACT, INFERENCE, and UNKNOWN breakdown
- Transparent, truthful execution provenance (LIVE_CORTEX, DETERMINISTIC_FALLBACK, GOVERNANCE_GUARD)
- Zero emojis and full compatibility with DeRule Light / Dark industrial themes
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, List, Optional
import streamlit as st

logger = logging.getLogger(__name__)


def render_copilot_chat(facade: Any) -> None:
    """Render global floating DeRule Copilot assistant interface."""
    # 1. Initialize session state
    if "copilot_open" not in st.session_state:
        st.session_state["copilot_open"] = False
    if "copilot_history" not in st.session_state:
        st.session_state["copilot_history"] = []

    # Active view context resolution
    current_machine_id = st.session_state.get("selected_machine_id")
    current_investigation_id = st.session_state.get("selected_investigation_id")

    copilot_open = bool(st.session_state.get("copilot_open", False))

    # 2. Render Launcher (Always visible at bottom-right)
    _render_launcher(is_open=copilot_open)

    # 3. Render Expanded Chat Panel ONLY when open
    if copilot_open:
        _render_window(
            facade=facade,
            current_machine_id=current_machine_id,
            current_investigation_id=current_investigation_id,
        )


def _render_launcher(is_open: Optional[bool] = None) -> None:
    """Render floating launcher button."""
    if is_open is None:
        is_open = bool(st.session_state.get("copilot_open", False))

    with st.container(key="derule_copilot_launcher_container"):
        if st.button(
            "Ask DeRule  ●",
            key="derule_copilot_open_btn",
            help="Close DeRule Assistant" if is_open else "Open DeRule Autonomous Reliability Copilot",
        ):
            st.session_state["copilot_open"] = not is_open
            st.rerun()


def _render_window(
    facade: Any,
    current_machine_id: Optional[str] = None,
    current_investigation_id: Optional[str] = None,
) -> None:
    """Render compact floating chat window."""
    with st.container(key="derule_copilot_window_container"):

        # Header Bar
        col_hdr_title, col_hdr_actions = st.columns([4, 1])
        with col_hdr_title:
            ctx_label = f"• Asset {current_machine_id}" if current_machine_id else "• Fleet Context"
            st.markdown(
                f"""
                <div style="display: flex; align-items: baseline; gap: 8px;">
                    <span style="font-size: 13px; font-weight: 700; color: var(--text-primary); letter-spacing: -0.01em;">
                        DeRule Copilot
                    </span>
                    <span style="font-size: 10px; font-weight: 600; color: var(--primary-accent); text-transform: uppercase;">
                        {ctx_label}
                    </span>
                </div>
                <div style="font-size: 9px; color: var(--text-muted); margin-top: 1px;">
                    Read-Only Autonomous Investigation Assistant
                </div>
                """,
                unsafe_allow_html=True,
            )

        with col_hdr_actions:
            col_clear, col_close = st.columns(2)
            with col_clear:
                if st.button("⌫", key="derule_copilot_clear_btn", help="Clear conversation history"):
                    st.session_state["copilot_history"] = []
                    st.rerun()
            with col_close:
                if st.button("X", key="derule_copilot_close_btn", help="Close assistant"):
                    st.session_state["copilot_open"] = False
                    st.rerun()

        st.markdown("<hr style='margin: 6px 0 10px 0; border: none; border-bottom: 1px solid var(--border-subtle);'/>", unsafe_allow_html=True)

        # Chat Message History Area with Independent Internal Scrolling
        with st.container(height=380):
            history = st.session_state.get("copilot_history", [])

            # Empty State: Suggested Questions
            if not history:
                _render_empty_state_suggestions(
                    facade=facade,
                    current_machine_id=current_machine_id,
                    current_investigation_id=current_investigation_id,
                )
            else:
                # Render Messages
                for idx, msg in enumerate(history):
                    _render_message(msg, idx)

        st.markdown("<hr style='margin: 8px 0; border: none; border-bottom: 1px solid var(--border-subtle);'/>", unsafe_allow_html=True)

        # Chat Input Form
        with st.form(key="derule_copilot_chat_form", clear_on_submit=True):
            col_inp, col_send = st.columns([5, 1])
            with col_inp:
                user_query = st.text_input(
                    "Query",
                    placeholder="Ask about M21 health, evidence, parts, downtime...",
                    label_visibility="collapsed",
                    key="derule_copilot_text_input",
                )
            with col_send:
                submitted = st.form_submit_button("Send", type="primary")

            if submitted and user_query and user_query.strip():
                query_clean = user_query.strip()
                # 1. Record user turn
                st.session_state["copilot_history"].append({
                    "role": "user",
                    "content": query_clean,
                    "timestamp": datetime.now(timezone.utc),
                })

                # 2. Query Copilot via Facade
                response_msg = facade.ask_copilot(
                    query=query_clean,
                    current_machine_id=current_machine_id,
                    current_investigation_id=current_investigation_id,
                )

                # 3. Record assistant response
                st.session_state["copilot_history"].append(response_msg.to_dict())
                st.rerun()


def _render_empty_state_suggestions(
    facade: Any,
    current_machine_id: Optional[str] = None,
    current_investigation_id: Optional[str] = None,
) -> None:
    """Render empty state with contextual quick prompts."""
    target_mach = current_machine_id or "M21"
    st.markdown(
        """
        <div style="font-size: 11px; color: var(--text-secondary); margin-bottom: 10px; line-height: 1.4;">
            I can answer technical questions, examine physical telemetry anomalies, evaluate hypotheses,
            inspect spare parts stock, and summarize downtime exposure.
        </div>
        """,
        unsafe_allow_html=True,
    )

    suggested_queries = [
        f"Why is {target_mach} marked critical?",
        f"Show me the evidence behind bearing degradation on {target_mach}",
        f"What should I inspect first on {target_mach}?",
        f"What parts are available for this repair?",
        f"What production impact is exposed?",
        "What machines are currently critical across the fleet?",
    ]

    st.markdown("<div style='font-size: 10px; font-weight: 600; color: var(--text-muted); text-transform: uppercase; margin-bottom: 6px;'>Suggested Inquiries</div>", unsafe_allow_html=True)

    for idx, prompt_text in enumerate(suggested_queries):
        if st.button(prompt_text, key=f"derule_copilot_sugg_{idx}"):
            # Append user message
            st.session_state["copilot_history"].append({
                "role": "user",
                "content": prompt_text,
                "timestamp": datetime.now(timezone.utc),
            })
            # Query copilot
            res = facade.ask_copilot(
                query=prompt_text,
                current_machine_id=current_machine_id,
                current_investigation_id=current_investigation_id,
            )
            st.session_state["copilot_history"].append(res.to_dict())
            st.rerun()


def _render_message(msg: Any, idx: int) -> None:
    """Render single chat message with grounding and provenance metadata."""
    msg_dict = msg if isinstance(msg, dict) else msg.to_dict()
    role = msg_dict.get("role", "assistant")
    content = msg_dict.get("content", "")
    facts: List[str] = msg_dict.get("observed_facts", [])
    inferences: List[str] = msg_dict.get("inferences", [])
    unknowns: List[str] = msg_dict.get("unknowns", [])
    tools: List[str] = msg_dict.get("tools_consulted", [])
    prov: str = msg_dict.get("provenance", "DETERMINISTIC_FALLBACK")

    if role == "user":
        st.markdown(
            f"""
            <div style="background: var(--bg-card-subtle); border: 1px solid var(--border-subtle); border-radius: 8px; padding: 8px 12px; margin-bottom: 10px;">
                <div style="font-size: 10px; font-weight: 700; color: var(--primary-accent); text-transform: uppercase; margin-bottom: 2px;">
                    OPERATOR
                </div>
                <div style="font-size: 12px; color: var(--text-primary);">
                    {content}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        # Assistant Response Container
        st.markdown(
            f"""
            <div style="background: var(--bg-card); border: 1px solid var(--border-strong); border-radius: 8px; padding: 10px 14px; margin-bottom: 12px;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                    <span style="font-size: 10px; font-weight: 700; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em;">
                        DERULE INVESTIGATION COPILOT
                    </span>
                    <span class="badge {'badge-healthy' if prov == 'LIVE_CORTEX' else ('badge-critical' if prov == 'GOVERNANCE_GUARD' else 'badge-neutral')}" style="font-size: 9px; padding: 2px 6px;">
                        {prov}
                    </span>
                </div>
                <div style="font-size: 12px; color: var(--text-primary); line-height: 1.5; margin-bottom: 8px;">
                    {content}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Grounding Details (Observed Facts, Inferences, Unknowns)
        if facts or inferences or unknowns:
            with st.expander("Grounding & Analytical Breakdown", expanded=False):
                if facts:
                    st.markdown("<div style='font-size: 10px; font-weight: 700; color: #16a34a; margin-top: 4px;'>[OBSERVED FACTS]</div>", unsafe_allow_html=True)
                    for f in facts:
                        st.markdown(f"<div style='font-size: 11px; color: var(--text-secondary); margin-left: 8px;'>• {f}</div>", unsafe_allow_html=True)

                if inferences:
                    st.markdown("<div style='font-size: 10px; font-weight: 700; color: var(--primary-accent); margin-top: 8px;'>[INFERENCES & HYPOTHESES]</div>", unsafe_allow_html=True)
                    for inf in inferences:
                        st.markdown(f"<div style='font-size: 11px; color: var(--text-secondary); margin-left: 8px;'>• {inf}</div>", unsafe_allow_html=True)

                if unknowns:
                    st.markdown("<div style='font-size: 10px; font-weight: 700; color: #f59e0b; margin-top: 8px;'>[UNKNOWNS & LIMITATIONS]</div>", unsafe_allow_html=True)
                    for u in unknowns:
                        st.markdown(f"<div style='font-size: 11px; color: var(--text-muted); margin-left: 8px;'>• {u}</div>", unsafe_allow_html=True)

        # Tools Consulted Footer
        if tools:
            tools_badges = " ".join([f"<span class='badge badge-neutral' style='font-size: 9px; margin-right: 4px;'>{t}</span>" for t in tools])
            st.markdown(
                f"""
                <div style="display: flex; align-items: center; gap: 6px; margin-top: -6px; margin-bottom: 12px;">
                    <span style="font-size: 9px; color: var(--text-muted); text-transform: uppercase;">Tools:</span>
                    <div>{tools_badges}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
