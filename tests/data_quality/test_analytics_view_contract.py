"""Static contract tests verifying analytics SQL views match SnowflakeRepository queries and domain models.

Ensures:
1. SQL view projections in 30_analytics_foundation.sql match columns selected by SnowflakeRepository.
2. Selected columns match Pydantic domain models in domain.models.analytics.
3. No invalid identifier runtime mismatch can occur between SQL DDL and application repository code.
Offline test requiring no live Snowflake credentials.
"""

import re
from pathlib import Path
from typing import Dict, List, Set
import pytest

from domain.models.analytics import (
    MachineHealthDaily,
    MachineOEEDaily,
    DowntimeSummary,
    MaintenanceSummary,
    InventoryRisk,
    ProductionContext,
)

DDL_FILE = Path("snowflake/ddl/coco_factory/30_analytics_foundation.sql")
REPO_FILE = Path("repositories/snowflake/snowflake_repository.py")

# Expected repository query column contracts
EXPECTED_VIEW_COLUMNS: Dict[str, List[str]] = {
    "MACHINE_HEALTH_DAILY": [
        "machine_id",
        "metric_date",
        "machine_name",
        "machine_type",
        "line_id",
        "line_name",
        "reading_count",
        "avg_vibration",
        "max_vibration",
        "avg_temperature",
        "max_temperature",
        "exceedance_count",
        "downtime_minutes",
        "breakdown_count",
        "maintenance_count",
        "open_alerts",
        "latest_prediction_id",
        "latest_failure_prob",
        "latest_risk_level",
        "health_status",
    ],
    "MACHINE_OEE_DAILY": [
        "machine_id",
        "metric_date",
        "machine_name",
        "line_id",
        "planned_production_minutes",
        "operating_minutes",
        "unplanned_downtime_minutes",
        "total_pieces",
        "good_pieces",
        "reject_pieces",
        "availability",
        "performance",
        "quality",
        "oee",
    ],
    "DOWNTIME_DAILY": [
        "machine_id",
        "metric_date",
        "machine_name",
        "line_id",
        "total_downtime_minutes",
        "breakdown_minutes",
        "changeover_minutes",
        "minor_stop_minutes",
        "no_material_minutes",
        "no_operator_minutes",
        "planned_maintenance_minutes",
        "breakdown_event_count",
        "total_event_count",
        "top_reason_code",
        "top_downtime_category",
    ],
    "MAINTENANCE_DAILY": [
        "machine_id",
        "metric_date",
        "machine_name",
        "line_id",
        "work_order_count",
        "corrective_count",
        "preventive_count",
        "breakdown_count",
        "total_labor_hours",
        "total_parts_cost_inr",
        "total_labor_cost_inr",
        "total_maintenance_cost_inr",
        "mean_time_to_repair_minutes",
    ],
    "INVENTORY_RISK": [
        "part_id",
        "part_name",
        "part_category",
        "compatible_model",
        "stock_qty",
        "reorder_level",
        "reorder_qty",
        "lead_time_days",
        "supplier_id",
        "supplier_name",
        "open_po_count",
        "open_po_qty",
        "stock_status",
        "is_critical_exposure",
    ],
    "PRODUCTION_CONTEXT": [
        "production_order_id",
        "machine_id",
        "machine_name",
        "line_id",
        "product_id",
        "product_name",
        "customer",
        "priority",
        "status",
        "planned_qty",
        "produced_qty",
        "progress_pct",
        "due_date",
        "days_until_due",
        "is_overdue",
        "unit_price_inr",
        "order_value_inr",
        "unfulfilled_revenue_exposure_inr",
    ],
}

VIEW_TO_MODEL = {
    "MACHINE_HEALTH_DAILY": MachineHealthDaily,
    "MACHINE_OEE_DAILY": MachineOEEDaily,
    "DOWNTIME_DAILY": DowntimeSummary,
    "MAINTENANCE_DAILY": MaintenanceSummary,
    "INVENTORY_RISK": InventoryRisk,
    "PRODUCTION_CONTEXT": ProductionContext,
}


def _extract_sql_view_projected_columns(ddl_content: str, view_name: str) -> Set[str]:
    """Extract output column names or AS aliases from the final SELECT clause of a CREATE VIEW statement."""
    # Find the CREATE VIEW ... AS statement
    pattern = rf"CREATE\s+OR\s+REPLACE\s+VIEW\s+(?:COCO_FACTORY\.ANALYTICS\.)?{view_name}\s+AS\s+(.*?)(?=CREATE\s+OR\s+REPLACE\s+VIEW|\Z)"
    match = re.search(pattern, ddl_content, re.DOTALL | re.IGNORECASE)
    assert match, f"Could not find CREATE VIEW for {view_name} in DDL"
    view_body = match.group(1)

    # Find the final SELECT statement in the view (after any CTEs)
    # If CTEs exist (WITH ...), find the final SELECT outside CTEs
    # In standard CTE views, the final SELECT comes after the last CTE definition
    lines = view_body.strip().splitlines()
    final_select_lines: List[str] = []
    in_final_select = False
    paren_depth = 0

    for line in lines:
        stripped = line.strip()
        paren_depth += stripped.count("(") - stripped.count(")")
        if paren_depth == 0 and re.match(r"^SELECT\b", stripped, re.IGNORECASE):
            in_final_select = True
            final_select_lines = [stripped]
            continue
        if in_final_select:
            if re.match(r"^FROM\b", stripped, re.IGNORECASE) and paren_depth == 0:
                break
            final_select_lines.append(stripped)

    final_select_text = " ".join(final_select_lines)
    # Remove leading SELECT
    select_clause = re.sub(r"^SELECT\s+", "", final_select_text, flags=re.IGNORECASE)

    # Split by comma (ignoring commas inside parentheses)
    cols: Set[str] = set()
    current_token = []
    p_depth = 0
    for char in select_clause:
        if char == "(":
            p_depth += 1
        elif char == ")":
            p_depth -= 1
        elif char == "," and p_depth == 0:
            token = "".join(current_token).strip()
            if token:
                cols.add(_parse_column_name(token))
            current_token = []
            continue
        current_token.append(char)
    if current_token:
        token = "".join(current_token).strip()
        if token:
            cols.add(_parse_column_name(token))

    return cols


def _parse_column_name(token: str) -> str:
    """Parse column alias from expression like 'foo AS bar' or 't.bar' or 'bar'."""
    # Check for AS alias
    as_match = re.search(r"\bAS\s+([A-Za-z0-9_]+)\s*$", token, re.IGNORECASE)
    if as_match:
        return as_match.group(1).lower()
    # Check for simple column reference like 't.column_name' or 'column_name'
    col_match = re.search(r"(?:[A-Za-z0-9_]+\.)?([A-Za-z0-9_]+)\s*$", token)
    if col_match:
        return col_match.group(1).lower()
    return token.strip().lower()


def test_ddl_file_exists():
    assert DDL_FILE.exists(), f"DDL file missing: {DDL_FILE}"
    assert REPO_FILE.exists(), f"Repository file missing: {REPO_FILE}"


@pytest.mark.parametrize("view_name, expected_cols", EXPECTED_VIEW_COLUMNS.items())
def test_analytics_views_project_required_columns(view_name: str, expected_cols: List[str]):
    """Verify that 30_analytics_foundation.sql projects every column requested by SnowflakeRepository."""
    ddl_content = DDL_FILE.read_text(encoding="utf-8")
    projected = _extract_sql_view_projected_columns(ddl_content, view_name)

    missing = [c for c in expected_cols if c.lower() not in projected]
    assert not missing, f"View {view_name} is missing projected columns required by SnowflakeRepository: {missing}. Found: {projected}"


@pytest.mark.parametrize("view_name, expected_cols", EXPECTED_VIEW_COLUMNS.items())
def test_snowflake_repository_queries_match_contract(view_name: str, expected_cols: List[str]):
    """Verify that SnowflakeRepository queries exactly the agreed canonical columns for each view."""
    repo_content = REPO_FILE.read_text(encoding="utf-8")
    # Match SELECT ... FROM COCO_FACTORY.ANALYTICS.{view_name} within triple-quoted strings
    pattern = rf'SELECT\s+([a-zA-Z0-9_,\s\n]+?)\s+FROM\s+COCO_FACTORY\.ANALYTICS\.{view_name}'
    matches = re.findall(pattern, repo_content, re.IGNORECASE)
    assert len(matches) >= 1, f"No queries found for {view_name} in SnowflakeRepository"

    for match in matches:
        # Extract column names from the SELECT clause
        raw_cols = [c.strip() for c in match.replace("\n", " ").split(",") if c.strip()]
        queried_cols = [_parse_column_name(c) for c in raw_cols]
        assert queried_cols == [c.lower() for c in expected_cols], (
            f"SnowflakeRepository query for {view_name} deviates from contract!\n"
            f"Queried:  {queried_cols}\n"
            f"Expected: {expected_cols}"
        )


@pytest.mark.parametrize("view_name, model_cls", VIEW_TO_MODEL.items())
def test_domain_models_match_expected_columns(view_name: str, model_cls):
    """Verify that the Pydantic domain models define attributes for all expected view columns."""
    expected_cols = EXPECTED_VIEW_COLUMNS[view_name]
    model_fields = set(model_cls.model_fields.keys())

    missing = [c for c in expected_cols if c not in model_fields]
    assert not missing, f"Domain model {model_cls.__name__} missing fields for {view_name}: {missing}"
