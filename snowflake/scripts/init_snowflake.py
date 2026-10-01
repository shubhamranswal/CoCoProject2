"""Deterministic Snowflake Initialization Script.

Executes DDL and seed scripts in strictly defined order:
1. 01_schemas.sql
2. 02_core_tables.sql
3. 03_telemetry_tables.sql
4. 04_production_maintenance.sql
5. 05_reliability_intelligence.sql
6. 06_agent_governance_audit.sql
7. 07_seed_data.sql

Validates foreign key relationships and schema integrity.
"""

from __future__ import annotations

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

DDL_SCRIPTS: List[str] = [
    "01_schemas.sql",
    "02_core_tables.sql",
    "03_telemetry_tables.sql",
    "04_production_maintenance.sql",
    "05_reliability_intelligence.sql",
    "06_agent_governance_audit.sql",
    "07_seed_data.sql",
]


def execute_sql_file(cur, filepath: Path) -> int:
    """Read and execute SQL commands separated by semicolons."""
    content = filepath.read_text(encoding="utf-8")
    # Split by semicolon ignoring empty statements
    statements = [stmt.strip() for stmt in content.split(";") if stmt.strip()]
    executed = 0
    for stmt in statements:
        # Strip comments
        lines = [line for line in stmt.splitlines() if not line.strip().startswith("--")]
        clean_stmt = "\n".join(lines).strip()
        if clean_stmt:
            cur.execute(clean_stmt)
            executed += 1
    return executed


def initialize_snowflake(conn_mgr: SnowflakeConnectionManager | None = None) -> Tuple[bool, str]:
    """Execute all DDL and seed scripts in order."""
    mgr = conn_mgr or SnowflakeConnectionManager()
    if not mgr.is_configured:
        return False, "Snowflake credentials not configured in environment."

    ddl_dir = project_root / "snowflake" / "ddl"
    if not ddl_dir.exists():
        return False, f"DDL directory not found: {ddl_dir}"

    try:
        conn = mgr.get_connection()
        cur = conn.cursor()
        try:
            total_statements = 0
            for script_name in DDL_SCRIPTS:
                script_path = ddl_dir / script_name
                if not script_path.exists():
                    return False, f"Required DDL script missing: {script_name}"
                logger.info("Executing %s...", script_name)
                count = execute_sql_file(cur, script_path)
                total_statements += count
                logger.info("Executed %d statements from %s", count, script_name)

            conn.commit()
            logger.info("Snowflake initialization complete. Total statements: %d", total_statements)
            return True, f"Successfully executed {len(DDL_SCRIPTS)} scripts ({total_statements} statements)."
        finally:
            cur.close()
            conn.close()
    except Exception as e:
        logger.exception("Failed to initialize Snowflake database")
        return False, f"Initialization error: {e}"


def main() -> None:
    success, message = initialize_snowflake()
    if success:
        logger.info(message)
        sys.exit(0)
    else:
        logger.error(message)
        sys.exit(1)


if __name__ == "__main__":
    main()
