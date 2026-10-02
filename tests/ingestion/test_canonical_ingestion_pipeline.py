"""Comprehensive Test Suite for M6.3 Canonical Snowflake Ingestion Pipeline.

Validates:
1. Exact source-to-target manifest for all 19 canonical datasets
2. Preflight validation of files, schemas, and row cardinalities
3. Canonical invariants for M21, C-M21-BRG, S-M21-VIB, SP-002, and PRED-000322
4. Staging PUT command generation with Windows-safe forward slashes
5. RAW COPY statements and dynamic execution batch ID injection
6. Idempotent CORE transformations and Data Quality query orchestration
7. Dry-run execution safety (zero live network/mutation calls)
8. Live execution guard enforcement
"""

from pathlib import Path
import re
from unittest.mock import MagicMock
import pytest

from ingestion.canonical_source import CanonicalSourceManager, CANONICAL_ENTITIES
from ingestion.manifest import (
    CANONICAL_MANIFEST,
    CanonicalEntityManifest,
    get_manifest,
    list_all_manifests,
    get_total_expected_rows,
)
from ingestion.validator import CanonicalSourceValidator, PreflightValidationReport
from ingestion.pipeline import CanonicalIngestionPipeline, IngestionPlan
from ingestion.cli import main as cli_main


@pytest.fixture
def source_mgr() -> CanonicalSourceManager:
    mgr = CanonicalSourceManager()
    if not mgr.root.exists():
        pytest.skip(f"Canonical dataset root does not exist: {mgr.root}")
    return mgr


@pytest.fixture
def mock_conn_mgr() -> MagicMock:
    mgr = MagicMock()
    mgr.is_configured = False
    mgr.config.database = "COCO_FACTORY"
    mgr.config.schema = "CORE"
    return mgr


@pytest.fixture
def ddl_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent / "snowflake" / "ddl" / "coco_factory"


# ==============================================================================
# SECTION 1: MANIFEST TESTS
# ==============================================================================

def test_manifest_contains_all_19_canonical_entities():
    """Verify manifest covers all 19 canonical manufacturing entities."""
    assert len(CANONICAL_MANIFEST) == 19
    for entity in CANONICAL_ENTITIES:
        assert entity in CANONICAL_MANIFEST
        m = get_manifest(entity)
        assert m.entity_name == entity
        assert m.source_filename.endswith(".csv")
        assert m.raw_table.startswith("COCO_FACTORY.RAW.")
        assert m.core_table.startswith("COCO_FACTORY.CORE.")
        assert m.stage_path.startswith("@COCO_FACTORY.RAW.FACTORY_STAGE/")
        assert len(m.expected_columns) > 0
        assert m.expected_rows > 0
        assert len(m.primary_keys) > 0


def test_manifest_cardinality_expectations():
    """Verify manifest row count expectations match canonical specification."""
    expected_row_counts = {
        "machine": 25,
        "component": 141,
        "sensor": 144,
        "sensor_reading": 2903040,
        "sensor_reading_hourly": 1254528,
        "production_order": 1524,
        "production_run": 19593,
        "downtime_event": 67385,
        "maintenance_work_order": 637,
        "technician": 6,
        "maintenance_log": 610,
        "wo_part_usage": 671,
        "spare_part": 32,
        "supplier": 12,
        "purchase_order": 217,
        "product": 8,
        "alert": 1142,
        "prediction": 326,
        "knowledge_doc": 16,
    }
    for entity, exp_count in expected_row_counts.items():
        assert CANONICAL_MANIFEST[entity].expected_rows == exp_count
    assert get_total_expected_rows() == 4250057


# ==============================================================================
# SECTION 2: CANONICAL SOURCE PREFLIGHT VALIDATION TESTS
# ==============================================================================

def test_canonical_source_validator_preflight(source_mgr: CanonicalSourceManager):
    """Run full preflight validation on the authoritative canonical dataset."""
    validator = CanonicalSourceValidator(source_mgr)
    report = validator.run_preflight_validation()

    assert report.is_valid is True
    assert report.total_datasets_checked == 19
    assert report.total_actual_rows == 4250057
    assert len(report.errors) == 0
    assert all(report.files_present.values())
    assert all(report.schema_matches.values())
    assert all(report.row_count_matches.values())


def test_canonical_invariants_validation(source_mgr: CanonicalSourceManager):
    """Verify all domain invariants for M21, PRED-000322, SP-002, and PRD-01278."""
    validator = CanonicalSourceValidator(source_mgr)
    invariants, errors = validator.validate_canonical_invariants()

    assert invariants["M21_IDENTITY (Grinder 3, L5, GR-600, Grinder)"] is True
    assert invariants["C-M21-BRG_COMPONENT (Drive-End Bearing 6206-2RS)"] is True
    assert invariants["M21_SENSORS (S-M21-VIB and S-M21-BTMP on C-M21-BRG)"] is True
    assert invariants["SP-002_STOCKOUT (6206-2RS, stock_qty=0, SUP-12, lead_time=5d)"] is True
    assert invariants["PRED-000322_PREDICTION (M21, C-M21-BRG, prob=0.95, risk=high, horizon=7d)"] is True
    assert invariants["PRD-01278_CUSTOMER (M21, customer=Keystone Hydraulics)"] is True


def test_canonical_column_types_and_nullability(source_mgr: CanonicalSourceManager):
    """Verify primary key nullability and numeric type constraints."""
    validator = CanonicalSourceValidator(source_mgr)
    type_checks, errors = validator.validate_column_types_and_nullability()

    assert len(errors) == 0
    assert type_checks["PK_NOT_NULL_MACHINE"] is True
    assert type_checks["NUMERIC_MACHINE_SHIFTS"] is True
    assert type_checks["PK_NOT_NULL_COMPONENT"] is True
    assert type_checks["PK_NOT_NULL_SPARE_PART"] is True
    assert type_checks["NUMERIC_SPARE_PART_COST"] is True
    assert type_checks["PK_NOT_NULL_PREDICTION"] is True
    assert type_checks["NUMERIC_PROBABILITY_BOUNDS_0_1"] is True


def test_canonical_data_quality_rules(source_mgr: CanonicalSourceManager):
    """Verify basic domain constraints and sanity bounds on the source dataset."""
    validator = CanonicalSourceValidator(source_mgr)
    dq_results, errors = validator.validate_data_quality_rules()

    assert len(errors) == 0
    assert dq_results["NON_NEGATIVE_STOCK_QTY"] is True
    assert dq_results["NON_NEGATIVE_DOWNTIME_DURATION"] is True
    assert dq_results["RUN_FRACTION_BOUNDS_0_1"] is True


# ==============================================================================
# SECTION 3: STAGING & PIPELINE ORCHESTRATION TESTS
# ==============================================================================

def test_pipeline_stage_put_commands(source_mgr: CanonicalSourceManager, mock_conn_mgr: MagicMock):
    """Verify staging PUT commands use forward slashes, AUTO_COMPRESS, and OVERWRITE."""
    pipeline = CanonicalIngestionPipeline(source_mgr=source_mgr, conn_mgr=mock_conn_mgr)
    put_commands = pipeline.build_stage_put_commands()

    assert len(put_commands) == 19
    for entity, cmd in put_commands:
        assert cmd.startswith("PUT file://")
        assert "@COCO_FACTORY.RAW.FACTORY_STAGE" in cmd
        assert "AUTO_COMPRESS=TRUE" in cmd
        assert "OVERWRITE=TRUE" in cmd
        # Snowflake PUT command requires forward slashes even on Windows
        file_part = cmd.split(" ")[1].replace("file://", "")
        assert "\\" not in file_part


def test_pipeline_raw_copy_batch_lineage_and_idempotency(source_mgr: CanonicalSourceManager, mock_conn_mgr: MagicMock):
    """Verify 70_raw_ingestion_copy.sql statements receive shared batch ID and prepends idempotent batch purge."""
    pipeline = CanonicalIngestionPipeline(source_mgr=source_mgr, conn_mgr=mock_conn_mgr)
    test_batch_id = "BATCH_20261002_TEST_001"
    statements = pipeline.build_raw_copy_statements(test_batch_id)

    # 2 USE statements + 19 DELETE purge statements + 19 COPY INTO statements = 40 statements
    assert len(statements) == 40

    copy_statements = [s for s in statements if s.startswith("COPY INTO RAW.")]
    assert len(copy_statements) == 19

    delete_statements = [s for s in statements if s.startswith("DELETE FROM RAW.")]
    assert len(delete_statements) == 19

    for s in copy_statements:
        assert test_batch_id in s
        assert "__BATCH_ID__" not in s
        assert "BATCH_INIT" not in s

    for s in delete_statements:
        assert test_batch_id in s
        assert "WHERE _batch_id =" in s


def test_pipeline_core_transforms_and_atomic_swap(source_mgr: CanonicalSourceManager, mock_conn_mgr: MagicMock):
    """Verify 80_core_conformed_transforms.sql includes all transforms and atomic telemetry swap."""
    pipeline = CanonicalIngestionPipeline(source_mgr=source_mgr, conn_mgr=mock_conn_mgr)
    transforms = pipeline.build_core_transform_statements()

    assert len(transforms) >= 20
    full_text = "\n".join(transforms)
    assert "MERGE INTO CORE.MACHINE" in full_text
    assert "MERGE INTO CORE.COMPONENT" in full_text
    assert "MERGE INTO CORE.SENSOR" in full_text
    assert "MERGE INTO CORE.SPARE_PART" in full_text
    assert "MERGE INTO CORE.PREDICTION" in full_text
    assert "CREATE OR REPLACE TRANSIENT TABLE CORE.SENSOR_READING_STAGE" in full_text
    assert "INSERT INTO CORE.SENSOR_READING_STAGE" in full_text
    assert "ALTER TABLE CORE.SENSOR_READING SWAP WITH CORE.SENSOR_READING_STAGE" in full_text
    assert "DROP TABLE IF EXISTS CORE.SENSOR_READING_STAGE" in full_text


def test_pipeline_data_quality_verification_queries(source_mgr: CanonicalSourceManager, mock_conn_mgr: MagicMock):
    """Verify 90_data_quality.sql queries are parsed and contain essential checks."""
    pipeline = CanonicalIngestionPipeline(source_mgr=source_mgr, conn_mgr=mock_conn_mgr)
    dq_statements = pipeline.build_data_quality_statements()

    assert len(dq_statements) >= 15
    full_text = "\n".join(dq_statements)
    assert "ORPHAN_COMPONENT" in full_text
    assert "ORPHAN_SENSOR_MACHINE" in full_text
    assert "ORPHAN_PO_PART" in full_text
    assert "M21_IDENTITY" in full_text
    assert "SP002_STOCKOUT" in full_text
    assert "PRED000322_M21_SCORE" in full_text


# ==============================================================================
# SECTION 4: DRY-RUN SAFETY & LIVE EXECUTION GUARD TESTS
# ==============================================================================

def test_dry_run_executes_without_touching_snowflake(source_mgr: CanonicalSourceManager, mock_conn_mgr: MagicMock):
    """Verify dry_run executes completely, returns ready plan, and NEVER calls Snowflake."""
    pipeline = CanonicalIngestionPipeline(source_mgr=source_mgr, conn_mgr=mock_conn_mgr)
    success, plan, output = pipeline.run_dry_run()

    assert success is True
    assert plan.is_ready_for_execution is True
    assert len(plan.stage_put_commands) == 19
    assert len(plan.raw_copy_statements) == 40
    assert len(plan.core_transform_statements) == 24
    assert len(plan.data_quality_statements) == 18
    assert "Dry-run preflight validation PASSED" in output

    # CRITICAL: Verify mock_conn_mgr was NEVER touched
    mock_conn_mgr.get_connection.assert_not_called()


def test_live_execution_guard_blocks_unauthorized_execution(source_mgr: CanonicalSourceManager, mock_conn_mgr: MagicMock):
    """Verify execute_live raises RuntimeError if execute_live flag is False."""
    pipeline = CanonicalIngestionPipeline(source_mgr=source_mgr, conn_mgr=mock_conn_mgr)

    with pytest.raises(RuntimeError) as exc_info:
        pipeline.execute_live(execute_live=False)

    assert "Live Snowflake mutation blocked" in str(exc_info.value)
    mock_conn_mgr.get_connection.assert_not_called()


def test_cli_preflight_and_dry_run_commands(capsys):
    """Verify CLI interface runs preflight and dry-run without errors."""
    # 1. Manifest
    ret_manifest = cli_main(["--manifest"])
    assert ret_manifest == 0
    captured_m = capsys.readouterr()
    assert "COCO_FACTORY CANONICAL DATASET SOURCE-TO-TARGET INGESTION MANIFEST" in captured_m.out
    assert "4,250,057" in captured_m.out

    # 2. Preflight
    ret_preflight = cli_main(["--preflight"])
    assert ret_preflight == 0
    captured_p = capsys.readouterr()
    assert "CANONICAL SOURCE PREFLIGHT VALIDATION REPORT: PASSED" in captured_p.out
    assert "M21_IDENTITY" in captured_p.out

    # 3. Dry run
    ret_dry_run = cli_main(["--dry-run", "--batch-id", "BATCH_PYTEST_DRYRUN"])
    assert ret_dry_run == 0
    captured_d = capsys.readouterr()
    assert "BATCH_PYTEST_DRYRUN" in captured_d.out
    assert "Dry-run preflight validation PASSED" in captured_d.out

    # 4. Live execution blocked without confirmation
    ret_live_blocked = cli_main(["--execute-live"])
    assert ret_live_blocked == 1
    captured_l = capsys.readouterr()
    assert "Live execution blocked" in captured_l.out


def test_pipeline_fails_when_dq_violations_found(source_mgr: CanonicalSourceManager):
    """Verify execute_live aborts and reports failure if DQ queries detect violations."""
    from ingestion.pipeline import DeploymentStage
    mock_cur = MagicMock()
    # Simulate valid telemetry pre-swap count: (2903040, 0)
    mock_cur.fetchone.return_value = (2903040, 0)
    # Simulate an orphan violation: [('ORPHAN_COMPONENT', 5)]
    mock_cur.fetchall.return_value = [("ORPHAN_COMPONENT", 5)]
    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cur

    mock_mgr = MagicMock()
    mock_mgr.is_configured = True
    mock_mgr.get_connection.return_value = mock_conn

    # Mock verify_session to pass read-only connection check
    from repositories.snowflake.connection import SnowflakeSessionVerification
    mock_mgr.verify_session.return_value = SnowflakeSessionVerification(
        is_connected=True,
        auth_method="PASSWORD",
        user="TEST_USER",
        role="SYSADMIN",
        warehouse="COMPUTE_WH",
        database="COCO_FACTORY",
        schema="RAW",
    )

    pipeline = CanonicalIngestionPipeline(source_mgr=source_mgr, conn_mgr=mock_mgr)
    result = pipeline.execute_live(execute_live=True)

    assert result.success is False
    assert result.stage == DeploymentStage.DATA_QUALITY_VERIFICATION
    assert any("ORPHAN_COMPONENT" in err for err in result.error_details)


def test_telemetry_swap_guard_aborts_when_stage_table_empty(source_mgr: CanonicalSourceManager):
    """Verify that if SENSOR_READING_STAGE has 0 rows, swap is aborted and staging table dropped."""
    from ingestion.pipeline import DeploymentStage
    mock_cur = MagicMock()
    # When checking SENSOR_READING_STAGE: return (0, 0) (0 rows!)
    mock_cur.fetchone.return_value = (0, 0)
    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cur

    mock_mgr = MagicMock()
    mock_mgr.is_configured = True
    mock_mgr.get_connection.return_value = mock_conn

    from repositories.snowflake.connection import SnowflakeSessionVerification
    mock_mgr.verify_session.return_value = SnowflakeSessionVerification(
        is_connected=True,
        auth_method="PASSWORD",
        user="TEST_USER",
        role="SYSADMIN",
        warehouse="COMPUTE_WH",
        database="COCO_FACTORY",
        schema="RAW",
    )

    pipeline = CanonicalIngestionPipeline(source_mgr=source_mgr, conn_mgr=mock_mgr)
    result = pipeline.execute_live(execute_live=True)

    assert result.success is False
    assert result.stage == DeploymentStage.TELEMETRY_SWAP_VALIDATION
    assert "Telemetry pre-swap validation failed" in result.message
    # Assert drop table was called to clean up staging table
    assert any("DROP TABLE IF EXISTS CORE.SENSOR_READING_STAGE" in str(c) for c in mock_cur.execute.call_args_list)


def test_pre_deployment_connection_checkpoint(mock_conn_mgr: MagicMock):
    """Verify read-only connection checkpoint inspects metadata without mutation."""
    from repositories.snowflake.connection import SnowflakeSessionVerification

    mock_conn_mgr.is_configured = True
    mock_conn_mgr.verify_session.return_value = SnowflakeSessionVerification(
        is_connected=True,
        auth_method="KEY_PAIR",
        user="SVC_COCO",
        role="COCO_ADMIN",
        warehouse="COCO_WH",
        database="COCO_FACTORY",
        schema="RAW",
        version="8.12.0",
        latency_ms=45.2,
    )

    pipeline = CanonicalIngestionPipeline(conn_mgr=mock_conn_mgr)
    ok, details, msg = pipeline.verify_pre_deployment_connection()

    assert ok is True
    assert details["user"] == "SVC_COCO"
    assert details["role"] == "COCO_ADMIN"
    assert details["database"] == "COCO_FACTORY"
    assert details["target_database"] == "COCO_FACTORY"
    assert "Pre-deployment connection verified successfully" in msg
    # Verify no connection mutation was performed
    mock_conn_mgr.get_connection.assert_not_called()


def test_bootstrap_connection_omits_database_and_schema():
    """Verify bootstrap connection connects at account level without database/schema in handshake."""
    from unittest.mock import patch
    from config import SnowflakeConfig
    from repositories.snowflake.connection import SnowflakeConnectionManager
    import sys

    cfg = SnowflakeConfig(
        account="xy12345.us-east-1",
        user="ACCOUNTADMIN_USER",
        password="SafePassword123!",
        warehouse="COMPUTE_WH",
        role="ACCOUNTADMIN",
        database="COCO_FACTORY",
        schema="CORE",
    )
    mgr = SnowflakeConnectionManager(cfg)
    assert mgr.is_configured

    mock_snowflake = MagicMock()
    mock_connector = MagicMock()
    mock_snowflake.connector = mock_connector

    with patch.dict(sys.modules, {"snowflake": mock_snowflake, "snowflake.connector": mock_connector}):
        # 1. Bootstrap connection: database and schema MUST be omitted
        conn = mgr.get_connection(bootstrap=True)
        assert mock_connector.connect.called
        kwargs = mock_connector.connect.call_args.kwargs
        assert kwargs["account"] == "xy12345.us-east-1"
        assert kwargs["user"] == "ACCOUNTADMIN_USER"
        assert kwargs["role"] == "ACCOUNTADMIN"
        assert kwargs["warehouse"] == "COMPUTE_WH"
        assert "database" not in kwargs, "Bootstrap connection must not pass database"
        assert "schema" not in kwargs, "Bootstrap connection must not pass schema"

        # 2. get_bootstrap_connection helper must also omit database and schema
        mock_connector.connect.reset_mock()
        conn_helper = mgr.get_bootstrap_connection()
        assert mock_connector.connect.called
        kwargs_helper = mock_connector.connect.call_args.kwargs
        assert "database" not in kwargs_helper
        assert "schema" not in kwargs_helper


def test_post_bootstrap_connection_targets_coco_factory_core():
    """Verify post-bootstrap connection explicitly targets COCO_FACTORY database and CORE schema."""
    from unittest.mock import patch
    from config import SnowflakeConfig
    from repositories.snowflake.connection import SnowflakeConnectionManager
    import sys

    cfg = SnowflakeConfig(
        account="xy12345.us-east-1",
        user="ACCOUNTADMIN_USER",
        password="SafePassword123!",
        warehouse="COMPUTE_WH",
        role="ACCOUNTADMIN",
        database="COCO_FACTORY",
        schema="CORE",
    )
    mgr = SnowflakeConnectionManager(cfg)

    mock_snowflake = MagicMock()
    mock_connector = MagicMock()
    mock_snowflake.connector = mock_connector

    with patch.dict(sys.modules, {"snowflake": mock_snowflake, "snowflake.connector": mock_connector}):
        conn = mgr.get_connection(bootstrap=False)
        assert mock_connector.connect.called
        kwargs = mock_connector.connect.call_args.kwargs
        assert kwargs["account"] == "xy12345.us-east-1"
        assert kwargs["user"] == "ACCOUNTADMIN_USER"
        assert kwargs["database"] == "COCO_FACTORY"
        assert kwargs["schema"] == "CORE"


def test_pre_deployment_connection_check_succeeds_in_bootstrap_mode_when_database_is_none():
    """Verify pre-deployment check succeeds when database does not yet exist on clean account."""
    from repositories.snowflake.connection import SnowflakeSessionVerification

    mock_conn_mgr = MagicMock()
    mock_conn_mgr.is_configured = True
    mock_conn_mgr.config.database = "COCO_FACTORY"
    mock_conn_mgr.config.schema = "CORE"
    mock_conn_mgr.verify_session.return_value = SnowflakeSessionVerification(
        is_connected=True,
        auth_method="PASSWORD",
        user="ACCOUNTADMIN_USER",
        role="ACCOUNTADMIN",
        warehouse="COMPUTE_WH",
        database=None,   # Database does not exist yet!
        schema=None,     # Schema does not exist yet!
        version="8.14.0",
        latency_ms=28.4,
    )

    pipeline = CanonicalIngestionPipeline(conn_mgr=mock_conn_mgr)
    ok, details, msg = pipeline.verify_pre_deployment_connection(bootstrap=True)

    assert ok is True
    assert details["is_connected"] is True
    assert details["database"] is None
    assert details["schema"] is None
    assert details["target_database"] == "COCO_FACTORY"
    assert details["target_schema"] == "CORE"
    assert details["bootstrap_mode"] is True
    assert "[Bootstrap - target COCO_FACTORY]" in msg
    mock_conn_mgr.get_connection.assert_not_called()


def test_init_coco_factory_uses_bootstrap_connection_and_verifies_context():
    """Verify initialize_coco_factory connects with bootstrap=True and validates post-bootstrap context."""
    from snowflake.scripts.init_coco_factory import initialize_coco_factory

    mock_mgr = MagicMock()
    mock_mgr.is_configured = True
    mock_mgr.config.database = "COCO_FACTORY"
    mock_mgr.config.schema = "CORE"

    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value = mock_cur
    mock_cur.fetchone.return_value = ("COCO_FACTORY", "CORE")
    mock_mgr.get_connection.return_value = mock_conn

    success, msg = initialize_coco_factory(conn_mgr=mock_mgr, dry_run=False)

    assert success is True
    # Crucial: verify get_connection was invoked with bootstrap=True
    mock_mgr.get_connection.assert_called_once_with(bootstrap=True)
    # Crucial: verify post-bootstrap USE DATABASE and USE SCHEMA were executed
    executed_statements = [call[0][0] for call in mock_cur.execute.call_args_list]
    assert any("USE DATABASE COCO_FACTORY" in s for s in executed_statements)
    assert any("USE SCHEMA CORE" in s for s in executed_statements)
    assert any("SELECT CURRENT_DATABASE(), CURRENT_SCHEMA()" in s for s in executed_statements)
    mock_conn.commit.assert_called_once()


def test_cli_check_connection(capsys, mock_conn_mgr: MagicMock):
    """Verify CLI --check-connection command runs read-only verification."""
    from unittest.mock import patch
    from repositories.snowflake.connection import SnowflakeSessionVerification

    mock_session = SnowflakeSessionVerification(
        is_connected=True,
        auth_method="PASSWORD",
        user="FACTORY_ADMIN",
        role="ENGINEER",
        warehouse="ANALYTICS_WH",
        database="COCO_FACTORY",
        schema="CORE",
        version="8.12.0",
        latency_ms=32.1,
    )

    with patch.object(CanonicalIngestionPipeline, "verify_pre_deployment_connection", return_value=(True, {
        "user": "FACTORY_ADMIN",
        "role": "ENGINEER",
        "warehouse": "ANALYTICS_WH",
        "database": "COCO_FACTORY",
        "schema": "CORE",
        "version": "8.12.0",
    }, "Verified")):
        ret = cli_main(["--check-connection"])
        assert ret == 0
        captured = capsys.readouterr()
        assert "FACTORY_ADMIN" in captured.out
        assert "COCO_FACTORY" in captured.out


def test_schema_validation_detects_unexpected_or_missing_columns(tmp_path):
    """Verify validator flags any unexpected or missing columns."""
    from ingestion.validator import CanonicalSourceValidator
    from ingestion.canonical_source import CanonicalSourceManager
    import csv

    # Create dummy canonical directory missing machine_type column in machine.csv
    test_root = tmp_path / "test_oee"
    test_root.mkdir()
    bad_machine = test_root / "machine.csv"
    with open(bad_machine, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["machine_id", "wrong_column_name"])

    mgr = CanonicalSourceManager(source_root=str(test_root))
    val = CanonicalSourceValidator(mgr)
    schemas, errors = val.validate_schemas()

    assert schemas.get("machine") is False
    assert any("machine" in e and ("missing" in e or "mismatch" in e) for e in errors)
