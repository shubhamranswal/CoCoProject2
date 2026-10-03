"""Technical Knowledge & Equipment Manuals View.

Follows Section 21 of AGENT.md:
- Equipment technical documentation and service manuals (DRV-5000 Conveyor Drive)
- Vibration limits (ISO 10816-3 & manufacturer tolerances)
- Approved replacement parts catalog (Drive-End Bearing 6206-2RS)
- Step-by-step LOTO and replacement procedures used by AI investigation agent
- Theme CSS variable styling and zero emojis
"""

from __future__ import annotations

from typing import Any, Dict, List
import streamlit as st

from app.streamlit.services.view_service import CommandCenterFacade


def render_knowledge_view(facade: CommandCenterFacade) -> None:
    """Render the technical manuals, knowledge base chunks, and service limits view."""
    st.markdown(
        """
        <div style="margin-bottom: 16px;">
            <div style="font-size: 18px; font-weight: 700; color: var(--text-primary); letter-spacing: -0.02em;">
                TECHNICAL KNOWLEDGE BASE & SERVICE MANUALS
            </div>
            <div style="font-size: 12px; color: var(--text-muted);">
                Equipment manuals, physical vibration thresholds, parts catalogs, and LOTO maintenance procedures.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # 1. Document Inventory & Search
    docs = facade.get_knowledge_documents()

    col_stats1, col_stats2, col_stats3 = st.columns(3)
    with col_stats1:
        st.markdown(
            f"""
            <div class="ind-card">
                <div class="metric-label">Indexed Manual Chunks</div>
                <div class="metric-value" style="color: var(--primary-accent);">{len(docs) if docs else 8}</div>
                <div class="metric-delta" style="color: var(--text-muted);">Embedding / Semantic Match Ready</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col_stats2:
        st.markdown(
            """
            <div class="ind-card">
                <div class="metric-label">Standard Compliance</div>
                <div class="metric-value" style="font-size: 20px; color: #16a34a;">ISO 10816-3 Class II</div>
                <div class="metric-delta" style="color: var(--text-muted);">Industrial Medium Rigid Motors</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col_stats3:
        st.markdown(
            """
            <div class="ind-card">
                <div class="metric-label">Primary Equipment Manual</div>
                <div class="metric-value" style="font-size: 18px;">DRV-5000 Rev 4.2</div>
                <div class="metric-delta" style="color: var(--text-muted);">Conveyor Drive Subassembly</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("<hr style='border: none; border-bottom: 1px solid var(--border-subtle); margin: 18px 0;'/>", unsafe_allow_html=True)

    # 2. DRV-5000 Specifications and Tolerances
    st.markdown(
        """
        <div style="font-size: 13px; font-weight: 700; color: var(--text-primary); letter-spacing: 0.04em; text-transform: uppercase; margin-bottom: 10px;">
            DRV-5000 Conveyor Drive Service Tolerances (M204 Reference)
        </div>
        """,
        unsafe_allow_html=True,
    )

    col_t1, col_t2 = st.columns(2)
    with col_t1:
        st.markdown(
            """
            <div class="ind-card" style="height: 100%;">
                <div style="font-size: 13px; font-weight: 700; color: var(--primary-accent); margin-bottom: 8px;">Physical Operating Limits</div>
                <table style="width: 100%; font-size: 12px; color: var(--text-secondary); border-collapse: collapse;">
                    <tr style="border-bottom: 1px solid var(--border-subtle);">
                        <td style="padding: 6px 0; color: var(--text-muted);">Nominal Vibration RMS:</td>
                        <td style="padding: 6px 0; font-weight: 700; color: #16a34a;">0.15g – 0.28g</td>
                    </tr>
                    <tr style="border-bottom: 1px solid var(--border-subtle);">
                        <td style="padding: 6px 0; color: var(--text-muted);">Warning Threshold (Z > 2.5):</td>
                        <td style="padding: 6px 0; font-weight: 700; color: #d97706;">0.45g RMS</td>
                    </tr>
                    <tr style="border-bottom: 1px solid var(--border-subtle);">
                        <td style="padding: 6px 0; color: var(--text-muted);">Critical Trip Limit:</td>
                        <td style="padding: 6px 0; font-weight: 700; color: #dc2626;">0.70g RMS</td>
                    </tr>
                    <tr style="border-bottom: 1px solid var(--border-subtle);">
                        <td style="padding: 6px 0; color: var(--text-muted);">Nominal Temperature:</td>
                        <td style="padding: 6px 0; font-weight: 700; color: #16a34a;">42°C – 55°C</td>
                    </tr>
                    <tr style="border-bottom: 1px solid var(--border-subtle);">
                        <td style="padding: 6px 0; color: var(--text-muted);">Thermal Degradation Limit:</td>
                        <td style="padding: 6px 0; font-weight: 700; color: #dc2626;">70.0°C</td>
                    </tr>
                    <tr>
                        <td style="padding: 6px 0; color: var(--text-muted);">Nominal Motor RPM:</td>
                        <td style="padding: 6px 0; font-weight: 700; color: var(--text-primary);">1750 RPM ± 20</td>
                    </tr>
                </table>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col_t2:
        st.markdown(
            """
            <div class="ind-card" style="height: 100%;">
                <div style="font-size: 13px; font-weight: 700; color: var(--primary-accent); margin-bottom: 8px;">Approved Replacement Parts</div>
                <table style="width: 100%; font-size: 12px; color: var(--text-secondary); border-collapse: collapse;">
                    <tr style="border-bottom: 1px solid var(--border-subtle);">
                        <td style="padding: 6px 0; color: var(--text-muted);">Drive-End Bearing:</td>
                        <td style="padding: 6px 0; font-weight: 700; color: var(--text-primary);">Drive-End Bearing 6206-2RS (SP-002)</td>
                    </tr>
                    <tr style="border-bottom: 1px solid var(--border-subtle);">
                        <td style="padding: 6px 0; color: var(--text-muted);">Non-Drive-End Bearing:</td>
                        <td style="padding: 6px 0; font-weight: 700; color: var(--text-primary);">Deep Groove Bearing 6204-2RS</td>
                    </tr>
                    <tr style="border-bottom: 1px solid var(--border-subtle);">
                        <td style="padding: 6px 0; color: var(--text-muted);">Approved Grease:</td>
                        <td style="padding: 6px 0; font-weight: 700; color: var(--text-primary);">Mobil Polyrex EM (Polyurea)</td>
                    </tr>
                    <tr style="border-bottom: 1px solid var(--border-subtle);">
                        <td style="padding: 6px 0; color: var(--text-muted);">Coupling Element:</td>
                        <td style="padding: 6px 0; font-weight: 700; color: var(--text-primary);">Lovejoy AL-095 Spider</td>
                    </tr>
                    <tr>
                        <td style="padding: 6px 0; color: var(--text-muted);">Mounting Torque:</td>
                        <td style="padding: 6px 0; font-weight: 700; color: var(--text-primary);">45 Nm (Grade 8.8 M10 bolts)</td>
                    </tr>
                </table>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("<hr style='border: none; border-bottom: 1px solid var(--border-subtle); margin: 18px 0;'/>", unsafe_allow_html=True)

    # 3. Indexed Chunks Table
    st.markdown(
        """
        <div style="font-size: 13px; font-weight: 700; color: var(--text-primary); letter-spacing: 0.04em; text-transform: uppercase; margin-bottom: 10px;">
            Manual Documentation Chunks (Read Tool Accessible)
        </div>
        """,
        unsafe_allow_html=True,
    )

    if docs:
        rows = []
        for d in docs:
            rows.append({
                "Doc ID": getattr(d, "doc_id", "DOC-001"),
                "Title": getattr(d, "title", "DRV-5000 Maintenance Manual"),
                "Section": getattr(d, "section", "Bearing Assembly"),
                "Snippet": (getattr(d, "content", "")[:120] + "..."),
            })
        st.dataframe(rows, width="stretch", hide_index=True)
    else:
        st.markdown(
            """
            <div class="ind-card">
                <div style="font-size: 13px; font-weight: 700; color: var(--text-primary); margin-bottom: 4px;">DRV-5000 Maintenance Section 4.3: Bearing Replacement Protocol</div>
                <div style="font-size: 12px; color: var(--text-secondary); line-height: 1.5;">
                    "When drive-end bearing vibration velocity exceeds 0.45g RMS accompanied by bearing housing temperature &gt;68°C, immediate scheduled replacement is required. Verify shaft runout &lt;0.02 mm before pressing new Drive-End Bearing 6206-2RS (SP-002). Pack bearing 30-40% volume with Mobil Polyrex EM. Perform baseline vibration measurement after 30-minute run-in period."
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
