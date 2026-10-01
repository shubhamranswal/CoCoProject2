"""Repository parity and behavior tests for AnalyticsRepository and KnowledgeSearchRepository.

Follows AGENT.md v2.0:
- Verifies that InMemoryRepository implements all methods defined in AnalyticsRepository
  and KnowledgeSearchRepository.
- Verifies queries, filters, sorting, and edge cases.
"""

from __future__ import annotations

from datetime import date
import pytest

from repositories.memory.memory_repository import InMemoryRepository
from repositories.base import AnalyticsRepository, KnowledgeSearchRepository


@pytest.fixture
def repo() -> InMemoryRepository:
    return InMemoryRepository(seed=True)


class TestAnalyticsRepository:
    """Verifies all methods on AnalyticsRepository interface."""

    def test_implements_interfaces(self, repo: InMemoryRepository):
        assert isinstance(repo, AnalyticsRepository)
        assert isinstance(repo, KnowledgeSearchRepository)

    def test_get_machine_health_daily(self, repo: InMemoryRepository):
        health_m21 = repo.get_machine_health_daily("M21", date(2026, 9, 28))
        assert health_m21 is not None
        assert health_m21.machine_id == "M21"
        assert health_m21.line_id == "L5"
        assert health_m21.health_status == "CRITICAL"

        # Latest query without explicit date
        latest_m21 = repo.get_machine_health_daily("M21")
        assert latest_m21 is not None
        assert latest_m21.machine_id == "M21"

        # Unknown machine returns None
        assert repo.get_machine_health_daily("M999") is None

    def test_list_machine_health_daily_filters(self, repo: InMemoryRepository):
        all_health = repo.list_machine_health_daily()
        assert len(all_health) >= 3

        l5_health = repo.list_machine_health_daily(line_id="L5")
        assert all(h.line_id == "L5" for h in l5_health)

        date_health = repo.list_machine_health_daily(metric_date=date(2026, 9, 28))
        assert all(h.metric_date == date(2026, 9, 28) for h in date_health)

    def test_get_machine_oee_daily(self, repo: InMemoryRepository):
        oee_m21 = repo.get_machine_oee_daily("M21", date(2026, 9, 28))
        assert oee_m21 is not None
        assert oee_m21.machine_id == "M21"
        assert 0.0 <= oee_m21.availability <= 1.0
        assert 0.0 <= oee_m21.performance <= 1.0
        assert 0.0 <= oee_m21.quality <= 1.0
        assert 0.0 <= oee_m21.oee <= 1.0

        assert repo.get_machine_oee_daily("M999") is None

    def test_list_machine_oee_daily_filters(self, repo: InMemoryRepository):
        all_oee = repo.list_machine_oee_daily()
        assert len(all_oee) >= 3

        l3_oee = repo.list_machine_oee_daily(line_id="L3")
        assert all(o.line_id == "L3" for o in l3_oee)

    def test_get_downtime_daily(self, repo: InMemoryRepository):
        dt = repo.get_downtime_daily("M21", date(2026, 9, 28))
        assert dt is not None
        assert dt.machine_id == "M21"
        assert dt.total_downtime_minutes >= 0.0
        assert dt.top_downtime_category == "minor_stop"

    def test_list_downtime_daily(self, repo: InMemoryRepository):
        dt_list = repo.list_downtime_daily(metric_date=date(2026, 9, 28))
        assert len(dt_list) >= 1

    def test_get_maintenance_daily(self, repo: InMemoryRepository):
        maint = repo.get_maintenance_daily("M21", date(2026, 9, 28))
        assert maint is not None
        assert maint.machine_id == "M21"

    def test_list_maintenance_daily(self, repo: InMemoryRepository):
        maint_list = repo.list_maintenance_daily(metric_date=date(2026, 9, 28))
        assert len(maint_list) >= 1

    def test_get_and_list_inventory_risk(self, repo: InMemoryRepository):
        part = repo.get_inventory_risk("SP-002")
        assert part is not None
        assert part.part_id == "SP-002"
        assert part.stock_status == "STOCKOUT"
        assert part.is_critical_exposure is True

        all_parts = repo.list_inventory_risks()
        assert len(all_parts) >= 3

        critical_parts = repo.list_inventory_risks(critical_only=True)
        assert all(p.is_critical_exposure for p in critical_parts)
        assert any(p.part_id == "SP-002" for p in critical_parts)

    def test_get_and_list_production_context(self, repo: InMemoryRepository):
        ctx = repo.get_production_context("PRD-01278")
        assert ctx is not None
        assert ctx.production_order_id == "PRD-01278"
        assert ctx.customer == "Keystone Hydraulics"
        assert ctx.unfulfilled_revenue_exposure_inr > 0

        m21_orders = repo.list_production_contexts(machine_id="M21")
        assert any(o.production_order_id == "PRD-01278" for o in m21_orders)

    def test_get_reliability_features(self, repo: InMemoryRepository):
        features = repo.get_reliability_features("M21", date(2026, 9, 28))
        assert features is not None
        assert features.machine_id == "M21"
        assert features.vib_mean_7d is not None
        assert features.vib_max_7d is not None
        assert features.vib_rel30 is not None
        assert features.vib_rel30 > 1.0  # Elevating trend relative to 30-day baseline


class TestKnowledgeSearchRepository:
    """Verifies all methods on KnowledgeSearchRepository interface."""

    def test_get_document(self, repo: InMemoryRepository):
        doc = repo.get_document("DOC-001")
        assert doc is not None
        assert doc.document_id == "DOC-001"
        assert "troubleshooting" in doc.doc_type
        assert doc.failure_code == "BD-BRG"

        assert repo.get_document("DOC-NONEXISTENT") is None

    def test_list_documents(self, repo: InMemoryRepository):
        all_docs = repo.list_documents()
        assert len(all_docs) == 16

        troubleshooting_docs = repo.list_documents(doc_type="troubleshooting")
        assert len(troubleshooting_docs) > 0
        assert all(d.doc_type == "troubleshooting" for d in troubleshooting_docs)

        brg_docs = repo.list_documents(failure_code="BD-BRG")
        assert any(d.document_id == "DOC-001" for d in brg_docs)

    def test_search_corpus(self, repo: InMemoryRepository):
        # Bearing keyword search
        results = repo.search_corpus("bearing lubrication", limit=3)
        assert len(results) > 0
        assert any(r.document_id in {"DOC-001", "DOC-002", "DOC-014"} for r in results)

        # Failure code filtered search
        brg_results = repo.search_corpus("temperature", limit=5, failure_code="BD-BRG")
        assert all(r.failure_code == "BD-BRG" for r in brg_results)

    def test_get_and_list_failure_modes(self, repo: InMemoryRepository):
        fm = repo.get_failure_mode("BD-BRG")
        assert fm is not None
        assert fm.failure_code == "BD-BRG"
        assert fm.category == "MECHANICAL"
        assert "vibration_rms" in fm.primary_sensors

        all_fms = repo.list_failure_modes()
        assert len(all_fms) == 10

        mechanical_fms = repo.list_failure_modes(category="MECHANICAL")
        assert all(m.category == "MECHANICAL" for m in mechanical_fms)
        assert any(m.failure_code == "BD-BRG" for m in mechanical_fms)
        assert any(m.failure_code == "PD-VIB" for m in mechanical_fms)
