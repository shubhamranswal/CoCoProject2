"""System Settings & Operational Policy Parameters View.

Follows Section 7 & 44 of AGENT.md:
- Operational system configuration (read-only)
- Interface display preferences (Light Mode / Dark Mode toggle)
- Additive failure risk model weights
- VerificationPolicy criteria and recovery thresholds
- Plant and machine metadata
- Theme CSS variable styling and zero emojis
"""

from __future__ import annotations

from typing import Any, Dict
import streamlit as st

from app.streamlit.services.view_service import CommandCenterFacade
from config import get_config


def render_settings_view(facade: CommandCenterFacade) -> None:
    """Render the operational configuration, appearance options, and policy parameter settings."""
    st.markdown(
        """
        <div style="margin-bottom: 16px;">
            <div style="font-size: 18px; font-weight: 700; color: var(--text-primary); letter-spacing: -0.02em;">
                OPERATIONAL SETTINGS & POLICY PARAMETERS
            </div>
            <div style="font-size: 12px; color: var(--text-muted);">
                Governed system configuration, interface display preferences, risk scoring weights, and verification thresholds.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    config = get_config()

    # 1. User Interface & Display Settings
    st.markdown(
        """
        <div style="font-size: 13px; font-weight: 700; color: var(--text-primary); letter-spacing: 0.04em; text-transform: uppercase; margin-bottom: 8px;">
            User Interface & Display Settings
        </div>
        """,
        unsafe_allow_html=True,
    )

    cur_theme = st.session_state.get("theme_mode", "light")
    col_t1, col_t2 = st.columns([2, 2])
    with col_t1:
        chosen_theme = st.radio(
            "Dashboard Color Theme:",
            options=["Light (Default Industrial)", "Dark (Console)"],
            index=0 if cur_theme == "light" else 1,
            key="settings_theme_radio",
            help="Toggle between clean industrial Light mode and Dark operations console.",
        )
        new_theme_mode = "light" if "Light" in chosen_theme else "dark"
        if new_theme_mode != cur_theme:
            st.session_state.theme_mode = new_theme_mode
            st.rerun()

    st.markdown("<hr style='border: none; border-bottom: 1px solid var(--border-subtle); margin: 16px 0;'/>", unsafe_allow_html=True)

    # 2. Environment & Connectivity Specs
    st.markdown(
        """
        <div style="font-size: 13px; font-weight: 700; color: var(--text-primary); letter-spacing: 0.04em; text-transform: uppercase; margin-bottom: 8px;">
            Runtime Environment & Connectivity
        </div>
        """,
        unsafe_allow_html=True,
    )

    col_c1, col_c2 = st.columns(2)
    with col_c1:
        st.markdown(
            f"""
            <div class="ind-card">
                <div style="font-size: 13px; font-weight: 700; color: var(--primary-accent); margin-bottom: 8px;">Application Environment</div>
                <table style="width: 100%; font-size: 12px; color: var(--text-secondary); border-collapse: collapse;">
                    <tr style="border-bottom: 1px solid var(--border-subtle);">
                        <td style="padding: 6px 0; color: var(--text-muted);">Environment Name:</td>
                        <td style="padding: 6px 0; font-weight: 700; color: #16a34a;">{config.env.upper()}</td>
                    </tr>
                    <tr style="border-bottom: 1px solid var(--border-subtle);">
                        <td style="padding: 6px 0; color: var(--text-muted);">Active Storage Backend:</td>
                        <td style="padding: 6px 0; font-weight: 700; color: var(--primary-accent);">{facade.backend_mode.upper()}</td>
                    </tr>
                    <tr style="border-bottom: 1px solid var(--border-subtle);">
                        <td style="padding: 6px 0; color: var(--text-muted);">Deterministic Mode:</td>
                        <td style="padding: 6px 0; font-weight: 700; color: #16a34a;">ENABLED (Offline Verified)</td>
                    </tr>
                    <tr>
                        <td style="padding: 6px 0; color: var(--text-muted);">Operator Session:</td>
                        <td style="padding: 6px 0; font-weight: 700; color: var(--text-primary);">{st.session_state.get('active_user', 'operator.shubham')}</td>
                    </tr>
                </table>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col_c2:
        st.markdown(
            f"""
            <div class="ind-card">
                <div style="font-size: 13px; font-weight: 700; color: var(--primary-accent); margin-bottom: 8px;">Snowflake Warehouse Configuration</div>
                <table style="width: 100%; font-size: 12px; color: var(--text-secondary); border-collapse: collapse;">
                    <tr style="border-bottom: 1px solid var(--border-subtle);">
                        <td style="padding: 6px 0; color: var(--text-muted);">Snowflake Account:</td>
                        <td style="padding: 6px 0; font-weight: 700; color: var(--text-primary);">{config.snowflake.account or 'NOT_CONFIGURED'}</td>
                    </tr>
                    <tr style="border-bottom: 1px solid var(--border-subtle);">
                        <td style="padding: 6px 0; color: var(--text-muted);">Database:</td>
                        <td style="padding: 6px 0; font-weight: 700; color: var(--text-primary);">{config.snowflake.database or 'COCO_FACTORY'}</td>
                    </tr>
                    <tr style="border-bottom: 1px solid var(--border-subtle);">
                        <td style="padding: 6px 0; color: var(--text-muted);">Schema:</td>
                        <td style="padding: 6px 0; font-weight: 700; color: var(--text-primary);">{config.snowflake.schema or 'APP'}</td>
                    </tr>
                    <tr>
                        <td style="padding: 6px 0; color: var(--text-muted);">Role:</td>
                        <td style="padding: 6px 0; font-weight: 700; color: var(--text-primary);">{config.snowflake.role or 'RELIABILITY_ANALYST'}</td>
                    </tr>
                </table>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("<hr style='border: none; border-bottom: 1px solid var(--border-subtle); margin: 18px 0;'/>", unsafe_allow_html=True)

    # 3. Risk Model & Verification Policy Parameters
    st.markdown(
        """
        <div style="font-size: 13px; font-weight: 700; color: var(--text-primary); letter-spacing: 0.04em; text-transform: uppercase; margin-bottom: 8px;">
            Governed Intelligence & Verification Thresholds
        </div>
        """,
        unsafe_allow_html=True,
    )

    col_p1, col_p2 = st.columns(2)
    with col_p1:
        st.markdown(
            """
            <div class="ind-card">
                <div style="font-size: 13px; font-weight: 700; color: var(--primary-accent); margin-bottom: 8px;">Deterministic Risk Model Weights</div>
                <table style="width: 100%; font-size: 12px; color: var(--text-secondary); border-collapse: collapse;">
                    <tr style="border-bottom: 1px solid var(--border-subtle);">
                        <td style="padding: 6px 0; color: var(--text-muted);">Vibration RMS Weight:</td>
                        <td style="padding: 6px 0; font-weight: 700; color: var(--primary-accent);">0.35</td>
                    </tr>
                    <tr style="border-bottom: 1px solid var(--border-subtle);">
                        <td style="padding: 6px 0; color: var(--text-muted);">Temperature Housing Weight:</td>
                        <td style="padding: 6px 0; font-weight: 700; color: var(--primary-accent);">0.25</td>
                    </tr>
                    <tr style="border-bottom: 1px solid var(--border-subtle);">
                        <td style="padding: 6px 0; color: var(--text-muted);">Active Anomaly Z-Score Factor:</td>
                        <td style="padding: 6px 0; font-weight: 700; color: var(--primary-accent);">0.20</td>
                    </tr>
                    <tr style="border-bottom: 1px solid var(--border-subtle);">
                        <td style="padding: 6px 0; color: var(--text-muted);">Failure History Weight:</td>
                        <td style="padding: 6px 0; font-weight: 700; color: var(--primary-accent);">0.10</td>
                    </tr>
                    <tr>
                        <td style="padding: 6px 0; color: var(--text-muted);">Operating Run-Hours Weight:</td>
                        <td style="padding: 6px 0; font-weight: 700; color: var(--primary-accent);">0.10</td>
                    </tr>
                </table>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col_p2:
        st.markdown(
            """
            <div class="ind-card">
                <div style="font-size: 13px; font-weight: 700; color: var(--primary-accent); margin-bottom: 8px;">VerificationPolicy Acceptance Criteria</div>
                <table style="width: 100%; font-size: 12px; color: var(--text-secondary); border-collapse: collapse;">
                    <tr style="border-bottom: 1px solid var(--border-subtle);">
                        <td style="padding: 6px 0; color: var(--text-muted);">Max Allowed Post-Maintenance Risk:</td>
                        <td style="padding: 6px 0; font-weight: 700; color: #16a34a;">&le; 0.30</td>
                    </tr>
                    <tr style="border-bottom: 1px solid var(--border-subtle);">
                        <td style="padding: 6px 0; color: var(--text-muted);">Max Allowed Post-Maint Vibration:</td>
                        <td style="padding: 6px 0; font-weight: 700; color: #16a34a;">&le; 0.40g RMS</td>
                    </tr>
                    <tr style="border-bottom: 1px solid var(--border-subtle);">
                        <td style="padding: 6px 0; color: var(--text-muted);">Max Allowed Post-Maint Temperature:</td>
                        <td style="padding: 6px 0; font-weight: 700; color: #16a34a;">&le; 60.0°C</td>
                    </tr>
                    <tr style="border-bottom: 1px solid var(--border-subtle);">
                        <td style="padding: 6px 0; color: var(--text-muted);">Min Required OEE Recovery:</td>
                        <td style="padding: 6px 0; font-weight: 700; color: #16a34a;">&ge; 0.75 (75%)</td>
                    </tr>
                    <tr>
                        <td style="padding: 6px 0; color: var(--text-muted);">Zero Active Critical Anomalies:</td>
                        <td style="padding: 6px 0; font-weight: 700; color: #16a34a;">MANDATORY</td>
                    </tr>
                </table>
            </div>
            """,
            unsafe_allow_html=True,
        )
