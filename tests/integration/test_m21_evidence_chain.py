"""Factual verification of the M21 Cross-Domain Evidence Chain.

Follows AGENT.md v2.0 (Milestone 2 - Phase 2G):
- Machine identity: M21 (Grinder 3, model GR-600, Line L5)
- Degraded component: C-M21-BRG (Drive-End Bearing 6206-2RS)
- Telemetry: S-M21-VIB (exceeds critical limit 4.5 mm/s at 4.88 mm/s) & S-M21-BTMP (84.2 degC)
- Predictive ML: PRED-000322 (failure_prob: 0.950, risk_level: high, top feature: VIB_max 0.50)
- Failure mode taxonomy: BD-BRG (Mechanical bearing breakdown)
- Inventory exposure: SP-002 (stock_qty: 0, critical exposure: True, lead time: 5 days, supplier SUP-12)
- Customer order exposure: PRD-01278 (Keystone Hydraulics, due 2026-09-29, 211 units remaining, INR 3.376M exposure)
- Knowledge corpus: DOC-001, DOC-002, DOC-010, DOC-011, DOC-014
"""

from __future__ import annotations

from datetime import date
import pytest

from repositories.memory.memory_repository import InMemoryRepository


@pytest.fixture
def repo() -> InMemoryRepository:
    return InMemoryRepository(seed=True)


class TestM21EvidenceChain:
    """Verifies that all factual links in the M21 reliability evidence chain are intact."""

    def test_m21_machine_identity(self, repo: InMemoryRepository):
        """M21 must be Grinder 3 on Line L5 with model GR-600."""
        machine = repo.get_machine("M21")
        assert machine is not None
        assert machine.name == "Grinder 3"
        assert machine.line_id == "L5"
        assert machine.asset_type == "Grinder"
        assert machine.model == "GR-600"

    def test_m21_component_and_sensor_topology(self, repo: InMemoryRepository):
        """M21 must have bearing C-M21-BRG monitored by S-M21-VIB and S-M21-BTMP."""
        components = repo.get_components("M21")
        comp_ids = {c.component_id for c in components}
        assert "C-M21-BRG" in comp_ids

        bearing = next(c for c in components if c.component_id == "C-M21-BRG")
        assert bearing.name == "Drive-End Bearing 6206-2RS"
        assert bearing.criticality == "CRITICAL"

        sensors = repo.get_sensors("M21")
        sensor_ids = {s.sensor_id for s in sensors}
        assert "S-M21-VIB" in sensor_ids
        assert "S-M21-BTMP" in sensor_ids

        vib_sensor = next(s for s in sensors if s.sensor_id == "S-M21-VIB")
        assert vib_sensor.component_id == "C-M21-BRG"
        assert vib_sensor.unit == "mm/s"

    def test_m21_machine_health_and_telemetry_exceedance(self, repo: InMemoryRepository):
        """M21 health daily on 2026-09-28 must show critical health with vibration exceedance."""
        health = repo.get_machine_health_daily("M21", date(2026, 9, 28))
        assert health is not None
        assert health.health_status == "CRITICAL"
        assert health.max_vibration is not None
        assert health.max_vibration > 4.5  # Critical threshold is 4.5 mm/s
        assert health.exceedance_count > 0
        assert health.latest_prediction_id == "PRED-000322"
        assert health.latest_failure_prob == 0.950

    def test_m21_predictive_ml_signal(self, repo: InMemoryRepository):
        """PRED-000322 must predict bearing failure on M21 with 0.95 probability."""
        pred = repo.get_canonical_prediction("PRED-000322")
        assert pred is not None
        assert pred.machine_id == "M21"
        assert pred.suspected_component_id == "C-M21-BRG"
        assert pred.horizon_days == 7
        assert pred.failure_prob == 0.950
        assert pred.risk_level == "high"
        assert "VIB_max" in pred.top_features

    def test_m21_failure_mode_taxonomy(self, repo: InMemoryRepository):
        """BD-BRG failure mode must map to Drive-End Bearing with vibration & temperature sensors."""
        failure_mode = repo.get_failure_mode("BD-BRG")
        assert failure_mode is not None
        assert failure_mode.category == "MECHANICAL"
        assert failure_mode.component_type == "Drive-End Bearing"
        assert "vibration_rms" in failure_mode.primary_sensors
        assert "bearing_temperature" in failure_mode.primary_sensors
        assert "Replace bearing assembly" in failure_mode.recommended_action

    def test_m21_inventory_exposure_and_stockout(self, repo: InMemoryRepository):
        """SP-002 (compatible with C-M21-BRG) must have 0 stock and critical exposure."""
        inv = repo.get_inventory_risk("SP-002")
        assert inv is not None
        assert inv.part_name == "Drive-End Bearing 6206-2RS"
        assert inv.stock_qty == 0
        assert inv.stock_status == "STOCKOUT"
        assert inv.is_critical_exposure is True
        assert inv.lead_time_days == 5
        assert inv.supplier_id == "SUP-12"

        # Supplier SUP-12 verification
        supplier = repo.get_supplier("SUP-12")
        assert supplier is not None
        assert supplier.supplier_name == "Vertex Industrial Supplies"

    def test_m21_production_order_financial_exposure(self, repo: InMemoryRepository):
        """Order PRD-01278 on M21 must show Keystone Hydraulics exposure of INR 3,376,000."""
        ctx = repo.get_production_context("PRD-01278")
        assert ctx is not None
        assert ctx.machine_id == "M21"
        assert ctx.customer == "Keystone Hydraulics"
        assert ctx.status == "in_progress"
        assert ctx.planned_qty == 3894
        assert ctx.produced_qty == 3683
        assert ctx.due_date == date(2026, 9, 29)
        assert ctx.unfulfilled_revenue_exposure_inr == 3376000.0

    def test_m21_knowledge_corpus_resolution(self, repo: InMemoryRepository):
        """Corpus search for bearing troubleshooting must retrieve DOC-001 and DOC-002."""
        results = repo.search_corpus("bearing vibration troubleshooting", limit=5)
        doc_ids = {d.document_id for d in results}
        assert "DOC-001" in doc_ids or "DOC-002" in doc_ids

        doc_001 = repo.get_document("DOC-001")
        assert doc_001 is not None
        assert doc_001.failure_code == "BD-BRG"
        assert "Rising vibration RMS, bearing temperature" in doc_001.content

        doc_002 = repo.get_document("DOC-002")
        assert doc_002 is not None
        assert "ISO 10816" in doc_002.title
        assert "2.8" in doc_002.content
        assert "4.5" in doc_002.content

    def test_complete_m21_evidence_chain_cross_domain_synthesis(self, repo: InMemoryRepository):
        """Cross-domain query: given M21 critical alert, all dependencies correlate factually."""
        # 1. Health
        health = repo.get_machine_health_daily("M21", date(2026, 9, 28))
        assert health.health_status == "CRITICAL"

        # 2. Prediction
        pred = repo.get_canonical_prediction(health.latest_prediction_id)
        assert pred.failure_prob >= 0.90

        # 3. Component & Part
        components = repo.get_components(health.machine_id)
        bearing = next(c for c in components if c.component_id == pred.suspected_component_id)
        assert "6206-2RS" in bearing.name

        # 4. Inventory Risk
        part = repo.get_inventory_risk("SP-002")
        assert part.compatible_model == "6206-2RS"
        assert part.is_critical_exposure is True

        # 5. Production Impact
        orders = repo.list_production_contexts(machine_id="M21", status="in_progress")
        assert len(orders) >= 1
        active_order = orders[0]
        assert active_order.customer == "Keystone Hydraulics"
        assert active_order.unfulfilled_revenue_exposure_inr > 0

        # 6. Maintenance Guide
        sop_docs = repo.list_documents(failure_code="BD-BRG")
        assert len(sop_docs) >= 1
