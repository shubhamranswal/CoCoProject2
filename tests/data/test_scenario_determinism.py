"""Tests verifying M204 scenario determinism and physical progression.

Strict adherence to AGENT.md:
- Deterministic behavior: identical inputs yield identical outputs bit-for-bit.
- Zero random.random() or non-reproducible state.
- Physical plausibility across all progression phases.
"""

from datetime import datetime, timezone
import pytest

from data.scenarios.m204_scenario import (
    M204ScenarioEngine,
    ScenarioPhase,
    deterministic_noise,
)


def test_deterministic_noise_reproducibility():
    """Verify that deterministic_noise returns exact same float for identical timestamp and sensor."""
    ts = datetime(2026, 3, 30, 10, 15, 0, tzinfo=timezone.utc)
    sensor = "SEN-M204-VIB"

    n1 = deterministic_noise(ts, sensor, amplitude=1.0)
    n2 = deterministic_noise(ts, sensor, amplitude=1.0)
    assert n1 == n2
    assert isinstance(n1, float)


def test_scenario_timeseries_determinism():
    """Verify two independent runs of generate_timeseries produce identical measurements bit-for-bit."""
    engine1 = M204ScenarioEngine(machine_id="M204")
    engine2 = M204ScenarioEngine(machine_id="M204")

    start_time = datetime(2026, 3, 30, 8, 0, 0, tzinfo=timezone.utc)
    ts1 = engine1.generate_timeseries(phase=ScenarioPhase.ANOMALOUS, num_points=12, start_time=start_time)
    ts2 = engine2.generate_timeseries(phase=ScenarioPhase.ANOMALOUS, num_points=12, start_time=start_time)

    assert len(ts1) == len(ts2) == 48  # 12 points * 4 sensors
    for m1, m2 in zip(ts1, ts2):
        assert m1.measurement_id == m2.measurement_id
        assert m1.machine_id == m2.machine_id
        assert m1.sensor_id == m2.sensor_id
        assert m1.timestamp == m2.timestamp
        assert m1.value == m2.value
        assert m1.unit == m2.unit


def test_physical_progression_monotonic_vibration():
    """Verify that vibration and temperature increase monotonically across degradation phases."""
    engine = M204ScenarioEngine(machine_id="M204")
    t0 = datetime(2026, 3, 30, 8, 0, 0, tzinfo=timezone.utc)

    p_norm = engine.get_phase_profile(ScenarioPhase.NORMAL, t0)
    p_deg = engine.get_phase_profile(ScenarioPhase.DEGRADING, t0)
    p_anom = engine.get_phase_profile(ScenarioPhase.ANOMALOUS, t0)
    p_high = engine.get_phase_profile(ScenarioPhase.HIGH_RISK, t0)

    # Vibration should strictly rise
    assert p_norm["vibration_rms"] < p_deg["vibration_rms"] < p_anom["vibration_rms"] < p_high["vibration_rms"]
    # Temperature should strictly rise
    assert p_norm["temperature_c"] < p_deg["temperature_c"] < p_anom["temperature_c"] < p_high["temperature_c"]


def test_recovery_phase_restores_nominal():
    """Verify that after repair, RECOVERED phase returns to nominal baselines."""
    engine = M204ScenarioEngine(machine_id="M204")
    t0 = datetime(2026, 3, 30, 8, 0, 0, tzinfo=timezone.utc)

    p_norm = engine.get_phase_profile(ScenarioPhase.NORMAL, t0)
    p_rec = engine.get_phase_profile(ScenarioPhase.RECOVERED, t0)

    assert abs(p_norm["vibration_rms"] - p_rec["vibration_rms"]) < 0.05
    assert abs(p_norm["temperature_c"] - p_rec["temperature_c"]) < 2.0


def test_operational_context_downtime_mapping():
    """Verify that downtime events are generated only during anomalous/high risk phases."""
    engine = M204ScenarioEngine(machine_id="M204")

    prod_norm, dt_norm = engine.generate_operational_context(ScenarioPhase.NORMAL)
    assert dt_norm is None
    assert prod_norm.scrap_units < 20

    prod_anom, dt_anom = engine.generate_operational_context(ScenarioPhase.ANOMALOUS)
    assert dt_anom is not None
    assert dt_anom.category == "UNPLANNED"
    assert dt_anom.duration_minutes > 0

    prod_high, dt_high = engine.generate_operational_context(ScenarioPhase.HIGH_RISK)
    assert dt_high is not None
    assert dt_high.duration_minutes >= 60.0
