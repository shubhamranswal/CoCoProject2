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
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path
from typing import List, Tuple

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


def execute_sql_file(cur, filepath: Path) -> int:
    """Read and execute SQL commands from a file."""
    content = filepath.read_text(encoding="utf-8")
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
) -> Tuple[bool, str]:
    """Execute all foundation DDL and optional pipelines."""
    ddl_dir = project_root / "snowflake" / "ddl" / "coco_factory"
    if not ddl_dir.exists():
        return False, f"COCO_FACTORY DDL directory not found: {ddl_dir}"

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
        content = file_path.read_text(encoding="utf-8")
        stmts = parse_sql_statements(content)
        plan.append((script_name, file_path, len(stmts)))

    if dry_run:
        logger.info("=== DRY RUN: COCO_FACTORY Deployment Plan ===")
        total_stmts = 0
        for name, _, count in plan:
            logger.info("Script: %s -> %d statements", name, count)
            total_stmts += count
        msg = f"Dry run validation successful. {len(plan)} scripts, {total_stmts} statements parsed."
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
            for name, file_path, _ in plan:
                logger.info("Executing %s...", name)
                count = execute_sql_file(cur, file_path)
                logger.info("Executed %d statements from %s", count, name)
                total_executed += count
            conn.commit()
            msg = f"Successfully deployed COCO_FACTORY: {len(plan)} scripts executed ({total_executed} statements)."
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
    args = parser.parse_args()

    success, message = initialize_coco_factory(
        dry_run=args.dry_run,
        load_data=args.load_data,
        transform_data=args.transform_data,
        verify=args.verify,
    )
    if not success:
        logger.error("COCO_FACTORY initialization failed: %s", message)
        sys.exit(1)
    logger.info("Done: %s", message)
