"""Global Sidebar Navigation and Demo Controls Component.

Follows Section 7 & 42 of AGENT.md:
- Structured hierarchical navigation
- Plant & Line filtering
- Real backend badge (Snowflake vs In-Memory Demo)
- Explicit, isolated Developer/Demo controls
"""

from __future__ import annotations

from typing import Callable
import streamlit as st

from app.streamlit.state import navigate_to


NAV_STRUCTURE = {
    "MAIN": ["Command Center"],
    "OPERATIONS": ["Assets", "Reliability", "OEE", "Quality"],
    "MAINTENANCE": ["Maintenance", "Work Orders"],
    "INTELLIGENCE": ["AI Investigations", "Knowledge", "Agent Activity"],
    "SYSTEM": ["Data & Pipelines", "Settings"],
}

NAV_ICONS = {
    "Command Center": "🧭",
    "Assets": "⚙️",
    "Reliability": "📈",
    "OEE": "📊",
    "Quality": "🔬",
    "Maintenance": "🛠️",
    "Work Orders": "📋",
    "AI Investigations": "🧠",
    "Knowledge": "📖",
    "Agent Activity": "🤖",
    "Data & Pipelines": "🔀",
    "Settings": "⚙️",
}


def render_sidebar(
    backend_mode: str,
    on_backend_change: Callable[[str], None],
    on_run_degradation: Callable[[], None],
    on_run_investigation: Callable[[], None],
    on_reset_demo: Callable[[], None],
) -> str:
    """Render the industrial application sidebar."""
    with st.sidebar:
        st.markdown(
            """
            <div style="padding: 10px 0 16px 0;">
                <div style="font-size: 13px; font-weight: 800; color: #38bdf8; letter-spacing: 0.08em; text-transform: uppercase;">
                    FACTORY RELIABILITY
                </div>
                <div style="font-size: 18px; font-weight: 800; color: #f8fafc; letter-spacing: -0.02em;">
                    COMMAND CENTER
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        current_nav = st.session_state.get("active_nav", "Command Center")

        # Navigation Groups
        for section, items in NAV_STRUCTURE.items():
            if section != "MAIN":
                st.markdown(
                    f"<div style='font-size: 10px; font-weight: 700; color: #64748b; letter-spacing: 0.08em; "
                    f"margin-top: 14px; margin-bottom: 4px; text-transform: uppercase;'>{section}</div>",
                    unsafe_allow_html=True,
                )

            for item in items:
                icon = NAV_ICONS.get(item, "•")
                is_selected = (current_nav == item)
                btn_type = "primary" if is_selected else "secondary"

                if st.button(
                    f"{icon}  {item}",
                    key=f"nav_btn_{item}",
                    type=btn_type,
                    use_container_width=True,
                ):
                    navigate_to(item)
                    st.rerun()

        st.markdown("<hr style='border: none; border-bottom: 1px solid #1f2430; margin: 16px 0;'/>", unsafe_allow_html=True)

        # Plant Context Filter
        st.markdown("<div style='font-size: 11px; font-weight: 700; color: #94a3b8; margin-bottom: 4px;'>OPERATIONAL SCOPE</div>", unsafe_allow_html=True)
        col_p, col_l = st.columns(2)
        with col_p:
            st.selectbox("Plant:", ["PLANT-01"], index=0, key="plant_selector", disabled=True)
        with col_l:
            line_options = ["ALL", "LINE-A", "LINE-B", "LINE-C"]
            cur_line = st.session_state.get("selected_line_id", "ALL")
            chosen_line = st.selectbox("Line:", line_options, index=line_options.index(cur_line) if cur_line in line_options else 0, key="line_selector")
            if chosen_line != st.session_state.get("selected_line_id"):
                st.session_state.selected_line_id = chosen_line
                st.rerun()

        # Backend Storage Status
        st.markdown("<div style='font-size: 11px; font-weight: 700; color: #94a3b8; margin-top: 10px; margin-bottom: 4px;'>STORAGE ENGINE</div>", unsafe_allow_html=True)
        selected_backend = st.radio(
            "Active Storage:",
            options=["in_memory", "snowflake"],
            index=0 if backend_mode == "in_memory" else 1,
            format_func=lambda x: "In-Memory (Deterministic)" if x == "in_memory" else "Snowflake Cloud",
            label_visibility="collapsed",
            key="sidebar_backend_radio",
        )
        if selected_backend != backend_mode:
            on_backend_change(selected_backend)
            st.rerun()

        if backend_mode == "snowflake":
            st.caption("🟢 Connected to Snowflake Gov. Schemas")
        else:
            st.caption("🔵 Running In-Memory Seeded Store")

        # Developer / Demo Controls (Isolated)
        with st.expander("🛠️ Demo Controls", expanded=False):
            st.caption("Golden Path Developer Controls (Isolated to local store):")
            if st.button("Simulate M204 Degradation", use_container_width=True, help="Trigger bearing wear telemetry"):
                on_run_degradation()
                st.session_state.scenario_stage = "INITIALIZED"
                st.success("M204 Degradation telemetry ingested.")
                st.rerun()

            if st.button("Trigger Investigation Agent", use_container_width=True, help="Dispatch agent on open alert"):
                on_run_investigation()
                st.session_state.scenario_stage = "INVESTIGATED"
                st.success("Reliability Agent completed investigation.")
                st.rerun()

            if st.button("Reset Demo to Baseline", use_container_width=True, help="Restore clean baseline state"):
                on_reset_demo()
                st.session_state.scenario_stage = "INITIALIZED"
                st.info("Demo state reset to clean baseline.")
                st.rerun()

        st.caption("Factory Reliability v1.2.0-prod")
        return current_nav
