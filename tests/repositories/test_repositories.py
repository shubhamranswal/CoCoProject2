"""Tests for repository abstractions and in-memory implementation."""

import pytest
from datetime import datetime

from domain.enums import FailureMode, HealthStatus, Priority, WorkOrderStatus
from domain.models import WorkOrder
from repositories.memory.memory_repository import InMemoryRepository


def test_seeded_repository_loads_m204(memory_repo: InMemoryRepository):
    m204 = memory_repo.get_machine("M204")
    assert m204 is not None
    assert m204.machine_id == "M204"
    assert m204.line_id == "LINE-B"
    assert m204.criticality == "CRITICAL"

    # Components
    components = memory_repo.get_components("M204")
    assert len(components) == 4
    comp_types = [c.component_type for c in components]
    assert "BEARING" in comp_types

    # Sensors
    sensors = memory_repo.get_sensors("M204")
    assert len(sensors) == 4
    sensor_types = [s.sensor_type.value for s in sensors]
    assert "VIBRATION" in sensor_types
    assert "TEMPERATURE" in sensor_types


def test_missing_machine_returns_none(memory_repo: InMemoryRepository):
    assert memory_repo.get_machine("NON_EXISTENT_MACHINE") is None


def test_work_order_crud_and_status_update(memory_repo: InMemoryRepository):
    wo = WorkOrder(
        work_order_id="WO-TEST-01",
        machine_id="M204",
        title="Check lubrication level",
        description="Verify polyurea grease quantity",
        failure_mode=FailureMode.LUBRICATION_FAILURE,
        priority=Priority.MEDIUM,
    )
    created = memory_repo.create_work_order(wo)
    assert created.work_order_id == "WO-TEST-01"

    fetched = memory_repo.get_work_order("WO-TEST-01")
    assert fetched is not None
    assert fetched.status == WorkOrderStatus.DRAFT

    updated = memory_repo.update_work_order_status("WO-TEST-01", WorkOrderStatus.IN_PROGRESS)
    assert updated.status == WorkOrderStatus.IN_PROGRESS


def test_work_order_idempotency(memory_repo: InMemoryRepository):
    wo1 = WorkOrder(
        work_order_id="WO-IDEMP-01",
        machine_id="M204",
        title="Replace bearing",
        description="Replace drive-end bearing",
        failure_mode=FailureMode.BEARING_DEGRADATION,
        priority=Priority.HIGH,
        idempotency_key="UNIQUE-INVESTIGATION-INV-001",
    )
    first_creation = memory_repo.create_work_order(wo1)

    wo2 = WorkOrder(
        work_order_id="WO-IDEMP-02",
        machine_id="M204",
        title="Replace bearing (Retry)",
        description="Duplicate attempt",
        failure_mode=FailureMode.BEARING_DEGRADATION,
        priority=Priority.HIGH,
        idempotency_key="UNIQUE-INVESTIGATION-INV-001",
    )
    second_creation = memory_repo.create_work_order(wo2)

    # Should return existing work order with original ID
    assert second_creation.work_order_id == "WO-IDEMP-01"


def test_repository_isolation():
    repo1 = InMemoryRepository(seed=False)
    repo2 = InMemoryRepository(seed=False)

    wo = WorkOrder(
        work_order_id="WO-ISO-01",
        machine_id="M204",
        title="Test Isolation",
        description="Checking memory separation",
        failure_mode=FailureMode.NORMAL_OPERATION,
        priority=Priority.LOW,
    )
    repo1.create_work_order(wo)

    assert repo1.get_work_order("WO-ISO-01") is not None
    assert repo2.get_work_order("WO-ISO-01") is None
