"""Factory Reliability Command Center — Streamlit Production Application.

Follows AGENT.md & architecture/architecture.md:
- Fully deterministic presentation shell connecting to governed backend services
- Real industrial dark theme, high information density, evidence-first layout
- Zero raw SQL executed in Streamlit
- Zero fake metrics or hardcoded states
- Complete operational lifecycle: Alerts → Agent Investigation → Human Approval → Work Order → Verification
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add project root directory to sys.path
file_path = Path(__file__).resolve()
repo_root = str(file_path.parent.parent.parent) if file_path.parent.name == "streamlit" else str(file_path.parent.parent)
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

import streamlit as st

from app.streamlit.components.header import render_header
from app.streamlit.components.sidebar import render_sidebar
from app.streamlit.components.styles import apply_industrial_theme
from app.streamlit.services.view_service import get_facade
from app.streamlit.state import init_session_state, navigate_to
from app.streamlit.views import (
    render_agent_activity_view,
    render_assets_view,
    render_command_center_view,
    render_investigations_view,
    render_knowledge_view,
    render_maintenance_view,
    render_oee_view,
    render_pipelines_view,
    render_quality_view,
    render_reliability_view,
    render_settings_view,
    render_work_orders_view,
)
from domain.enums import AlertStatus
from domain.exceptions import RepositoryUnavailableError

def main() -> None:
    # 1. Page Configuration
    try:
        st.set_page_config(
            page_title="Factory Reliability Command Center",
            page_icon="🏭",
            layout="wide",
            initial_sidebar_state="expanded",
        )
    except Exception:
        pass

    # 2. Apply Custom Industrial Dark Theme
    apply_industrial_theme()

    # 3. Initialize Session State
    init_session_state()

    # 4. Storage Backend Selection & Facade Instantiation
    if "backend_mode" not in st.session_state:
        st.session_state.backend_mode = "in_memory"

    backend_error = None
    facade = None
    try:
        facade = get_facade(backend_mode=st.session_state.backend_mode)
    except RepositoryUnavailableError as exc:
        backend_error = str(exc)

    # 5. Sidebar Callbacks
    def handle_backend_change(new_mode: str) -> None:
        st.session_state.backend_mode = new_mode
        # Clear cache to instantiate new facade for backend
        st.cache_resource.clear()

    def handle_run_degradation() -> None:
        if facade:
            facade.run_m204_degradation_pipeline()
            st.session_state.scenario_stage = "DEGRADED"
            navigate_to("Command Center", machine_id="M204")

    def handle_run_investigation() -> None:
        if facade:
            alerts = facade.repo.list_alerts(machine_id="M204", status=AlertStatus.OPEN)
            if alerts:
                res = facade.run_reliability_investigation(alerts[0].alert_id)
                st.session_state.selected_investigation_id = res.investigation.investigation_id
                st.session_state.scenario_stage = "INVESTIGATED"
                navigate_to("AI Investigations", machine_id="M204", investigation_id=res.investigation.investigation_id)

    def handle_reset_demo() -> None:
        if facade:
            facade.reset_demo(seed_degradation=False)
            st.session_state.scenario_stage = "HEALTHY"
            st.session_state.selected_investigation_id = None
            st.session_state.selected_work_order_id = None
            navigate_to("Command Center", machine_id="M204")

    # 6. Sidebar Navigation & Demo Controls
    render_sidebar(
        backend_mode=st.session_state.backend_mode,
        on_backend_change=handle_backend_change,
        on_run_degradation=handle_run_degradation,
        on_run_investigation=handle_run_investigation,
        on_reset_demo=handle_reset_demo,
    )

    # 7. Error Banner if Backend Unavailable (Strict No Silent Fallback)
    if backend_error or facade is None:
        st.markdown(
            """
            <div style="background: #1e1014; border: 1px solid #ef4444; border-radius: 8px; padding: 20px; margin-top: 10px;">
                <div style="display: flex; align-items: center; gap: 10px;">
                    <span style="font-size: 24px;">🚫</span>
                    <div>
                        <div style="font-size: 16px; font-weight: 800; color: #fca5a5;">
                            STORAGE BACKEND UNAVAILABLE: SNOWFLAKE CLOUD
                        </div>
                        <div style="font-size: 12px; color: #94a3b8; margin-top: 4px;">
                            The application is configured to run in <code>LIVE DATA • SNOWFLAKE</code> mode, but a connection to Snowflake could not be established.
                        </div>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.error(f"Connection Diagnostic: {backend_error}")
        st.markdown(
            """
            **Operational Safety Guardrail**:
            To prevent misleading operations, silent fallback to in-memory mock data is strictly disabled.
            You can verify your Snowflake environment credentials in `.env`, or explicitly switch to deterministic in-memory demo mode below.
            """
        )
        col_err1, col_err2 = st.columns(2)
        with col_err1:
            if st.button("🔄 Retry Snowflake Connection", type="primary", use_container_width=True):
                st.cache_resource.clear()
                st.rerun()
        with col_err2:
            if st.button("🔵 Switch to Demo Mode (In-Memory)", use_container_width=True):
                st.session_state.backend_mode = "in_memory"
                st.cache_resource.clear()
                st.rerun()
        st.stop()

    # 8. Global Header
    freshness = facade.get_data_freshness() if facade else None
    render_header(
        on_search=facade.search_entities,
        backend_mode=st.session_state.backend_mode,
        freshness=freshness,
    )

    st.markdown("<hr style='border: none; border-bottom: 1px solid #1f2430; margin: 8px 0 16px 0;'/>", unsafe_allow_html=True)

    # 8. View Router
    active_view = st.session_state.get("active_nav", "Command Center")

    if active_view == "Command Center":
        render_command_center_view(facade)
    elif active_view == "Assets":
        render_assets_view(facade)
    elif active_view == "Reliability":
        render_reliability_view(facade)
    elif active_view == "OEE":
        render_oee_view(facade)
    elif active_view == "Quality":
        render_quality_view(facade)
    elif active_view == "Maintenance":
        render_maintenance_view(facade)
    elif active_view == "Work Orders":
        render_work_orders_view(facade)
    elif active_view == "AI Investigations":
        render_investigations_view(facade)
    elif active_view == "Knowledge":
        render_knowledge_view(facade)
    elif active_view == "Agent Activity":
        render_agent_activity_view(facade)
    elif active_view == "Data & Pipelines":
        render_pipelines_view(facade)
    elif active_view == "Settings":
        render_settings_view(facade)
    else:
        render_command_center_view(facade)

    # 9. Global Footer
    st.markdown("<hr style='border: none; border-bottom: 1px solid #1f2430; margin: 30px 0 12px 0;'/>", unsafe_allow_html=True)
    col_foot_left, col_foot_right = st.columns([2, 1])
    with col_foot_left:
        st.caption("Factory Reliability Command Center — Deterministic Closed-Loop Architecture | Built for Industrial Operations")
    with col_foot_right:
        backend_label = "Snowflake Cloud Gov" if st.session_state.backend_mode == "snowflake" else "In-Memory Seeded Store"
        st.caption(f"Status: **ONLINE** | Backend: `{backend_label}` | Version: `v1.2.0`")


if __name__ == "__main__":
    main()

