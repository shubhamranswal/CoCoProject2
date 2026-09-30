"""Command Center View — Primary Hero Operational Screen.

Follows Section 9 of AGENT.md:
- Live plant operational status
- High-level KPIs
- Hero Critical Event card (M204 Bearing Degradation)
- Asset Health status grid
- Active investigations summary
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
from app.streamlit.services.view_service import CommandCenterFacade
from app.streamlit.state import navigate_to


def render_command_center_view(facade: CommandCenterFacade) -> None:
    """Render the primary operational command center screen."""
    st.markdown(
        """
        <div style="margin-bottom: 14px;">
            <div style="font-size: 20px; font-weight: 800; color: #f8fafc; letter-spacing: -0.02em;">
                LIVE RELIABILITY OPERATIONS
            </div>
            <div style="font-size: 12px; color: #94a3b8;">
                Real-time operational health, active failure precursors, and autonomous reliability investigations.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # 1. KPI Row
    kpis = facade.get_kpis()
    render_kpi_row(kpis)

    st.markdown("<hr style='border: none; border-bottom: 1px solid #1f2430; margin: 14px 0;'/>", unsafe_allow_html=True)

    # 2. Critical Events (Hero M204 Alert Card)
    st.markdown(
        """
        <div style="font-size: 14px; font-weight: 800; color: #ef4444; letter-spacing: 0.04em; text-transform: uppercase; margin-bottom: 8px;">
            🚨 Critical Active Failure Precursors
        </div>
        """,
        unsafe_allow_html=True,
    )
    critical_events = facade.get_critical_events()
    if critical_events:
        for ev in critical_events:
            render_critical_alert_card(ev)
    else:
        st.success("🟢 No critical operational alerts currently active across fleet.")

    st.markdown("<hr style='border: none; border-bottom: 1px solid #1f2430; margin: 16px 0;'/>", unsafe_allow_html=True)

    # 3. Two-Column Layout: Asset Health Grid & Active Investigations
    col_grid, col_inv = st.columns([3, 2])

    with col_grid:
        line_filter = st.session_state.get("selected_line_id", "ALL")
        asset_grid = facade.get_asset_grid(line_id=line_filter)
        render_asset_grid_table(
            asset_grid=asset_grid,
            on_select_machine=lambda m_id: navigate_to("Assets", machine_id=m_id),
        )

    with col_inv:
        st.markdown(
            """
            <div style="font-size: 13px; font-weight: 700; color: #f8fafc; text-transform: uppercase; margin-bottom: 8px;">
                🧠 Active Investigations & Cases
            </div>
            """,
            unsafe_allow_html=True,
        )
        investigations = facade.get_investigations()
        if investigations:
            for inv in investigations[:5]:
                confidence_pct = inv.confidence * 100 if inv.confidence else 92.0
                st_color = "#f59e0b" if inv.status.value == "PENDING_APPROVAL" else ("#10b981" if inv.status.value == "CLOSED" else "#3b82f6")
                st.markdown(
                    f"""
                    <div class="ind-card">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <div>
                                <span style="font-size: 12px; font-weight: 700; color: #38bdf8;">{inv.investigation_id}</span>
                                <span class="badge badge-neutral" style="margin-left: 6px;">{inv.machine_id}</span>
                            </div>
                            <div style="font-size: 11px; font-weight: 700; color: {st_color};">
                                {inv.status.value}
                            </div>
                        </div>
                        <div style="font-size: 12px; font-weight: 600; color: #f8fafc; margin-top: 6px;">
                            {inv.failure_mode.value.replace('_', ' ')}
                        </div>
                        <div style="font-size: 11px; color: #94a3b8; margin-top: 2px;">
                            Confidence: <b>{confidence_pct:.0f}%</b> &nbsp;|&nbsp; Evidence: <b>{len(inv.evidence)} items</b>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                if st.button("Open Workspace", key=f"inv_open_{inv.investigation_id}", use_container_width=True):
                    navigate_to("AI Investigations", machine_id=inv.machine_id, investigation_id=inv.investigation_id)
                    st.rerun()
        else:
            st.info("No investigations active.")
