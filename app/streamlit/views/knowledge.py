"""Technical Knowledge & Equipment Manuals View.

Follows Section 21 of AGENT.md:
- Equipment technical documentation and service manuals (DRV-5000 Conveyor Drive)
- Vibration limits (ISO 10816-3 & manufacturer tolerances)
- Approved replacement parts catalog (SKF 6205-2RSH deep groove ball bearings)
- Step-by-step LOTO and replacement procedures used by AI investigation agent
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
            <div style="font-size: 20px; font-weight: 800; color: #f8fafc; letter-spacing: -0.02em;">
                TECHNICAL KNOWLEDGE BASE & SERVICE MANUALS
            </div>
            <div style="font-size: 12px; color: #94a3b8;">
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
            <div style="background: #111520; border: 1px solid #1f2430; border-radius: 6px; padding: 14px;">
                <div style="font-size: 11px; font-weight: 700; color: #94a3b8; text-transform: uppercase;">Indexed Manual Chunks</div>
                <div style="font-size: 26px; font-weight: 800; color: #38bdf8; margin: 4px 0;">{len(docs) if docs else 8}</div>
                <div style="font-size: 11px; color: #94a3b8;">Embedding / Semantic Match Ready</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col_stats2:
        st.markdown(
            """
            <div style="background: #111520; border: 1px solid #1f2430; border-radius: 6px; padding: 14px;">
                <div style="font-size: 11px; font-weight: 700; color: #94a3b8; text-transform: uppercase;">Standard Compliance</div>
                <div style="font-size: 20px; font-weight: 800; color: #22c55e; margin: 7px 0;">ISO 10816-3 Class II</div>
                <div style="font-size: 11px; color: #94a3b8;">Industrial Medium Rigid Motors</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col_stats3:
        st.markdown(
            """
            <div style="background: #111520; border: 1px solid #1f2430; border-radius: 6px; padding: 14px;">
                <div style="font-size: 11px; font-weight: 700; color: #94a3b8; text-transform: uppercase;">Primary Equipment Manual</div>
                <div style="font-size: 16px; font-weight: 800; color: #f8fafc; margin: 9px 0;">DRV-5000 Rev 4.2</div>
                <div style="font-size: 11px; color: #94a3b8;">Conveyor Drive Subassembly</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("<hr style='border: none; border-bottom: 1px solid #1f2430; margin: 18px 0;'/>", unsafe_allow_html=True)

    # 2. DRV-5000 Specifications and Tolerances
    st.markdown(
        """
        <div style="font-size: 14px; font-weight: 800; color: #f8fafc; letter-spacing: 0.04em; text-transform: uppercase; margin-bottom: 10px;">
            📖 DRV-5000 Conveyor Drive Service Tolerances (M204 Reference)
        </div>
        """,
        unsafe_allow_html=True,
    )

    col_t1, col_t2 = st.columns(2)
    with col_t1:
        st.markdown(
            """
            <div style="background: #111520; border: 1px solid #1f2430; border-radius: 6px; padding: 16px; height: 100%;">
                <div style="font-size: 14px; font-weight: 800; color: #38bdf8; margin-bottom: 8px;">Physical Operating Limits</div>
                <table style="width: 100%; font-size: 12px; color: #cbd5e1; border-collapse: collapse;">
                    <tr style="border-bottom: 1px solid #1f2430;">
                        <td style="padding: 6px 0; color: #94a3b8;">Nominal Vibration RMS:</td>
                        <td style="padding: 6px 0; font-weight: 700; color: #22c55e;">0.15g – 0.28g</td>
                    </tr>
                    <tr style="border-bottom: 1px solid #1f2430;">
                        <td style="padding: 6px 0; color: #94a3b8;">Warning Threshold (Z > 2.5):</td>
                        <td style="padding: 6px 0; font-weight: 700; color: #f59e0b;">0.45g RMS</td>
                    </tr>
                    <tr style="border-bottom: 1px solid #1f2430;">
                        <td style="padding: 6px 0; color: #94a3b8;">Critical Trip Limit:</td>
                        <td style="padding: 6px 0; font-weight: 700; color: #ef4444;">0.70g RMS</td>
                    </tr>
                    <tr style="border-bottom: 1px solid #1f2430;">
                        <td style="padding: 6px 0; color: #94a3b8;">Nominal Temperature:</td>
                        <td style="padding: 6px 0; font-weight: 700; color: #22c55e;">42°C – 55°C</td>
                    </tr>
                    <tr style="border-bottom: 1px solid #1f2430;">
                        <td style="padding: 6px 0; color: #94a3b8;">Thermal Degradation Limit:</td>
                        <td style="padding: 6px 0; font-weight: 700; color: #ef4444;">70.0°C</td>
                    </tr>
                    <tr>
                        <td style="padding: 6px 0; color: #94a3b8;">Nominal Motor RPM:</td>
                        <td style="padding: 6px 0; font-weight: 700; color: #f8fafc;">1750 RPM ± 20</td>
                    </tr>
                </table>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col_t2:
        st.markdown(
            """
            <div style="background: #111520; border: 1px solid #1f2430; border-radius: 6px; padding: 16px; height: 100%;">
                <div style="font-size: 14px; font-weight: 800; color: #38bdf8; margin-bottom: 8px;">Approved Replacement Parts</div>
                <table style="width: 100%; font-size: 12px; color: #cbd5e1; border-collapse: collapse;">
                    <tr style="border-bottom: 1px solid #1f2430;">
                        <td style="padding: 6px 0; color: #94a3b8;">Drive-End Bearing:</td>
                        <td style="padding: 6px 0; font-weight: 700; color: #f8fafc;">SKF 6205-2RSH (Deep Groove)</td>
                    </tr>
                    <tr style="border-bottom: 1px solid #1f2430;">
                        <td style="padding: 6px 0; color: #94a3b8;">Non-Drive-End Bearing:</td>
                        <td style="padding: 6px 0; font-weight: 700; color: #f8fafc;">SKF 6204-2RSH</td>
                    </tr>
                    <tr style="border-bottom: 1px solid #1f2430;">
                        <td style="padding: 6px 0; color: #94a3b8;">Approved Grease:</td>
                        <td style="padding: 6px 0; font-weight: 700; color: #f8fafc;">Mobil Polyrex EM (Polyurea)</td>
                    </tr>
                    <tr style="border-bottom: 1px solid #1f2430;">
                        <td style="padding: 6px 0; color: #94a3b8;">Coupling Element:</td>
                        <td style="padding: 6px 0; font-weight: 700; color: #f8fafc;">Lovejoy AL-095 Spider</td>
                    </tr>
                    <tr>
                        <td style="padding: 6px 0; color: #94a3b8;">Mounting Torque:</td>
                        <td style="padding: 6px 0; font-weight: 700; color: #f8fafc;">45 Nm (Grade 8.8 M10 bolts)</td>
                    </tr>
                </table>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("<hr style='border: none; border-bottom: 1px solid #1f2430; margin: 18px 0;'/>", unsafe_allow_html=True)

    # 3. Indexed Chunks Table
    st.markdown(
        """
        <div style="font-size: 14px; font-weight: 800; color: #f8fafc; letter-spacing: 0.04em; text-transform: uppercase; margin-bottom: 10px;">
            📑 Manual Documentation Chunks (Read Tool Accessible)
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
        st.dataframe(rows, use_container_width=True, hide_index=True)
    else:
        st.markdown(
            """
            <div style="background: #111520; border: 1px solid #1f2430; border-radius: 6px; padding: 14px;">
                <div style="font-size: 13px; font-weight: 700; color: #f8fafc; margin-bottom: 4px;">DRV-5000 Maintenance Section 4.3: Bearing Replacement Protocol</div>
                <div style="font-size: 12px; color: #cbd5e1; line-height: 1.5;">
                    "When drive-end bearing vibration velocity exceeds 0.45g RMS accompanied by bearing housing temperature &gt;68°C, immediate scheduled replacement is required. Verify shaft runout &lt;0.02 mm before pressing new SKF 6205-2RSH bearing. Pack bearing 30-40% volume with Mobil Polyrex EM. Perform baseline vibration measurement after 30-minute run-in period."
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
