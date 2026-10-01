"""Data quality and invariant tests for Analytics and Foundation views.

Follows AGENT.md v2.0:
- Verifies OEE bounds [0.0, 1.0] for Availability, Performance, Quality, and OEE.
- Verifies downtime non-negativity and category breakdown consistency.
- Verifies inventory exposure logic and non-negative stock.
- Verifies production order exposure calculations.
- Verifies SQL DDL definitions in 30_analytics_foundation.sql, 40_ml_foundation.sql, and 50_knowledge_foundation.sql.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
import pytest

from domain.models import (
    MachineOEEDaily,
    MachineHealthDaily,
    DowntimeSummary,
    InventoryRisk,
    ProductionContext,
    ReliabilityFeatures,
)
from data.generators.canonical_fixtures import (
    CANONICAL_HEALTH_DAILY,
    CANONICAL_OEE_DAILY,
    CANONICAL_DOWNTIME_DAILY,
    CANONICAL_INVENTORY_RISKS,
    CANONICAL_PRODUCTION_CONTEXTS,
    CANONICAL_RELIABILITY_FEATURES,
    CANONICAL_FAILURE_MODES,
    CANONICAL_KNOWLEDGE_DOCS,
)


class TestAnalyticsDataQuality:
    """Verifies mathematical invariants and schema bounds for analytics domain models."""

    def test_oee_bounds_and_components(self):
        """All OEE components must strictly lie within [0.0, 1.0]."""
        for oee_record in CANONICAL_OEE_DAILY:
            assert 0.0 <= oee_record.availability <= 1.0, f"Availability out of bounds for {oee_record.machine_id}"
            assert 0.0 <= oee_record.performance <= 1.0, f"Performance out of bounds for {oee_record.machine_id}"
            assert 0.0 <= oee_record.quality <= 1.0, f"Quality out of bounds for {oee_record.machine_id}"
            assert 0.0 <= oee_record.oee <= 1.0, f"OEE out of bounds for {oee_record.machine_id}"

            # Quality invariant: good pieces + reject pieces == total pieces
            assert oee_record.good_pieces + oee_record.reject_pieces == oee_record.total_pieces
            assert oee_record.total_pieces > 0
            computed_quality = round(oee_record.good_pieces / oee_record.total_pieces, 4)
            assert abs(computed_quality - oee_record.quality) < 0.01

    def test_downtime_invariants(self):
        """Downtime minutes must be non-negative and sum properly."""
        for dt in CANONICAL_DOWNTIME_DAILY:
            assert dt.total_downtime_minutes >= 0.0
            assert dt.breakdown_minutes >= 0.0
            assert dt.changeover_minutes >= 0.0
            assert dt.minor_stop_minutes >= 0.0
            assert dt.no_material_minutes >= 0.0
            assert dt.no_operator_minutes >= 0.0
            assert dt.planned_maintenance_minutes >= 0.0
            assert dt.breakdown_event_count >= 0
            assert dt.total_event_count >= 0

            cat_sum = (
                dt.breakdown_minutes
                + dt.changeover_minutes
                + dt.minor_stop_minutes
                + dt.no_material_minutes
                + dt.no_operator_minutes
                + dt.planned_maintenance_minutes
            )
            assert abs(cat_sum - dt.total_downtime_minutes) < 0.01

    def test_inventory_exposure_invariants(self):
        """Inventory quantities must be non-negative and critical exposure flags accurate."""
        for inv in CANONICAL_INVENTORY_RISKS:
            assert inv.stock_qty >= 0
            assert inv.reorder_level >= 0
            assert inv.lead_time_days >= 0
            assert inv.stock_status in {"STOCKOUT", "LOW_STOCK", "HEALTHY"}

            if inv.stock_qty == 0:
                assert inv.stock_status == "STOCKOUT"
            elif inv.stock_qty <= inv.reorder_level:
                assert inv.stock_status == "LOW_STOCK"
            else:
                assert inv.stock_status == "HEALTHY"

        # SP-002 must be flagged as critical exposure stockout
        sp_002 = next((r for r in CANONICAL_INVENTORY_RISKS if r.part_id == "SP-002"), None)
        assert sp_002 is not None
        assert sp_002.stock_qty == 0
        assert sp_002.is_critical_exposure is True

    def test_production_context_financial_invariants(self):
        """Production order revenue exposure must match unfulfilled quantity * unit price."""
        for ctx in CANONICAL_PRODUCTION_CONTEXTS:
            assert ctx.planned_qty >= ctx.produced_qty
            assert 0.0 <= ctx.progress_pct <= 100.0
            expected_unfulfilled = ctx.planned_qty - ctx.produced_qty
            expected_exposure = expected_unfulfilled * ctx.unit_price_inr
            assert abs(ctx.unfulfilled_revenue_exposure_inr - expected_exposure) < 1.0
            assert abs(ctx.order_value_inr - (ctx.planned_qty * ctx.unit_price_inr)) < 1.0

    def test_machine_health_aggregates(self):
        """Machine health daily records must contain non-negative readings and valid status."""
        for h in CANONICAL_HEALTH_DAILY:
            assert h.reading_count > 0
            assert h.health_status in {"HEALTHY", "WARNING", "DEGRADED", "CRITICAL"}
            if h.avg_vibration is not None and h.max_vibration is not None:
                assert h.max_vibration >= h.avg_vibration
            if h.avg_temperature is not None and h.max_temperature is not None:
                assert h.max_temperature >= h.avg_temperature

    def test_ddl_files_exist_and_contain_required_objects(self):
        """Snowflake DDL scripts must define required views and tables."""
        ddl_dir = Path("snowflake/ddl/coco_factory")
        analytics_file = ddl_dir / "30_analytics_foundation.sql"
        ml_file = ddl_dir / "40_ml_foundation.sql"
        knowledge_file = ddl_dir / "50_knowledge_foundation.sql"

        assert analytics_file.exists()
        assert ml_file.exists()
        assert knowledge_file.exists()

        analytics_sql = analytics_file.read_text(encoding="utf-8")
        assert "CREATE OR REPLACE VIEW MACHINE_HEALTH_DAILY" in analytics_sql
        assert "CREATE OR REPLACE VIEW MACHINE_OEE_DAILY" in analytics_sql
        assert "CREATE OR REPLACE VIEW DOWNTIME_DAILY" in analytics_sql
        assert "CREATE OR REPLACE VIEW MAINTENANCE_DAILY" in analytics_sql
        assert "CREATE OR REPLACE VIEW INVENTORY_RISK" in analytics_sql
        assert "CREATE OR REPLACE VIEW PRODUCTION_CONTEXT" in analytics_sql

        ml_sql = ml_file.read_text(encoding="utf-8")
        assert "CREATE TABLE IF NOT EXISTS MACHINE_FEATURE_DAILY" in ml_sql
        assert "CREATE OR REPLACE VIEW V_MACHINE_FEATURE_DAILY" in ml_sql
        assert "CREATE TABLE IF NOT EXISTS MODEL_REGISTRY" in ml_sql
        assert "CREATE TABLE IF NOT EXISTS INFERENCE_LOG" in ml_sql

        knowledge_sql = knowledge_file.read_text(encoding="utf-8")
        assert "CREATE TABLE IF NOT EXISTS CORPUS" in knowledge_sql
        assert "CREATE TABLE IF NOT EXISTS FAILURE_MODE_TAXONOMY" in knowledge_sql
        assert "CREATE OR REPLACE VIEW V_CORPUS_SEARCH_FEED" in knowledge_sql
        assert "MERGE INTO KNOWLEDGE.CORPUS" in knowledge_sql
        assert "MERGE INTO KNOWLEDGE.FAILURE_MODE_TAXONOMY" in knowledge_sql
