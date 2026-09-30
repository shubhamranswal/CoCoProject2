"""System Settings & Operational Policy Parameters View.

Follows Section 7 & 44 of AGENT.md:
- Operational system configuration (read-only)
- Additive failure risk model weights
- VerificationPolicy criteria and recovery thresholds
- Plant and machine metadata
"""

from __future__ import annotations

from typing import Any, Dict
import streamlit as st

from app.streamlit.services.view_service import CommandCenterFacade
from config import get_config


def render_settings_view(facade: CommandCenterFacade) -> None:
    """Render the read-only operational configuration and policy parameter settings."""
    st.markdown(
        """
        <div style="margin-bottom: 16px;">
            <div style="font-size: 20px; font-weight: 800; color: #f8fafc; letter-spacing: -0.02em;">
                OPERATIONAL SETTINGS & POLICY PARAMETERS
            </div>
            <div style="font-size: 12px; color: #94a3b8;">
                Governed system configuration, risk scoring weights, and verification thresholds (Read-Only).
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    config = get_config()

    # 1. Environment & Connectivity Specs
    st.markdown(
        """
        <div style="font-size: 14px; font-weight: 800; color: #f8fafc; letter-spacing: 0.04em; text-transform: uppercase; margin-bottom: 8px;">
            ⚙️ Runtime Environment & Connectivity
        </div>
        """,
        unsafe_allow_html=True,
    )

    col_c1, col_c2 = st.columns(2)
    with col_c1:
        st.markdown(
            f"""
            <div style="background: #111520; border: 1px solid #1f2430; border-radius: 6px; padding: 16px;">
                <div style="font-size: 13px; font-weight: 800; color: #38bdf8; margin-bottom: 8px;">Application Environment</div>
                <table style="width: 100%; font-size: 12px; color: #cbd5e1; border-collapse: collapse;">
                    <tr style="border-bottom: 1px solid #1f2430;">
                        <td style="padding: 6px 0; color: #94a3b8;">Environment Name:</td>
                        <td style="padding: 6px 0; font-weight: 700; color: #22c55e;">{config.env.upper()}</td>
                    </tr>
                    <tr style="border-bottom: 1px solid #1f2430;">
                        <td style="padding: 6px 0; color: #94a3b8;">Active Storage Backend:</td>
                        <td style="padding: 6px 0; font-weight: 700; color: #38bdf8;">{facade.backend_mode.upper()}</td>
                    </tr>
                    <tr style="border-bottom: 1px solid #1f2430;">
                        <td style="padding: 6px 0; color: #94a3b8;">Deterministic Mode:</td>
                        <td style="padding: 6px 0; font-weight: 700; color: #22c55e;">ENABLED (Offline Verified)</td>
                    </tr>
                    <tr>
                        <td style="padding: 6px 0; color: #94a3b8;">Operator Session:</td>
                        <td style="padding: 6px 0; font-weight: 700; color: #f8fafc;">{st.session_state.get('active_user', 'operator.sarah')}</td>
                    </tr>
                </table>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col_c2:
        st.markdown(
            f"""
            <div style="background: #111520; border: 1px solid #1f2430; border-radius: 6px; padding: 16px;">
                <div style="font-size: 13px; font-weight: 800; color: #38bdf8; margin-bottom: 8px;">Snowflake Warehouse Configuration</div>
                <table style="width: 100%; font-size: 12px; color: #cbd5e1; border-collapse: collapse;">
                    <tr style="border-bottom: 1px solid #1f2430;">
                        <td style="padding: 6px 0; color: #94a3b8;">Snowflake Account:</td>
                        <td style="padding: 6px 0; font-weight: 700; color: #f8fafc;">{config.snowflake.account or 'NOT_CONFIGURED'}</td>
                    </tr>
                    <tr style="border-bottom: 1px solid #1f2430;">
                        <td style="padding: 6px 0; color: #94a3b8;">Database:</td>
                        <td style="padding: 6px 0; font-weight: 700; color: #f8fafc;">{config.snowflake.database or 'FACTORY_RELIABILITY_PROD'}</td>
                    </tr>
                    <tr style="border-bottom: 1px solid #1f2430;">
                        <td style="padding: 6px 0; color: #94a3b8;">Schema:</td>
                        <td style="padding: 6px 0; font-weight: 700; color: #f8fafc;">{config.snowflake.schema or 'PUBLIC'}</td>
                    </tr>
                    <tr>
                        <td style="padding: 6px 0; color: #94a3b8;">Role:</td>
                        <td style="padding: 6px 0; font-weight: 700; color: #f8fafc;">{config.snowflake.role or 'RELIABILITY_ANALYST'}</td>
                    </tr>
                </table>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("<hr style='border: none; border-bottom: 1px solid #1f2430; margin: 18px 0;'/>", unsafe_allow_html=True)

    # 2. Risk Model & Verification Policy Parameters
    st.markdown(
        """
        <div style="font-size: 14px; font-weight: 800; color: #f8fafc; letter-spacing: 0.04em; text-transform: uppercase; margin-bottom: 8px;">
            🛡️ Governed Intelligence & Verification Thresholds
        </div>
        """,
        unsafe_allow_html=True,
    )

    col_p1, col_p2 = st.columns(2)
    with col_p1:
        st.markdown(
            """
            <div style="background: #111520; border: 1px solid #1f2430; border-radius: 6px; padding: 16px;">
                <div style="font-size: 13px; font-weight: 800; color: #38bdf8; margin-bottom: 8px;">Deterministic Risk Model Weights</div>
                <table style="width: 100%; font-size: 12px; color: #cbd5e1; border-collapse: collapse;">
                    <tr style="border-bottom: 1px solid #1f2430;">
                        <td style="padding: 6px 0; color: #94a3b8;">Vibration RMS Weight:</td>
                        <td style="padding: 6px 0; font-weight: 700; color: #38bdf8;">0.35</td>
                    </tr>
                    <tr style="border-bottom: 1px solid #1f2430;">
                        <td style="padding: 6px 0; color: #94a3b8;">Temperature Housing Weight:</td>
                        <td style="padding: 6px 0; font-weight: 700; color: #38bdf8;">0.25</td>
                    </tr>
                    <tr style="border-bottom: 1px solid #1f2430;">
                        <td style="padding: 6px 0; color: #94a3b8;">Active Anomaly Z-Score Factor:</td>
                        <td style="padding: 6px 0; font-weight: 700; color: #38bdf8;">0.20</td>
                    </tr>
                    <tr style="border-bottom: 1px solid #1f2430;">
                        <td style="padding: 6px 0; color: #94a3b8;">Failure History Weight:</td>
                        <td style="padding: 6px 0; font-weight: 700; color: #38bdf8;">0.10</td>
                    </tr>
                    <tr>
                        <td style="padding: 6px 0; color: #94a3b8;">Operating Run-Hours Weight:</td>
                        <td style="padding: 6px 0; font-weight: 700; color: #38bdf8;">0.10</td>
                    </tr>
                </table>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col_p2:
        st.markdown(
            """
            <div style="background: #111520; border: 1px solid #1f2430; border-radius: 6px; padding: 16px;">
                <div style="font-size: 13px; font-weight: 800; color: #38bdf8; margin-bottom: 8px;">VerificationPolicy Acceptance Criteria</div>
                <table style="width: 100%; font-size: 12px; color: #cbd5e1; border-collapse: collapse;">
                    <tr style="border-bottom: 1px solid #1f2430;">
                        <td style="padding: 6px 0; color: #94a3b8;">Max Allowed Post-Maintenance Risk:</td>
                        <td style="padding: 6px 0; font-weight: 700; color: #22c55e;">&le; 0.30</td>
                    </tr>
                    <tr style="border-bottom: 1px solid #1f2430;">
                        <td style="padding: 6px 0; color: #94a3b8;">Max Allowed Post-Maint Vibration:</td>
                        <td style="padding: 6px 0; font-weight: 700; color: #22c55e;">&le; 0.40g RMS</td>
                    </tr>
                    <tr style="border-bottom: 1px solid #1f2430;">
                        <td style="padding: 6px 0; color: #94a3b8;">Max Allowed Post-Maint Temperature:</td>
                        <td style="padding: 6px 0; font-weight: 700; color: #22c55e;">&le; 60.0°C</td>
                    </tr>
                    <tr style="border-bottom: 1px solid #1f2430;">
                        <td style="padding: 6px 0; color: #94a3b8;">Min Required OEE Recovery:</td>
                        <td style="padding: 6px 0; font-weight: 700; color: #22c55e;">&ge; 0.75 (75%)</td>
                    </tr>
                    <tr>
                        <td style="padding: 6px 0; color: #94a3b8;">Zero Active Critical Anomalies:</td>
                        <td style="padding: 6px 0; font-weight: 700; color: #22c55e;">MANDATORY</td>
                    </tr>
                </table>
            </div>
            """,
            unsafe_allow_html=True,
        )
