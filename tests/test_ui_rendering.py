"""Tests for Streamlit UI Rendering and Navigation.

Validates that:
- The Streamlit application renders without exceptions.
- Default theme is Light mode.
- Both Light and Dark theme modes render cleanly.
- All 12 views in the information architecture render without exceptions.
"""

from __future__ import annotations

from pathlib import Path
import pytest
from streamlit.testing.v1 import AppTest


APP_PATH = str((Path(__file__).parent.parent / "app" / "streamlit_app.py").resolve())

VIEWS = [
    "Command Center",
    "Assets",
    "Reliability",
    "OEE",
    "Quality",
    "Maintenance",
    "Work Orders",
    "AI Investigations",
    "Knowledge",
    "Agent Activity",
    "Data & Pipelines",
    "Settings",
]


def test_ui_default_theme_is_light() -> None:
    """Verify that default theme initialized in session state is light."""
    at = AppTest.from_file(APP_PATH)
    at.run(timeout=10)
    assert not at.exception
    assert at.session_state["theme_mode"] == "light"


def test_theme_mode_toggle_between_light_and_dark() -> None:
    """Verify theme toggle between light and dark works cleanly via the UI."""
    at = AppTest.from_file(APP_PATH)
    at.run(timeout=10)
    assert not at.exception
    assert at.session_state["theme_mode"] == "light"

    # Toggle to Dark mode via UI control
    at.sidebar.segmented_control(key="sidebar_theme_selector").set_value("Dark").run()
    assert not at.exception
    assert at.session_state["theme_mode"] == "dark"

    # Toggle back to Light mode via UI control
    at.sidebar.segmented_control(key="sidebar_theme_selector").set_value("Light").run()
    assert not at.exception
    assert at.session_state["theme_mode"] == "light"


@pytest.mark.parametrize("view_name", VIEWS)
def test_all_12_views_render_in_light_mode(view_name: str) -> None:
    """Verify each of the 12 views renders cleanly in default light mode."""
    at = AppTest.from_file(APP_PATH)
    at.run(timeout=10)
    assert not at.exception

    at.session_state["theme_mode"] = "light"
    at.session_state["active_nav"] = view_name
    at.run(timeout=10)
    assert not at.exception


@pytest.mark.parametrize("view_name", VIEWS)
def test_all_12_views_render_in_dark_mode(view_name: str) -> None:
    """Verify each of the 12 views renders cleanly in dark mode."""
    at = AppTest.from_file(APP_PATH)
    at.run(timeout=10)
    assert not at.exception

    at.session_state["theme_mode"] = "dark"
    at.session_state["active_nav"] = view_name
    at.run(timeout=10)
    assert not at.exception
