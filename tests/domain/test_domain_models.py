"""Tests for domain models and validation."""

from datetime import datetime
import pytest
from pydantic import ValidationError

from domain.enums import (
    FailureMode,
    HealthStatus,
    MachineState,
    Priority,
    SensorType,
    Severity,
    WorkOrderStatus,
)
from domain.models import (
    FailureRisk,
    HealthAssessment,
    Machine,
    Sensor,
    TelemetryMeasurement,
    WorkOrder,
)


def test_valid_machine_instantiation():
    m = Machine(
        machine_id="M204",
        line_id="LINE-B",
        machine_code="M204",
        name="Conveyor Drive Motor",
        health_status=HealthStatus.HEALTHY,
        state=MachineState.RUNNING,
    )
    assert m.machine_id == "M204"
    assert m.health_status == HealthStatus.HEALTHY
    assert m.state == MachineState.RUNNING


def test_invalid_machine_enum_raises():
    with pytest.raises(ValidationError):
        Machine(
            machine_id="M204",
            line_id="LINE-B",
            machine_code="M204",
            name="Conveyor Drive Motor",
            health_status="NON_EXISTENT_STATUS",  # type: ignore
        )


def test_failure_risk_score_bounds():
    # Valid bounds: 0.0 <= risk_score <= 1.0
    valid_risk = FailureRisk(
        risk_id="RISK-01",
        machine_id="M204",
        failure_mode=FailureMode.BEARING_DEGRADATION,
        risk_score=0.87,
    )
    assert valid_risk.risk_score == 0.87

    # Invalid: > 1.0
    with pytest.raises(ValidationError):
        FailureRisk(
            risk_id="RISK-02",
            machine_id="M204",
            failure_mode=FailureMode.BEARING_DEGRADATION,
            risk_score=1.5,
        )

    # Invalid: < 0.0
    with pytest.raises(ValidationError):
        FailureRisk(
            risk_id="RISK-03",
            machine_id="M204",
            failure_mode=FailureMode.BEARING_DEGRADATION,
            risk_score=-0.1,
        )


def test_health_assessment_score_bounds():
    # Valid: 0 to 100
    ha = HealthAssessment(
        assessment_id="HA-01",
        machine_id="M204",
        health_status=HealthStatus.HEALTHY,
        health_score=95.0,
    )
    assert ha.health_score == 95.0

    # Invalid > 100
    with pytest.raises(ValidationError):
        HealthAssessment(
            assessment_id="HA-02",
            machine_id="M204",
            health_status=HealthStatus.HEALTHY,
            health_score=105.0,
        )


def test_sensor_creation_and_type():
    s = Sensor(
        sensor_id="SEN-M204-VIB",
        machine_id="M204",
        sensor_type=SensorType.VIBRATION,
        name="Drive-End Bearing Accelerometer",
        unit="g",
        range_min=0.0,
        range_max=5.0,
    )
    assert s.sensor_type == SensorType.VIBRATION
    assert s.range_max == 5.0


def test_work_order_creation_and_defaults():
    wo = WorkOrder(
        work_order_id="WO-001",
        machine_id="M204",
        title="Inspect Bearing Assembly",
        description="Inspect Drive-end bearing for flaking",
        failure_mode=FailureMode.BEARING_DEGRADATION,
        priority=Priority.HIGH,
    )
    assert wo.status == WorkOrderStatus.DRAFT
    assert isinstance(wo.created_at, datetime)
