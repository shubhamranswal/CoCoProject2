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

        /* Hero Action Toolbar */
        .hero-action-toolbar {
            background-color: #12151e;
            border: 1px solid #dc2626;
            border-top: 1px solid rgba(255, 255, 255, 0.08);
            border-left: 5px solid #dc2626;
            border-radius: 0 0 6px 6px;
            padding: 10px 16px;
            margin-top: -16px;
            margin-bottom: 16px;
        }

        /* Streamlit Button Overrides — Dark Industrial Aesthetic */
        .stButton > button,
        button[kind="secondary"],
        button[data-testid="baseButton-secondary"] {
            background-color: #171b26 !important;
            color: #cbd5e1 !important;
            border: 1px solid #2d3548 !important;
            border-radius: 5px !important;
            font-size: 13px !important;
            font-weight: 600 !important;
            box-shadow: none !important;
            transition: all 0.15s ease-in-out !important;
        }

        .stButton > button:hover,
        button[kind="secondary"]:hover,
        button[data-testid="baseButton-secondary"]:hover {
            background-color: #222838 !important;
            border-color: #3b82f6 !important;
            color: #ffffff !important;
        }

        .stButton > button:active,
        button[kind="secondary"]:active,
        button[data-testid="baseButton-secondary"]:active {
            background-color: #1a202c !important;
            border-color: #2563eb !important;
        }

        /* Primary Action Buttons */
        .stButton > button[kind="primary"],
        button[kind="primary"],
        button[data-testid="baseButton-primary"] {
            background: linear-gradient(135deg, #dc2626 0%, #b91c1c 100%) !important;
            border: 1px solid #ef4444 !important;
            color: #ffffff !important;
            font-size: 13px !important;
            font-weight: 700 !important;
            box-shadow: 0 2px 4px rgba(220, 38, 38, 0.3) !important;
        }

        .stButton > button[kind="primary"]:hover,
        button[kind="primary"]:hover,
        button[data-testid="baseButton-primary"]:hover {
            background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%) !important;
            border-color: #f87171 !important;
            color: #ffffff !important;
        }

        /* Disabled Buttons */
        .stButton > button:disabled,
        button[disabled],
        button:disabled {
            background-color: #0f1219 !important;
            color: #475569 !important;
            border: 1px solid #1e2433 !important;
            cursor: not-allowed !important;
            opacity: 0.6 !important;
            box-shadow: none !important;
        }

        /* Sidebar Navigation Buttons */
        section[data-testid="stSidebar"] .stButton > button {
            background-color: #151822 !important;
            color: #94a3b8 !important;
            border: 1px solid #1e2433 !important;
            border-radius: 5px !important;
            text-align: left !important;
            justify-content: flex-start !important;
            font-size: 13px !important;
            font-weight: 600 !important;
            padding: 8px 12px !important;
            margin-bottom: 2px !important;
            box-shadow: none !important;
        }

        section[data-testid="stSidebar"] .stButton > button:hover {
            background-color: #1e2436 !important;
            border-color: #38bdf8 !important;
            color: #f8fafc !important;
        }

        section[data-testid="stSidebar"] .stButton > button[kind="primary"],
        section[data-testid="stSidebar"] .stButton > button[data-testid="baseButton-primary"] {
            background: linear-gradient(135deg, #ef4444 0%, #b91c1c 100%) !important;
            border: 1px solid #f87171 !important;
            color: #ffffff !important;
            font-weight: 700 !important;
            box-shadow: 0 2px 6px rgba(239, 68, 68, 0.35) !important;
        }

        /* Inputs & Global Search */
        div[data-testid="stTextInput"] input {
            background-color: #141722 !important;
            border: 1px solid #232938 !important;
            color: #f8fafc !important;
            border-radius: 4px !important;
            font-size: 12px !important;
        }

        div[data-testid="stTextInput"] input:focus {
            border-color: #38bdf8 !important;
            box-shadow: 0 0 0 1px #38bdf8 !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
