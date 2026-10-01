"""Automated Data Quality and Referential Integrity Verification Suite for Canonical Manufacturing Dataset.

Validates the canonical dataset at C:\\Users\\shubh\\Desktop\\oee_v2 against the AGENT.md v2.0 contract.
"""

from __future__ import annotations

import os
from pathlib import Path
import pytest
import pandas as pd

from ingestion.canonical_source import CanonicalSourceManager, CANONICAL_ENTITIES


@pytest.fixture(scope="module")
def source_mgr() -> CanonicalSourceManager:
    mgr = CanonicalSourceManager()
    if not mgr.root.exists():
        pytest.skip(f"Canonical dataset root does not exist: {mgr.root}")
    return mgr


class TestCanonicalDatasetCompleteness:
    """Validates that all 19 canonical entities exist physically."""

    def test_all_19_entities_present(self, source_mgr: CanonicalSourceManager):
        all_present, missing = source_mgr.validate_dataset_presence()
        assert all_present, f"Missing canonical dataset files: {missing}"

    def test_cardinality_expectations(self, source_mgr: CanonicalSourceManager):
        """Verifies row counts of canonical master entities."""
        # 1. Machines: exactly 25
        df_m = source_mgr.read_entity_df("machine")
        assert df_m is not None
        assert len(df_m) == 25

        # 2. Components: exactly 141
        df_c = source_mgr.read_entity_df("component")
        assert df_c is not None
        assert len(df_c) == 141

        # 3. Sensors: exactly 144
        df_s = source_mgr.read_entity_df("sensor")
        assert df_s is not None
        assert len(df_s) == 144

        # 4. Products: 8
        df_p = source_mgr.read_entity_df("product")
        assert df_p is not None
        assert len(df_p) == 8

        # 5. Technicians: 6
        df_t = source_mgr.read_entity_df("technician")
        assert df_t is not None
        assert len(df_t) == 6

        # 6. Spare Parts: 32
        df_sp = source_mgr.read_entity_df("spare_part")
        assert df_sp is not None
        assert len(df_sp) == 32

        # 7. Suppliers: 12
        df_sup = source_mgr.read_entity_df("supplier")
        assert df_sup is not None
        assert len(df_sup) == 12

        # 8. Purchase Orders: 217
        df_po = source_mgr.read_entity_df("purchase_order")
        assert df_po is not None
        assert len(df_po) == 217

        # 9. Knowledge Docs: 16
        df_kd = source_mgr.read_entity_df("knowledge_doc")
        assert df_kd is not None
        assert len(df_kd) == 16

        # 10. Predictions: 326
        df_pred = source_mgr.read_entity_df("prediction")
        assert df_pred is not None
        assert len(df_pred) == 326

        # 11. Alerts: 1,142
        df_alert = source_mgr.read_entity_df("alert")
        assert df_alert is not None
        assert len(df_alert) == 1142

        # 12. Maintenance Work Orders: 637
        df_wo = source_mgr.read_entity_df("maintenance_work_order")
        assert df_wo is not None
        assert len(df_wo) == 637

        # 13. Production Orders: 1,524 (PRD-00001 through PRD-01524)
        df_po = source_mgr.read_entity_df("production_order")
        assert df_po is not None
        assert len(df_po) in (1524, 1525)


class TestCanonicalReferentialIntegrity:
    """Verifies relational integrity and foreign key validity."""

    def test_components_belong_to_valid_machines(self, source_mgr: CanonicalSourceManager):
        df_m = source_mgr.read_entity_df("machine")
        df_c = source_mgr.read_entity_df("component")
        valid_machines = set(df_m["machine_id"])
        component_machines = set(df_c["machine_id"])
        assert component_machines.issubset(valid_machines)

    def test_sensors_belong_to_valid_machines_and_components(self, source_mgr: CanonicalSourceManager):
        df_m = source_mgr.read_entity_df("machine")
        df_c = source_mgr.read_entity_df("component")
        df_s = source_mgr.read_entity_df("sensor")
        valid_machines = set(df_m["machine_id"])
        valid_components = set(df_c["component_id"])

        sensor_machines = set(df_s["machine_id"])
        assert sensor_machines.issubset(valid_machines)

        sensor_components = set(df_s["component_id"].dropna())
        assert sensor_components.issubset(valid_components)

    def test_spare_parts_belong_to_valid_suppliers(self, source_mgr: CanonicalSourceManager):
        df_sup = source_mgr.read_entity_df("supplier")
        df_sp = source_mgr.read_entity_df("spare_part")
        valid_suppliers = set(df_sup["supplier_id"])
        part_suppliers = set(df_sp["supplier_id"].dropna())
        assert part_suppliers.issubset(valid_suppliers)

    def test_purchase_orders_reference_valid_parts_and_suppliers(self, source_mgr: CanonicalSourceManager):
        df_sup = source_mgr.read_entity_df("supplier")
        df_sp = source_mgr.read_entity_df("spare_part")
        df_po = source_mgr.read_entity_df("purchase_order")

        valid_suppliers = set(df_sup["supplier_id"])
        valid_parts = set(df_sp["part_id"])

        po_suppliers = set(df_po["supplier_id"])
        po_parts = set(df_po["part_id"])

        assert po_suppliers.issubset(valid_suppliers)
        assert po_parts.issubset(valid_parts)

    def test_work_order_part_usages_reference_valid_parts(self, source_mgr: CanonicalSourceManager):
        df_sp = source_mgr.read_entity_df("spare_part")
        df_usage = source_mgr.read_entity_df("wo_part_usage")
        valid_parts = set(df_sp["part_id"])
        usage_parts = set(df_usage["part_id"])
        assert usage_parts.issubset(valid_parts)


class TestCanonicalDomainConstraints:
    """Verifies domain constraints, positive quantities, and sanity bounds."""

    def test_spare_part_stock_quantities_non_negative(self, source_mgr: CanonicalSourceManager):
        df_sp = source_mgr.read_entity_df("spare_part")
        assert (df_sp["stock_qty"] >= 0).all()

    def test_downtime_durations_non_negative(self, source_mgr: CanonicalSourceManager):
        df_dt = source_mgr.read_entity_df("downtime_event")
        assert (df_dt["duration_min"] >= 0).all()

    def test_hourly_telemetry_run_fraction_in_bounds(self, source_mgr: CanonicalSourceManager):
        # Sample hourly sensor reading
        path = source_mgr.resolve_entity_path("sensor_reading_hourly")
        assert path is not None
        df_sample = pd.read_csv(path, nrows=5000)
        assert ((df_sample["run_fraction"] >= 0.0) & (df_sample["run_fraction"] <= 1.0)).all()


class TestCanonicalM21ScenarioVerification:
    """Verifies all aspects of the canonical M21 primary scenario per AGENT.md contract."""

    def test_m21_machine_identity(self, source_mgr: CanonicalSourceManager):
        df_m = source_mgr.read_entity_df("machine")
        m21 = df_m[df_m["machine_id"] == "M21"]
        assert len(m21) == 1
        row = m21.iloc[0]
        assert row["machine_name"] == "Grinder 3"
        assert row["line_id"] == "L5"
        assert row["model"] == "GR-600"
        assert row["machine_type"] == "Grinder"

    def test_m21_bearing_component(self, source_mgr: CanonicalSourceManager):
        df_c = source_mgr.read_entity_df("component")
        comp = df_c[df_c["component_id"] == "C-M21-BRG"]
        assert len(comp) == 1
        row = comp.iloc[0]
        assert row["machine_id"] == "M21"
        assert row["component_type"] == "Drive-End Bearing"
        assert row["model"] == "6206-2RS"

    def test_m21_sensors(self, source_mgr: CanonicalSourceManager):
        df_s = source_mgr.read_entity_df("sensor")
        m21_sensors = df_s[df_s["machine_id"] == "M21"]
        sensor_ids = set(m21_sensors["sensor_id"])
        assert "S-M21-VIB" in sensor_ids
        assert "S-M21-BTMP" in sensor_ids

        vib = m21_sensors[m21_sensors["sensor_id"] == "S-M21-VIB"].iloc[0]
        assert vib["component_id"] == "C-M21-BRG"
        assert vib["sensor_type"] == "vibration_rms"

        btmp = m21_sensors[m21_sensors["sensor_id"] == "S-M21-BTMP"].iloc[0]
        assert btmp["component_id"] == "C-M21-BRG"
        assert btmp["sensor_type"] == "bearing_temperature"

    def test_m21_spare_part_sp002_stockout(self, source_mgr: CanonicalSourceManager):
        df_sp = source_mgr.read_entity_df("spare_part")
        sp002 = df_sp[df_sp["part_id"] == "SP-002"]
        assert len(sp002) == 1
        row = sp002.iloc[0]
        assert row["compatible_model"] == "6206-2RS"
        assert row["stock_qty"] == 0
        assert row["supplier_id"] == "SUP-12"
        assert row["lead_time_days"] == 5

    def test_m21_customer_production_order_keystone(self, source_mgr: CanonicalSourceManager):
        df_po = source_mgr.read_entity_df("production_order")
        po = df_po[df_po["production_order_id"] == "PRD-01278"]
        assert len(po) == 1
        row = po.iloc[0]
        assert row["machine_id"] == "M21"
        assert row["customer"] == "Keystone Hydraulics"

    def test_m21_prediction_pred000322(self, source_mgr: CanonicalSourceManager):
        df_pred = source_mgr.read_entity_df("prediction")
        pred = df_pred[df_pred["prediction_id"] == "PRED-000322"]
        assert len(pred) == 1
        row = pred.iloc[0]
        assert row["machine_id"] == "M21"
        assert row["suspected_component_id"] == "C-M21-BRG"
        assert float(row["failure_prob"]) >= 0.90
        assert row["risk_level"] == "high"
