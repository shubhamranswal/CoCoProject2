"""Industrial SaaS Dashboard Styling and Custom CSS.

Follows Visual Direction in AGENT.md & Production UI Requirements:
- Default theme: Light mode (option to change to dark and back to light)
- Real industrial SaaS/dashboard console feel (clean, technical, high information density)
- Typography: Poppins (Google Fonts) with clean sans-serif fallbacks
- Buttons: Rounded (8px), modern dashboard style, not sharp rectangular blocks
- Sidebar: Persistent, structured navigation with clear active-state treatment
- Cards: Subtle borders, clean spacing, clear visual hierarchy
- Tables: Dense enough for operational use, but readable
- Status indicators: Professional badges and dots, NO EMOJIS in product UI
- Responsive desktop layout
"""

from __future__ import annotations

import streamlit as st


def apply_industrial_theme(theme_mode: str = "light") -> None:
    """Inject custom industrial SaaS stylesheet into Streamlit.
    
    Supports both 'light' (default) and 'dark' themes with CSS variables.
    """
    is_dark = (theme_mode.lower() == "dark")

    if is_dark:
        # Dark Mode Palette (Industrial Slate Dark)
        vars_css = """
        :root {
            --bg-app: #0b0f17;
            --bg-sidebar: #111827;
            --bg-card: #151d2c;
            --bg-card-subtle: #1c2638;
            --bg-hover: #222f46;
            --border-subtle: #243044;
            --border-strong: #33435c;
            
            --text-primary: #f8fafc;
            --text-secondary: #cbd5e1;
            --text-muted: #94a3b8;
            
            --primary-accent: #38bdf8;
            --primary-accent-hover: #0ea5e9;
            
            --btn-sec-bg: #162030;
            --btn-sec-border: #28374d;
            --btn-sec-text: #e2e8f0;
            --btn-sec-hover-bg: #1e2c42;
            --btn-sec-hover-border: #38bdf8;
            --btn-sec-hover-text: #ffffff;
            
            --btn-prim-bg: linear-gradient(135deg, #0284c7 0%, #0369a1 100%);
            --btn-prim-border: #0284c7;
            --btn-prim-text: #ffffff;
            
            --nav-btn-bg: #151d2c;
            --nav-btn-border: #222e42;
            --nav-btn-text: #94a3b8;
            --nav-btn-hover-bg: #1c2638;
            --nav-btn-hover-text: #f8fafc;
            --nav-btn-active-bg: #0284c7;
            --nav-btn-active-border: #38bdf8;
            --nav-btn-active-text: #ffffff;

            --card-hero-bg: linear-gradient(135deg, #1f1418 0%, #171c26 100%);
            --card-hero-border: #ef4444;
            --card-hero-bar: #ef4444;
            
            --card-warn-bg: linear-gradient(135deg, #1f1a14 0%, #171c26 100%);
            --card-warn-border: #f59e0b;
            --card-warn-bar: #f59e0b;
            
            --card-health-bg: linear-gradient(135deg, #131e17 0%, #171c26 100%);
            --card-health-border: #10b981;
            --card-health-bar: #10b981;

            --badge-crit-bg: rgba(239, 68, 68, 0.18);
            --badge-crit-border: rgba(239, 68, 68, 0.4);
            --badge-crit-text: #fca5a5;
            
            --badge-warn-bg: rgba(245, 158, 11, 0.18);
            --badge-warn-border: rgba(245, 158, 11, 0.4);
            --badge-warn-text: #fcd34d;
            
            --badge-health-bg: rgba(16, 185, 129, 0.18);
            --badge-health-border: rgba(16, 185, 129, 0.4);
            --badge-health-text: #6ee7b7;
            
            --badge-info-bg: rgba(56, 189, 248, 0.18);
            --badge-info-border: rgba(56, 189, 248, 0.4);
            --badge-info-text: #7dd3fc;
            
            --badge-neutral-bg: rgba(148, 163, 184, 0.14);
            --badge-neutral-border: rgba(148, 163, 184, 0.28);
            --badge-neutral-text: #cbd5e1;
            
            --card-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.35);
            --toolbar-bg: #141b28;
            --box-subtle-bg: rgba(0, 0, 0, 0.25);
            --table-header-bg: #141c2b;
            --table-row-alt-bg: #131a26;
            --table-hover-bg: #1a2436;
        }
        """
    else:
        # Light Mode Palette (Default — Professional Industrial White/Slate)
        vars_css = """
        :root {
            --bg-app: #f8fafc;
            --bg-sidebar: #ffffff;
            --bg-card: #ffffff;
            --bg-card-subtle: #f1f5f9;
            --bg-hover: #e2e8f0;
            --border-subtle: #e2e8f0;
            --border-strong: #cbd5e1;
            
            --text-primary: #0f172a;
            --text-secondary: #334155;
            --text-muted: #64748b;
            
            --primary-accent: #0284c7;
            --primary-accent-hover: #0369a1;
            
            --btn-sec-bg: #ffffff;
            --btn-sec-border: #cbd5e1;
            --btn-sec-text: #1e293b;
            --btn-sec-hover-bg: #f8fafc;
            --btn-sec-hover-border: #0284c7;
            --btn-sec-hover-text: #0284c7;
            
            --btn-prim-bg: linear-gradient(135deg, #0284c7 0%, #0369a1 100%);
            --btn-prim-border: #0284c7;
            --btn-prim-text: #ffffff;
            
            --nav-btn-bg: #ffffff;
            --nav-btn-border: #e2e8f0;
            --nav-btn-text: #475569;
            --nav-btn-hover-bg: #f1f5f9;
            --nav-btn-hover-text: #0f172a;
            --nav-btn-active-bg: #0f172a;
            --nav-btn-active-border: #0f172a;
            --nav-btn-active-text: #ffffff;

            --card-hero-bg: #fff5f5;
            --card-hero-border: #fecaca;
            --card-hero-bar: #dc2626;
            
            --card-warn-bg: #fffbeb;
            --card-warn-border: #fef3c7;
            --card-warn-bar: #d97706;
            
            --card-health-bg: #f0fdf4;
            --card-health-border: #dcfce7;
            --card-health-bar: #16a34a;

            --badge-crit-bg: #fef2f2;
            --badge-crit-border: #fecaca;
            --badge-crit-text: #dc2626;
            
            --badge-warn-bg: #fffbeb;
            --badge-warn-border: #fde68a;
            --badge-warn-text: #b45309;
            
            --badge-health-bg: #f0fdf4;
            --badge-health-border: #bbf7d0;
            --badge-health-text: #15803d;
            
            --badge-info-bg: #f0f9ff;
            --badge-info-border: #bae6fd;
            --badge-info-text: #0369a1;
            
            --badge-neutral-bg: #f1f5f9;
            --badge-neutral-border: #e2e8f0;
            --badge-neutral-text: #475569;
            
            --card-shadow: 0 1px 3px 0 rgba(15, 23, 42, 0.06), 0 1px 2px -1px rgba(15, 23, 42, 0.04);
            --toolbar-bg: #f8fafc;
            --box-subtle-bg: #f8fafc;
            --table-header-bg: #f1f5f9;
            --table-row-alt-bg: #fafafa;
            --table-hover-bg: #f1f5f9;
        }
        """

    full_css = f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700&display=swap');

        {vars_css}

        /* Global Font & Canvas */
        html, body, [class*="css"], .stApp {{
            font-family: 'Poppins', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important;
            background-color: var(--bg-app) !important;
            color: var(--text-primary) !important;
        }}

        /* Sidebar Styling */
        section[data-testid="stSidebar"] {{
            background-color: var(--bg-sidebar) !important;
            border-right: 1px solid var(--border-subtle) !important;
        }}

        section[data-testid="stSidebar"] > div:first-child {{
            padding-top: 1.5rem !important;
        }}

        /* Common Text Utilities */
        .text-primary {{ color: var(--text-primary) !important; }}
        .text-secondary {{ color: var(--text-secondary) !important; }}
        .text-muted {{ color: var(--text-muted) !important; }}
        .text-crit {{ color: #dc2626 !important; font-weight: 600; }}
        .text-warn {{ color: #d97706 !important; font-weight: 600; }}
        .text-health {{ color: #16a34a !important; font-weight: 600; }}
        .text-accent {{ color: var(--primary-accent) !important; font-weight: 600; }}

        /* Status Dot Indicators (Zero Emojis) */
        .status-dot {{
            display: inline-block;
            width: 8px;
            height: 8px;
            border-radius: 50%;
            margin-right: 6px;
            vertical-align: middle;
        }}
        .status-dot-critical {{ background-color: #dc2626; box-shadow: 0 0 0 2px rgba(220, 38, 38, 0.2); }}
        .status-dot-warning {{ background-color: #d97706; box-shadow: 0 0 0 2px rgba(217, 119, 6, 0.2); }}
        .status-dot-healthy {{ background-color: #16a34a; box-shadow: 0 0 0 2px rgba(22, 163, 74, 0.2); }}
        .status-dot-info {{ background-color: #0284c7; box-shadow: 0 0 0 2px rgba(2, 132, 199, 0.2); }}
        .status-dot-neutral {{ background-color: #94a3b8; }}

        /* Professional Semantic Badges */
        .badge {{
            display: inline-flex;
            align-items: center;
            padding: 3px 8px;
            font-size: 11px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            border-radius: 6px;
            line-height: 1.2;
            vertical-align: middle;
        }}
        .badge-critical {{
            background-color: var(--badge-crit-bg);
            color: var(--badge-crit-text);
            border: 1px solid var(--badge-crit-border);
        }}
        .badge-warning {{
            background-color: var(--badge-warn-bg);
            color: var(--badge-warn-text);
            border: 1px solid var(--badge-warn-border);
        }}
        .badge-healthy {{
            background-color: var(--badge-health-bg);
            color: var(--badge-health-text);
            border: 1px solid var(--badge-health-border);
        }}
        .badge-info {{
            background-color: var(--badge-info-bg);
            color: var(--badge-info-text);
            border: 1px solid var(--badge-info-border);
        }}
        .badge-neutral {{
            background-color: var(--badge-neutral-bg);
            color: var(--badge-neutral-text);
            border: 1px solid var(--badge-neutral-border);
        }}

        /* Industrial Cards */
        .ind-card {{
            background-color: var(--bg-card);
            border: 1px solid var(--border-subtle);
            border-radius: 8px;
            padding: 14px 18px;
            margin-bottom: 12px;
            box-shadow: var(--card-shadow);
        }}

        .ind-card-hero {{
            background: var(--card-hero-bg);
            border: 1px solid var(--card-hero-border);
            border-left: 4px solid var(--card-hero-bar);
            border-radius: 8px;
            padding: 18px 22px;
            margin-bottom: 16px;
            box-shadow: var(--card-shadow);
        }}

        .ind-card-warning {{
            background: var(--card-warn-bg);
            border: 1px solid var(--card-warn-border);
            border-left: 4px solid var(--card-warn-bar);
            border-radius: 8px;
            padding: 16px 20px;
            margin-bottom: 14px;
            box-shadow: var(--card-shadow);
        }}

        .ind-card-success {{
            background: var(--card-health-bg);
            border: 1px solid var(--card-health-border);
            border-left: 4px solid var(--card-health-bar);
            border-radius: 8px;
            padding: 16px 20px;
            margin-bottom: 14px;
            box-shadow: var(--card-shadow);
        }}

        /* Metric Titles & Values */
        .metric-label {{
            font-size: 11px;
            font-weight: 600;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 4px;
        }}
        .metric-value {{
            font-size: 24px;
            font-weight: 700;
            color: var(--text-primary);
            line-height: 1.15;
        }}
        .metric-delta {{
            font-size: 11px;
            margin-top: 4px;
            font-weight: 500;
        }}

        /* Evidence Box */
        .evidence-box {{
            background-color: var(--box-subtle-bg);
            border: 1px solid var(--border-subtle);
            border-radius: 6px;
            padding: 10px 14px;
            margin-bottom: 8px;
        }}

        /* Hero Action Toolbar */
        .hero-action-toolbar {{
            background-color: var(--toolbar-bg);
            border: 1px solid var(--card-hero-border);
            border-top: none;
            border-left: 4px solid var(--card-hero-bar);
            border-radius: 0 0 8px 8px;
            padding: 12px 18px;
            margin-top: -16px;
            margin-bottom: 16px;
        }}

        /* Timeline Items */
        .timeline-step {{
            border-left: 2px solid var(--border-strong);
            padding-left: 14px;
            margin-left: 8px;
            margin-bottom: 12px;
            position: relative;
        }}
        .timeline-step::before {{
            content: "";
            position: absolute;
            left: -6px;
            top: 4px;
            width: 10px;
            height: 10px;
            border-radius: 50%;
            background-color: #0284c7;
        }}
        .timeline-step.completed::before {{
            background-color: #16a34a;
        }}
        .timeline-step.critical::before {{
            background-color: #dc2626;
        }}

        /* Modern Dashboard Rounded Buttons */
        .stButton > button,
        button[kind="secondary"],
        button[data-testid="baseButton-secondary"] {{
            background-color: var(--btn-sec-bg) !important;
            color: var(--btn-sec-text) !important;
            border: 1px solid var(--btn-sec-border) !important;
            border-radius: 8px !important;
            font-size: 13px !important;
            font-weight: 600 !important;
            font-family: 'Poppins', sans-serif !important;
            padding: 7px 14px !important;
            box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04) !important;
            transition: all 0.15s ease-in-out !important;
        }}

        .stButton > button:hover,
        button[kind="secondary"]:hover,
        button[data-testid="baseButton-secondary"]:hover {{
            background-color: var(--btn-sec-hover-bg) !important;
            border-color: var(--btn-sec-hover-border) !important;
            color: var(--btn-sec-hover-text) !important;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.08) !important;
        }}

        .stButton > button:active,
        button[kind="secondary"]:active,
        button[data-testid="baseButton-secondary"]:active {{
            transform: translateY(1px);
        }}

        /* Primary Action Buttons */
        .stButton > button[kind="primary"],
        button[kind="primary"],
        button[data-testid="baseButton-primary"] {{
            background: var(--btn-prim-bg) !important;
            border: 1px solid var(--btn-prim-border) !important;
            color: var(--btn-prim-text) !important;
            border-radius: 8px !important;
            font-size: 13px !important;
            font-weight: 600 !important;
            font-family: 'Poppins', sans-serif !important;
            padding: 7px 16px !important;
            box-shadow: 0 1px 3px rgba(2, 132, 199, 0.25) !important;
            transition: all 0.15s ease-in-out !important;
        }}

        .stButton > button[kind="primary"]:hover,
        button[kind="primary"]:hover,
        button[data-testid="baseButton-primary"]:hover {{
            filter: brightness(1.08) !important;
            box-shadow: 0 3px 6px rgba(2, 132, 199, 0.35) !important;
        }}

        /* Disabled Buttons */
        .stButton > button:disabled,
        button[disabled],
        button:disabled {{
            background-color: var(--bg-hover) !important;
            color: var(--text-muted) !important;
            border: 1px solid var(--border-subtle) !important;
            border-radius: 8px !important;
            cursor: not-allowed !important;
            opacity: 0.65 !important;
            box-shadow: none !important;
        }}

        /* Sidebar Navigation Buttons with Clear Active State */
        section[data-testid="stSidebar"] .stButton > button {{
            background-color: var(--nav-btn-bg) !important;
            color: var(--nav-btn-text) !important;
            border: 1px solid var(--nav-btn-border) !important;
            border-radius: 8px !important;
            text-align: left !important;
            justify-content: flex-start !important;
            font-size: 13px !important;
            font-weight: 500 !important;
            font-family: 'Poppins', sans-serif !important;
            padding: 8px 14px !important;
            margin-bottom: 3px !important;
            box-shadow: none !important;
            transition: all 0.15s ease-in-out !important;
        }}

        section[data-testid="stSidebar"] .stButton > button:hover {{
            background-color: var(--nav-btn-hover-bg) !important;
            color: var(--nav-btn-hover-text) !important;
            border-color: var(--border-strong) !important;
        }}

        /* Active Navigation Item (Styled via Primary kind) */
        section[data-testid="stSidebar"] .stButton > button[kind="primary"],
        section[data-testid="stSidebar"] .stButton > button[data-testid="baseButton-primary"] {{
            background-color: var(--nav-btn-active-bg) !important;
            border: 1px solid var(--nav-btn-active-border) !important;
            color: var(--nav-btn-active-text) !important;
            font-weight: 600 !important;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.12) !important;
        }}

        /* Inputs, Selectboxes & Search */
        div[data-testid="stTextInput"] input,
        div[data-testid="stSelectbox"] > div > div {{
            background-color: var(--bg-card) !important;
            border: 1px solid var(--border-subtle) !important;
            color: var(--text-primary) !important;
            border-radius: 8px !important;
            font-size: 13px !important;
            font-family: 'Poppins', sans-serif !important;
        }}

        div[data-testid="stTextInput"] input:focus {{
            border-color: var(--primary-accent) !important;
            box-shadow: 0 0 0 1px var(--primary-accent) !important;
        }}

        /* Expanders */
        div[data-testid="stExpander"] {{
            background-color: var(--bg-card) !important;
            border: 1px solid var(--border-subtle) !important;
            border-radius: 8px !important;
            box-shadow: var(--card-shadow) !important;
            margin-bottom: 8px !important;
        }}

        div[data-testid="stExpander"] summary {{
            font-size: 13px !important;
            font-weight: 600 !important;
            color: var(--text-primary) !important;
            padding: 10px 14px !important;
        }}

        /* Dense Operational Tables */
        .dense-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 12px;
            font-family: 'Poppins', sans-serif;
            background-color: var(--bg-card);
            border: 1px solid var(--border-subtle);
            border-radius: 8px;
            overflow: hidden;
            margin-top: 8px;
            margin-bottom: 12px;
        }}

        .dense-table th {{
            background-color: var(--table-header-bg);
            color: var(--text-muted);
            font-weight: 600;
            text-align: left;
            padding: 8px 12px;
            text-transform: uppercase;
            font-size: 11px;
            letter-spacing: 0.04em;
            border-bottom: 1px solid var(--border-subtle);
        }}

        .dense-table td {{
            padding: 8px 12px;
            border-bottom: 1px solid var(--border-subtle);
            color: var(--text-primary);
        }}

        .dense-table tr:last-child td {{
            border-bottom: none;
        }}

        .dense-table tr:hover td {{
            background-color: var(--table-hover-bg);
        }}
        </style>
    """
    st.markdown(full_css, unsafe_allow_html=True)
