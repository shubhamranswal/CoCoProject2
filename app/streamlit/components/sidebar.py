"""Global Sidebar Navigation and Demo Controls Component.

Follows Section 5 & 6 of DeRule Product Specification:
- Brand Anchor: Official DeRule logo asset, product name "DeRule", tagline "Detect. Investigate. Act"
- Theme Control: Segmented toggle control between Light and Dark
- Hierarchical Enterprise Navigation: MAIN, OPERATIONS, MAINTENANCE, INTELLIGENCE, SYSTEM
- Environment Indicator: SNOWFLAKE / LOCAL with connection status, DB, WH
- Explicit, isolated Developer/Demo controls
- Zero emojis across all navigation and controls
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable
import streamlit as st

from app.streamlit.state import navigate_to
from config import get_config


NAV_STRUCTURE = {
    "MAIN": ["Command Center"],
    "OPERATIONS": ["Production", "Alerts", "Downtime"],
    "MAINTENANCE": ["Maintenance", "Work Orders", "Inventory"],
    "INTELLIGENCE": ["Investigations", "Reliability", "Knowledge"],
    "SYSTEM": ["System Health", "Settings"],
}


def _is_nav_active(item: str, current_nav: str) -> bool:
    """Evaluate if nav item is active, supporting canonical and legacy aliases."""
    if current_nav == item:
        return True
    aliases = {
        "Production": ["Assets", "Production"],
        "Investigations": ["AI Investigations", "Investigations"],
        "Downtime": ["OEE", "Downtime"],
        "System Health": ["Data & Pipelines", "System Health"],
        "Alerts": ["Alerts"],
        "Inventory": ["Inventory"],
    }
    return current_nav in aliases.get(item, [])


def render_sidebar(
    backend_mode: str,
    on_backend_change: Callable[[str], None],
    on_run_degradation: Callable[[], None],
    on_run_investigation: Callable[[], None],
    on_reset_demo: Callable[[], None],
) -> str:
    """Render the DeRule enterprise sidebar."""
    with st.sidebar:
        current_theme = st.session_state.get("theme_mode", "light")
        cfg = get_config()

        # 1. Official DeRule Logo & Branding Hierarchy
        logo_filename = "dark.png" if current_theme == "dark" else "light.png"
        root_path = Path(__file__).resolve().parent.parent.parent.parent
        logo_path = root_path / "logo" / logo_filename
        if not logo_path.exists():
            logo_path = Path("logo") / logo_filename

        if logo_path.exists():
            st.image(str(logo_path), width=42)

        st.markdown(
            """
            <div class="derule-sidebar-brand" style="padding: 4px 0 8px 0; margin-top: -2px; margin-bottom: 8px;">
                <div style="font-size: 18px; font-weight: 700; color: var(--text-primary); letter-spacing: -0.02em; line-height: 1.1;">
                    DeRule
                </div>
                <div style="font-size: 10px; font-weight: 600; color: var(--primary-accent); letter-spacing: 0.06em; text-transform: uppercase; margin-top: 2px;">
                    Detect. Investigate. Act
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # 2. Native Segmented Theme Toggle Control
        selected_theme = st.segmented_control(
            "Interface Theme:",
            options=["Light", "Dark"],
            default="Light" if current_theme == "light" else "Dark",
            key="sidebar_theme_selector",
            label_visibility="collapsed",
        )
        if selected_theme and selected_theme.lower() != current_theme:
            st.session_state.theme_mode = selected_theme.lower()
            st.rerun()

        st.markdown("<hr style='border: none; border-bottom: 1px solid var(--border-subtle); margin: 10px 0 8px 0;'/>", unsafe_allow_html=True)

        current_nav = st.session_state.get("active_nav", "Command Center")

        # 3. Enterprise Navigation Hierarchy
        for section, items in NAV_STRUCTURE.items():
            st.markdown(
                f"<div style='font-size: 10px; font-weight: 700; color: var(--text-muted); letter-spacing: 0.08em; "
                f"margin-top: 10px; margin-bottom: 4px; text-transform: uppercase;'>{section}</div>",
                unsafe_allow_html=True,
            )

            for item in items:
                is_selected = _is_nav_active(item, current_nav)
                btn_type = "primary" if is_selected else "secondary"

                if st.button(
                    item,
                    key=f"nav_btn_{item}",
                    type=btn_type,
                    use_container_width=True,
                ):
                    navigate_to(item)
                    st.rerun()

        st.markdown("<hr style='border: none; border-bottom: 1px solid var(--border-subtle); margin: 12px 0;'/>", unsafe_allow_html=True)

        # 4. Operational Plant Context
        st.markdown("<div style='font-size: 10px; font-weight: 700; color: var(--text-muted); letter-spacing: 0.08em; text-transform: uppercase; margin-bottom: 4px;'>OPERATIONAL SCOPE</div>", unsafe_allow_html=True)
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

        # 5. Environment & Storage Indicator
        st.markdown("<div style='font-size: 10px; font-weight: 700; color: var(--text-muted); letter-spacing: 0.08em; text-transform: uppercase; margin-top: 8px; margin-bottom: 6px;'>ENVIRONMENT & ENGINE</div>", unsafe_allow_html=True)
        
        if backend_mode == "snowflake":
            st.markdown(
                f"""
                <div class="ind-card" style="padding: 8px 10px; margin-bottom: 6px;">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <span style="font-size: 11px; font-weight: 700; color: var(--text-primary); letter-spacing: 0.04em;">SNOWFLAKE</span>
                        <span class="badge badge-healthy" style="font-size: 9px;"><span class="status-dot status-dot-healthy"></span>Connected</span>
                    </div>
                    <div style="font-size: 10px; color: var(--text-muted); margin-top: 3px;">
                        DB: <code>{cfg.snowflake.database or 'COCO_FACTORY'}</code> &nbsp;|&nbsp; WH: <code>{cfg.snowflake.warehouse or 'COMPUTE_WH'}</code>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                """
                <div class="ind-card" style="padding: 8px 10px; margin-bottom: 6px;">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <span style="font-size: 11px; font-weight: 700; color: var(--text-primary); letter-spacing: 0.04em;">LOCAL STORE</span>
                        <span class="badge badge-info" style="font-size: 9px;"><span class="status-dot status-dot-info"></span>In-Memory</span>
                    </div>
                    <div style="font-size: 10px; color: var(--text-muted); margin-top: 3px;">
                        Deterministic Seeded Store
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        # 6. Developer Controls (Isolated)
        with st.expander("Developer Controls", expanded=False):
            st.caption("Active Storage Tier:")
            selected_backend = st.selectbox(
                "Storage Backend",
                options=["snowflake", "in_memory"],
                index=0 if backend_mode == "snowflake" else 1,
                format_func=lambda x: "Snowflake Cloud" if x == "snowflake" else "In-Memory (Deterministic)",
                key="sidebar_backend_select",
                label_visibility="collapsed",
            )
            if selected_backend != backend_mode:
                on_backend_change(selected_backend)
                st.rerun()

            st.markdown("<hr style='border: none; border-bottom: 1px solid var(--border-subtle); margin: 8px 0;'/>", unsafe_allow_html=True)
            st.caption("Diagnostic Simulation:")
            if st.button("Simulate Asset Wear Precursor", use_container_width=True, help="Trigger bearing wear telemetry"):
                on_run_degradation()
                st.session_state.scenario_stage = "INITIALIZED"
                st.success("Telemetry precursor ingested.")
                st.rerun()

            if st.button("Trigger Investigation Agent", use_container_width=True, help="Dispatch agent on open alert"):
                on_run_investigation()
                st.session_state.scenario_stage = "INVESTIGATED"
                st.success("Investigation agent completed analysis.")
                st.rerun()

            if st.button("Reset Environment to Baseline", use_container_width=True, help="Restore clean baseline state"):
                on_reset_demo()
                st.session_state.scenario_stage = "INITIALIZED"
                st.info("Environment reset to clean baseline.")
                st.rerun()

        st.caption("DeRule Enterprise v1.2.0-prod")
        return current_nav
