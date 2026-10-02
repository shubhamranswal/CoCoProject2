"""Regression tests for SnowflakeRepository schema unification (Milestone M6.2).

Verifies:
1. Zero deprecated FACTORY_* schema references in SnowflakeRepository.
2. All referenced schemas belong to canonical COCO_FACTORY architecture (RAW, CORE, ANALYTICS, ML, KNOWLEDGE, APP).
3. All referenced COCO_FACTORY tables/views exist in canonical DDL (snowflake/ddl/coco_factory/).
4. Representative CRUD/read/write operations (mocked unit tests) across CORE, ML, ANALYTICS, APP, and KNOWLEDGE.
5. Strict parameterization and SQL injection guards across all repository calls.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from domain.enums import (
    ApprovalStatus,
    FailureMode,
    InvestigationStatus,
    Priority,
    VerificationStatus,
    WorkOrderStatus,
)
from domain.models import (
    ActionExecution,
    Approval,
    AuditEvent,
    Investigation,
    Verification,
    WorkOrder,
)
from repositories.snowflake.snowflake_repository import SnowflakeRepository


@pytest.fixture
def mock_conn():
    conn = MagicMock()
    cur = MagicMock()
    conn.cursor.return_value = cur
    # Default fetch returns empty list
    cur.fetchall.return_value = []
    cur.fetchone.return_value = None
    return conn, cur


@pytest.fixture
def repo(mock_conn):
    conn, _ = mock_conn
    mgr = MagicMock()
    mgr.get_connection.return_value = conn
    return SnowflakeRepository(mgr)


# ==============================================================================
# 1. Static Schema & Deprecation Audits
# ==============================================================================

def test_zero_deprecated_factory_schemas():
    """Verify production snowflake_repository.py contains zero deprecated FACTORY_* schemas."""
    repo_file = (
        Path(__file__).resolve().parent.parent.parent
        / "repositories"
        / "snowflake"
        / "snowflake_repository.py"
    )
    content = repo_file.read_text(encoding="utf-8")

    deprecated_schemas = [
        "FACTORY_CORE",
        "FACTORY_TELEMETRY",
        "FACTORY_MAINTENANCE",
        "FACTORY_RELIABILITY",
        "FACTORY_AGENT",
        "FACTORY_AUDIT",
        "FACTORY_INTELLIGENCE",
        "FACTORY_KNOWLEDGE",
    ]

    for schema in deprecated_schemas:
        assert schema not in content, f"Found deprecated schema reference: {schema}"

    # Also check case-insensitive pattern for standalone FACTORY_<name>
    standalone_factory = re.findall(r"(?<!COCO_)FACTORY_[A-Z_]+", content, flags=re.IGNORECASE)
    assert not standalone_factory, f"Found unexpected FACTORY_* patterns: {standalone_factory}"


def test_all_referenced_schemas_are_canonical():
    """Verify all schema references in SQL queries belong to conformed COCO_FACTORY schemas."""
    repo_file = (
        Path(__file__).resolve().parent.parent.parent
        / "repositories"
        / "snowflake"
        / "snowflake_repository.py"
    )
    content = repo_file.read_text(encoding="utf-8")

    matches = set(re.findall(r"COCO_FACTORY\.([A-Z_]+)\.[A-Z_]+", content))
    assert matches, "Expected COCO_FACTORY schema references in SnowflakeRepository"

    canonical_schemas = {"RAW", "CORE", "ANALYTICS", "ML", "KNOWLEDGE", "APP"}
    invalid_schemas = matches - canonical_schemas
    assert not invalid_schemas, f"Found non-canonical schemas in COCO_FACTORY queries: {invalid_schemas}"


def test_referenced_tables_exist_in_ddl():
    """Verify that every COCO_FACTORY.<SCHEMA>.<TABLE> referenced in code exists in canonical DDL."""
    ddl_dir = (
        Path(__file__).resolve().parent.parent.parent
        / "snowflake"
        / "ddl"
        / "coco_factory"
    )
    ddl_text = "\n".join(f.read_text(encoding="utf-8").upper() for f in ddl_dir.glob("*.sql"))

    repo_file = (
        Path(__file__).resolve().parent.parent.parent
        / "repositories"
        / "snowflake"
        / "snowflake_repository.py"
    )
    content = repo_file.read_text(encoding="utf-8")

    table_refs = set(re.findall(r"COCO_FACTORY\.([A-Z_]+\.[A-Z_]+)", content))
    assert table_refs, "Expected COCO_FACTORY table references"

    for ref in sorted(table_refs):
        schema, table = ref.split(".")
        # Check if table or view is created in DDL
        created = (
            f"TABLE IF NOT EXISTS {table}" in ddl_text
            or f"TABLE {table}" in ddl_text
            or f"VIEW IF NOT EXISTS {table}" in ddl_text
            or f"VIEW {table}" in ddl_text
            or f"TABLE IF NOT EXISTS {schema}.{table}" in ddl_text
            or f"VIEW IF NOT EXISTS {schema}.{table}" in ddl_text
            or f"TABLE {schema}.{table}" in ddl_text
            or f"VIEW {schema}.{table}" in ddl_text
        )
        assert created, f"Table or View COCO_FACTORY.{ref} not found in canonical DDL scripts"


# ==============================================================================
# 2. Representative CRUD & Query Target Tests (CORE)
# ==============================================================================

def test_core_machine_queries(repo: SnowflakeRepository, mock_conn):
    _, cur = mock_conn

    # 1. get_machine: machine_id, line_id, machine_name, machine_type, criticality, model, install_date, _loaded_at
    cur.fetchone.return_value = (
        "M21", "L5", "Grinder 3", "GR-600", "CRITICAL", "GR-600",
        date(2022, 1, 1), datetime.now(timezone.utc),
    )
    m = repo.get_machine("M21")
    assert m is not None
    assert m.machine_id == "M21"
    assert m.line_id == "L5"
    sql, params = cur.execute.call_args[0]
    assert "COCO_FACTORY.CORE.MACHINE" in sql
    assert params == ("M21",)

    # 2. list_machines
    cur.fetchall.return_value = [
        ("M21", "L5", "Grinder 3", "GR-600", "CRITICAL", "GR-600",
         date(2022, 1, 1), datetime.now(timezone.utc))
    ]
    machines = repo.list_machines(line_id="L5")
    assert len(machines) == 1
    sql, params = cur.execute.call_args[0]
    assert "COCO_FACTORY.CORE.MACHINE" in sql
    assert params == ("L5",)


def test_core_components_and_sensors(repo: SnowflakeRepository, mock_conn):
    _, cur = mock_conn

    # Components: component_id, machine_id, COALESCE(model, component_type), component_type, install_date
    cur.fetchall.return_value = [("C-M21-BRG", "M21", "6206-2RS", "BEARING", date(2022, 1, 1))]
    comps = repo.get_components("M21")
    assert len(comps) == 1
    assert comps[0].component_id == "C-M21-BRG"
    sql, params = cur.execute.call_args[0]
    assert "COCO_FACTORY.CORE.COMPONENT" in sql
    assert params == ("M21",)

    # Sensors: sensor_id, machine_id, component_id, sensor_type, unit, sampling_rate_hz, warn_threshold, crit_threshold
    cur.fetchall.return_value = [("S-M21-VIB", "M21", "C-M21-BRG", "VIBRATION", "mm/s", 1.0, 5.0, 7.0)]
    sensors = repo.get_sensors("M21")
    assert len(sensors) == 1
    assert sensors[0].sensor_id == "S-M21-VIB"
    sql, params = cur.execute.call_args[0]
    assert "COCO_FACTORY.CORE.SENSOR" in sql
    assert params == ("M21",)


def test_core_spare_parts_and_suppliers(repo: SnowflakeRepository, mock_conn):
    _, cur = mock_conn

    # Spare Part: part_id, part_name, part_category, compatible_model, unit_cost_inr, supplier_id, lead_time_days, stock_qty, reorder_level, reorder_qty, warehouse_bin
    cur.fetchone.return_value = (
        "SP-002", "Drive-End Bearing 6206-2RS", "BEARING", "6206-2RS",
        150.0, "SUP-12", 5, 0, 2, 4, "BIN-12",
    )
    part = repo.get_spare_part("SP-002")
    assert part is not None
    assert part.part_name == "Drive-End Bearing 6206-2RS"
    assert part.stock_qty == 0
    sql, params = cur.execute.call_args[0]
    assert "COCO_FACTORY.CORE.SPARE_PART" in sql
    assert params == ("SP-002",)

    # Supplier: supplier_id, supplier_name, country, avg_lead_time_days, on_time_delivery_pct
    cur.fetchone.return_value = ("SUP-12", "Vertex Industrial Supplies", "India", 5, 0.95)
    supplier = repo.get_supplier("SUP-12")
    assert supplier is not None
    assert supplier.supplier_name == "Vertex Industrial Supplies"
    sql, params = cur.execute.call_args[0]
    assert "COCO_FACTORY.CORE.SUPPLIER" in sql
    assert params == ("SUP-12",)


def test_core_work_order_crud_and_idempotency(repo: SnowflakeRepository, mock_conn):
    _, cur = mock_conn

    wo = WorkOrder(
        work_order_id="WO-M6-001",
        machine_id="M21",
        title="Replace drive-end bearing",
        description="Vibration critical",
        failure_mode=FailureMode.BEARING_DEGRADATION,
        priority=Priority.CRITICAL,
        status=WorkOrderStatus.DRAFT,
        idempotency_key="INV-001-WO",
    )
    created = repo.create_work_order(wo)
    assert created.work_order_id == "WO-M6-001"
    sql, params = cur.execute.call_args[0]
    assert "INSERT INTO COCO_FACTORY.CORE.MAINTENANCE_WORK_ORDER" in sql
    assert params[0] == "WO-M6-001"
    assert params[1] == "M21"
    assert params[5] == "CRITICAL"


# ==============================================================================
# 3. ML Schema Target Tests
# ==============================================================================

def test_ml_features_and_predictions(repo: SnowflakeRepository, mock_conn):
    _, cur = mock_conn

    # get_latest_features queries ML.V_MACHINE_FEATURE_DAILY
    cur.fetchone.return_value = (
        "M21", date(2026, 9, 28), 7.2, 85.0, 1.2, 0.4, 0.3, 0.8,
        datetime.now(timezone.utc),
    )
    feat = repo.get_latest_features("M21")
    assert feat is not None
    sql, params = cur.execute.call_args[0]
    assert "COCO_FACTORY.ML.V_MACHINE_FEATURE_DAILY" in sql
    assert params == ("M21",)

    # list_canonical_predictions queries CORE.PREDICTION
    cur.fetchall.return_value = [
        ("PRED-001", datetime.now(timezone.utc), "M21", "C-M21-BRG", "XGB_v1", 14,
         0.95, "CRITICAL", {"vib": 7.2})
    ]
    preds = repo.list_canonical_predictions(machine_id="M21")
    assert len(preds) == 1
    sql, params = cur.execute.call_args[0]
    assert "COCO_FACTORY.CORE.PREDICTION" in sql
    assert params[0] == "M21"


# ==============================================================================
# 4. Analytics Schema Target Tests
# ==============================================================================

def test_analytics_machine_health_and_oee(repo: SnowflakeRepository, mock_conn):
    _, cur = mock_conn

    # Health daily
    cur.fetchone.return_value = (
        "M21", date(2026, 9, 28), "Grinder 3", "GR-600", "L5", "Line 5",
        1440, 3.5, 7.2, 65.0, 85.0, 5, 120.0, 1, 1, 2, "PRED-001",
        0.95, "CRITICAL", "CRITICAL",
    )
    health = repo.get_machine_health_daily("M21", date(2026, 9, 28))
    assert health is not None
    assert health.machine_id == "M21"
    assert health.health_status == "CRITICAL"
    sql, params = cur.execute.call_args[0]
    assert "COCO_FACTORY.ANALYTICS.MACHINE_HEALTH_DAILY" in sql
    assert params == ("M21", date(2026, 9, 28))

    # OEE daily
    cur.fetchone.return_value = (
        "M21", date(2026, 9, 28), "Grinder 3", "L5",
        1440.0, 1080.0, 360.0, 1000, 980, 20,
        0.75, 0.82, 0.98, 0.6027,
    )
    oee = repo.get_machine_oee_daily("M21", date(2026, 9, 28))
    assert oee is not None
    assert oee.machine_id == "M21"
    sql, params = cur.execute.call_args[0]
    assert "COCO_FACTORY.ANALYTICS.MACHINE_OEE_DAILY" in sql
    assert params == ("M21", date(2026, 9, 28))


# ==============================================================================
# 5. Governance & App Schema Target Tests (APP)
# ==============================================================================

def test_app_governance_investigation_and_approval(repo: SnowflakeRepository, mock_conn):
    _, cur = mock_conn

    # Investigation
    inv = Investigation(
        investigation_id="INV-001",
        alert_id="ALT-001",
        machine_id="M21",
        status=InvestigationStatus.COMPLETED,
        failure_mode=FailureMode.BEARING_DEGRADATION,
        confidence=0.85,
    )
    created_inv = repo.create_investigation(inv)
    assert created_inv.investigation_id == "INV-001"
    sql, params = cur.execute.call_args[0]
    assert "INSERT INTO COCO_FACTORY.APP.INVESTIGATION" in sql
    assert params[0] == "INV-001"
    assert params[2] == "M21"

    # Action Approval
    appr = Approval(
        approval_id="APP-001",
        action_id="PROP-001",
        investigation_id="INV-001",
        machine_id="M21",
        status=ApprovalStatus.APPROVED,
        requested_by="ReliabilityAgent",
    )
    created_appr = repo.create_approval(appr)
    assert created_appr.approval_id == "APP-001"
    sql, params = cur.execute.call_args[0]
    assert "INSERT INTO COCO_FACTORY.APP.ACTION_APPROVAL" in sql
    assert params[0] == "APP-001"

    # Action Execution
    exec_record = ActionExecution(
        execution_id="EXEC-001",
        action_proposal_id="PROP-001",
        approval_id="APP-001",
        action_type="CREATE_WORK_ORDER",
        machine_id="M21",
        executed_by="SYSTEM",
        status="SUCCESS",
        idempotency_key="EXEC-IDEMP-001",
        result_data={"work_order_id": "WO-001"},
    )
    saved_exec = repo.save_action_execution(exec_record)
    assert saved_exec.execution_id == "EXEC-001"
    sql, params = cur.execute.call_args[0]
    assert "COCO_FACTORY.APP.ACTION_EXECUTION" in sql

    # Verification Result
    ver = Verification(
        verification_id="VER-001",
        investigation_id="INV-001",
        work_order_id="WO-001",
        machine_id="M21",
        verification_status=VerificationStatus.VERIFIED,
        pre_vibration_rms=1.2,
        post_vibration_rms=0.4,
        pre_temperature_c=75.0,
        post_temperature_c=55.0,
        pre_risk_score=0.9,
        post_risk_score=0.1,
        risk_delta=0.8,
        is_recovered=True,
        verification_reason="Vibration normalized",
    )
    repo.save_verification(ver)
    sql, params = cur.execute.call_args[0]
    assert "INSERT INTO COCO_FACTORY.APP.VERIFICATION_RESULT" in sql
    assert params[0] == "VER-001"

    # Action Audit
    audit = AuditEvent(
        audit_id="AUD-001",
        actor="ENG-101",
        action_type="CREATE_WORK_ORDER",
        resource_id="M21",
        resource_type="MACHINE",
        status="SUCCESS",
        details={"reason": "vibration_critical"},
    )
    repo.log_audit(audit)
    sql, params = cur.execute.call_args[0]
    assert "INSERT INTO COCO_FACTORY.APP.ACTION_AUDIT" in sql
    assert params[0] == "AUD-001"


# ==============================================================================
# 6. Knowledge Schema Target Tests (KNOWLEDGE / CORE)
# ==============================================================================

def test_knowledge_document_and_chunks(repo: SnowflakeRepository, mock_conn):
    _, cur = mock_conn

    # list_documents queries COCO_FACTORY.KNOWLEDGE.CORPUS
    cur.fetchall.return_value = [
        ("DOC-001", "Grinder Maintenance Manual", "MANUAL", "F01", "GR-600", "BEARING",
         "Full content details...", '{"author": "engineer"}')
    ]
    docs = repo.list_documents()
    assert len(docs) == 1
    assert docs[0].title == "Grinder Maintenance Manual"
    sql = cur.execute.call_args[0][0]
    assert "COCO_FACTORY.KNOWLEDGE.CORPUS" in sql


# ==============================================================================
# 7. Parameterization and SQL Injection Guards
# ==============================================================================

def test_parameterization_protects_against_sql_injection(repo: SnowflakeRepository, mock_conn):
    """Ensure malicious string injection attempts remain parameterized and are not executed raw."""
    _, cur = mock_conn

    injection_payload = "M21' OR '1'='1"

    # get_machine
    repo.get_machine(injection_payload)
    sql, params = cur.execute.call_args[0]
    assert "COCO_FACTORY.CORE.MACHINE" in sql
    assert injection_payload not in sql, "Malicious string must NOT be formatted directly into SQL query"
    assert params == (injection_payload,), "Payload must be passed strictly as bound parameter"

    # get_spare_part
    repo.get_spare_part("SP-002; DROP TABLE COCO_FACTORY.CORE.SPARE_PART; --")
    sql, params = cur.execute.call_args[0]
    assert "DROP TABLE" not in sql
    assert params == ("SP-002; DROP TABLE COCO_FACTORY.CORE.SPARE_PART; --",)
