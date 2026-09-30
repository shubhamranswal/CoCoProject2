"""Industrial Plotly Telemetry Charts Component.

Follows Sections 14 & 15 of AGENT.md:
- Vibration trend with baseline, warning, and critical thresholds
- Temperature trend with baseline and critical limits
- Signal Correlation view (Vibration + Temperature + Failure Risk) demonstrating harmonic runaway
- Dark industrial aesthetic with crisp traces
"""

from __future__ import annotations

from typing import Any, Dict, List
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st


DARK_LAYOUT = dict(
    paper_bgcolor="#12151c",
    plot_bgcolor="#161922",
    font=dict(color="#cbd5e1", size=11),
    margin=dict(l=40, r=40, t=35, b=30),
    xaxis=dict(gridcolor="#232936", zerolinecolor="#232936"),
    yaxis=dict(gridcolor="#232936", zerolinecolor="#232936"),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1.0),
)


def render_vibration_trend_chart(telemetry_data: Dict[str, Any]) -> None:
    """Render Vibration RMS trend chart with baseline and warning/critical thresholds."""
    measurements = telemetry_data.get("vibration_measurements", [])
    baseline = telemetry_data.get("vibration_baseline")

    if not measurements:
        st.info("No vibration telemetry measurements available.")
        return

    times = [m.timestamp for m in measurements]
    vals = [m.value for m in measurements]

    fig = go.Figure()

    # Actual measurements
    fig.add_trace(
        go.Scatter(
            x=times,
            y=vals,
            mode="lines+markers",
            name="Vibration RMS",
            line=dict(color="#ef4444", width=2.5),
            marker=dict(size=5, color="#ef4444"),
        )
    )

    # Threshold horizontal reference lines
    base_val = baseline.baseline_mean if baseline else 0.450
    warn_val = baseline.warning_threshold if baseline else 0.700
    crit_val = baseline.critical_threshold if baseline else 0.850

    fig.add_hline(y=base_val, line_dash="dash", line_color="#10b981", annotation_text=f"Baseline ({base_val}g)", annotation_position="top left")
    fig.add_hline(y=warn_val, line_dash="dash", line_color="#f59e0b", annotation_text=f"Warning ({warn_val}g)", annotation_position="top left")
    fig.add_hline(y=crit_val, line_dash="dash", line_color="#dc2626", annotation_text=f"Critical ({crit_val}g)", annotation_position="top left")

    fig.update_layout(
        **DARK_LAYOUT,
        title="Vibration RMS Trend (g)",
        yaxis_title="Vibration (g)",
        height=320,
    )
    st.plotly_chart(fig, use_container_width=True)


def render_temperature_trend_chart(telemetry_data: Dict[str, Any]) -> None:
    """Render Bearing Temperature trend chart with nominal baseline and limits."""
    measurements = telemetry_data.get("temperature_measurements", [])
    baseline = telemetry_data.get("temperature_baseline")

    if not measurements:
        st.info("No temperature telemetry measurements available.")
        return

    times = [m.timestamp for m in measurements]
    vals = [m.value for m in measurements]

    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=times,
            y=vals,
            mode="lines+markers",
            name="RTD Bearing Temp",
            line=dict(color="#f97316", width=2.5),
            marker=dict(size=5, color="#f97316"),
        )
    )

    base_val = baseline.baseline_mean if baseline else 58.5
    crit_val = baseline.critical_threshold if baseline else 80.0

    fig.add_hline(y=base_val, line_dash="dash", line_color="#10b981", annotation_text=f"Baseline ({base_val}°C)", annotation_position="top left")
    fig.add_hline(y=crit_val, line_dash="dash", line_color="#ef4444", annotation_text=f"Critical Alarm ({crit_val}°C)", annotation_position="top left")

    fig.update_layout(
        **DARK_LAYOUT,
        title="Bearing Temperature Trend (°C)",
        yaxis_title="Temp (°C)",
        height=320,
    )
    st.plotly_chart(fig, use_container_width=True)


def render_signal_correlation_chart(telemetry_data: Dict[str, Any]) -> None:
    """Render synchronized 3-signal correlation chart: Vibration + Temperature + Failure Risk."""
    vib_meas = telemetry_data.get("vibration_measurements", [])
    temp_meas = telemetry_data.get("temperature_measurements", [])

    if not vib_meas or not temp_meas:
        st.info("Insufficient synchronous measurements for correlation analysis.")
        return

    times = [m.timestamp for m in vib_meas]
    vibs = [m.value for m in vib_meas]
    temps = [m.value for m in temp_meas[:len(times)]]

    # Calculate synthetic deterministic risk trajectory matching vibration progression
    risks = [round(min(1.0, max(0.1, (v - 0.45) / 0.50 * 0.90 + 0.10)), 3) for v in vibs]

    fig = make_subplots(
        rows=3,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.08,
        subplot_titles=(
            "Vibration RMS (Harmonic Spike)",
            "Drive-End Bearing Temperature (Thermal Runaway)",
            "Predicted Failure Risk (Horizon: 72h)",
        ),
    )

    fig.add_trace(
        go.Scatter(x=times, y=vibs, mode="lines", name="Vibration (g)", line=dict(color="#ef4444", width=2)),
        row=1, col=1,
    )
    fig.add_trace(
        go.Scatter(x=times, y=temps, mode="lines", name="Temp (°C)", line=dict(color="#f97316", width=2)),
        row=2, col=1,
    )
    fig.add_trace(
        go.Scatter(x=times, y=risks, mode="lines+markers", name="Risk Score", line=dict(color="#eab308", width=2)),
        row=3, col=1,
    )

    fig.update_layout(
        **DARK_LAYOUT,
        height=480,
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True)
