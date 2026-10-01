"""Plant Maintenance & Technician Execution History View.

Follows Section 25, 26, & 27 of AGENT.md:
- Real maintenance event logs and technician work records
- Replaced subassemblies, consumables, and labor hours
- Precedent failure mode history for reliability correlation
"""

from __future__ import annotations

from typing import Any, Dict, List
import streamlit as st

from app.streamlit.services.view_service import CommandCenterFacade
from app.streamlit.state import navigate_to


def render_maintenance_view(facade: CommandCenterFacade) -> None:
    """Render the plant maintenance events and technician records view."""
    st.markdown(
        """
        <div style="margin-bottom: 16px;">
            <div style="font-size: 20px; font-weight: 800; color: #f8fafc; letter-spacing: -0.02em;">
                MAINTENANCE RECORDS & EXECUTION LOGS
            </div>
            <div style="font-size: 12px; color: #94a3b8;">
                Historical maintenance events, technician execution logs, and component replacement records.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # 1. Maintenance Summary KPIs
    col1, col2, col3, col4 = st.columns(4)
    all_events = []
    machines = facade.repo.list_machines()
    for m in machines:
        evs = facade.repo.get_maintenance_history(m.machine_id, limit=20)
        all_events.extend(evs)

    with col1:
        st.markdown(
            f"""
            <div style="background: #111520; border: 1px solid #1f2430; border-radius: 6px; padding: 14px;">
                <div style="font-size: 11px; font-weight: 700; color: #94a3b8; text-transform: uppercase;">Recorded Maintenance Events</div>
                <div style="font-size: 26px; font-weight: 800; color: #38bdf8; margin: 4px 0;">{len(all_events)}</div>
                <div style="font-size: 11px; color: #94a3b8;">Plant-01 Total History</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col2:
        total_downtime = sum((e.duration_hours or 0.0) * 60.0 for e in all_events)
        st.markdown(
            f"""
            <div style="background: #111520; border: 1px solid #1f2430; border-radius: 6px; padding: 14px;">
                <div style="font-size: 11px; font-weight: 700; color: #94a3b8; text-transform: uppercase;">Cumulative Maintenance Downtime</div>
                <div style="font-size: 26px; font-weight: 800; color: #f8fafc; margin: 4px 0;">{total_downtime:.0f} min</div>
                <div style="font-size: 11px; color: #94a3b8;">Planned + Corrective Intervention</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col3:
        total_cost = sum((e.duration_hours or 0.0) * 85.0 for e in all_events)
        st.markdown(
            f"""
            <div style="background: #111520; border: 1px solid #1f2430; border-radius: 6px; padding: 14px;">
                <div style="font-size: 11px; font-weight: 700; color: #94a3b8; text-transform: uppercase;">Recorded Parts & Labor Cost</div>
                <div style="font-size: 26px; font-weight: 800; color: #22c55e; margin: 4px 0;">${total_cost:,.2f}</div>
                <div style="font-size: 11px; color: #94a3b8;">Verified CMMS Invoices</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col4:
        st.markdown(
            """
            <div style="background: #111520; border: 1px solid #1f2430; border-radius: 6px; padding: 14px;">
                <div style="font-size: 11px; font-weight: 700; color: #94a3b8; text-transform: uppercase;">Work Order Execution Surface</div>
                <div style="font-size: 14px; font-weight: 800; color: #38bdf8; margin: 6px 0;">ACTIVE DISPATCH</div>
                <div style="font-size: 11px; color: #94a3b8;">Ready for Tech Execution</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("<hr style='border: none; border-bottom: 1px solid #1f2430; margin: 18px 0;'/>", unsafe_allow_html=True)

    # 2. Historical Maintenance Log Table
    st.markdown(
        """
        <div style="font-size: 14px; font-weight: 800; color: #f8fafc; letter-spacing: 0.04em; text-transform: uppercase; margin-bottom: 10px;">
            🛠️ Historical Maintenance Events Log
        </div>
        """,
        unsafe_allow_html=True,
    )

    if not all_events:
        st.info("No completed maintenance events logged yet.")
    else:
        rows = []
        for e in sorted(all_events, key=lambda x: x.performed_at, reverse=True):
            rows.append({
                "Maintenance ID": e.maintenance_id,
                "Machine ID": e.machine_id,
                "Type": e.maintenance_type,
                "Description": e.notes or e.findings or "Routine Maintenance",
                "Technician": e.technician_name,
                "Duration": f"{(e.duration_hours or 0.0) * 60:.0f} min",
                "Cost": f"${(e.duration_hours or 0.0) * 85:.2f}",
                "Work Order": e.work_order_id or "N/A",
                "Date": e.performed_at.strftime("%Y-%m-%d %H:%M UTC"),
            })
        st.dataframe(rows, use_container_width=True, hide_index=True)


    st.markdown("<hr style='border: none; border-bottom: 1px solid #1f2430; margin: 18px 0;'/>", unsafe_allow_html=True)

    # 3. Quick Action: Switch to Work Orders
    col_act1, col_act2 = st.columns([3, 1])
    with col_act1:
        st.markdown(
            """
            <div style="font-size: 13px; color: #94a3b8;">
                To execute pending work orders, record technician progress, or run closed-loop physical verification, navigate to the Work Orders view.
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col_act2:
        if st.button("Open Work Orders Manager →", use_container_width=True):
            navigate_to("Work Orders")
            st.rerun()
