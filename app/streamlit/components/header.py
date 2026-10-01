"""Top Bar and Application Header Component.

Follows Section 8 of AGENT.md:
- Plant 01 context
- Global search field across known domain entities
- System status and active operator indicator
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, Dict, List
import streamlit as st

from app.streamlit.state import navigate_to


def render_header(
    on_search: Callable[[str], List[Dict[str, Any]]],
    backend_mode: str,
    freshness: Any = None,
) -> None:
    """Render the global industrial command center header bar."""
    col_title, col_ctx, col_search, col_status = st.columns([3, 2, 3, 2])

    with col_title:
        st.markdown(
            """
            <div style="display: flex; align-items: center; gap: 8px;">
                <span style="font-size: 22px;">🏭</span>
                <div>
                    <div style="font-size: 17px; font-weight: 800; color: #f8fafc; letter-spacing: -0.02em;">
                        FACTORY RELIABILITY COMMAND CENTER
                    </div>
                    <div style="font-size: 11px; color: #94a3b8; letter-spacing: 0.04em; text-transform: uppercase;">
                        Autonomous Reliability & Closed-Loop Operations
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col_ctx:
        plant_val = st.session_state.get("selected_plant_id", "PLANT-01")
        line_val = st.session_state.get("selected_line_id", "ALL")
        st.markdown(
            f"""
            <div style="font-size: 12px; color: #cbd5e1; padding-top: 4px;">
                📍 <b>Plant 01</b> (Pune Packaging) &nbsp;|&nbsp; Line: <b>{line_val}</b>
            </div>
            <div style="font-size: 11px; color: #64748b;">
                Operator: <code>{st.session_state.get("active_user", "operator.sarah")}</code>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col_search:
        search_query = st.text_input(
            "Global Search",
            value=st.session_state.get("search_query", ""),
            placeholder="Search M204, bearing, alert, WO-...",
            label_visibility="collapsed",
            key="global_search_input",
        )
        if search_query:
            st.session_state.search_query = search_query

    with col_status:
        now_str = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")
        is_snowflake = (backend_mode == "snowflake")
        backend_badge = (
            "<span class='badge badge-info' style='background: #0284c7; color: white;'>LIVE DATA • SNOWFLAKE</span>"
            if is_snowflake
            else "<span class='badge badge-neutral' style='background: #334155; color: #94a3b8;'>DEMO MODE • IN-MEMORY</span>"
        )
        freshness_label = f"Freshness: {freshness.display_age}" if freshness else "Freshness: <1.5s"
        st.markdown(
            f"""
            <div style="text-align: right; font-size: 11px; padding-top: 2px;">
                <span style="color: #22c55e;">●</span> <b>ONLINE</b> &nbsp;•&nbsp; <span style="color: #38bdf8;">{freshness_label}</span><br>
                <div style="margin-top: 2px;">{backend_badge}</div>
                <span style="color: #64748b; font-size: 10px;">Clock: {now_str}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("<hr style='border: none; border-bottom: 1px solid #1f2430; margin: 8px 0 16px 0;'/>", unsafe_allow_html=True)

    # If search has active query, show deterministic search dropdown results
    if st.session_state.get("search_query"):
        results = on_search(st.session_state.search_query)
        if results:
            with st.expander(f"🔍 Search Results for '{st.session_state.search_query}' ({len(results)} matches)", expanded=True):
                for res in results:
                    r_col1, r_col2 = st.columns([4, 1])
                    with r_col1:
                        st.markdown(f"**[{res['type']}]** {res['title']}")
                        st.caption(res["subtitle"])
                    with r_col2:
                        if st.button("Open", key=f"search_btn_{res['type']}_{res['id']}"):
                            navigate_to(res["nav_view"], **res["nav_param"])
                            st.session_state.search_query = ""
                            st.rerun()
        else:
            st.info(f"No entities matching '{st.session_state.search_query}' found.")
