"""Command Center View — Primary Hero Operational Screen.

Follows Section 12 of DeRule Product Specification:
- Header: DeRule Command Center, "Detect. Investigate. Act", Environment, System Status
- KEY SIGNALS: Critical Alerts, Machines At Risk, Open Work Orders, Production Exposure
- RELIABILITY OVERVIEW: Fleet OEE, Availability, Performance, Quality
- ACTIVE INVESTIGATIONS: High-signal case cards with confidence & evidence counts
- PRODUCTION / RELIABILITY SIGNALS: Asset Health Grid and Critical Failure Precursors
- Zero emojis and clean enterprise styling
"""

from __future__ import annotations

from typing import Any
import streamlit as st

from app.streamlit.components import (
    render_alert_card,
    render_asset_grid_table,
    render_critical_alert_card,
    render_kpi_row,
)
from app.streamlit.components.metric_cards import render_key_signals, render_reliability_overview
from app.streamlit.services.view_service import CommandCenterFacade
from app.streamlit.state import navigate_to
from config import get_config


def render_command_center_view(facade: CommandCenterFacade) -> None:
    """Render the primary operational command center screen."""
    cfg = get_config()
    backend_mode = st.session_state.get("backend_mode", "snowflake")
    env_name = "SNOWFLAKE" if backend_mode == "snowflake" else "LOCAL (IN-MEMORY)"

    # 1. Header & Operational Status
    st.markdown(
        f"""
        <div style="margin-bottom: 16px;">
            <div style="display: flex; justify-content: space-between; align-items: flex-end; flex-wrap: wrap; gap: 8px;">
                <div>
                    <div style="font-size: 20px; font-weight: 700; color: var(--text-primary); letter-spacing: -0.02em; line-height: 1.1;">
                        Command Center
                    </div>
                    <div style="font-size: 11px; font-weight: 500; color: var(--text-muted); margin-top: 3px;">
                        Factory Reliability & Operations Intelligence
                    </div>
                </div>
                <div style="font-size: 11px; color: var(--text-muted); text-align: right;">
                    <span>Environment: <b>{env_name}</b></span> &nbsp;|&nbsp;
                    <span>System Status: <span class="status-dot status-dot-healthy"></span><b>Connected</b></span>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    kpis = facade.get_kpis()

    # 2. Key Signals Section
    st.markdown(
        """
        <div style="font-size: 11px; font-weight: 700; color: var(--text-muted); letter-spacing: 0.08em; text-transform: uppercase; margin-bottom: 6px;">
            Key Operational Signals
        </div>
        """,
        unsafe_allow_html=True,
    )
    render_key_signals(kpis)

    st.markdown("<hr style='border: none; border-bottom: 1px solid var(--border-subtle); margin: 14px 0;'/>", unsafe_allow_html=True)

    # 3. Reliability Overview Section
    st.markdown(
        """
        <div style="font-size: 11px; font-weight: 700; color: var(--text-muted); letter-spacing: 0.08em; text-transform: uppercase; margin-bottom: 6px;">
            Reliability Overview
        </div>
        """,
        unsafe_allow_html=True,
    )
    render_reliability_overview(kpis)

    st.markdown("<hr style='border: none; border-bottom: 1px solid var(--border-subtle); margin: 14px 0;'/>", unsafe_allow_html=True)

    # 4. Critical Active Failure Precursors (Hero Alert Card)
    st.markdown(
        """
        <div style="font-size: 11px; font-weight: 700; color: #dc2626; letter-spacing: 0.08em; text-transform: uppercase; margin-bottom: 8px;">
            Active Failure Precursors & Threat Identification
        </div>
        """,
        unsafe_allow_html=True,
    )
    critical_events = facade.get_critical_events()
    if critical_events:
        for ev in critical_events:
            render_critical_alert_card(ev)
    else:
        st.markdown(
            """
            <div class="ind-card" style="padding: 14px 18px; border-left: 3px solid #16a34a; display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                <div style="display: flex; align-items: center; gap: 10px;">
                    <span class="status-dot status-dot-healthy"></span>
                    <div>
                        <div style="font-size: 12px; font-weight: 600; color: var(--text-primary);">
                            No Active Failure Precursors
                        </div>
                        <div style="font-size: 11px; color: var(--text-muted); margin-top: 1px;">
                            DeRule is not currently detecting additional machine-level failure precursors across monitored streams.
                        </div>
                    </div>
                </div>
                <span class="badge badge-healthy">ALL NOMINAL</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("<hr style='border: none; border-bottom: 1px solid var(--border-subtle); margin: 16px 0;'/>", unsafe_allow_html=True)

    # 5. Two-Column Layout: Fleet Asset Health Grid & Active Investigations
    col_grid, col_inv = st.columns([3, 2])

    with col_grid:
        st.markdown(
            """
            <div style="font-size: 11px; font-weight: 700; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 8px;">
                Fleet Asset Health Status
            </div>
            """,
            unsafe_allow_html=True,
        )
        line_filter = st.session_state.get("selected_line_id", "ALL")
        asset_grid = facade.get_asset_grid(line_id=line_filter)
        render_asset_grid_table(
            asset_grid=asset_grid,
            on_select_machine=lambda m_id: navigate_to("Assets", machine_id=m_id),
        )

    with col_inv:
        st.markdown(
            """
            <div style="font-size: 11px; font-weight: 700; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 8px;">
                Active Investigations & Cases
            </div>
            """,
            unsafe_allow_html=True,
        )
        investigations = facade.get_investigations()
        if investigations:
            for inv in investigations[:5]:
                confidence_pct = inv.confidence * 100 if inv.confidence else 92.0
                st_color = "#d97706" if inv.status.value == "PENDING_APPROVAL" else ("#16a34a" if inv.status.value == "CLOSED" else "#0284c7")
                fm_str = inv.failure_mode.value.replace('_', ' ') if hasattr(inv.failure_mode, "value") else str(inv.failure_mode).replace('_', ' ')
                st.markdown(
                    f"""
                    <div class="ind-card">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <div>
                                <span style="font-size: 12px; font-weight: 700; color: var(--primary-accent);">{inv.investigation_id}</span>
                                <span class="badge badge-neutral" style="margin-left: 6px;">{inv.machine_id}</span>
                            </div>
                            <div style="font-size: 11px; font-weight: 700; color: {st_color};">
                                {inv.status.value}
                            </div>
                        </div>
                        <div style="font-size: 13px; font-weight: 600; color: var(--text-primary); margin-top: 6px;">
                            {fm_str}
                        </div>
                        <div style="font-size: 11px; color: var(--text-muted); margin-top: 2px;">
                            Confidence: <b>{confidence_pct:.0f}%</b> &nbsp;|&nbsp; Evidence: <b>{len(inv.evidence)} items</b>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                if st.button("Open Investigation Workspace", key=f"inv_open_{inv.investigation_id}", use_container_width=True):
                    navigate_to("AI Investigations", machine_id=inv.machine_id, investigation_id=inv.investigation_id)
                    st.rerun()
        else:
            st.info("No investigations active.")
