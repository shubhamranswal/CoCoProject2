"""Industrial Data Tables Component.

Follows Sections 12 & 30 of AGENT.md:
- High information density asset health grid
- Work order inventory table
- Maintenance history table
- Clear semantic status indicators with 1-click navigation
- Clean industrial typography, theme CSS variables, and zero emojis
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List
import streamlit as st

from domain.enums import HealthStatus
from app.streamlit.state import navigate_to


def render_asset_grid_table(
    asset_grid: List[Dict[str, Any]],
    on_select_machine: Callable[[str], None],
) -> None:
    """Render the high information density asset health table."""
    st.markdown(
        """
        <div style="font-size: 13px; font-weight: 700; color: var(--text-primary); text-transform: uppercase; letter-spacing: 0.04em; margin-bottom: 8px;">
            Fleet Asset Health Status
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Headers
    h1, h2, h3, h4, h5, h6, h7 = st.columns([1.2, 2.5, 1.2, 1.2, 1.2, 1.2, 1.2])
    h1.caption("**ASSET ID**")
    h2.caption("**MACHINE NAME**")
    h3.caption("**LINE**")
    h4.caption("**HEALTH**")
    h5.caption("**RISK SCORE**")
    h6.caption("**ALERTS**")
    h7.caption("**ACTION**")

    st.markdown("<hr style='border: none; border-bottom: 1px solid var(--border-subtle); margin: 4px 0 8px 0;'/>", unsafe_allow_html=True)

    for item in asset_grid:
        m = item["machine"]
        risk = item["risk"]
        alerts_cnt = item["active_alerts_count"]

        c1, c2, c3, c4, c5, c6, c7 = st.columns([1.2, 2.5, 1.2, 1.2, 1.2, 1.2, 1.2])

        # Health badge
        if m.health_status == HealthStatus.CRITICAL:
            h_badge = "<span class='badge badge-critical'>CRITICAL</span>"
        elif m.health_status == HealthStatus.DEGRADING:
            h_badge = "<span class='badge badge-warning'>WARNING</span>"
        else:
            h_badge = "<span class='badge badge-healthy'>HEALTHY</span>"

        risk_val = f"{risk.risk_score * 100:.0f}%" if risk else "--"
        risk_color = "#dc2626" if (risk and risk.risk_score > 0.7) else ("#d97706" if (risk and risk.risk_score > 0.4) else "#16a34a")

        c1.markdown(f"<div style='padding-top: 7px;'><b><code>{m.machine_id}</code></b></div>", unsafe_allow_html=True)
        c2.markdown(f"<div style='padding-top: 7px; font-weight: 500;'>{m.name}</div>", unsafe_allow_html=True)
        c3.markdown(f"<div style='padding-top: 7px;'><code>{m.line_id}</code></div>", unsafe_allow_html=True)
        c4.markdown(f"<div style='padding-top: 7px;'>{h_badge}</div>", unsafe_allow_html=True)
        c5.markdown(f"<div style='padding-top: 7px; color: {risk_color}; font-weight: 700;'>{risk_val}</div>", unsafe_allow_html=True)
        c6.markdown(f"<div style='padding-top: 7px;'>{alerts_cnt} active</div>" if alerts_cnt > 0 else "<div style='padding-top: 7px; color: var(--text-muted);'>0</div>", unsafe_allow_html=True)

        with c7:
            if st.button("Inspect", key=f"inspect_{m.machine_id}", use_container_width=True):
                on_select_machine(m.machine_id)
                navigate_to("Assets", machine_id=m.machine_id)
                st.rerun()

        st.markdown("<hr style='border: none; border-bottom: 1px solid var(--border-subtle); margin: 2px 0;'/>", unsafe_allow_html=True)


def render_work_orders_table(
    work_orders: List[Any],
    on_select_work_order: Callable[[str], None],
) -> None:
    """Render the work orders table."""
    if not work_orders:
        st.info("No work orders found matching criteria.")
        return

    h1, h2, h3, h4, h5, h6, h7 = st.columns([1.5, 1.2, 2.5, 1.2, 1.2, 1.5, 1.2])
    h1.caption("**WO ID**")
    h2.caption("**MACHINE**")
    h3.caption("**TITLE**")
    h4.caption("**PRIORITY**")
    h5.caption("**STATUS**")
    h6.caption("**ASSIGNED**")
    h7.caption("**ACTION**")

    st.markdown("<hr style='border: none; border-bottom: 1px solid var(--border-subtle); margin: 4px 0 8px 0;'/>", unsafe_allow_html=True)

    for wo in work_orders:
        c1, c2, c3, c4, c5, c6, c7 = st.columns([1.5, 1.2, 2.5, 1.2, 1.2, 1.5, 1.2])
        c1.markdown(f"<code>{wo.work_order_id}</code>", unsafe_allow_html=True)
        c2.markdown(f"<b>{wo.machine_id}</b>", unsafe_allow_html=True)
        c3.markdown(f"{wo.title}")
        c4.markdown(f"<span class='badge badge-warning'>{wo.priority.value}</span>", unsafe_allow_html=True)

        st_badge = "<span class='badge badge-healthy'>" if wo.status.value == "VERIFIED" else ("<span class='badge badge-info'>" if wo.status.value == "COMPLETED" else "<span class='badge badge-neutral'>")
        c5.markdown(f"{st_badge}{wo.status.value}</span>", unsafe_allow_html=True)
        c6.markdown(f"{wo.assigned_to}")

        with c7:
            if st.button("Details", key=f"view_wo_{wo.work_order_id}", use_container_width=True):
                on_select_work_order(wo.work_order_id)
                navigate_to("Work Orders", work_order_id=wo.work_order_id)
                st.rerun()

        st.markdown("<hr style='border: none; border-bottom: 1px solid var(--border-subtle); margin: 2px 0;'/>", unsafe_allow_html=True)
