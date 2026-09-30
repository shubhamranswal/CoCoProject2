"""Deterministic seed data for Plant 01, Line A/B/C, 10 machines, and primary machine M204."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict, List

from domain.enums import FailureMode, HealthStatus, MachineState, Priority, SensorType
from domain.models import (
    Baseline,
    Component,
    Document,
    Failure,
    KnowledgeChunk,
    Machine,
    MaintenanceEvent,
    Plant,
    ProductionLine,
    Sensor,
)

PLANT_01 = Plant(
    plant_id="PLANT-01",
    plant_code="PLT01",
    name="Pune Automotive Assembly & Packaging Plant",
    location="Pune, India",
    timezone="Asia/Kolkata",
)

LINES: List[ProductionLine] = [
    ProductionLine(
        line_id="LINE-A",
        plant_id="PLANT-01",
        line_code="LINE-A",
        name="Stamping & Body Assembly Line A",
        target_units_per_hour=120.0,
    ),
    ProductionLine(
        line_id="LINE-B",
        plant_id="PLANT-01",
        line_code="LINE-B",
        name="High-Speed Packaging & Conveyor Line B",
        target_units_per_hour=350.0,
    ),
    ProductionLine(
        line_id="LINE-C",
        plant_id="PLANT-01",
        line_code="LINE-C",
        name="Final Inspection & Palletizing Line C",
        target_units_per_hour=200.0,
    ),
]

MACHINES: List[Machine] = [
    # Line A
    Machine(machine_id="M101", line_id="LINE-A", machine_code="M101", name="Hydraulic Stamping Press 1", criticality="HIGH"),
    Machine(machine_id="M102", line_id="LINE-A", machine_code="M102", name="Transfer Feed Servo 1", criticality="MEDIUM"),
    Machine(machine_id="M103", line_id="LINE-A", machine_code="M103", name="Robotic Spot Welder Alpha", criticality="HIGH"),
    Machine(machine_id="M104", line_id="LINE-A", machine_code="M104", name="Roller Hemming Station 1", criticality="LOW"),
    # Line B (Contains Primary M204)
    Machine(machine_id="M201", line_id="LINE-B", machine_code="M201", name="Rotary Bottle Filler", criticality="HIGH"),
    Machine(machine_id="M202", line_id="LINE-B", machine_code="M202", name="High-Speed Capper Unit", criticality="MEDIUM"),
    Machine(machine_id="M203", line_id="LINE-B", machine_code="M203", name="Continuous Induction Sealer", criticality="MEDIUM"),
    Machine(
        machine_id="M204",
        line_id="LINE-B",
        machine_code="M204",
        name="Conveyor Drive Motor B4",
        asset_type="ELECTRIC_MOTOR",
        criticality="CRITICAL",
        health_status=HealthStatus.HEALTHY,
        state=MachineState.RUNNING,
        manufacturer="Siemens / Industrial Dynamics",
        model="DRV-5000",
        serial_number="SN-DRV5000-2024-M204",
        commission_date=datetime(2023, 1, 15),
    ),
    # Line C
    Machine(machine_id="M301", line_id="LINE-C", machine_code="M301", name="Vision Inspection Tunnel", criticality="MEDIUM"),
    Machine(machine_id="M302", line_id="LINE-C", machine_code="M302", name="Automated Palletizer Robot", criticality="HIGH"),
]

M204_COMPONENTS: List[Component] = [
    Component(
        component_id="CMP-M204-BRG",
        machine_id="M204",
        name="Drive-End Deep Groove Ball Bearing Assembly",
        component_type="BEARING",
        criticality="CRITICAL",
        installed_at=datetime(2025, 4, 10),
        health_status=HealthStatus.HEALTHY,
    ),
    Component(
        component_id="CMP-M204-STR",
        machine_id="M204",
        name="Stator Winding Assembly",
        component_type="STATOR",
        criticality="HIGH",
        installed_at=datetime(2023, 1, 15),
        health_status=HealthStatus.HEALTHY,
    ),
    Component(
        component_id="CMP-M204-SHF",
        machine_id="M204",
        name="Motor Drive Shaft",
        component_type="SHAFT",
        criticality="HIGH",
        installed_at=datetime(2023, 1, 15),
        health_status=HealthStatus.HEALTHY,
    ),
    Component(
        component_id="CMP-M204-CPG",
        machine_id="M204",
        name="Flexible Gearbox Coupling",
        component_type="COUPLING",
        criticality="MEDIUM",
        installed_at=datetime(2024, 8, 20),
        health_status=HealthStatus.HEALTHY,
    ),
]

M204_SENSORS: List[Sensor] = [
    Sensor(
        sensor_id="SEN-M204-VIB",
        machine_id="M204",
        component_id="CMP-M204-BRG",
        sensor_type=SensorType.VIBRATION,
        name="Drive-End Bearing Accelerometer",
        unit="g",
        sampling_rate_hz=100.0,
        range_min=0.0,
        range_max=5.0,
    ),
    Sensor(
        sensor_id="SEN-M204-TMP",
        machine_id="M204",
        component_id="CMP-M204-BRG",
        sensor_type=SensorType.TEMPERATURE,
        name="Drive-End Bearing RTD Probe",
        unit="°C",
        sampling_rate_hz=1.0,
        range_min=-10.0,
        range_max=150.0,
    ),
    Sensor(
        sensor_id="SEN-M204-RPM",
        machine_id="M204",
        component_id="CMP-M204-SHF",
        sensor_type=SensorType.RPM,
        name="Optical Shaft Tachometer",
        unit="RPM",
        sampling_rate_hz=10.0,
        range_min=0.0,
        range_max=3000.0,
    ),
    Sensor(
        sensor_id="SEN-M204-CUR",
        machine_id="M204",
        component_id="CMP-M204-STR",
        sensor_type=SensorType.CURRENT,
        name="CT Motor Phase Current Sensor",
        unit="A",
        sampling_rate_hz=10.0,
        range_min=0.0,
        range_max=60.0,
    ),
]

M204_BASELINES: List[Baseline] = [
    Baseline(
        baseline_id="BASE-M204-VIB",
        machine_id="M204",
        signal_name="vibration_rms",
        operating_regime="NORMAL_LOAD",
        baseline_mean=0.45,
        baseline_std=0.04,
        warning_threshold=0.70,
        critical_threshold=1.00,
        unit="g",
    ),
    Baseline(
        baseline_id="BASE-M204-TMP",
        machine_id="M204",
        signal_name="temperature",
        operating_regime="NORMAL_LOAD",
        baseline_mean=58.5,
        baseline_std=2.1,
        warning_threshold=75.0,
        critical_threshold=90.0,
        unit="°C",
    ),
    Baseline(
        baseline_id="BASE-M204-RPM",
        machine_id="M204",
        signal_name="rpm",
        operating_regime="NORMAL_LOAD",
        baseline_mean=1750.0,
        baseline_std=15.0,
        warning_threshold=1650.0,
        critical_threshold=1500.0,
        unit="RPM",
    ),
    Baseline(
        baseline_id="BASE-M204-CUR",
        machine_id="M204",
        signal_name="current",
        operating_regime="NORMAL_LOAD",
        baseline_mean=18.5,
        baseline_std=0.8,
        warning_threshold=24.0,
        critical_threshold=30.0,
        unit="A",
    ),
]

M204_FAILURES: List[Failure] = [
    Failure(
        failure_id="FAIL-M204-2025-01",
        machine_id="M204",
        component_id="CMP-M204-BRG",
        failure_mode=FailureMode.BEARING_DEGRADATION,
        occurred_at=datetime(2025, 4, 8, 14, 20),
        root_cause="Bearing inner race micro-spalling causing thermal runaway and high vibration harmonic",
        downtime_hours=5.5,
        maintenance_action_taken="Emergency shutdown, replaced drive-end ball bearing assembly, re-greased with synthetic polyurea grease",
        resolved_at=datetime(2025, 4, 8, 19, 50),
    )
]

M204_MAINTENANCE_HISTORY: List[MaintenanceEvent] = [
    MaintenanceEvent(
        maintenance_id="MNT-M204-2025-04",
        machine_id="M204",
        component_id="CMP-M204-BRG",
        maintenance_type="REPLACEMENT",
        performed_at=datetime(2025, 4, 8, 18, 0),
        technician_name="Rajesh Kumar",
        duration_hours=3.5,
        parts_replaced=["BEARING-6210-2RS"],
        notes="Replaced defective drive-end bearing following spalling failure. Dynamic balance confirmed < 0.45g RMS.",
    ),
    MaintenanceEvent(
        maintenance_id="MNT-M204-2026-08",
        machine_id="M204",
        component_id="CMP-M204-BRG",
        maintenance_type="INSPECTION",
        performed_at=datetime(2026, 8, 12, 9, 30),
        technician_name="Amit Sharma",
        duration_hours=1.0,
        parts_replaced=[],
        notes="Routine 120-day predictive inspection. Vibration RMS was 0.48g, operating temp 60.1°C. Lubrication replenished.",
    ),
]

M204_MANUAL = Document(
    document_id="DOC-DRV5000-MANUAL",
    title="DRV-5000 Industrial Motor Technical Service & Maintenance Manual",
    doc_type="MANUAL",
    machine_model="DRV-5000",
    version="3.2",
    chunks=[
        KnowledgeChunk(
            chunk_id="CHK-DRV5000-01",
            document_id="DOC-DRV5000-MANUAL",
            section_title="4.2 Drive-End Bearing Specifications & Tolerances",
            content=(
                "The DRV-5000 utilizes premium deep groove ball bearings (model 6210-2RS C3). "
                "Baseline vibration velocity in ISO 10816-3 Class II zone A should not exceed 0.55 g RMS (or 2.8 mm/s). "
                "Vibration RMS exceeding 0.75 g indicates early raceway fatigue or lubrication degradation. "
                "Continuous operation above 1.0 g RMS poses severe risk of catastrophic seizure."
            ),
            tags=["bearing", "vibration", "limits", "M204"],
        ),
        KnowledgeChunk(
            chunk_id="CHK-DRV5000-02",
            document_id="DOC-DRV5000-MANUAL",
            section_title="5.1 Thermal Operating Limits & Precursors",
            content=(
                "Normal steady-state bearing temperature under nominal 80% duty cycle is 55°C - 65°C. "
                "A rising thermal gradient exceeding +2°C/hr coupled with increasing vibration peak-to-peak amplitude "
                "is the canonical signature of bearing raceway flaking and grease breakdown. Immediate endoscopic inspection "
                "and replacement within 48 to 72 operational hours is mandatory."
            ),
            tags=["temperature", "bearing_degradation", "thermal_gradient"],
        ),
        KnowledgeChunk(
            chunk_id="CHK-DRV5000-03",
            document_id="DOC-DRV5000-MANUAL",
            section_title="7.4 Recommended Corrective Work Order Procedure",
            content=(
                "1. Isolate motor power (LOTO procedure). "
                "2. Decouple motor shaft from Line B main conveyor gearbox. "
                "3. Use hydraulic puller to extract 6210-2RS bearing assembly. "
                "4. Inspect shaft seat for fretting corrosion. "
                "5. Heat replacement bearing to 110°C induction and mount flush against shaft shoulder. "
                "6. Verify radial runout < 0.02 mm and re-align coupling within 0.05 mm angular tolerance."
            ),
            tags=["work_order", "procedure", "replacement", "checklist"],
        ),
    ],
)
