"""Deterministic Initialization and Deployment Script for COCO_FACTORY.

Executes DDL scripts in strictly defined order:
1. 00_database.sql
2. 01_schemas.sql
3. 02_file_formats.sql
4. 03_stage.sql
5. 10_raw_tables.sql
6. 20_core_tables.sql
7. 30_analytics_foundation.sql
8. 40_ml_foundation.sql
9. 50_knowledge_foundation.sql
10. 60_app_foundation.sql
Optional data loading & transformation:
11. 70_raw_ingestion_copy.sql (via --load-data)
12. 80_core_conformed_transforms.sql (via --transform-data)
13. 90_data_quality.sql (via --verify)

Supports --dry-run mode for local validation when Snowflake is offline.
Supports dynamic --batch-id injection across all 19 RAW ingestion COPY statements.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import logging
import os
import re
import sys
from pathlib import Path
from typing import List, Optional, Tuple

# Ensure project root is in path
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from repositories.snowflake.connection import SnowflakeConnectionManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

FOUNDATION_DDL_SCRIPTS: List[str] = [
    "00_database.sql",
    "01_schemas.sql",
    "02_file_formats.sql",
    "03_stage.sql",
    "10_raw_tables.sql",
    "20_core_tables.sql",
    "30_analytics_foundation.sql",
    "40_ml_foundation.sql",
    "50_knowledge_foundation.sql",
    "60_app_foundation.sql",
]


def generate_batch_id() -> str:
    """Generate a deterministic execution-level batch ID: BATCH_YYYYMMDD_HHMMSS."""
    return f"BATCH_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"


def prepare_script_content(script_name: str, content: str, batch_id: str) -> str:
    """Prepare script content by injecting execution-level parameters such as _BATCH_ID."""
    if script_name == "70_raw_ingestion_copy.sql":
        # Replace '__BATCH_ID__' placeholder or legacy 'BATCH_INIT' with the execution batch ID
        content = content.replace("'__BATCH_ID__'", f"'{batch_id}'")
        content = content.replace("'BATCH_INIT'", f"'{batch_id}'")
    return content


def parse_sql_statements(content: str) -> List[str]:
    """Parse raw SQL content into distinct executable statements, stripping comments."""
    statements: List[str] = []
    # Split by semicolon
    raw_statements = [s.strip() for s in content.split(";") if s.strip()]
    for raw in raw_statements:
        lines = [line for line in raw.splitlines() if not line.strip().startswith("--")]
        clean = "\n".join(lines).strip()
        if clean:
            statements.append(clean)
    return statements


def execute_sql_file(cur, filepath: Path, batch_id: Optional[str] = None) -> int:
    """Read and execute SQL commands from a file with dynamic parameter injection."""
    raw_content = filepath.read_text(encoding="utf-8")
    content = prepare_script_content(filepath.name, raw_content, batch_id or generate_batch_id())
    statements = parse_sql_statements(content)
    executed = 0
    for stmt in statements:
        cur.execute(stmt)
        executed += 1
    return executed


def initialize_coco_factory(
    conn_mgr: SnowflakeConnectionManager | None = None,
    dry_run: bool = False,
    load_data: bool = False,
    transform_data: bool = False,
    verify: bool = False,
    batch_id: Optional[str] = None,
) -> Tuple[bool, str]:
    """Execute all foundation DDL and optional pipelines with dynamic batch lineage."""
    ddl_dir = project_root / "snowflake" / "ddl" / "coco_factory"
    if not ddl_dir.exists():
        return False, f"COCO_FACTORY DDL directory not found: {ddl_dir}"

    effective_batch_id = (batch_id.strip() if batch_id else None) or generate_batch_id()

    scripts_to_run = list(FOUNDATION_DDL_SCRIPTS)
    if load_data:
        scripts_to_run.append("70_raw_ingestion_copy.sql")
    if transform_data:
        scripts_to_run.append("80_core_conformed_transforms.sql")
    if verify:
        scripts_to_run.append("90_data_quality.sql")

    # Verify all files exist and parse
    plan = []
    for script_name in scripts_to_run:
        file_path = ddl_dir / script_name
        if not file_path.exists():
            return False, f"Missing DDL script: {file_path}"
        raw_content = file_path.read_text(encoding="utf-8")
        content = prepare_script_content(script_name, raw_content, effective_batch_id)
        stmts = parse_sql_statements(content)
        plan.append((script_name, file_path, len(stmts), content))

    if dry_run:
        logger.info("=== DRY RUN: COCO_FACTORY Deployment Plan ===")
        logger.info("Shared execution batch ID: %s", effective_batch_id)
        total_stmts = 0
        for name, _, count, _ in plan:
            logger.info("Script: %s -> %d statements", name, count)
            total_stmts += count
        msg = f"Dry run validation successful. {len(plan)} scripts, {total_stmts} statements parsed. Batch ID: {effective_batch_id}"
        logger.info(msg)
        return True, msg

    mgr = conn_mgr or SnowflakeConnectionManager()
    if not mgr.is_configured:
        return False, "Snowflake credentials not configured in environment. Use --dry-run for syntax validation."

    try:
        conn = mgr.get_connection()
        cur = conn.cursor()
        try:
            total_executed = 0
            logger.info("Executing deployment with shared batch ID: %s", effective_batch_id)
            for name, file_path, _, prepared_content in plan:
                logger.info("Executing %s...", name)
                statements = parse_sql_statements(prepared_content)
                for stmt in statements:
                    cur.execute(stmt)
                    total_executed += 1
                logger.info("Executed %d statements from %s", len(statements), name)
            conn.commit()
            msg = f"Successfully deployed COCO_FACTORY: {len(plan)} scripts executed ({total_executed} statements). Batch ID: {effective_batch_id}"
            logger.info(msg)
            return True, msg
        finally:
            cur.close()
            conn.close()
    except Exception as e:
        logger.error("Failed to initialize COCO_FACTORY: %s", e)
        return False, str(e)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Initialize COCO_FACTORY in Snowflake")
    parser.add_argument("--dry-run", action="store_true", help="Validate scripts without executing against live Snowflake")
    parser.add_argument("--load-data", action="store_true", help="Include 70_raw_ingestion_copy.sql")
    parser.add_argument("--transform-data", action="store_true", help="Include 80_core_conformed_transforms.sql")
    parser.add_argument("--verify", action="store_true", help="Include 90_data_quality.sql")
    parser.add_argument("--batch-id", default=None, help="Explicit batch ID for RAW ingestion (defaults to execution timestamp)")
    args = parser.parse_args()

    success, message = initialize_coco_factory(
        dry_run=args.dry_run,
        load_data=args.load_data,
        transform_data=args.transform_data,
        verify=args.verify,
        batch_id=args.batch_id,
    )
    if not success:
        logger.error("COCO_FACTORY initialization failed: %s", message)
        sys.exit(1)
    logger.info("Done: %s", message)
