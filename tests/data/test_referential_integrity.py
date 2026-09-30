"""Tests verifying referential integrity across the industrial hierarchy."""

from datetime import datetime, timezone
import pytest

from domain.models import TelemetryMeasurement
from repositories.memory.memory_repository import InMemoryRepository
from data.scenarios.m204_scenario import M204ScenarioEngine, ScenarioPhase


def test_m204_hierarchy_referential_integrity(memory_repo: InMemoryRepository):
    # 1. Fetch M204
    m204 = memory_repo.get_machine("M204")
    assert m204 is not None, "Machine M204 must exist in reference seed"

    # 2. Verify Line relationship
    lines = memory_repo.list_lines("PLANT-01")
    line_ids = [line.line_id for line in lines]
    assert m204.line_id in line_ids, f"M204 line {m204.line_id} must belong to PLANT-01"
    assert m204.line_id == "LINE-B"

    # 3. Verify Plant relationship
    target_line = next(line for line in lines if line.line_id == m204.line_id)
    plant = memory_repo.get_plant(target_line.plant_id)
    assert plant is not None
    assert plant.plant_id == "PLANT-01"


def test_m204_sensor_and_telemetry_referential_integrity(memory_repo: InMemoryRepository):
    # Fetch M204
    m204 = memory_repo.get_machine("M204")
    assert m204 is not None

    # Fetch Sensors
    sensors = memory_repo.get_sensors("M204")
    assert len(sensors) >= 4
    sensor_map = {s.sensor_id: s for s in sensors}

    # Verify sensor components link back to M204 components
    components = memory_repo.get_components("M204")
    comp_ids = {c.component_id for c in components}
    for s in sensors:
        assert s.machine_id == "M204"
        if s.component_id:
            assert s.component_id in comp_ids, f"Sensor {s.sensor_id} component {s.component_id} not in M204 components"

    # Generate telemetry measurement linked to a valid sensor
    vib_sensor = sensor_map["SEN-M204-VIB"]
    measurement = TelemetryMeasurement(
        measurement_id="MEAS-M204-TEST-01",
        machine_id=m204.machine_id,
        sensor_id=vib_sensor.sensor_id,
        timestamp=datetime.now(timezone.utc),
        value=0.48,
        unit=vib_sensor.unit,
        quality="VALID",
    )
    memory_repo.save_measurements([measurement])

    # Retrieve and verify
    retrieved = memory_repo.get_recent_measurements("M204", sensor_id=vib_sensor.sensor_id, limit=5)
    assert len(retrieved) >= 1
    assert retrieved[0].sensor_id == vib_sensor.sensor_id
    assert retrieved[0].machine_id == "M204"


def test_m204_scenario_engine_phase_transitions():
    engine = M204ScenarioEngine("M204")
    assert engine.current_phase == ScenarioPhase.NORMAL

    # Normal profile
    norm_profile = engine.generate_current_telemetry_profile()
    assert 0.35 <= norm_profile["vibration_rms"] <= 0.55
    assert 55.0 <= norm_profile["temperature_c"] <= 62.0
    assert norm_profile["risk_score"] < 0.20

    # Transition to DEGRADING
    engine.transition_to(ScenarioPhase.DEGRADING, reason="Initial micro-spalling in bearing raceway")
    assert engine.current_phase == ScenarioPhase.DEGRADING
    deg_profile = engine.generate_current_telemetry_profile()
    assert deg_profile["vibration_rms"] > norm_profile["vibration_rms"]

    # Transition to HIGH_RISK
    engine.transition_to(ScenarioPhase.HIGH_RISK, reason="Critical vibration and thermal runaway")
    assert engine.current_phase == ScenarioPhase.HIGH_RISK
    risk_profile = engine.generate_current_telemetry_profile()
    assert risk_profile["risk_score"] >= 0.80
    assert risk_profile["vibration_rms"] > 0.80

    # Reset
    engine.reset_to_healthy()
    assert engine.current_phase == ScenarioPhase.NORMAL
    reset_profile = engine.generate_current_telemetry_profile()
    assert reset_profile["risk_score"] < 0.20
