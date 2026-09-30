"""Streamlit View Components Package.

Exports all primary command center views for routing.
"""

from app.streamlit.views.agent_activity import render_agent_activity_view
from app.streamlit.views.assets import render_assets_view
from app.streamlit.views.command_center import render_command_center_view
from app.streamlit.views.investigations import render_investigations_view
from app.streamlit.views.knowledge import render_knowledge_view
from app.streamlit.views.maintenance import render_maintenance_view
from app.streamlit.views.oee import render_oee_view
from app.streamlit.views.pipelines import render_pipelines_view
from app.streamlit.views.quality import render_quality_view
from app.streamlit.views.reliability import render_reliability_view
from app.streamlit.views.settings import render_settings_view
from app.streamlit.views.work_orders import render_work_orders_view

__all__ = [
    "render_agent_activity_view",
    "render_assets_view",
    "render_command_center_view",
    "render_investigations_view",
    "render_knowledge_view",
    "render_maintenance_view",
    "render_oee_view",
    "render_pipelines_view",
    "render_quality_view",
    "render_reliability_view",
    "render_settings_view",
    "render_work_orders_view",
]
