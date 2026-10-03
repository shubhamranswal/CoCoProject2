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
    AlertStatus,
    ApprovalStatus,
    FailureMode,
    HealthStatus,
    InvestigationStatus,
    MachineState,
    Priority,
    Severity,
    VerificationStatus,
    WorkOrderStatus,
)
from domain.models import (
    ActionExecution,
    ActionOutcome,
    Alert,
    Approval,
    AuditEvent,
    Investigation,
    Machine,
    Verification,
    WorkOrder,
)
from domain.exceptions import UnsupportedOperationError
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

    # 1. get_machine: machine_id, line_id, machine_name, machine_type, criticality, model, install_date, _loaded_at, health_status, plant_id
    cur.fetchone.return_value = (
        "M21", "L5", "Grinder 3", "GR-600", "CRITICAL", "GR-600",
        date(2022, 1, 1), datetime.now(timezone.utc), "CRITICAL", "PLT01",
    )
    m = repo.get_machine("M21")
    assert m is not None
    assert m.machine_id == "M21"
    assert m.line_id == "L5"
    assert m.plant_id == "PLT01"
    sql, params = cur.execute.call_args[0]
    assert "COCO_FACTORY.CORE.MACHINE" in sql
    assert "m.plant_id" in sql
    assert params == ("M21",)

    # 2. list_machines
    cur.fetchall.return_value = [
        ("M21", "L5", "Grinder 3", "GR-600", "CRITICAL", "GR-600",
         date(2022, 1, 1), datetime.now(timezone.utc), "CRITICAL", "PLT01")
    ]
    machines = repo.list_machines(line_id="L5")
    assert len(machines) == 1
    assert machines[0].plant_id == "PLT01"
    sql, params = cur.execute.call_args[0]
    assert "COCO_FACTORY.CORE.MACHINE" in sql
    assert "m.plant_id" in sql
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
    assert "COCO_FACTORY.APP.INVESTIGATION" in sql
    assert params[0] == "INV-001"
    assert "M21" in params

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

    # Action Outcome (Closed-Loop Learning 15-column schema)
    outcome = ActionOutcome(
        outcome_id="OUT-001",
        action_proposal_id="PROP-001",
        execution_id="EXEC-001",
        verification_id="VER-001",
        work_order_id="WO-001",
        prediction_id="PRED-001",
        machine_id="M21",
        failure_mode="BEARING_DEGRADATION",
        observed_failure_confirmed=True,
        downtime_avoided_hours=12.5,
        verification_status=VerificationStatus.VERIFIED,
        telemetry_provenance={"source": "telemetry_post_eval", "baseline_hours": 24},
        is_simulated_telemetry=False,
        feedback_notes="Maintenance completed successfully",
    )
    repo.save_action_outcome(outcome)
    sql, params = cur.execute.call_args[0]
    assert "INSERT INTO COCO_FACTORY.APP.ACTION_OUTCOME" in sql
    assert "execution_id" in sql
    assert "verification_id" in sql
    assert "telemetry_provenance" in sql
    assert "is_simulated_telemetry" in sql
    assert params[0] == "OUT-001"
    assert params[1] == "PROP-001"
    assert params[2] == "EXEC-001"
    assert params[3] == "VER-001"
    assert params[4] == "WO-001"
    assert params[5] == "PRED-001"
    assert params[6] == "M21"
    assert params[7] == "BEARING_DEGRADATION"
    assert params[8] is True
    assert params[9] == 12.5
    assert params[10] == "VERIFIED"
    assert "telemetry_post_eval" in params[11]
    assert params[12] is False
    assert params[13] == "Maintenance completed successfully"

    # get_action_outcome
    cur.fetchone.return_value = (
        "OUT-001", "PROP-001", "EXEC-001", "VER-001", "WO-001", "PRED-001", "M21",
        "BEARING_DEGRADATION", True, 12.5, "VERIFIED",
        '{"source": "telemetry_post_eval", "baseline_hours": 24}',
        False, "Maintenance completed successfully", datetime.now(timezone.utc),
    )
    fetched_outcome = repo.get_action_outcome("OUT-001")
    assert fetched_outcome is not None
    assert fetched_outcome.outcome_id == "OUT-001"
    assert fetched_outcome.execution_id == "EXEC-001"
    assert fetched_outcome.verification_id == "VER-001"
    assert fetched_outcome.telemetry_provenance["source"] == "telemetry_post_eval"
    assert fetched_outcome.is_simulated_telemetry is False

    # list_action_outcomes
    cur.fetchall.return_value = [
        (
            "OUT-001", "PROP-001", "EXEC-001", "VER-001", "WO-001", "PRED-001", "M21",
            "BEARING_DEGRADATION", True, 12.5, "VERIFIED",
            '{"source": "telemetry_post_eval", "baseline_hours": 24}',
            False, "Maintenance completed successfully", datetime.now(timezone.utc),
        )
    ]
    outcome_list = repo.list_action_outcomes(machine_id="M21")
    assert len(outcome_list) == 1
    assert outcome_list[0].execution_id == "EXEC-001"
    assert outcome_list[0].verification_id == "VER-001"
    assert outcome_list[0].telemetry_provenance["baseline_hours"] == 24



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


# ==============================================================================
# 8. Behavioral Contract & Authoritative Snowflake Persistence Tests
# ==============================================================================

def test_snowflake_repository_has_no_in_process_authoritative_caches(repo: SnowflakeRepository):
    """Verify SnowflakeRepository does not use in-memory caches as authoritative persistence."""
    assert not hasattr(repo, "_machine_health_overrides")
    assert not hasattr(repo, "_health_assessment_cache")
    assert getattr(repo, "is_derived_health", False) is True


def test_update_machine_health_explicitly_rejects_unsupported_write(repo: SnowflakeRepository):
    """Verify update_machine_health explicitly raises UnsupportedOperationError on Snowflake backend."""
    with pytest.raises(UnsupportedOperationError) as exc_info:
        repo.update_machine_health("M21", HealthStatus.CRITICAL, MachineState.STOPPED)
    assert "update_machine_health is unsupported on SnowflakeRepository" in str(exc_info.value)
    assert "COCO_FACTORY.CORE.MACHINE is an immutable master dimension" in str(exc_info.value)


def test_save_health_assessment_explicitly_rejects_unsupported_write(repo: SnowflakeRepository):
    """Verify save_health_assessment explicitly raises UnsupportedOperationError on Snowflake backend."""
    from domain.models import HealthAssessment
    ha = HealthAssessment(
        assessment_id="HA-M21-TEST",
        machine_id="M21",
        health_status=HealthStatus.CRITICAL,
        health_score=35.0,
        primary_concern="Bearing degradation",
    )
    with pytest.raises(UnsupportedOperationError) as exc_info:
        repo.save_health_assessment(ha)
    assert "save_health_assessment is unsupported on SnowflakeRepository" in str(exc_info.value)
    assert "COCO_FACTORY.ANALYTICS.MACHINE_HEALTH_DAILY" in str(exc_info.value)


def test_get_machine_derives_health_authoritatively_from_analytics_view(repo: SnowflakeRepository, mock_conn):
    """Verify get_machine extracts authoritative health status directly from Snowflake SQL join."""
    _, cur = mock_conn

    # Mock Snowflake return with joined health_status = 'CRITICAL'
    cur.fetchone.return_value = (
        "M21", "L5", "Grinder 3", "GR-600", "CRITICAL", "GR-600",
        date(2022, 1, 1), datetime.now(timezone.utc), "CRITICAL",
    )
    m = repo.get_machine("M21")
    assert m is not None
    assert m.machine_id == "M21"
    assert m.health_status == HealthStatus.CRITICAL

    sql, params = cur.execute.call_args[0]
    assert "COCO_FACTORY.CORE.MACHINE" in sql
    assert "COCO_FACTORY.ANALYTICS.MACHINE_HEALTH_DAILY" in sql
    assert params == ("M21",)


def test_get_latest_health_assessment_queries_snowflake_with_no_memory_fallback(repo: SnowflakeRepository, mock_conn):
    """Verify get_latest_health_assessment strictly returns None when DB has no row (no memory fallback)."""
    _, cur = mock_conn

    # 1. When DB has no row, must return None directly
    cur.fetchone.return_value = None
    latest = repo.get_latest_health_assessment("M21")
    assert latest is None

    # 2. When DB has record in ANALYTICS.MACHINE_HEALTH_DAILY, it is used authoritatively
    cur.fetchone.return_value = (
        "HA-M21-20260928", "M21", "CRITICAL", 0.95, "high", 3, date(2026, 9, 28)
    )
    db_assessment = repo.get_latest_health_assessment("M21")
    assert db_assessment is not None
    assert db_assessment.assessment_id == "HA-M21-20260928"
    assert db_assessment.health_status == HealthStatus.CRITICAL
    assert db_assessment.health_score == 5.0  # round((1.0 - 0.95) * 100, 1)
    sql, params = cur.execute.call_args[0]
    assert "critical_alert_count" not in sql
    assert "COCO_FACTORY.ANALYTICS.MACHINE_HEALTH_DAILY" in sql


def test_process_restart_preserves_authoritative_snowflake_state():
    """Verify that restarting the application (instantiating fresh repository) reads authoritative state."""
    conn = MagicMock()
    cur = MagicMock()
    conn.cursor.return_value = cur
    mgr = MagicMock()
    mgr.get_connection.return_value = conn

    # First process lifecycle
    proc1_repo = SnowflakeRepository(mgr)
    cur.fetchone.return_value = (
        "M21", "L5", "Grinder 3", "GR-600", "CRITICAL", "GR-600",
        date(2022, 1, 1), datetime.now(timezone.utc), "CRITICAL",
    )
    m1 = proc1_repo.get_machine("M21")
    assert m1.health_status == HealthStatus.CRITICAL

    # Process restart / replacement with new instance
    proc2_repo = SnowflakeRepository(mgr)
    m2 = proc2_repo.get_machine("M21")
    assert m2.health_status == HealthStatus.CRITICAL
    assert m2.machine_id == m1.machine_id


def test_reliability_service_with_snowflake_repository_contract():
    """Verify ReliabilityService works seamlessly with SnowflakeRepository without unsupported writes."""
    from services.reliability_service import ReliabilityService
    from domain.models import FeatureVector

    conn = MagicMock()
    cur = MagicMock()
    conn.cursor.return_value = cur
    cur.fetchall.return_value = []
    cur.fetchone.return_value = None
    mgr = MagicMock()
    mgr.get_connection.return_value = conn

    repo = SnowflakeRepository(mgr)
    svc = ReliabilityService(reliability_repo=repo, machine_repo=repo, maintenance_repo=repo)

    features = FeatureVector(
        feature_id="FV-TEST-1",
        machine_id="M21",
        timestamp=datetime.now(timezone.utc),
        vibration_rms=7.5,
        vibration_peak=10.2,
        temperature_mean=85.0,
    )
    risk = svc.evaluate_failure_risk(
        machine_id="M21",
        features=features,
        active_anomalies=[],
        failure_mode=FailureMode.BEARING_DEGRADATION,
    )
    assert risk is not None
    assert risk.machine_id == "M21"
    # Verify FailureRisk was persisted to CORE.PREDICTION
    sql, params = cur.execute.call_args[0]
    assert "COCO_FACTORY.CORE.PREDICTION" in sql


def test_verification_service_with_snowflake_repository_contract():
    """Verify VerificationService handles SnowflakeRepository without calling unsupported machine health write."""
    from services.verification_service import VerificationService
    from domain.models import WorkOrder, Investigation, FeatureVector, FailureRisk
    from domain.enums import Priority

    conn = MagicMock()
    cur = MagicMock()
    conn.cursor.return_value = cur
    conn.commit.return_value = None
    cur.fetchall.return_value = []
    cur.fetchone.return_value = None
    mgr = MagicMock()
    mgr.get_connection.return_value = conn

    repo = SnowflakeRepository(mgr)
    v_svc = VerificationService(
        repository=repo,
        maintenance_repo=repo,
        investigation_repo=repo,
        machine_repo=repo,
    )

    wo = WorkOrder(
        work_order_id="WO-001",
        machine_id="M21",
        title="Replace bearing",
        description="Physical bearing replacement",
        failure_mode=FailureMode.BEARING_DEGRADATION,
        priority=Priority.HIGH,
        status=WorkOrderStatus.COMPLETED,
    )
    inv = Investigation(
        investigation_id="INV-001",
        machine_id="M21",
        status=InvestigationStatus.PENDING_APPROVAL,
    )

    repo.get_work_order = MagicMock(return_value=wo)
    repo.get_investigation = MagicMock(return_value=inv)
    repo.save_verification = MagicMock()
    repo.save_action_outcome = MagicMock()
    repo.update_work_order_status = MagicMock()
    repo.update_investigation = MagicMock()

    pre_feat = FeatureVector(
        feature_id="FV-PRE-TEST",
        machine_id="M21",
        timestamp=datetime.now(timezone.utc),
        vibration_rms=1.45,
        vibration_peak=2.10,
        temperature_mean=78.5,
    )
    pre_risk = FailureRisk(
        risk_id="RISK-PRE",
        machine_id="M21",
        risk_score=0.95,
        failure_mode=FailureMode.BEARING_DEGRADATION,
    )
    post_feat = FeatureVector(
        feature_id="FV-POST-TEST",
        machine_id="M21",
        timestamp=datetime.now(timezone.utc),
        vibration_rms=0.42,
        vibration_peak=0.60,
        temperature_mean=58.0,
    )
    post_risk = FailureRisk(
        risk_id="RISK-POST",
        machine_id="M21",
        risk_score=0.12,
        failure_mode=FailureMode.NORMAL_OPERATION,
    )

    # Verification must run cleanly without raising UnsupportedOperationError
    ver = v_svc.verify_recovery(
        work_order_id="WO-001",
        investigation_id="INV-001",
        machine_id="M21",
        pre_features=pre_feat,
        post_features=post_feat,
        pre_risk=pre_risk,
        post_risk=post_risk,
        verifier="OPERATOR",
    )
    assert ver.is_recovered is True
    assert ver.verification_status == VerificationStatus.VERIFIED


def test_memory_repository_behavior_remains_intact_for_unit_and_demo_mode():
    """Verify InMemoryRepository retains full in-memory mutation behavior for unit/demo mode."""
    from repositories.memory.memory_repository import InMemoryRepository
    mem_repo = InMemoryRepository(seed=True)

    # In-memory update_machine_health mutates and persists locally
    updated = mem_repo.update_machine_health("M204", HealthStatus.CRITICAL, MachineState.STOPPED)
    assert updated.health_status == HealthStatus.CRITICAL
    assert updated.state == MachineState.STOPPED

    fetched = mem_repo.get_machine("M204")
    assert fetched.health_status == HealthStatus.CRITICAL
    assert fetched.state == MachineState.STOPPED


def test_get_plant_and_list_lines_behavioral_contract(repo: SnowflakeRepository, mock_conn):
    """Verify null safety, uniqueness, and canonical metadata derivation for plant and lines."""
    _, cur = mock_conn

    # 1. Null / empty / whitespace checks
    assert repo.get_plant("") is None
    assert repo.get_plant("   ") is None
    assert repo.get_plant(None) is None
    assert repo.list_lines("") == []
    assert repo.list_lines("   ") == []
    assert repo.list_lines(None) == []

    # 2. Canonical plant retrieval
    cur.fetchone.return_value = ("PLT01",)
    plant = repo.get_plant("PLT01")
    assert plant is not None
    assert plant.plant_id == "PLT01"
    assert plant.name == "Pune Automotive Assembly & Machining Plant"
    assert plant.location == "Pune, India"
    assert plant.timezone == "Asia/Kolkata"

    # 3. Canonical lines retrieval with metadata parity
    cur.fetchall.return_value = [
        ("L1", "PLT01"),
        ("L2", "PLT01"),
        ("L3", "PLT01"),
        ("L4", "PLT01"),
        ("L5", "PLT01"),
    ]
    lines = repo.list_lines("PLT01")
    assert len(lines) == 5
    line_map = {l.line_id: l for l in lines}

    assert line_map["L1"].name == "Heavy Machining Line 1"
    assert line_map["L1"].target_units_per_hour == 80.0

    assert line_map["L2"].name == "Precision Lathe & Turning Line 2"
    assert line_map["L2"].target_units_per_hour == 100.0

    assert line_map["L3"].name == "Stamping & Press Line 3"
    assert line_map["L3"].target_units_per_hour == 150.0

    assert line_map["L4"].name == "Assembly & Injection Molding Line 4"
    assert line_map["L4"].target_units_per_hour == 120.0

    assert line_map["L5"].name == "Grinding & Finishing Line 5"
    assert line_map["L5"].target_units_per_hour == 90.0


# ==============================================================================
# 5. M6.4 Remediation Tests: Machine plant_id, Alert Mappings, and Analytics DDL
# ==============================================================================

def test_machine_model_plant_id_compatibility():
    """Verify Machine domain model accepts optional plant_id with backwards compatibility."""
    # With plant_id
    m1 = Machine(
        machine_id="M1",
        line_id="L1",
        machine_code="M1",
        name="Machine 1",
        plant_id="PLT01",
    )
    assert m1.plant_id == "PLT01"

    # Backwards compatibility: plant_id omitted
    m2 = Machine(
        machine_id="M2",
        line_id="L1",
        machine_code="M2",
        name="Machine 2",
    )
    assert m2.plant_id is None


def test_explicit_alert_severity_mapping():
    """Verify map_alert_severity explicitly maps canonical Snowflake values with safe fallbacks."""
    from repositories.snowflake.snowflake_repository import map_alert_severity
    from domain.enums import Severity

    # Canonical Snowflake lowercase strings
    assert map_alert_severity("critical") == Severity.CRITICAL
    assert map_alert_severity("warning") == Severity.HIGH
    assert map_alert_severity("warn") == Severity.HIGH

    # Standard uppercase values
    assert map_alert_severity("CRITICAL") == Severity.CRITICAL
    assert map_alert_severity("HIGH") == Severity.HIGH
    assert map_alert_severity("MEDIUM") == Severity.MEDIUM
    assert map_alert_severity("LOW") == Severity.LOW

    # Unknown and empty fallbacks
    assert map_alert_severity("") == Severity.MEDIUM
    assert map_alert_severity(None) == Severity.MEDIUM
    assert map_alert_severity("unexpected_status") == Severity.MEDIUM


def test_explicit_alert_status_mapping():
    """Verify map_alert_status explicitly maps canonical Snowflake values with safe fallbacks."""
    from repositories.snowflake.snowflake_repository import map_alert_status
    from domain.enums import AlertStatus

    # Canonical Snowflake lowercase strings
    assert map_alert_status("open") == AlertStatus.OPEN
    assert map_alert_status("acknowledged") == AlertStatus.INVESTIGATING
    assert map_alert_status("closed") == AlertStatus.RESOLVED

    # Standard uppercase values
    assert map_alert_status("OPEN") == AlertStatus.OPEN
    assert map_alert_status("INVESTIGATING") == AlertStatus.INVESTIGATING
    assert map_alert_status("RESOLVED") == AlertStatus.RESOLVED
    assert map_alert_status("ACTION_PROPOSED") == AlertStatus.ACTION_PROPOSED
    assert map_alert_status("DISMISSED") == AlertStatus.DISMISSED

    # Unknown and empty fallbacks
    assert map_alert_status("") == AlertStatus.OPEN
    assert map_alert_status(None) == AlertStatus.OPEN
    assert map_alert_status("unknown_status") == AlertStatus.OPEN


def test_alert_deserialization_and_filtering(repo: SnowflakeRepository, mock_conn):
    """Verify get_alert and list_alerts deserialize canonical lowercase values and filter correctly."""
    from domain.enums import AlertStatus, Severity, FailureMode
    _, cur = mock_conn

    # 1. get_alert deserialization
    cur.fetchone.return_value = (
        "ALT-000033", "M21", "C-M21-BRG", "critical", "closed",
        "High bearing vibration exceedance", 0.95, "BEARING_DEGRADATION",
        datetime(2026, 9, 28, 12, 0, tzinfo=timezone.utc), None, None,
    )
    alert = repo.get_alert("ALT-000033")
    assert alert is not None
    assert alert.alert_id == "ALT-000033"
    assert alert.severity == Severity.CRITICAL
    assert alert.status == AlertStatus.RESOLVED

    # 2. list_alerts with status=AlertStatus.OPEN
    cur.fetchall.return_value = [
        ("ALT-000001", "M21", "C-M21-BRG", "warning", "open",
         "Elevated vibration precursor", 0.70, "BEARING_DEGRADATION",
         datetime(2026, 9, 28, 10, 0, tzinfo=timezone.utc), None, None)
    ]
    alerts = repo.list_alerts(machine_id="M21", status=AlertStatus.OPEN)
    assert len(alerts) == 1
    assert alerts[0].severity == Severity.HIGH
    assert alerts[0].status == AlertStatus.OPEN
    sql, _ = cur.execute.call_args[0]
    assert "LOWER(status) = 'open'" in sql


def test_analytics_ddl_case_insensitive_critical_matching():
    """Verify 30_analytics_foundation.sql matches critical severity case-insensitively."""
    ddl_path = (
        Path(__file__).resolve().parent.parent.parent
        / "snowflake"
        / "ddl"
        / "coco_factory"
        / "30_analytics_foundation.sql"
    )
    ddl_content = ddl_path.read_text(encoding="utf-8")
    assert "UPPER(SEVERITY) = 'CRITICAL'" in ddl_content.upper(), (
        "Expected case-insensitive UPPER(severity) = 'CRITICAL' in 30_analytics_foundation.sql"
    )


def test_list_action_proposals_priority_hydration(repo: SnowflakeRepository, mock_conn):
    """Verify list_action_proposals hydrates ActionProposal without NameError and correctly maps Priority."""
    _, cur = mock_conn
    now = datetime(2026, 10, 2, 14, 0, tzinfo=timezone.utc)

    # Mock rows with LOW, MEDIUM, HIGH, CRITICAL, and unknown fallback
    cur.fetchall.return_value = [
        ("PROP-001", "INV-001", "REC-001", "M21", "C-M21-BRG", "INSPECT", "LOW", "LOW", "Check", "{}", "PROPOSED", "IDEM-1", None, True, now, now),
        ("PROP-002", "INV-001", "REC-002", "M21", "C-M21-BRG", "INSPECT", "MEDIUM", "MED", "Check", "{}", "PROPOSED", "IDEM-2", None, True, now, now),
        ("PROP-003", "INV-001", "REC-003", "M21", "C-M21-BRG", "INSPECT", "HIGH", "HIGH", "Check", "{}", "PROPOSED", "IDEM-3", None, True, now, now),
        ("PROP-004", "INV-001", "REC-004", "M21", "C-M21-BRG", "INSPECT", "CRITICAL", "CRIT", "Check", "{}", "PROPOSED", "IDEM-4", None, True, now, now),
        ("PROP-005", "INV-001", "REC-005", "M21", "C-M21-BRG", "INSPECT", "UNKNOWN", "HIGH", "Check", "{}", "PROPOSED", "IDEM-5", None, True, now, now),
    ]

    proposals = repo.list_action_proposals(machine_id="M21")
    assert len(proposals) == 5
    assert proposals[0].priority == Priority.LOW
    assert proposals[1].priority == Priority.MEDIUM
    assert proposals[2].priority == Priority.HIGH
    assert proposals[3].priority == Priority.CRITICAL
    assert proposals[4].priority == Priority.HIGH  # Fallback for unknown
