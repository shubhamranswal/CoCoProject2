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
    KnowledgeDocument,
    FailureModeTaxonomy,
    MachineHealthDaily,
    MachineOEEDaily,
    DowntimeSummary,
    MaintenanceSummary,
    InventoryRisk,
    ProductionContext,
    ReliabilityFeatures,
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

# Canonical 10 Failure Mode Taxonomies (Phase 2D)
CANONICAL_FAILURE_MODES: List[FailureModeTaxonomy] = [
    FailureModeTaxonomy(
        failure_code="BD-BRG",
        failure_name="Bearing Breakdown",
        category="MECHANICAL",
        component_type="Drive-End Bearing",
        typical_symptoms="Machine tripped on high vibration, bearing knock",
        primary_sensors=["vibration_rms", "bearing_temperature"],
        recommended_action="Replace bearing assembly, inspect housing, regrease and align shaft",
    ),
    FailureModeTaxonomy(
        failure_code="PD-VIB",
        failure_name="Predictive Bearing Degradation",
        category="MECHANICAL",
        component_type="Drive-End Bearing",
        typical_symptoms="High-frequency vibration RMS escalation above warning limit (2.8 mm/s)",
        primary_sensors=["vibration_rms", "bearing_temperature"],
        recommended_action="Schedule proactive bearing replacement before catastrophic race spalling",
    ),
    FailureModeTaxonomy(
        failure_code="BD-MTR",
        failure_name="Motor Winding / Stator Failure",
        category="ELECTRICAL",
        component_type="Drive Motor",
        typical_symptoms="Burning odor near motor enclosure, drive fault trip",
        primary_sensors=["motor_current", "winding_temperature"],
        recommended_action="Repair or replace drive motor, clean cooling airway, verify phase balance",
    ),
    FailureModeTaxonomy(
        failure_code="PD-CUR",
        failure_name="Predictive Motor Current Overload",
        category="ELECTRICAL",
        component_type="Drive Motor",
        typical_symptoms="Current draw trending above nominal under steady mechanical load",
        primary_sensors=["motor_current"],
        recommended_action="Inspect driven component for binding, lubricate transmission",
    ),
    FailureModeTaxonomy(
        failure_code="BD-HYD",
        failure_name="Hydraulic Pressure Loss",
        category="HYDRAULIC",
        component_type="Hydraulic Pump",
        typical_symptoms="Hydraulic pressure unstable, pump whining noise, slow cylinder stroke",
        primary_sensors=["hydraulic_pressure"],
        recommended_action="Replace worn hydraulic component, flush system oil and change filter cartridge",
    ),
    FailureModeTaxonomy(
        failure_code="BD-CLT",
        failure_name="Coolant Circulation Failure",
        category="COOLING",
        component_type="Coolant Pump",
        typical_symptoms="Coolant flow low warning, pump noisy, chip flushing ineffective",
        primary_sensors=["coolant_flow"],
        recommended_action="Clean suction strainer, replace worn impeller, refill coolant reservoir",
    ),
    FailureModeTaxonomy(
        failure_code="BD-DRV",
        failure_name="Drive Belt / Gearbox Mechanical Wear",
        category="MECHANICAL",
        component_type="Gearbox/Drive Belt",
        typical_symptoms="Gearbox noise, severe backlash, belt squeal upon spindle acceleration",
        primary_sensors=["rotational_speed"],
        recommended_action="Replace drive belt or worn gear set, set tension and verify alignment",
    ),
    FailureModeTaxonomy(
        failure_code="BD-ELC",
        failure_name="Electrical Panel / PLC Fault",
        category="ELECTRICAL",
        component_type="PLC/Electrical Panel",
        typical_symptoms="Control panel emergency stop trip, random 24V bus dip",
        primary_sensors=["general"],
        recommended_action="Reseat or replace faulty I/O module, tighten terminal screws and test I/O rack",
    ),
    FailureModeTaxonomy(
        failure_code="BD-TLG",
        failure_name="Tooling Wear & Dimension Drift",
        category="TOOLING",
        component_type="Tooling",
        typical_symptoms="Dimensional drift out of tolerance, excessive surface roughness, chatter",
        primary_sensors=["vibration_rms"],
        recommended_action="Index or replace cutting inserts/tool assembly, recalibrate tool offset table",
    ),
    FailureModeTaxonomy(
        failure_code="PM-ROUTINE",
        failure_name="Scheduled Preventive Maintenance",
        category="PREVENTIVE",
        component_type="General",
        typical_symptoms="Calendar/operating-hour interval reached without active failure fault",
        primary_sensors=["general"],
        recommended_action="Perform standard multi-point inspection, lubrication replenishment, and filter swap",
    ),
]

# Canonical 16 Knowledge Documents (Phase 2C)
CANONICAL_KNOWLEDGE_DOCS: List[KnowledgeDocument] = [
    KnowledgeDocument(
        document_id="DOC-001",
        title="Bearing failure troubleshooting guide",
        doc_type="troubleshooting",
        failure_code="BD-BRG",
        model="ALL",
        component_type="Drive-End Bearing",
        content=(
            "Rising vibration RMS, bearing temperature and audible noise at the drive end indicate "
            "bearing degradation. Typical root causes are lubrication failure, contamination, shaft "
            "misalignment and overload. Check grease condition and quantity, inspect housing seals, "
            "verify shaft alignment and look for raceway pitting (outer race, inner race or rolling element). "
            "Replace the bearing when vibration stays above the critical level and re-check trend values "
            "for 48 hours after restart."
        ),
        metadata={"category": "DIAGNOSTICS", "criticality": "CRITICAL"},
    ),
    KnowledgeDocument(
        document_id="DOC-002",
        title="Vibration severity reference (ISO 10816 style bands)",
        doc_type="reference",
        failure_code="BD-BRG",
        model="ALL",
        component_type="Drive-End Bearing",
        content=(
            "Vibration is judged on RMS velocity in mm/s. For small machines under about 15 kW this plant "
            "uses a warning level of 2.8 and a critical level of 4.5; for medium machines it uses 4.5 and 7.1. "
            "A sustained rise across several days matters more than a single-hour spike. Isolated one-minute "
            "spikes without a trend are usually electrical noise or process shocks and do not need a work order."
        ),
        metadata={"category": "ENGINEERING_REFERENCE", "standard": "ISO 10816"},
    ),
    KnowledgeDocument(
        document_id="DOC-003",
        title="Motor overheating and overload guide",
        doc_type="troubleshooting",
        failure_code="BD-MTR",
        model="ALL",
        component_type="Drive Motor",
        content=(
            "High winding temperature with rising current and falling speed suggests overload, blocked "
            "cooling, phase imbalance or insulation breakdown. Check fan cover and cooling path, measure "
            "current on all phases, test insulation resistance and inspect motor bearings. Warning limit for "
            "winding temperature is 110 degC and critical is 130 degC."
        ),
        metadata={"category": "DIAGNOSTICS"},
    ),
    KnowledgeDocument(
        document_id="DOC-004",
        title="Hydraulic pressure loss guide",
        doc_type="troubleshooting",
        failure_code="BD-HYD",
        model="ALL",
        component_type="Hydraulic Pump",
        content=(
            "A gradual drop in working pressure points to pump wear, internal leakage or contaminated oil; "
            "sudden loss points to seal failure or low oil level. Check oil level and condition, replace "
            "filters, inspect seals and measure pump output. Warning level is 140 bar and critical is 120 bar "
            "on this plant's presses and injection molding machines."
        ),
        metadata={"category": "DIAGNOSTICS"},
    ),
    KnowledgeDocument(
        document_id="DOC-005",
        title="Coolant flow low alarm guide",
        doc_type="troubleshooting",
        failure_code="BD-CLT",
        model="ALL",
        component_type="Coolant Pump",
        content=(
            "Falling coolant flow is usually a clogged filter, worn impeller or line leak. Clean or replace "
            "the filter, inspect the impeller and check hoses and clamps. Continuing to run with low flow "
            "risks overheating tools and spindles. Warning level is 22 L/min and critical is 15 L/min."
        ),
        metadata={"category": "DIAGNOSTICS"},
    ),
    KnowledgeDocument(
        document_id="DOC-006",
        title="Drive belt and gearbox guide",
        doc_type="troubleshooting",
        failure_code="BD-DRV",
        model="ALL",
        component_type="Gearbox/Drive Belt",
        content=(
            "Speed loss with squeal or gearbox noise indicates belt slippage, gear wear or a loose coupling. "
            "Check belt tension and condition, coupling bolts, alignment and gearbox oil for metal particles. "
            "Falling rotational speed below 96 percent of nominal is a warning and below 92 percent is critical."
        ),
        metadata={"category": "DIAGNOSTICS"},
    ),
    KnowledgeDocument(
        document_id="DOC-007",
        title="PLC and electrical fault guide",
        doc_type="troubleshooting",
        failure_code="BD-ELC",
        model="ALL",
        component_type="PLC/Electrical Panel",
        content=(
            "Intermittent stops with control faults are commonly loose terminals, failing I/O modules, power "
            "quality issues or damaged sensor cables. Check terminals for heat marks, review supply voltage logs, "
            "run I/O self-tests and inspect sensor cabling. Electrical faults are often sudden and show little "
            "precursor in vibration or temperature trends."
        ),
        metadata={"category": "DIAGNOSTICS"},
    ),
    KnowledgeDocument(
        document_id="DOC-008",
        title="Tooling wear and changeover SOP",
        doc_type="sop",
        failure_code="BD-TLG",
        model="ALL",
        component_type="Tooling",
        content=(
            "Replace tooling at the life limit or when surface finish or dimensions drift. After every tool "
            "change verify offsets on a first-off part. Incorrect offsets are a frequent cause of scrap and "
            "short stops right after changeover."
        ),
        metadata={"category": "OPERATING_PROCEDURE"},
    ),
    KnowledgeDocument(
        document_id="DOC-009",
        title="Preventive maintenance checklist - general",
        doc_type="sop",
        failure_code="PM-ROUTINE",
        model="ALL",
        component_type="General",
        content=(
            "At each PM: check lubrication points, belt tension, filters, fasteners and guards; record vibration "
            "and temperature readings; clean cooling paths and verify sensor calibration. Record observations in "
            "the work order so trends can be reviewed later."
        ),
        metadata={"category": "OPERATING_PROCEDURE"},
    ),
    KnowledgeDocument(
        document_id="DOC-010",
        title="Condition-based maintenance policy",
        doc_type="policy",
        failure_code="PM-ROUTINE",
        model="ALL",
        component_type="General",
        content=(
            "A predictive work order is raised when a monitored trend crosses its warning level or a model "
            "predicts a high failure probability within seven days. Schedule the work in the next planned stop, "
            "confirm spare availability first, and close the work order with the root cause category so the "
            "prediction model can learn from it."
        ),
        metadata={"category": "GOVERNANCE"},
    ),
    KnowledgeDocument(
        document_id="DOC-011",
        title="Spare parts criticality and stocking",
        doc_type="policy",
        failure_code="PM-ROUTINE",
        model="ALL",
        component_type="General",
        content=(
            "Critical spares (bearings, motors, hydraulic pumps) must never be at zero stock for machines "
            "rated criticality A. If stock is zero, raise an expedited purchase order when a predictive alert "
            "is open on the matching machine. Check supplier lead time before scheduling the maintenance window."
        ),
        metadata={"category": "GOVERNANCE"},
    ),
    KnowledgeDocument(
        document_id="DOC-012",
        title="OEE loss categories",
        doc_type="reference",
        failure_code="PM-ROUTINE",
        model="ALL",
        component_type="General",
        content=(
            "OEE is availability x performance x quality. Availability losses are breakdowns, changeovers, "
            "material shortages and operator absence. Performance losses are minor stops and reduced speed. "
            "Quality losses are scrap and rework. Planned maintenance is excluded from planned production time."
        ),
        metadata={"category": "ENGINEERING_REFERENCE"},
    ),
    KnowledgeDocument(
        document_id="DOC-013",
        title="Injection molding machine - hydraulic section notes",
        doc_type="oem_manual",
        failure_code="BD-HYD",
        model="Injection Molding",
        component_type="Hydraulic Pump",
        content=(
            "Keep oil temperature stable and change filters on schedule. Low oil level causes cavitation and "
            "accelerates pump wear. Pressure below the working range during injection is an early sign of pump "
            "or seal degradation."
        ),
        metadata={"category": "OEM_MANUAL"},
    ),
    KnowledgeDocument(
        document_id="DOC-014",
        title="CNC machine - spindle and coolant notes",
        doc_type="oem_manual",
        failure_code="BD-BRG",
        model="CNC Milling",
        component_type="Drive-End Bearing",
        content=(
            "Spindle bearings are sensitive to contamination; keep coolant clean and seals intact. Rising spindle "
            "vibration with stable load is a strong bearing indicator. Run the warm-up routine before heavy cuts."
        ),
        metadata={"category": "OEM_MANUAL"},
    ),
    KnowledgeDocument(
        document_id="DOC-015",
        title="Air compressor - motor and cooling notes",
        doc_type="oem_manual",
        failure_code="BD-MTR",
        model="Air Compressor",
        component_type="Drive Motor",
        content=(
            "Compressor motors run at higher speed and power. Keep cooler fins clean and monitor winding "
            "temperature. Speed sag with rising current indicates overload or belt/drive issues."
        ),
        metadata={"category": "OEM_MANUAL"},
    ),
    KnowledgeDocument(
        document_id="DOC-016",
        title="Conveyor and packaging - drive notes",
        doc_type="oem_manual",
        failure_code="BD-DRV",
        model="Conveyor Assembly",
        component_type="Gearbox/Drive Belt",
        content=(
            "Check belt tracking and tension weekly. Speed loss and squeal indicate belt slip. Keep gearbox oil "
            "at the correct level and inspect couplings during PM."
        ),
        metadata={"category": "OEM_MANUAL"},
    ),
]

# Canonical Analytical Fixtures (Phase 2A & 2B)
CANONICAL_HEALTH_DAILY: List[MachineHealthDaily] = [
    MachineHealthDaily(
        machine_id="M21",
        metric_date=date(2026, 9, 28),
        machine_name="Grinder 3",
        machine_type="Grinder",
        line_id="L5",
        line_name="Grinding & Finishing Line 5",
        reading_count=1440,
        avg_vibration=3.42,
        max_vibration=4.88,
        avg_temperature=78.5,
        max_temperature=84.2,
        exceedance_count=14,
        downtime_minutes=45.0,
        breakdown_count=0,
        maintenance_count=0,
        open_alerts=1,
        latest_prediction_id="PRED-000322",
        latest_failure_prob=0.950,
        latest_risk_level="high",
        health_status="CRITICAL",
    ),
    MachineHealthDaily(
        machine_id="M15",
        metric_date=date(2026, 9, 28),
        machine_name="Conveyor Assembly 2",
        machine_type="Conveyor Assembly",
        line_id="L3",
        line_name="Stamping & Press Line 3",
        reading_count=1440,
        avg_vibration=1.85,
        max_vibration=2.40,
        avg_temperature=62.1,
        max_temperature=68.5,
        exceedance_count=5,
        downtime_minutes=25.0,
        breakdown_count=0,
        maintenance_count=0,
        open_alerts=1,
        latest_prediction_id="PRED-000316",
        latest_failure_prob=0.784,
        latest_risk_level="high",
        health_status="WARNING",
    ),
    MachineHealthDaily(
        machine_id="M05",
        metric_date=date(2026, 9, 28),
        machine_name="Grinder 1",
        machine_type="Grinder",
        line_id="L1",
        line_name="Heavy Machining Line 1",
        reading_count=1440,
        avg_vibration=2.10,
        max_vibration=2.75,
        avg_temperature=65.0,
        max_temperature=71.2,
        exceedance_count=8,
        downtime_minutes=30.0,
        breakdown_count=0,
        maintenance_count=0,
        open_alerts=1,
        latest_prediction_id="PRED-000306",
        latest_failure_prob=0.910,
        latest_risk_level="high",
        health_status="CRITICAL",
    ),
]

CANONICAL_OEE_DAILY: List[MachineOEEDaily] = [
    MachineOEEDaily(
        machine_id="M21",
        metric_date=date(2026, 9, 28),
        machine_name="Grinder 3",
        line_id="L5",
        planned_production_minutes=1440.0,
        operating_minutes=1395.0,
        unplanned_downtime_minutes=45.0,
        total_pieces=1250,
        good_pieces=1225,
        reject_pieces=25,
        availability=0.9688,
        performance=0.9200,
        quality=0.9800,
        oee=0.8735,
    ),
    MachineOEEDaily(
        machine_id="M15",
        metric_date=date(2026, 9, 28),
        machine_name="Conveyor Assembly 2",
        line_id="L3",
        planned_production_minutes=1440.0,
        operating_minutes=1415.0,
        unplanned_downtime_minutes=25.0,
        total_pieces=3200,
        good_pieces=3160,
        reject_pieces=40,
        availability=0.9826,
        performance=0.9500,
        quality=0.9875,
        oee=0.9218,
    ),
    MachineOEEDaily(
        machine_id="M05",
        metric_date=date(2026, 9, 28),
        machine_name="Grinder 1",
        line_id="L1",
        planned_production_minutes=1440.0,
        operating_minutes=1410.0,
        unplanned_downtime_minutes=30.0,
        total_pieces=1100,
        good_pieces=1067,
        reject_pieces=33,
        availability=0.9792,
        performance=0.8800,
        quality=0.9700,
        oee=0.8358,
    ),
]

CANONICAL_DOWNTIME_DAILY: List[DowntimeSummary] = [
    DowntimeSummary(
        machine_id="M21",
        metric_date=date(2026, 9, 28),
        machine_name="Grinder 3",
        line_id="L5",
        total_downtime_minutes=45.0,
        breakdown_minutes=0.0,
        changeover_minutes=0.0,
        minor_stop_minutes=45.0,
        no_material_minutes=0.0,
        no_operator_minutes=0.0,
        planned_maintenance_minutes=0.0,
        breakdown_event_count=0,
        total_event_count=3,
        top_reason_code="MS-VIB",
        top_downtime_category="minor_stop",
    )
]

CANONICAL_MAINTENANCE_DAILY: List[MaintenanceSummary] = [
    MaintenanceSummary(
        machine_id="M21",
        metric_date=date(2026, 9, 28),
        machine_name="Grinder 3",
        line_id="L5",
        work_order_count=0,
        corrective_count=0,
        preventive_count=0,
        breakdown_count=0,
        total_labor_hours=0.0,
        total_parts_cost_inr=0.0,
        total_labor_cost_inr=0.0,
        total_maintenance_cost_inr=0.0,
        mean_time_to_repair_minutes=None,
    )
]

CANONICAL_INVENTORY_RISKS: List[InventoryRisk] = [
    InventoryRisk(
        part_id="SP-002",
        part_name="Drive-End Bearing 6206-2RS",
        part_category="Drive-End Bearing",
        compatible_model="6206-2RS",
        stock_qty=0,
        reorder_level=2,
        reorder_qty=4,
        lead_time_days=5,
        supplier_id="SUP-12",
        supplier_name="Vertex Industrial Supplies",
        open_po_count=0,
        open_po_qty=0,
        stock_status="STOCKOUT",
        is_critical_exposure=True,
    ),
    InventoryRisk(
        part_id="SP-001",
        part_name="Drive-End Bearing 6205-2RS",
        part_category="Drive-End Bearing",
        compatible_model="6205-2RS",
        stock_qty=0,
        reorder_level=2,
        reorder_qty=4,
        lead_time_days=8,
        supplier_id="SUP-12",
        supplier_name="Vertex Industrial Supplies",
        open_po_count=0,
        open_po_qty=0,
        stock_status="STOCKOUT",
        is_critical_exposure=True,
    ),
    InventoryRisk(
        part_id="SP-004",
        part_name="Drive-End Bearing NU210",
        part_category="Drive-End Bearing",
        compatible_model="NU210",
        stock_qty=3,
        reorder_level=2,
        reorder_qty=4,
        lead_time_days=6,
        supplier_id="SUP-01",
        supplier_name="Apex Bearings Pvt Ltd",
        open_po_count=0,
        open_po_qty=0,
        stock_status="HEALTHY",
        is_critical_exposure=False,
    ),
]

CANONICAL_PRODUCTION_CONTEXTS: List[ProductionContext] = [
    ProductionContext(
        production_order_id="PRD-01278",
        machine_id="M21",
        machine_name="Grinder 3",
        line_id="L5",
        product_id="P008",
        product_name="High-Pressure Hydraulic Cylinder Shaft",
        customer="Keystone Hydraulics",
        priority="Medium",
        status="in_progress",
        planned_qty=3894,
        produced_qty=3683,
        progress_pct=94.58,
        due_date=date(2026, 9, 29),
        days_until_due=1,
        is_overdue=False,
        unit_price_inr=16000.0,
        order_value_inr=62304000.0,
        unfulfilled_revenue_exposure_inr=3376000.0,
    )
]

CANONICAL_RELIABILITY_FEATURES: List[ReliabilityFeatures] = [
    ReliabilityFeatures(
        machine_id="M21",
        feature_date=date(2026, 9, 28),
        vib_mean_7d=3.12,
        vib_max_7d=4.88,
        vib_std_7d=0.65,
        vib_rel30=1.48,
        vib_slope_7d=0.28,
        temp_mean_7d=76.4,
        temp_max_7d=84.2,
        temp_rel30=1.18,
        exceedance_ratio_7d=0.12,
        downtime_ratio_7d=0.05,
        unplanned_downtime_hours_7d=6.2,
        breakdown_count_30d=0,
        days_since_last_maint=42,
    ),
    ReliabilityFeatures(
        machine_id="M15",
        feature_date=date(2026, 9, 28),
        vib_mean_7d=1.75,
        vib_max_7d=2.40,
        vib_std_7d=0.35,
        vib_rel30=1.15,
        vib_slope_7d=0.05,
        temp_mean_7d=61.2,
        temp_max_7d=68.5,
        temp_rel30=1.05,
        exceedance_ratio_7d=0.03,
        downtime_ratio_7d=0.02,
        unplanned_downtime_hours_7d=2.1,
        breakdown_count_30d=0,
        days_since_last_maint=85,
    ),
]
