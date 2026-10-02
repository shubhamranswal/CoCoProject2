"""Evidence Panel Component.

Follows Section 18 of AGENT.md:
- Groups evidence: Telemetry, Anomalies, Failure History, Maintenance, OEE, Machine Documentation
- Renders typed facts: source, observed value, baseline value, delta %, and SUPPORTS / CONTRADICTORY badge
- Evidence-first transparency rather than opaque AI assertions
- Zero emojis and theme variable styling
"""

from __future__ import annotations

from typing import List
import streamlit as st

from domain.models import Evidence


def render_evidence_panel(evidence_list: List[Evidence]) -> None:
    """Render the structured evidence panel grouped by category."""
    if not evidence_list:
        st.info("No evidence records collected yet. Run investigation agent to gather evidence.")
        return

    # Group evidence items by evidence_type
    groups: dict[str, List[Evidence]] = {}
    for ev in evidence_list:
        ev_type = ev.evidence_type or "GENERAL"
        groups.setdefault(ev_type, []).append(ev)

    category_labels = {
        "TELEMETRY": "Physical Sensor Telemetry",
        "ANOMALY": "Statistical Anomalies",
        "FAILURE": "Historical Failure Patterns",
        "MAINTENANCE": "Recent Maintenance Records",
        "OEE": "Production & OEE Impact",
        "DOCUMENT": "Technical Manual & Service Limits",
        "GENERAL": "General Observations",
    }

    st.markdown(
        f"""
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
            <div style="font-size: 13px; font-weight: 700; color: var(--text-primary); text-transform: uppercase; letter-spacing: 0.04em;">
                Collected Evidence Repository ({len(evidence_list)} Items)
            </div>
            <div style="font-size: 11px; color: var(--text-muted);">
                Typed audit records correlated by Reliability Agent
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    tabs = st.tabs([category_labels.get(k, k) for k in groups.keys()])

    for tab, (grp_key, items) in zip(tabs, groups.items()):
        with tab:
            for item in items:
                # Semantic badge for relationship
                if item.relationship == "SUPPORTS":
                    badge_html = "<span class='badge badge-critical'>SUPPORTS ROOT CAUSE</span>"
                elif item.is_contradictory or item.relationship == "CONTRADICTS":
                    badge_html = "<span class='badge badge-warning'>CONTRADICTS</span>"
                else:
                    badge_html = "<span class='badge badge-neutral'>CONTEXTUAL FACT</span>"

                baseline_str = f" | Baseline: <code>{item.baseline_value}</code>" if item.baseline_value else ""
                observed_str = f"Observed: <b>{item.observed_value}</b>" if item.observed_value else ""

                st.markdown(
                    f"""
                    <div class="evidence-box">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                            <div>
                                <span style="font-size: 11px; font-weight: 700; color: var(--primary-accent);">[{item.evidence_id}]</span>
                                <span style="font-size: 12px; font-weight: 600; color: var(--text-primary); margin-left: 6px;">{item.metric or item.source}</span>
                            </div>
                            <div>{badge_html}</div>
                        </div>
                        <div style="font-size: 12px; color: var(--text-secondary); margin-bottom: 4px;">
                            {item.summary or item.observed_fact}
                        </div>
                        <div style="font-size: 11px; color: var(--text-muted);">
                            Source: <code>{item.source}</code> &nbsp;|&nbsp; {observed_str}{baseline_str}
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
