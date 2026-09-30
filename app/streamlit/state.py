"""Centralized session state management for Streamlit application.

Follows AGENT.md:
- Session state manages UI navigation and selections only
- Operational state belongs strictly in the backend repository
"""

from __future__ import annotations

from typing import Any, Dict, Optional
import streamlit as st


def init_session_state() -> None:
    """Initialize default session state keys if not already present."""
    defaults: Dict[str, Any] = {
        "active_nav": "Command Center",
        "selected_machine_id": "M204",
        "selected_investigation_id": None,
        "selected_work_order_id": None,
        "search_query": "",
        "active_user": "operator.sarah",
        "selected_plant_id": "PLANT-01",
        "selected_line_id": "ALL",
        "last_action_message": None,
        "scenario_stage": "INITIALIZED",  # INITIALIZED, INVESTIGATED, APPROVED, WORK_ORDER_CREATED, COMPLETED, VERIFIED
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


def navigate_to(
    view_name: str,
    machine_id: Optional[str] = None,
    investigation_id: Optional[str] = None,
    work_order_id: Optional[str] = None,
) -> None:
    """Navigate to a specific view and optionally select an entity."""
    st.session_state.active_nav = view_name
    if machine_id:
        st.session_state.selected_machine_id = machine_id
    if investigation_id:
        st.session_state.selected_investigation_id = investigation_id
    if work_order_id:
        st.session_state.selected_work_order_id = work_order_id
