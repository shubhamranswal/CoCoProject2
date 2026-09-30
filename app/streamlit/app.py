"""Factory Reliability Command Center - Streamlit Foundation Shell.

Follows AGENT.md:
- Foundation smoke test verifying configuration, repository loading, and M204 retrieval
- Never claims in-memory is Snowflake
- Clean presentation without business logic embedded in rendering
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add project root directory to sys.path
file_path = Path(__file__).resolve()
repo_root = str(file_path.parent.parent.parent) if file_path.parent.name == "streamlit" else str(file_path.parent.parent)
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

import streamlit as st

from config import get_config
from domain.enums import HealthStatus
from repositories import get_repository

# Set page configuration
st.set_page_config(
    page_title="Factory Reliability Command Center",
    page_icon="🏭",
    layout="wide",
)

config = get_config()

# Header & Platform Info
st.title("🏭 Factory Reliability Command Center")
st.caption("Autonomous Reliability Intelligence for Industrial Operations — Foundational Architecture")

# Sidebar: Environment & Backend Configuration
with st.sidebar:
    st.header("⚙️ System Environment")
    st.write(f"**Environment:** `{config.env.upper()}`")
    
    backend_mode = st.radio(
        "Active Storage Backend:",
        options=["in_memory", "snowflake"],
        index=0 if config.storage_backend == "in_memory" else 1,
        help="Select between deterministic in-memory seeded store or Snowflake cloud database.",
    )

    if backend_mode == "snowflake":
        if config.snowflake.is_configured:
            st.success("🟢 Snowflake Configured")
            st.caption(f"Account: `{config.snowflake.account}`")
            st.caption(f"Database: `{config.snowflake.database}`")
        else:
            st.warning("⚠️ Snowflake Not Configured. Using In-Memory fallback.")
            st.caption("Set SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER, SNOWFLAKE_PASSWORD in environment.")
    else:
        st.info("🔵 Storage: In-Memory (Deterministic Reference State)")

# Initialize Repository
repo = get_repository(backend=backend_mode)
plant = repo.get_plant("PLANT-01")
m204 = repo.get_machine("M204")

st.divider()

# Primary Operational Smoke Test View
if not plant or not m204:
    st.error("Failed to load reference plant or machine M204.")
else:
    col_meta, col_status = st.columns([2, 1])

    with col_meta:
        st.subheader(f"📍 {plant.name} ({plant.plant_code})")
        st.write(f"**Location:** {plant.location} | **Timezone:** `{plant.timezone}`")
        st.write(f"**Target Machine:** `{m204.machine_code}` — **{m204.name}**")
        st.write(f"**Manufacturer & Model:** {m204.manufacturer} / `{m204.model}`")
        st.write(f"**Serial Number:** `{m204.serial_number}`")

    with col_status:
        st.metric(
            label="M204 Health Status",
            value=m204.health_status.value,
            delta="Normal" if m204.health_status == HealthStatus.HEALTHY else "Degraded",
            delta_color="normal" if m204.health_status == HealthStatus.HEALTHY else "inverse",
        )
        st.metric(label="Machine Operational State", value=m204.state.value)
        st.metric(label="Production Criticality", value=m204.criticality)

    st.divider()

    # M204 Subassembly Components & Sensors
    tab_components, tab_sensors = st.tabs(["🔩 Monitored Components", "📡 Active Telemetry Sensors"])

    with tab_components:
        components = repo.get_components("M204")
        st.write(f"Found **{len(components)}** monitored subassembly components:")
        for cmp in components:
            with st.expander(f"⚙️ {cmp.name} ({cmp.component_type})", expanded=True):
                st.write(f"- **ID:** `{cmp.component_id}`")
                st.write(f"- **Criticality:** `{cmp.criticality}`")
                st.write(f"- **Health:** `{cmp.health_status.value}`")

    with tab_sensors:
        sensors = repo.get_sensors("M204")
        st.write(f"Found **{len(sensors)}** calibrated telemetry sensors:")
        for s in sensors:
            st.markdown(
                f"- **{s.name}** (`{s.sensor_id}`) — Type: `{s.sensor_type.value}` | Unit: `{s.unit}` | "
                f"Range: `[{s.range_min}, {s.range_max}]` | Frequency: `{s.sampling_rate_hz} Hz`"
            )

st.divider()
st.caption(f"Storage Backend Status: **{backend_mode.upper()}** | Build Phase: **Phase 3 (Foundation)**")
