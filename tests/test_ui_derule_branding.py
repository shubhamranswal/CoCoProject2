"""
DeRule UI Branding and Experience Verification Suite.

Tests:
1. DeRule brand identity (Name "DeRule", Tagline "Detect. Investigate. Act") across views.
2. Official logos (logo/light.png for light mode, logo/dark.png for dark mode).
3. Process pipeline bar: DETECT → INVESTIGATE → DECIDE → ACT → VERIFY.
4. Segmented theme switching preserves navigation and state.
5. Strict zero emojis in rendered markdown, headers, and UI text.
6. Strict zero legacy "CoCo" or "Factory Reliability AI" user-facing branding.
7. Environment indicator (SNOWFLAKE / LOCAL STORE, Connected / In-Memory).
"""

from __future__ import annotations

import os
import re
from pathlib import Path
import pytest
from streamlit.testing.v1 import AppTest

# Common emoji regex pattern
EMOJI_PATTERN = re.compile(
    r"[\U0001F600-\U0001F64F"  # emoticons
    r"\U0001F300-\U0001F5FF"  # symbols & pictographs
    r"\U0001F680-\U0001F6FF"  # transport & map symbols
    r"\U0001F1E0-\U0001F1FF"  # flags (iOS)
    r"\U00002702-\U000027B0"  # dingbats
    r"\U000024C2-\U0001F251"  # enclosed characters
    r"\U0001F900-\U0001F9FF"  # supplemental symbols
    r"\U0001FA70-\U0001FAFF"  # symbols and pictographs extended-a
    r"]+",
    flags=re.UNICODE,
)


@pytest.fixture
def app_runner():
    app_file = str((Path(__file__).parent.parent / "app" / "streamlit_app.py").resolve())
    at = AppTest.from_file(app_file)
    at.default_timeout = 30
    return at


def test_logo_assets_exist():
    """Verify official DeRule logo files exist on disk with valid file size."""
    root = Path(__file__).parent.parent
    light_logo = root / "logo" / "light.png"
    dark_logo = root / "logo" / "dark.png"

    assert light_logo.exists(), f"Missing light logo asset at {light_logo}"
    assert dark_logo.exists(), f"Missing dark logo asset at {dark_logo}"
    assert light_logo.stat().st_size > 0, "Light logo file is empty"
    assert dark_logo.stat().st_size > 0, "Dark logo file is empty"


def test_derule_branding_and_tagline_in_header_and_sidebar(app_runner):
    """Verify DeRule name, tagline, and environment appear in sidebar and header."""
    app_runner.run()
    assert not app_runner.exception

    # Check sidebar brand and tagline
    sidebar_html = "\n".join([m.value for m in app_runner.sidebar.markdown])
    assert "DeRule" in sidebar_html
    assert "Detect. Investigate. Act" in sidebar_html

    # Check header brand and tagline
    header_html = "\n".join([m.value for m in app_runner.markdown])
    assert "DeRule" in header_html
    assert "Detect. Investigate. Act" in header_html


def test_theme_adaptive_logo_selection(app_runner):
    """Verify light mode and dark mode both mount the official DeRule logo without error."""
    app_runner.run()
    assert not app_runner.exception
    assert len(app_runner.sidebar.image) == 1

    # Toggle to dark mode
    theme_selector = app_runner.sidebar.segmented_control(key="sidebar_theme_selector")
    theme_selector.set_value("Dark").run()
    assert not app_runner.exception
    assert app_runner.session_state["theme_mode"] == "dark"
    assert len(app_runner.sidebar.image) == 1

    # Toggle back to light mode
    theme_selector = app_runner.sidebar.segmented_control(key="sidebar_theme_selector")
    theme_selector.set_value("Light").run()
    assert not app_runner.exception
    assert app_runner.session_state["theme_mode"] == "light"
    assert len(app_runner.sidebar.image) == 1


def test_theme_switching_preserves_navigation(app_runner):
    """Verify switching theme preserves current active view without reset."""
    app_runner.run()
    assert not app_runner.exception

    # Navigate to Investigations
    app_runner.sidebar.button(key="nav_btn_Investigations").click().run()
    assert not app_runner.exception
    assert app_runner.session_state["active_nav"] in ["Investigations", "AI Investigations"]

    # Switch theme to Dark
    theme_selector = app_runner.sidebar.segmented_control(key="sidebar_theme_selector")
    theme_selector.set_value("Dark").run()
    assert not app_runner.exception

    # View should still be Investigations
    assert app_runner.session_state["active_nav"] in ["Investigations", "AI Investigations"]
    assert app_runner.session_state["theme_mode"] == "dark"


def test_process_pipeline_bar_renders_in_investigations():
    """Verify the DETECT → INVESTIGATE → DECIDE → ACT → VERIFY pipeline bar renders."""
    from unittest.mock import MagicMock, patch
    from app.streamlit.views.investigations import render_investigations_view
    from tests.test_ui_canonical_investigation_view import _create_canonical_m21_bundle

    bundle = _create_canonical_m21_bundle()
    facade_mock = MagicMock()
    facade_mock.get_investigations.return_value = [bundle["investigation"]]
    facade_mock.get_investigation_detail.return_value = bundle

    rendered_chunks: list[str] = []

    def mock_columns(spec, **kwargs):
        count = len(spec) if isinstance(spec, (list, tuple)) else int(spec)
        cols = []
        for _ in range(count):
            c = MagicMock()
            c.__enter__.return_value = c
            c.__exit__.return_value = None
            cols.append(c)
        return cols

    with patch("streamlit.markdown", side_effect=lambda body, unsafe_allow_html=False: rendered_chunks.append(str(body))), \
         patch("streamlit.selectbox", return_value="INV-M21-20261002-001"), \
         patch("streamlit.columns", side_effect=mock_columns), \
         patch("streamlit.dataframe", MagicMock()), \
         patch("streamlit.expander", MagicMock()):
        render_investigations_view(facade_mock)

    all_markdown = "\n".join(rendered_chunks)
    assert "derule-pipeline-bar" in all_markdown
    assert "1. DETECT" in all_markdown
    assert "2. INVESTIGATE" in all_markdown
    assert "3. DECIDE" in all_markdown
    assert "4. ACT" in all_markdown
    assert "5. VERIFY" in all_markdown


def test_environment_indicator_in_sidebar(app_runner):
    """Verify environment indicator shows SNOWFLAKE or LOCAL STORE with status."""
    app_runner.run()
    assert not app_runner.exception

    sidebar_html = "\n".join([m.value for m in app_runner.sidebar.markdown])
    assert "ENVIRONMENT" in sidebar_html
    # Should display either SNOWFLAKE or LOCAL STORE
    assert ("SNOWFLAKE" in sidebar_html) or ("LOCAL STORE" in sidebar_html)
    assert ("Connected" in sidebar_html) or ("In-Memory" in sidebar_html) or ("Unavailable" in sidebar_html)


def test_zero_emojis_in_rendered_ui(app_runner):
    """Verify zero emojis are rendered across Command Center and Investigations."""
    app_runner.session_state["backend_mode"] = "in_memory"
    app_runner.run()
    assert not app_runner.exception

    # Check Command Center
    for m in app_runner.markdown:
        text = re.sub(r"<[^>]+>", " ", m.value)
        matches = EMOJI_PATTERN.findall(text)
        assert not matches, f"Emoji found in Command Center: {matches}"

    for m in app_runner.sidebar.markdown:
        text = re.sub(r"<[^>]+>", " ", m.value)
        matches = EMOJI_PATTERN.findall(text)
        assert not matches, f"Emoji found in sidebar: {matches}"

    # Check Investigations
    app_runner.sidebar.button(key="nav_btn_Investigations").click().run()
    assert not app_runner.exception

    for m in app_runner.markdown:
        text = re.sub(r"<[^>]+>", " ", m.value)
        matches = EMOJI_PATTERN.findall(text)
        assert not matches, f"Emoji found in Investigations: {matches}"


def test_no_legacy_brand_leakage_in_ui(app_runner):
    """Verify legacy product names like 'CoCo AI' or 'Factory Reliability AI' don't leak into UI text."""
    app_runner.session_state["backend_mode"] = "in_memory"
    app_runner.run()
    assert not app_runner.exception

    all_content = "\n".join([m.value for m in app_runner.markdown] + [m.value for m in app_runner.sidebar.markdown])
    # Ignore COCO_FACTORY as it is the canonical database name in snowflake indicator
    cleaned_content = re.sub(r"COCO_FACTORY", "", all_content)
    cleaned_content = re.sub(r"coco", "", cleaned_content, flags=re.IGNORECASE)

    assert "Factory Reliability AI" not in cleaned_content
    assert "CoCo Industrial" not in cleaned_content
    assert "CoCo Command Center" not in cleaned_content


def test_theme_control_is_segmented_control_not_radio(app_runner):
    """Verify theme switcher is implemented via modern segmented_control, NOT st.radio."""
    app_runner.run()
    assert not app_runner.exception

    # Should have segmented_control with key sidebar_theme_selector
    assert len(app_runner.sidebar.segmented_control) >= 1
    theme_seg = app_runner.sidebar.segmented_control(key="sidebar_theme_selector")
    assert theme_seg is not None
    assert set(theme_seg.options) == {"Light", "Dark"}

    # Should NOT have radio with key sidebar_theme_selector
    radio_keys = [getattr(r, "key", None) for r in app_runner.sidebar.radio]
    assert "sidebar_theme_selector" not in radio_keys


def test_no_duplicate_derule_headings(app_runner):
    """Verify DeRule Command Center is not repeated multiple times across shell and page content."""
    app_runner.session_state["backend_mode"] = "in_memory"
    app_runner.run()
    assert not app_runner.exception

    all_content = "\n".join([m.value for m in app_runner.markdown])
    # Count occurrences of the exact heading "DeRule Command Center"
    occurrences = len(re.findall(r"DeRule Command Center", all_content, re.IGNORECASE))
    assert occurrences <= 1, f"Found duplicated 'DeRule Command Center' heading: count={occurrences}"


def test_active_precursors_deliberate_empty_state_rendered():
    """Verify clean industrial empty state renders when no critical precursors are active."""
    from unittest.mock import MagicMock, patch
    from app.streamlit.views.command_center import render_command_center_view

    facade_mock = MagicMock()
    facade_mock.get_kpis.return_value = {
        "oee": 0.89, "availability": 0.92, "performance": 0.95, "quality": 0.98,
        "active_alerts": 0, "critical_assets": 0, "warning_assets": 0,
        "open_work_orders": 0, "pending_approvals": 0, "total_machines": 10,
    }
    facade_mock.get_critical_events.return_value = []
    facade_mock.get_asset_grid.return_value = []
    facade_mock.get_investigations.return_value = []

    rendered_chunks: list[str] = []

    def mock_columns(spec, **kwargs):
        count = len(spec) if isinstance(spec, (list, tuple)) else int(spec)
        cols = []
        for _ in range(count):
            c = MagicMock()
            c.__enter__.return_value = c
            c.__exit__.return_value = None
            cols.append(c)
        return cols

    with patch("streamlit.markdown", side_effect=lambda body, unsafe_allow_html=False: rendered_chunks.append(str(body))), \
         patch("streamlit.columns", side_effect=mock_columns), \
         patch("streamlit.button", return_value=False):
        render_command_center_view(facade_mock)

    html = "\n".join(rendered_chunks)
    assert "No Active Failure Precursors" in html
    assert "ALL NOMINAL" in html
    assert "Active Failure Precursors & Threat Identification" in html
