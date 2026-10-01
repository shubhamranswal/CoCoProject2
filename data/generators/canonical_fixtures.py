"""Deterministic test fixtures for canonical 25-machine factory dataset.

Follows AGENT.md v2.0:
- Explicitly labeled test fixtures for unit tests and offline execution
- Represents canonical M21, M15, M05 scenarios with exact physical IDs:
  - M21 = Grinder 3 (GR-600, Line L5)
  - C-M21-BRG = Drive-End Bearing (6206-2RS)
  - S-M21-VIB = Vibration RMS (warn: 2.8, crit: 4.5 mm/s)
  - S-M21-BTMP = Bearing Temperature (warn: 75, crit: 90 degC)
  - SP-002 = Drive-End Bearing 6206-2RS (stock: 0, lead: 5 days, supplier: SUP-12)
  - PRD-01278 = Production order for Keystone Hydraulics due 2026-09-29
  - PRED-000322 = High risk (0.95 prob) bearing breakdown prediction on M21
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Dict, List

from domain.enums import FailureMode, HealthStatus, MachineState, Priority, SensorType
from domain.models import (
    Baseline,
    Component,
    Document,
    Failure,
    Machine,
    MaintenanceEvent,
    Plant,
    ProductionLine,
    Sensor,
    Product,
    ProductionOrder,
    PurchaseOrder,
    SparePart,
    Supplier,
    CanonicalPrediction,
)

CANONICAL_PLANT = Plant(
    plant_id="PLT01",
    plant_code="PLT01",
    name="Pune Automotive Assembly & Machining Plant",
    location="Pune, India",
    timezone="Asia/Kolkata",
)

CANONICAL_LINES: List[ProductionLine] = [
    ProductionLine(line_id="L1", plant_id="PLT01", line_code="L1", name="Heavy Machining Line 1", target_units_per_hour=80.0),
    ProductionLine(line_id="L2", plant_id="PLT01", line_code="L2", name="Precision Lathe & Turning Line 2", target_units_per_hour=100.0),
    ProductionLine(line_id="L3", plant_id="PLT01", line_code="L3", name="Stamping & Press Line 3", target_units_per_hour=150.0),
    ProductionLine(line_id="L4", plant_id="PLT01", line_code="L4", name="Assembly & Injection Molding Line 4", target_units_per_hour=120.0),
    ProductionLine(line_id="L5", plant_id="PLT01", line_code="L5", name="Grinding & Finishing Line 5", target_units_per_hour=90.0),
]

# Canonical 25 machines from machine.csv
CANONICAL_MACHINES: List[Machine] = [
    Machine(machine_id="M01", line_id="L1", machine_code="M01", name="CNC Lathe 1", asset_type="CNC Lathe", criticality="B"),
    Machine(machine_id="M02", line_id="L1", machine_code="M02", name="CNC Milling 1", asset_type="CNC Milling", criticality="A"),
    Machine(machine_id="M03", line_id="L1", machine_code="M03", name="Hydraulic Press 1", asset_type="Hydraulic Press", criticality="C"),
    Machine(machine_id="M04", line_id="L1", machine_code="M04", name="Injection Molding 1", asset_type="Injection Molding", criticality="B"),
    Machine(machine_id="M05", line_id="L1", machine_code="M05", name="Grinder 1", asset_type="Grinder", criticality="B"),
    Machine(machine_id="M06", line_id="L2", machine_code="M06", name="Packaging Line 1", asset_type="Packaging Line", criticality="B"),
    Machine(machine_id="M07", line_id="L2", machine_code="M07", name="Conveyor Assembly 1", asset_type="Conveyor Assembly", criticality="C"),
    Machine(machine_id="M08", line_id="L2", machine_code="M08", name="Air Compressor 1", asset_type="Air Compressor", criticality="C"),
    Machine(machine_id="M09", line_id="L2", machine_code="M09", name="CNC Lathe 2", asset_type="CNC Lathe", criticality="C"),
    Machine(machine_id="M10", line_id="L2", machine_code="M10", name="CNC Milling 2", asset_type="CNC Milling", criticality="A"),
    Machine(machine_id="M11", line_id="L3", machine_code="M11", name="Hydraulic Press 2", asset_type="Hydraulic Press", criticality="A"),
    Machine(machine_id="M12", line_id="L3", machine_code="M12", name="Injection Molding 2", asset_type="Injection Molding", criticality="B"),
    Machine(machine_id="M13", line_id="L3", machine_code="M13", name="Grinder 2", asset_type="Grinder", criticality="C"),
    Machine(machine_id="M14", line_id="L3", machine_code="M14", name="Packaging Line 2", asset_type="Packaging Line", criticality="B"),
    Machine(machine_id="M15", line_id="L3", machine_code="M15", name="Conveyor Assembly 2", asset_type="Conveyor Assembly", criticality="A"),
    Machine(machine_id="M16", line_id="L4", machine_code="M16", name="Air Compressor 2", asset_type="Air Compressor", criticality="A"),
    Machine(machine_id="M17", line_id="L4", machine_code="M17", name="CNC Lathe 3", asset_type="CNC Lathe", criticality="A"),
    Machine(machine_id="M18", line_id="L4", machine_code="M18", name="CNC Milling 3", asset_type="CNC Milling", criticality="A"),
    Machine(machine_id="M19", line_id="L4", machine_code="M19", name="Hydraulic Press 3", asset_type="Hydraulic Press", criticality="C"),
    Machine(machine_id="M20", line_id="L4", machine_code="M20", name="Injection Molding 3", asset_type="Injection Molding", criticality="B"),
    Machine(
        machine_id="M21",
        line_id="L5",
        machine_code="M21",
        name="Grinder 3",
        asset_type="Grinder",
        criticality="B",
        health_status=HealthStatus.HEALTHY,
        state=MachineState.RUNNING,
        model="GR-600",
    ),
    Machine(machine_id="M22", line_id="L5", machine_code="M22", name="Packaging Line 3", asset_type="Packaging Line", criticality="B"),
    Machine(machine_id="M23", line_id="L5", machine_code="M23", name="Conveyor Assembly 3", asset_type="Conveyor Assembly", criticality="C"),
    Machine(machine_id="M24", line_id="L5", machine_code="M24", name="Air Compressor 3", asset_type="Air Compressor", criticality="C"),
    Machine(machine_id="M25", line_id="L5", machine_code="M25", name="CNC Lathe 4", asset_type="CNC Lathe", criticality="A"),
]

# Canonical Components for Spotlight assets (M21, M15, M05)
CANONICAL_COMPONENTS: List[Component] = [
    # M21 (Grinder 3)
    Component(component_id="C-M21-BRG", machine_id="M21", name="Drive-End Bearing 6206-2RS", component_type="Drive-End Bearing", criticality="CRITICAL"),
    Component(component_id="C-M21-MTR", machine_id="M21", name="Drive Motor IE3-12kW", component_type="Drive Motor", criticality="HIGH"),
    Component(component_id="C-M21-CLT", machine_id="M21", name="Coolant Pump CP-40", component_type="Coolant Pump", criticality="MEDIUM"),
    Component(component_id="C-M21-DRV", machine_id="M21", name="Gearbox/Drive Belt Gearbox-GR12", component_type="Gearbox/Drive Belt", criticality="MEDIUM"),
    Component(component_id="C-M21-ELC", machine_id="M21", name="PLC/Electrical Panel S7-1500", component_type="PLC/Electrical Panel", criticality="HIGH"),
    Component(component_id="C-M21-TLG", machine_id="M21", name="Tooling Cutter-EM12", component_type="Tooling", criticality="LOW"),
    # M15 (Conveyor Assembly 2)
    Component(component_id="C-M15-MTR", machine_id="M15", name="Drive Motor IE3-5kW", component_type="Drive Motor", criticality="CRITICAL"),
    Component(component_id="C-M15-BRG", machine_id="M15", name="Drive-End Bearing 6205-2RS", component_type="Drive-End Bearing", criticality="HIGH"),
    # M05 (Grinder 1)
    Component(component_id="C-M05-CLT", machine_id="M05", name="Coolant Pump CP-75", component_type="Coolant Pump", criticality="CRITICAL"),
    Component(component_id="C-M05-BRG", machine_id="M05", name="Drive-End Bearing NU210", component_type="Drive-End Bearing", criticality="HIGH"),
]

# Canonical Sensors for Spotlight assets
CANONICAL_SENSORS: List[Sensor] = [
    Sensor(sensor_id="S-M21-VIB", machine_id="M21", component_id="C-M21-BRG", sensor_type=SensorType.VIBRATION, name="Drive-End Bearing Accelerometer", unit="mm/s", sampling_rate_hz=12000.0, range_min=0.0, range_max=20.0),
    Sensor(sensor_id="S-M21-BTMP", machine_id="M21", component_id="C-M21-BRG", sensor_type=SensorType.TEMPERATURE, name="Bearing Thermocouple Probe", unit="degC", sampling_rate_hz=1.0, range_min=-10.0, range_max=150.0),
    Sensor(sensor_id="S-M21-CUR", machine_id="M21", component_id="C-M21-MTR", sensor_type=SensorType.CURRENT, name="Drive Motor Current CT", unit="A", sampling_rate_hz=100.0, range_min=0.0, range_max=50.0),
    Sensor(sensor_id="S-M21-WTMP", machine_id="M21", component_id="C-M21-MTR", sensor_type=SensorType.TEMPERATURE, name="Stator Winding Temp Sensor", unit="degC", sampling_rate_hz=1.0, range_min=-10.0, range_max=180.0),
    Sensor(sensor_id="S-M21-RPM", machine_id="M21", component_id="C-M21-MTR", sensor_type=SensorType.RPM, name="Spindle Encoder Tachometer", unit="rpm", sampling_rate_hz=10.0, range_min=0.0, range_max=3000.0),
    Sensor(sensor_id="S-M21-FLW", machine_id="M21", component_id="C-M21-CLT", sensor_type=SensorType.FLOW, name="Coolant Line Flowmeter", unit="L/min", sampling_rate_hz=1.0, range_min=0.0, range_max=50.0),
    # M15
    Sensor(sensor_id="S-M15-RPM", machine_id="M15", component_id="C-M15-MTR", sensor_type=SensorType.RPM, name="Conveyor Motor Tachometer", unit="rpm", sampling_rate_hz=10.0, range_min=0.0, range_max=3000.0),
    # M05
    Sensor(sensor_id="S-M05-FLW", machine_id="M05", component_id="C-M05-CLT", sensor_type=SensorType.FLOW, name="Grinder Coolant Flowmeter", unit="L/min", sampling_rate_hz=1.0, range_min=0.0, range_max=50.0),
]

# Canonical Spare Parts
CANONICAL_SPARE_PARTS: List[SparePart] = [
    SparePart(part_id="SP-001", part_name="Drive-End Bearing 6205-2RS", part_category="Drive-End Bearing", compatible_model="6205-2RS", unit_cost_inr=4890.0, supplier_id="SUP-12", lead_time_days=8, stock_qty=0, reorder_level=2, reorder_qty=4, warehouse_bin="WH-A16"),
    SparePart(part_id="SP-002", part_name="Drive-End Bearing 6206-2RS", part_category="Drive-End Bearing", compatible_model="6206-2RS", unit_cost_inr=5590.0, supplier_id="SUP-12", lead_time_days=5, stock_qty=0, reorder_level=2, reorder_qty=4, warehouse_bin="WH-B01"),
    SparePart(part_id="SP-003", part_name="Drive-End Bearing 6308-C3", part_category="Drive-End Bearing", compatible_model="6308-C3", unit_cost_inr=7800.0, supplier_id="SUP-10", lead_time_days=33, stock_qty=2, reorder_level=2, reorder_qty=4, warehouse_bin="WH-D13"),
    SparePart(part_id="SP-004", part_name="Drive-End Bearing NU210", part_category="Drive-End Bearing", compatible_model="NU210", unit_cost_inr=3430.0, supplier_id="SUP-01", lead_time_days=6, stock_qty=3, reorder_level=2, reorder_qty=4, warehouse_bin="WH-D16"),
    SparePart(part_id="SP-005", part_name="Coolant Pump CP-40", part_category="Coolant Pump", compatible_model="CP-40", unit_cost_inr=11920.0, supplier_id="SUP-04", lead_time_days=6, stock_qty=6, reorder_level=2, reorder_qty=4, warehouse_bin="WH-C09"),
]

# Canonical Suppliers
CANONICAL_SUPPLIERS: List[Supplier] = [
    Supplier(supplier_id="SUP-01", supplier_name="Apex Bearings Pvt Ltd", country="India", avg_lead_time_days=6, on_time_delivery_pct=96.0),
    Supplier(supplier_id="SUP-04", supplier_name="Coolflow Industrial", country="India", avg_lead_time_days=5, on_time_delivery_pct=95.0),
    Supplier(supplier_id="SUP-10", supplier_name="EuroMotion GmbH", country="Germany", avg_lead_time_days=35, on_time_delivery_pct=88.0),
    Supplier(supplier_id="SUP-12", supplier_name="Vertex Industrial Supplies", country="India", avg_lead_time_days=7, on_time_delivery_pct=94.0),
]

# Canonical Purchase Orders
CANONICAL_PURCHASE_ORDERS: List[PurchaseOrder] = [
    PurchaseOrder(po_id="PO-00015", supplier_id="SUP-12", part_id="SP-002", qty=4, unit_cost_inr=5590.0, order_date=date(2026, 8, 15), expected_delivery_date=date(2026, 8, 20), actual_delivery_date=date(2026, 8, 22), status="received", order_type="replenishment"),
    PurchaseOrder(po_id="PO-00204", supplier_id="SUP-12", part_id="SP-002", qty=1, unit_cost_inr=6428.0, order_date=date(2026, 6, 11), expected_delivery_date=date(2026, 6, 12), actual_delivery_date=date(2026, 6, 12), status="received", order_type="expedited", linked_wo_id="WO-000394"),
    PurchaseOrder(po_id="PO-00214", supplier_id="SUP-12", part_id="SP-002", qty=1, unit_cost_inr=6428.0, order_date=date(2026, 3, 18), expected_delivery_date=date(2026, 3, 20), actual_delivery_date=date(2026, 3, 20), status="received", order_type="expedited", linked_wo_id="WO-000035"),
]

# Canonical Production Orders
CANONICAL_PRODUCTION_ORDERS: List[ProductionOrder] = [
    ProductionOrder(
        production_order_id="PRD-01278",
        machine_id="M21",
        product_id="P008",
        customer="Keystone Hydraulics",
        planned_qty=3894,
        produced_qty=3683,
        planned_start=datetime(2026, 9, 25, 6, 0, 0),
        planned_end=datetime(2026, 9, 29, 6, 0, 0),
        due_date=date(2026, 9, 29),
        priority="Medium",
        status="in_progress",
    )
]

# Canonical Predictions on 2026-09-28
CANONICAL_PREDICTIONS: List[CanonicalPrediction] = [
    CanonicalPrediction(
        prediction_id="PRED-000322",
        scored_ts=datetime(2026, 9, 28, 23, 0, 0),
        machine_id="M21",
        suspected_component_id="C-M21-BRG",
        model_name="hgb_failure_7d_v1",
        horizon_days=7,
        failure_prob=0.950,
        risk_level="high",
        top_features='[{"feature": "VIB_max", "share": 0.5}, {"feature": "VIB_mean", "share": 0.27}, {"feature": "VIB_rel30", "share": 0.22}]',
    ),
    CanonicalPrediction(
        prediction_id="PRED-000316",
        scored_ts=datetime(2026, 9, 28, 23, 0, 0),
        machine_id="M15",
        suspected_component_id="C-M15-MTR",
        model_name="hgb_failure_7d_v1",
        horizon_days=7,
        failure_prob=0.784,
        risk_level="high",
        top_features='[{"feature": "RPM_rel30", "share": 0.56}, {"feature": "RPM_slope7", "share": 0.35}, {"feature": "WTMP_max", "share": 0.09}]',
    ),
    CanonicalPrediction(
        prediction_id="PRED-000306",
        scored_ts=datetime(2026, 9, 28, 23, 0, 0),
        machine_id="M05",
        suspected_component_id="C-M05-CLT",
        model_name="hgb_failure_7d_v1",
        horizon_days=7,
        failure_prob=0.910,
        risk_level="high",
        top_features='[{"feature": "FLW_rel30", "share": 0.73}, {"feature": "FLW_slope7", "share": 0.18}, {"feature": "FLW_max", "share": 0.09}]',
    ),
]
