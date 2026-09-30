"""Industrial Dark Theme Styling and Custom CSS.

Follows Visual Direction in AGENT.md:
- Dark, industrial, high information density, clean, technical, calm, evidence-first
- Clear semantic status colors (HEALTHY: Green, WARNING: Amber, CRITICAL: Red, PENDING: Orange)
- Crisp borders and compact layouts suitable for factory reliability operations
"""

import streamlit as st


def apply_industrial_theme() -> None:
    """Inject custom industrial stylesheet into Streamlit."""
    st.markdown(
        """
        <style>
        /* Base typography & backgrounds */
        .stApp {
            background-color: #0c0e12;
            color: #e2e8f0;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
        }

        /* Sidebar Styling */
        section[data-testid="stSidebar"] {
            background-color: #12151c;
            border-right: 1px solid #1f2430;
        }

        /* Industrial Metric Cards */
        .ind-card {
            background-color: #161922;
            border: 1px solid #232936;
            border-radius: 6px;
            padding: 14px 18px;
            margin-bottom: 12px;
        }

        .ind-card-hero {
            background: linear-gradient(135deg, #1b1e28 0%, #151821 100%);
            border: 1px solid #dc2626;
            border-left: 5px solid #dc2626;
            border-radius: 6px;
            padding: 18px 22px;
            margin-bottom: 16px;
        }

        .ind-card-warning {
            background: linear-gradient(135deg, #1d1b22 0%, #151821 100%);
            border: 1px solid #d97706;
            border-left: 5px solid #d97706;
            border-radius: 6px;
            padding: 16px 20px;
            margin-bottom: 14px;
        }

        .ind-card-success {
            background: linear-gradient(135deg, #15221b 0%, #131b17 100%);
            border: 1px solid #059669;
            border-left: 5px solid #059669;
            border-radius: 6px;
            padding: 16px 20px;
            margin-bottom: 14px;
        }

        /* Semantic Badges */
        .badge {
            display: inline-block;
            padding: 2px 8px;
            font-size: 11px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            border-radius: 3px;
        }
        .badge-critical {
            background-color: rgba(239, 68, 68, 0.18);
            color: #ef4444;
            border: 1px solid rgba(239, 68, 68, 0.4);
        }
        .badge-warning {
            background-color: rgba(245, 158, 11, 0.18);
            color: #f59e0b;
            border: 1px solid rgba(245, 158, 11, 0.4);
        }
        .badge-healthy {
            background-color: rgba(16, 185, 129, 0.18);
            color: #10b981;
            border: 1px solid rgba(16, 185, 129, 0.4);
        }
        .badge-info {
            background-color: rgba(59, 130, 246, 0.18);
            color: #60a5fa;
            border: 1px solid rgba(59, 130, 246, 0.4);
        }
        .badge-neutral {
            background-color: rgba(148, 163, 184, 0.12);
            color: #94a3b8;
            border: 1px solid rgba(148, 163, 184, 0.25);
        }

        /* Metric Titles & Subtitles */
        .metric-label {
            font-size: 12px;
            font-weight: 600;
            color: #94a3b8;
            text-transform: uppercase;
            letter-spacing: 0.04em;
            margin-bottom: 4px;
        }
        .metric-value {
            font-size: 26px;
            font-weight: 700;
            color: #f8fafc;
            line-height: 1.1;
        }
        .metric-delta {
            font-size: 12px;
            margin-top: 4px;
            font-weight: 500;
        }

        /* Timeline Items */
        .timeline-step {
            border-left: 2px solid #2e3648;
            padding-left: 14px;
            margin-left: 8px;
            margin-bottom: 12px;
            position: relative;
        }
        .timeline-step::before {
            content: "";
            position: absolute;
            left: -6px;
            top: 4px;
            width: 10px;
            height: 10px;
            border-radius: 50%;
            background-color: #3b82f6;
        }
        .timeline-step.completed::before {
            background-color: #10b981;
        }
        .timeline-step.critical::before {
            background-color: #ef4444;
        }

        /* Evidence Box */
        .evidence-box {
            background-color: #141720;
            border: 1px solid #232a38;
            border-radius: 5px;
            padding: 10px 14px;
            margin-bottom: 8px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
