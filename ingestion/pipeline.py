"""Canonical Snowflake Ingestion Pipeline Orchestrator.

Orchestrates the complete 5-stage ELT pipeline for the 19 canonical manufacturing datasets:
1. PREFLIGHT: Source presence, schema, row counts, and canonical domain invariants validation
2. CONNECTION CHECK: Read-only verification of account, user, role, warehouse, and database context
3. STAGE: Idempotent PUT upload of canonical CSV files to @COCO_FACTORY.RAW.FACTORY_STAGE
4. RAW LOAD: Deterministic, idempotent batch-tagged COPY INTO execution with pre-purge per batch
5. CORE TRANSFORM: Conformed transformations with type casting, deduplication, and atomic swap
6. DATA QUALITY: Automated referential integrity and invariant verification

Supports strict dry-run mode and guards live execution behind explicit confirmation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import logging
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Tuple

from ingestion.canonical_source import CanonicalSourceManager
from ingestion.manifest import CANONICAL_MANIFEST, CanonicalEntityManifest, get_total_expected_rows
from ingestion.validator import CanonicalSourceValidator, PreflightValidationReport
from repositories.snowflake.connection import SnowflakeConnectionManager

logger = logging.getLogger(__name__)


class DeploymentStage(str, Enum):
    """Pipeline deployment lifecycle stages."""

    PREFLIGHT_VALIDATION = "PREFLIGHT_VALIDATION"
    CONNECTION_CHECK = "CONNECTION_CHECK"
    BOOTSTRAP_FOUNDATION = "BOOTSTRAP_FOUNDATION"
    STAGING_PUT = "STAGING_PUT"
    RAW_COPY = "RAW_COPY"
    CORE_TRANSFORMS = "CORE_TRANSFORMS"
    TELEMETRY_SWAP_VALIDATION = "TELEMETRY_SWAP_VALIDATION"
    DATA_QUALITY_VERIFICATION = "DATA_QUALITY_VERIFICATION"
    COMPLETED = "COMPLETED"


@dataclass
class DeploymentResult:
    """Structured result of a live or simulated pipeline deployment."""

    success: bool
    stage: DeploymentStage
    batch_id: str
    message: str
    error_details: List[str] = field(default_factory=list)
    executed_statements: int = 0


@dataclass
class IngestionPlan:
    """Compiled execution plan for canonical Snowflake ingestion."""

    batch_id: str
    preflight_report: PreflightValidationReport
    stage_put_commands: List[Tuple[str, str]] = field(default_factory=list)  # (entity, put_command)
    raw_copy_statements: List[str] = field(default_factory=list)
    core_transform_statements: List[str] = field(default_factory=list)
    data_quality_statements: List[str] = field(default_factory=list)
    is_ready_for_execution: bool = False

    def generate_plan_summary(self) -> str:
        """Render a readable summary of the execution plan."""
        lines = []
        lines.append("=" * 80)
        lines.append(f"CANONICAL INGESTION EXECUTION PLAN (Batch ID: {self.batch_id})")
        lines.append("=" * 80)
        lines.append(f"Preflight Validation: {'PASSED' if self.preflight_report.is_valid else 'FAILED'}")
        lines.append(f"Datasets in Scope:    {len(self.stage_put_commands)} / 19")
        lines.append(f"Expected Rows:        {self.preflight_report.total_expected_rows:,}")
        lines.append(f"Staging Commands:     {len(self.stage_put_commands)} PUT statements")
        lines.append(f"RAW COPY Statements:  {len(self.raw_copy_statements)} statements (with batch purge)")
        lines.append(f"CORE Transform Steps: {len(self.core_transform_statements)} statements (with atomic swap)")
        lines.append(f"Data Quality Checks:  {len(self.data_quality_statements)} queries")
        lines.append("-" * 80)
        lines.append("STAGING ORCHESTRATION (Local File -> @COCO_FACTORY.RAW.FACTORY_STAGE):")
        for entity, cmd in self.stage_put_commands:
            lines.append(f"  [{entity:<22}] {cmd}")
        lines.append("-" * 80)
        lines.append("RAW COPY ORCHESTRATION (Sample Statements):")
        for i, stmt in enumerate(self.raw_copy_statements[:4], 1):
            first_line = stmt.strip().splitlines()[0]
            lines.append(f"  {i}. {first_line}...")
        if len(self.raw_copy_statements) > 4:
            lines.append(f"  ... ({len(self.raw_copy_statements) - 4} more statements)")
        lines.append("-" * 80)
        lines.append("CORE TRANSFORMS IN SCOPE:")
        for i, stmt in enumerate(self.core_transform_statements[:4], 1):
            first_line = stmt.strip().splitlines()[0]
            lines.append(f"  {i}. {first_line}...")
        if len(self.core_transform_statements) > 4:
            lines.append(f"  ... ({len(self.core_transform_statements) - 4} more transform statements)")
        lines.append("=" * 80)
        return "\n".join(lines)


class CanonicalIngestionPipeline:
    """Orchestrates validation, staging, raw loading, and conformed transformations for COCO_FACTORY."""

    def __init__(
        self,
        source_mgr: Optional[CanonicalSourceManager] = None,
        conn_mgr: Optional[SnowflakeConnectionManager] = None,
        ddl_dir: Optional[Path] = None,
    ) -> None:
        self.source_mgr = source_mgr or CanonicalSourceManager()
        self.validator = CanonicalSourceValidator(self.source_mgr)
        self.conn_mgr = conn_mgr or SnowflakeConnectionManager()
        if ddl_dir:
            self.ddl_dir = ddl_dir
        else:
            self.ddl_dir = Path(__file__).resolve().parent.parent / "snowflake" / "ddl" / "coco_factory"

    def generate_batch_id(self) -> str:
        """Deterministic execution-level batch identifier."""
        return f"BATCH_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"

    def parse_sql_file(self, filename: str) -> List[str]:
        """Parse clean SQL statements from a file in the DDL directory."""
        file_path = self.ddl_dir / filename
        if not file_path.exists():
            raise FileNotFoundError(f"DDL file not found: {file_path}")

        content = file_path.read_text(encoding="utf-8")
        raw_statements = [s.strip() for s in content.split(";") if s.strip()]
        statements = []
        for raw in raw_statements:
            clean_lines = [l for l in raw.splitlines() if not l.strip().startswith("--")]
            clean = "\n".join(clean_lines).strip()
            if clean:
                statements.append(clean)
        return statements

    def verify_pre_deployment_connection(self, bootstrap: bool = True) -> Tuple[bool, Dict[str, Any], str]:
        """Read-only verification of account, user, role, warehouse, and database context.
        
        Performs strictly non-mutating metadata inspection.
        When bootstrap=True, connects without requiring target database/schema to pre-exist,
        enabling clean-account deployment verification.
        """
        if not self.conn_mgr.is_configured:
            return False, {}, "Snowflake credentials not configured in environment."

        session = self.conn_mgr.verify_session(bootstrap=bootstrap)
        target_db = getattr(self.conn_mgr.config, "database", "COCO_FACTORY")
        target_schema = getattr(self.conn_mgr.config, "schema", "CORE")
        details = {
            "is_connected": session.is_connected,
            "user": session.user,
            "role": session.role,
            "warehouse": session.warehouse,
            "database": session.database,
            "schema": session.schema,
            "target_database": target_db,
            "target_schema": target_schema,
            "bootstrap_mode": bootstrap,
            "version": session.version,
            "latency_ms": session.latency_ms,
            "error_message": session.error_message,
        }

        if not session.is_connected:
            return False, details, f"Pre-deployment connection check failed: {session.error_message}"

        db_label = session.database or f"[Bootstrap - target {target_db}]"
        schema_label = session.schema or f"[Bootstrap - target {target_schema}]"
        summary = (
            f"Pre-deployment connection verified successfully: user={session.user}, "
            f"role={session.role}, warehouse={session.warehouse}, database={db_label}, "
            f"schema={schema_label}, latency={session.latency_ms}ms"
        )
        return True, details, summary

    def build_stage_put_commands(self) -> List[Tuple[str, str]]:
        """Generate idempotent PUT commands for all 19 canonical CSV files."""
        commands = []
        for entity, manifest in CANONICAL_MANIFEST.items():
            path = self.source_mgr.resolve_entity_path(entity)
            if not path:
                raise FileNotFoundError(f"Cannot resolve source path for canonical entity '{entity}'")

            # Snowflake PUT command requires forward slashes on all platforms
            posix_path = str(path.resolve()).replace("\\", "/")
            stage_target = "@COCO_FACTORY.RAW.FACTORY_STAGE"
            # AUTO_COMPRESS=TRUE ensures fast network upload; OVERWRITE=TRUE ensures idempotency
            cmd = f"PUT file://{posix_path} {stage_target} AUTO_COMPRESS=TRUE OVERWRITE=TRUE"
            commands.append((entity, cmd))
        return commands

    def build_raw_copy_statements(self, batch_id: str) -> List[str]:
        """Prepare RAW ingestion statements with execution batch ID and idempotent purge."""
        file_path = self.ddl_dir / "70_raw_ingestion_copy.sql"
        if not file_path.exists():
            raise FileNotFoundError(f"DDL file not found: {file_path}")

        content = file_path.read_text(encoding="utf-8")
        content = content.replace("'__BATCH_ID__'", f"'{batch_id}'")
        content = content.replace("'BATCH_INIT'", f"'{batch_id}'")

        raw_statements = [s.strip() for s in content.split(";") if s.strip()]
        statements = []

        for raw in raw_statements:
            clean_lines = [l for l in raw.splitlines() if not l.strip().startswith("--")]
            clean = "\n".join(clean_lines).strip()
            if not clean:
                continue

            # Idempotency hardening: prepend a targeted DELETE for this batch ID
            match = re.match(r"COPY\s+INTO\s+RAW\.(\w+)", clean, re.IGNORECASE)
            if match:
                table_name = match.group(1).upper()
                purge_stmt = f"DELETE FROM RAW.{table_name} WHERE _batch_id = '{batch_id}'"
                statements.append(purge_stmt)

            statements.append(clean)

        return statements

    def build_core_transform_statements(self) -> List[str]:
        """Parse conformed ELT transforms from 80_core_conformed_transforms.sql."""
        return self.parse_sql_file("80_core_conformed_transforms.sql")

    def build_data_quality_statements(self) -> List[str]:
        """Parse verification checks from 90_data_quality.sql."""
        return self.parse_sql_file("90_data_quality.sql")

    def build_plan(self, batch_id: Optional[str] = None) -> IngestionPlan:
        """Run preflight validation and assemble the complete ingestion plan."""
        effective_batch_id = (batch_id.strip() if batch_id else None) or self.generate_batch_id()

        # Step 1: Preflight Validation
        preflight = self.validator.run_preflight_validation()

        # Step 2: Build Staging PUT commands
        stage_commands = self.build_stage_put_commands()

        # Step 3: Build RAW COPY statements (with idempotent purge per batch)
        raw_statements = self.build_raw_copy_statements(effective_batch_id)

        # Step 4: Build CORE conformed transform statements (with atomic transient swap)
        transform_statements = self.build_core_transform_statements()

        # Step 5: Build Data Quality verification statements
        dq_statements = self.build_data_quality_statements()

        plan = IngestionPlan(
            batch_id=effective_batch_id,
            preflight_report=preflight,
            stage_put_commands=stage_commands,
            raw_copy_statements=raw_statements,
            core_transform_statements=transform_statements,
            data_quality_statements=dq_statements,
            is_ready_for_execution=preflight.is_valid,
        )
        return plan

    def run_dry_run(self, batch_id: Optional[str] = None) -> Tuple[bool, IngestionPlan, str]:
        """Execute complete dry-run validation without touching live Snowflake data."""
        plan = self.build_plan(batch_id=batch_id)
        summary = plan.generate_plan_summary()

        if not plan.is_ready_for_execution:
            err_msg = f"Dry-run preflight validation FAILED with {len(plan.preflight_report.errors)} errors."
            return False, plan, f"{plan.preflight_report.generate_summary()}\n\n{err_msg}"

        msg = f"Dry-run preflight validation PASSED. All 19 canonical datasets and invariants verified. Plan ready for batch {plan.batch_id}."
        return True, plan, f"{plan.preflight_report.generate_summary()}\n\n{summary}\n\n{msg}"

    def execute_live(
        self,
        batch_id: Optional[str] = None,
        execute_live: bool = False,
    ) -> DeploymentResult:
        """Execute ingestion against live Snowflake with fail-closed semantics across all stages.
        
        Strictly guarded behind execute_live=True.
        """
        if not execute_live:
            raise RuntimeError(
                "Live Snowflake mutation blocked. Executing live staging/ingestion requires "
                "explicit parameter 'execute_live=True'. Preflight validation must be reviewed first."
            )

        effective_batch_id = (batch_id.strip() if batch_id else None) or self.generate_batch_id()

        # Stage 1: Preflight Validation Checkpoint
        preflight = self.validator.run_preflight_validation()
        if not preflight.is_valid:
            logger.error("Deployment failed at PREFLIGHT_VALIDATION stage for batch %s", effective_batch_id)
            return DeploymentResult(
                success=False,
                stage=DeploymentStage.PREFLIGHT_VALIDATION,
                batch_id=effective_batch_id,
                message=f"Preflight validation failed with {len(preflight.errors)} errors.",
                error_details=preflight.errors,
            )

        # Stage 2: Read-Only Connection & Session Checkpoint
        conn_ok, conn_details, conn_msg = self.verify_pre_deployment_connection()
        if not conn_ok:
            logger.error("Deployment failed at CONNECTION_CHECK stage for batch %s: %s", effective_batch_id, conn_msg)
            return DeploymentResult(
                success=False,
                stage=DeploymentStage.CONNECTION_CHECK,
                batch_id=effective_batch_id,
                message=conn_msg,
                error_details=[conn_msg],
            )

        plan = self.build_plan(batch_id=effective_batch_id)

        # Stage 3: Bootstrap Foundation DDL (Database, Schemas, Formats, Stages, Tables, Views)
        logger.info("Executing foundation bootstrap DDL for COCO_FACTORY...")
        from snowflake.scripts.init_coco_factory import initialize_coco_factory

        init_ok, init_msg = initialize_coco_factory(
            conn_mgr=self.conn_mgr,
            dry_run=False,
            load_data=False,
            transform_data=False,
            verify=False,
            batch_id=effective_batch_id,
            bootstrap=True,
        )
        if not init_ok:
            logger.error("Deployment failed at BOOTSTRAP_FOUNDATION stage for batch %s: %s", effective_batch_id, init_msg)
            return DeploymentResult(
                success=False,
                stage=DeploymentStage.BOOTSTRAP_FOUNDATION,
                batch_id=effective_batch_id,
                message=f"Foundation DDL initialization failed: {init_msg}",
                error_details=[init_msg],
            )

        conn = self.conn_mgr.get_connection(bootstrap=False)
        cur = conn.cursor()
        total_executed = 0
        try:
            # Stage 4: Staging Upload (PUT)
            logger.info("Executing staging PUT commands for 19 canonical datasets...")
            for entity, cmd in plan.stage_put_commands:
                try:
                    logger.info("Staging entity: %s", entity)
                    cur.execute(cmd)
                    total_executed += 1
                except Exception as e:
                    logger.error("Staging failed on entity %s: %s", entity, e)
                    return DeploymentResult(
                        success=False,
                        stage=DeploymentStage.STAGING_PUT,
                        batch_id=effective_batch_id,
                        message=f"Staging PUT failed for entity '{entity}': {e}",
                        error_details=[str(e)],
                        executed_statements=total_executed,
                    )

            # Stage 4: RAW Copy Ingestion (with Idempotent Purge)
            logger.info("Executing RAW COPY statements with batch %s...", plan.batch_id)
            for stmt in plan.raw_copy_statements:
                try:
                    cur.execute(stmt)
                    total_executed += 1
                except Exception as e:
                    logger.error("RAW copy failed on statement: %s | Error: %s", stmt[:80], e)
                    return DeploymentResult(
                        success=False,
                        stage=DeploymentStage.RAW_COPY,
                        batch_id=effective_batch_id,
                        message=f"RAW copy failed on batch '{plan.batch_id}': {e}",
                        error_details=[str(e)],
                        executed_statements=total_executed,
                    )

            # Stage 5: CORE Conformed Transforms & Telemetry Atomic Swap
            logger.info("Executing CORE conformed transforms...")
            for stmt in plan.core_transform_statements:
                # Pre-swap verification guard for SENSOR_READING
                if "ALTER TABLE CORE.SENSOR_READING SWAP WITH CORE.SENSOR_READING_STAGE" in stmt:
                    logger.info("Validating transient stage table prior to atomic swap...")
                    cur.execute("SELECT COUNT(*), COUNT(CASE WHEN sensor_id IS NULL OR ts IS NULL THEN 1 END) FROM CORE.SENSOR_READING_STAGE")
                    row = cur.fetchone()
                    try:
                        stg_count = int(row[0]) if (row and row[0] is not None) else 0
                        stg_nulls = int(row[1]) if (row and len(row) > 1 and row[1] is not None) else 0
                    except (ValueError, TypeError):
                        stg_count = 0
                        stg_nulls = 1

                    if stg_count == 0 or stg_nulls > 0:
                        # Abort swap and clean up staging table; CORE.SENSOR_READING remains untouched!
                        cur.execute("DROP TABLE IF EXISTS CORE.SENSOR_READING_STAGE")
                        err = f"Telemetry pre-swap validation failed: count={stg_count}, null_pks={stg_nulls}. Swap aborted."
                        logger.error(err)
                        return DeploymentResult(
                            success=False,
                            stage=DeploymentStage.TELEMETRY_SWAP_VALIDATION,
                            batch_id=effective_batch_id,
                            message=err,
                            error_details=[err],
                            executed_statements=total_executed,
                        )

                try:
                    cur.execute(stmt)
                    total_executed += 1
                except Exception as e:
                    logger.error("Core transform failed on statement: %s | Error: %s", stmt[:80], e)
                    # Clean up transient table if left over
                    try:
                        cur.execute("DROP TABLE IF EXISTS CORE.SENSOR_READING_STAGE")
                    except Exception:
                        pass
                    return DeploymentResult(
                        success=False,
                        stage=DeploymentStage.CORE_TRANSFORMS,
                        batch_id=effective_batch_id,
                        message=f"Core transformation failed: {e}",
                        error_details=[str(e)],
                        executed_statements=total_executed,
                    )

            # Commit all conformed transforms
            conn.commit()

            # Stage 6: Data Quality Verification
            logger.info("Executing Data Quality verification...")
            dq_failures = []
            for stmt in plan.data_quality_statements:
                try:
                    cur.execute(stmt)
                    rows = cur.fetchall()
                    total_executed += 1
                    for r in rows:
                        # 1. Null PK check: (table_name, row_count, null_pk_count)
                        if len(r) == 3 and r[2] is not None and not isinstance(r[2], bool) and isinstance(r[2], (int, float)) and r[2] > 0:
                            dq_failures.append(f"Null PKs detected in table {r[0]}: count={r[2]}")
                        # 2. Canonical scenario boolean check: (check_name, passes)
                        elif len(r) == 2 and isinstance(r[1], bool):
                            if not r[1]:
                                dq_failures.append(f"Canonical scenario check failed: {r[0]}")
                        # 3. Orphan or domain violation count check: (check_name, violations)
                        elif len(r) == 2 and not isinstance(r[1], bool) and isinstance(r[1], (int, float)) and r[1] > 0:
                            dq_failures.append(f"DQ violation in {r[0]}: {r[1]} violations")
                except Exception as e:
                    dq_failures.append(f"DQ query execution failed: {e}")

            if dq_failures:
                logger.error("Deployment failed at DATA_QUALITY_VERIFICATION stage: %s", dq_failures)
                return DeploymentResult(
                    success=False,
                    stage=DeploymentStage.DATA_QUALITY_VERIFICATION,
                    batch_id=effective_batch_id,
                    message=f"Data quality validation failed with {len(dq_failures)} violations.",
                    error_details=dq_failures,
                    executed_statements=total_executed,
                )

            logger.info("Live deployment successfully completed for batch %s", effective_batch_id)
            return DeploymentResult(
                success=True,
                stage=DeploymentStage.COMPLETED,
                batch_id=effective_batch_id,
                message=f"Live ingestion successfully completed ({total_executed} statements executed).",
                executed_statements=total_executed,
            )
        finally:
            cur.close()
            conn.close()
