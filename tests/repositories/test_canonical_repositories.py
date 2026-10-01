"""Tests for canonical supply chain and prediction repository operations."""

from datetime import datetime, timezone
import pytest

from domain.models.erp import CanonicalPrediction, PurchaseOrder, SparePart, Supplier
from repositories.memory.memory_repository import InMemoryRepository


@pytest.fixture
def repo() -> InMemoryRepository:
    return InMemoryRepository(seed=True)


class TestCanonicalRepositoryOperations:
    def test_canonical_machines_seeded(self, repo: InMemoryRepository):
        m21 = repo.get_machine("M21")
        assert m21 is not None
        assert m21.name == "Grinder 3"
        assert m21.line_id == "L5"
        assert m21.model == "GR-600"

        # Verify spotlight machines
        m15 = repo.get_machine("M15")
        assert m15 is not None
        assert m15.name == "Conveyor Assembly 2"

        m05 = repo.get_machine("M05")
        assert m05 is not None
        assert m05.name == "Grinder 1"

    def test_canonical_components_and_sensors(self, repo: InMemoryRepository):
        comps = repo.get_components("M21")
        assert len(comps) >= 1
        comp_ids = {c.component_id for c in comps}
        assert "C-M21-BRG" in comp_ids

        sensors = repo.get_sensors("M21")
        sensor_ids = {s.sensor_id for s in sensors}
        assert "S-M21-VIB" in sensor_ids
        assert "S-M21-BTMP" in sensor_ids

    def test_spare_part_operations(self, repo: InMemoryRepository):
        part = repo.get_spare_part("SP-002")
        assert part is not None
        assert part.part_name == "Drive-End Bearing 6206-2RS"
        assert part.stock_qty == 0
        assert part.lead_time_days == 5

        all_parts = repo.list_spare_parts()
        assert len(all_parts) >= 4

        sup12_parts = repo.list_spare_parts(supplier_id="SUP-12")
        assert len(sup12_parts) >= 2

    def test_supplier_operations(self, repo: InMemoryRepository):
        supplier = repo.get_supplier("SUP-12")
        assert supplier is not None
        assert supplier.supplier_name == "Vertex Industrial Supplies"
        assert supplier.country == "India"

        suppliers = repo.list_suppliers()
        assert len(suppliers) >= 3

    def test_purchase_order_operations(self, repo: InMemoryRepository):
        po = repo.get_purchase_order("PO-00015")
        assert po is not None
        assert po.supplier_id == "SUP-12"
        assert po.part_id == "SP-002"
        assert po.status == "received"

        part_pos = repo.list_purchase_orders(part_id="SP-002")
        assert len(part_pos) >= 2

    def test_production_order_operations(self, repo: InMemoryRepository):
        order = repo.get_production_order("PRD-01278")
        assert order is not None
        assert order.customer == "Keystone Hydraulics"
        assert order.machine_id == "M21"
        assert order.priority == "Medium"

        m21_orders = repo.list_production_orders(machine_id="M21")
        assert len(m21_orders) >= 1

    def test_canonical_prediction_lifecycle(self, repo: InMemoryRepository):
        pred = repo.get_canonical_prediction("PRED-000322")
        assert pred is not None
        assert pred.machine_id == "M21"
        assert pred.failure_prob == 0.95
        assert pred.risk_level == "high"

        m21_preds = repo.list_canonical_predictions(machine_id="M21")
        assert len(m21_preds) >= 1

        # Test saving new prediction
        new_pred = CanonicalPrediction(
            prediction_id="PRED-TEST-001",
            scored_ts=datetime.now(timezone.utc),
            machine_id="M21",
            suspected_component_id="C-M21-BRG",
            model_name="hgb_failure_7d_v1",
            horizon_days=7,
            failure_prob=0.98,
            risk_level="high",
            top_features='[{"feature": "VIB_mean", "share": 0.85}]',
        )
        repo.save_canonical_prediction(new_pred)
        retrieved = repo.get_canonical_prediction("PRED-TEST-001")
        assert retrieved is not None
        assert retrieved.failure_prob == 0.98
