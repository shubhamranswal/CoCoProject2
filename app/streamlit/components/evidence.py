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

    # Group evidence items by category or evidence_type
    groups: dict[str, List[Evidence]] = {}
    for ev in evidence_list:
        key = ev.category or ev.evidence_type or "GENERAL"
        groups.setdefault(key, []).append(ev)

    category_labels = {
        "SENSOR": "Physical Sensor Telemetry",
        "TELEMETRY": "Physical Sensor Telemetry",
        "PREDICTION": "ML Failure Predictions",
        "ANOMALY": "Statistical Anomalies",
        "FAILURE_HISTORY": "Historical Failure Precedents",
        "FAILURE": "Historical Failure Precedents",
        "MAINTENANCE": "Maintenance Work Orders",
        "INVENTORY": "Spare Parts & Inventory Exposure",
        "PRODUCTION": "Production Commitments & Exposure",
        "KNOWLEDGE": "Technical Guidance & Service Limits",
        "DOCUMENT": "Technical Guidance & Service Limits",
        "OEE": "Production & OEE Impact",
        "GENERAL": "General Observations",
    }

    st.markdown(
        f"""
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
            <div style="font-size: 13px; font-weight: 700; color: var(--text-primary); text-transform: uppercase; letter-spacing: 0.04em;">
                Collected Evidence Repository ({len(evidence_list)} Items)
            </div>
            <div style="font-size: 11px; color: var(--text-muted);">
                Typed audit records grounded by InvestigationService
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
                    rel_badge = "<span class='badge badge-critical'>SUPPORTS ROOT CAUSE</span>"
                elif item.is_contradictory or item.relationship == "CONTRADICTS":
                    rel_badge = "<span class='badge badge-warning'>CONTRADICTS</span>"
                elif item.relationship == "CORRELATES":
                    rel_badge = "<span class='badge badge-info'>CORRELATES</span>"
                else:
                    rel_badge = "<span class='badge badge-neutral'>CONTEXTUAL FACT</span>"

                # Severity badge if available
                sev_badge = ""
                if item.severity:
                    sev_upper = str(item.severity).upper()
                    if sev_upper in ("CRITICAL", "ALARM", "HIGH"):
                        sev_badge = f"<span class='badge badge-critical' style='margin-left: 4px;'>{sev_upper}</span>"
                    elif sev_upper in ("WARNING", "MEDIUM"):
                        sev_badge = f"<span class='badge badge-warning' style='margin-left: 4px;'>{sev_upper}</span>"
                    else:
                        sev_badge = f"<span class='badge badge-neutral' style='margin-left: 4px;'>{sev_upper}</span>"

                # Category badge
                cat_name = item.category or item.evidence_type
                cat_badge = f"<span class='badge badge-neutral' style='margin-left: 6px;'>{cat_name}</span>" if cat_name else ""

                # Metric and observation
                unit_str = f" {item.unit}" if item.unit else ""
                observed_str = f"Observed: <b>{item.observed_value}{unit_str}</b>" if item.observed_value is not None else ""
                baseline_str = f" | Baseline: <code>{item.baseline_value}</code>" if item.baseline_value is not None else ""

                # Technical provenance & source details
                src_meta_items = []
                if item.source:
                    src_meta_items.append(f"Source: <code>{item.source}</code>")
                if item.source_type:
                    src_meta_items.append(f"Type: <code>{item.source_type}</code>")
                if item.source_id:
                    src_meta_items.append(f"ID: <code>{item.source_id}</code>")
                if item.source_reference:
                    src_meta_items.append(f"Ref: <code>{item.source_reference}</code>")

                src_meta_line = " &nbsp;|&nbsp; ".join(src_meta_items) if src_meta_items else ""

                # Claim vs summary text
                claim_html = ""
                if item.claim:
                    claim_html = f"<div style='font-size: 13px; font-weight: 600; color: var(--text-primary); margin-bottom: 4px;'>{item.claim}</div>"

                summary_text = item.summary or item.observed_fact or ""
                summary_html = ""
                if summary_text and summary_text != item.claim:
                    summary_html = f"<div style='font-size: 12px; color: var(--text-secondary); margin-bottom: 6px;'>{summary_text}</div>"

                st.markdown(
                    f"""
                    <div class="evidence-box">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                            <div>
                                <span style="font-size: 11px; font-weight: 700; color: var(--primary-accent);">[{item.evidence_id}]</span>
                                {cat_badge}
                                <span style="font-size: 12px; font-weight: 600; color: var(--text-primary); margin-left: 6px;">{item.metric or item.source}</span>
                            </div>
                            <div>{rel_badge}{sev_badge}</div>
                        </div>
                        {claim_html}
                        {summary_html}
                        <div style="font-size: 11px; color: var(--text-muted); margin-top: 4px;">
                            {observed_str}{baseline_str}
                        </div>
                        {f'<div style="font-size: 11px; color: var(--text-muted); margin-top: 2px;">{src_meta_line}</div>' if src_meta_line else ''}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
