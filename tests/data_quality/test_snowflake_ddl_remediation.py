"""Regression tests for Snowflake DDL and Ingestion Remediation.

Verifies:
1. Shared batch ID generation and dynamic injection across all 19 RAW ingestion statements.
2. Explicit batch ID override support.
3. Fallback batch ID generation.
4. Presence of TRUNCATE TABLE CORE.SENSOR_READING immediately before telemetry insert.
"""

from pathlib import Path
import re
import pytest

from snowflake.scripts.init_coco_factory import (
    generate_batch_id,
    prepare_script_content,
    initialize_coco_factory,
    parse_sql_statements,
)


@pytest.fixture
def ddl_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent / "snowflake" / "ddl" / "coco_factory"


class TestSnowflakeDDLRemediation:
    def test_fallback_batch_id_generation(self):
        """Verifies that generate_batch_id generates a non-empty, timestamped batch identifier."""
        b1 = generate_batch_id()
        assert b1.startswith("BATCH_")
        assert len(b1) >= 15

    def test_shared_batch_id_injected_across_all_19_tables(self, ddl_root: Path):
        """Verifies that all 19 COPY INTO statements receive the exact same batch ID."""
        sql_file = ddl_root / "70_raw_ingestion_copy.sql"
        assert sql_file.exists()
        raw_content = sql_file.read_text(encoding="utf-8")

        test_batch_id = "BATCH_TEST_EXEC_20261001"
        prepared = prepare_script_content("70_raw_ingestion_copy.sql", raw_content, test_batch_id)

        # Ensure no placeholder remains
        assert "__BATCH_ID__" not in prepared
        assert "BATCH_INIT" not in prepared

        # Count occurrences of the injected batch ID
        matches = re.findall(rf"'{re.escape(test_batch_id)}'", prepared)
        assert len(matches) == 19, f"Expected 19 occurrences of {test_batch_id}, found {len(matches)}"

    def test_explicit_batch_id_override_dry_run(self):
        """Verifies that an explicit batch ID passed to initialize_coco_factory is reflected in the plan."""
        custom_id = "BATCH_CUSTOM_OVERRIDE_001"
        success, message = initialize_coco_factory(
            dry_run=True,
            load_data=True,
            batch_id=custom_id,
        )
        assert success
        assert custom_id in message

    def test_telemetry_atomic_swap_rebuild(self, ddl_root: Path):
        """Verifies failure-safe atomic rebuild strategy with transient staging table and swap."""
        sql_file = ddl_root / "80_core_conformed_transforms.sql"
        assert sql_file.exists()
        content = sql_file.read_text(encoding="utf-8")

        stage_create_pos = content.find("CREATE OR REPLACE TRANSIENT TABLE CORE.SENSOR_READING_STAGE")
        insert_pos = content.find("INSERT INTO CORE.SENSOR_READING_STAGE")
        swap_pos = content.find("ALTER TABLE CORE.SENSOR_READING SWAP WITH CORE.SENSOR_READING_STAGE;")
        drop_pos = content.find("DROP TABLE IF EXISTS CORE.SENSOR_READING_STAGE;")

        assert stage_create_pos != -1, "Transient staging table creation was not found."
        assert insert_pos != -1, "Insert into transient staging table was not found."
        assert swap_pos != -1, "Atomic swap statement was not found."
        assert drop_pos != -1, "Cleanup drop statement was not found."

        assert stage_create_pos < insert_pos < swap_pos < drop_pos, (
            "Statements must execute in sequence: CREATE STAGE -> INSERT STAGE -> SWAP -> DROP STAGE"
        )

        statements = parse_sql_statements(content)
        assert any("CREATE OR REPLACE TRANSIENT TABLE CORE.SENSOR_READING_STAGE" in s for s in statements)
        assert any("SWAP WITH CORE.SENSOR_READING_STAGE" in s for s in statements)
