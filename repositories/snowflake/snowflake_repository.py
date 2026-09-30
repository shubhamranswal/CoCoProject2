"""Snowflake-backed repository implementation for production operations.

Follows AGENT.md:
- Queries governed Snowflake schemas: FACTORY_CORE, FACTORY_TELEMETRY, FACTORY_INTELLIGENCE, etc.
- Uses parameterized queries to prevent SQL injection.
- Does not move entire tables into Python memory.
"""

from __future__ import annotations

from typing import List, Optional
from datetime import datetime

from domain.enums import AlertStatus, ApprovalStatus, HealthStatus, MachineState, WorkOrderStatus, SensorType, Severity, FailureMode
from domain.models import (
    Alert,
    Anomaly,
    Approval,
    AuditEvent,
    Baseline,
    Component,
    Document,
    Evidence,
    Failure,
    FailureRisk,
    FeatureVector,
    HealthAssessment,
    Investigation,
    Machine,
    MaintenanceEvent,
    Plant,
    ProductionLine,
    Sensor,
    TelemetryMeasurement,
    Verification,
    WorkOrder,
)
from repositories.base import (
    GovernanceRepository,
    InvestigationRepository,
    KnowledgeRepository,
    MachineRepository,
    MaintenanceRepository,
    ReliabilityRepository,
    TelemetryRepository,
)
from repositories.snowflake.connection import SnowflakeConnectionManager


class SnowflakeRepository(
    MachineRepository,
    TelemetryRepository,
    MaintenanceRepository,
    ReliabilityRepository,
    InvestigationRepository,
    GovernanceRepository,
    KnowledgeRepository,
):
    def __init__(self, connection_manager: Optional[SnowflakeConnectionManager] = None) -> None:
        self.conn_mgr = connection_manager or SnowflakeConnectionManager()

    # MachineRepository
    def get_plant(self, plant_id: str) -> Optional[Plant]:
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT plant_id, plant_code, name, location, timezone, created_at "
                "FROM FACTORY_CORE.PLANT WHERE plant_id = %s",
                (plant_id,),
            )
            row = cur.fetchone()
            if not row:
                return None
            return Plant(
                plant_id=row[0],
                plant_code=row[1],
                name=row[2],
                location=row[3],
                timezone=row[4],
                created_at=row[5],
            )
        finally:
            cur.close()
            conn.close()

    def list_lines(self, plant_id: str) -> List[ProductionLine]:
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT line_id, plant_id, line_code, name, target_units_per_hour, status, created_at "
                "FROM FACTORY_CORE.PRODUCTION_LINE WHERE plant_id = %s ORDER BY line_id",
                (plant_id,),
            )
            rows = cur.fetchall()
            return [
                ProductionLine(
                    line_id=r[0],
                    plant_id=r[1],
                    line_code=r[2],
                    name=r[3],
                    target_units_per_hour=r[4],
                    status=r[5],
                    created_at=r[6],
                )
                for r in rows
            ]
        finally:
            cur.close()
            conn.close()

    def get_machine(self, machine_id: str) -> Optional[Machine]:
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT machine_id, line_id, machine_code, name, asset_type, criticality, "
                "health_status, state, manufacturer, model, serial_number, commission_date, created_at "
                "FROM FACTORY_CORE.MACHINE WHERE machine_id = %s",
                (machine_id,),
            )
            r = cur.fetchone()
            if not r:
                return None
            return Machine(
                machine_id=r[0],
                line_id=r[1],
                machine_code=r[2],
                name=r[3],
                asset_type=r[4],
                criticality=r[5],
                health_status=HealthStatus(r[6]),
                state=MachineState(r[7]),
                manufacturer=r[8],
                model=r[9],
                serial_number=r[10],
                commission_date=r[11],
                created_at=r[12],
            )
        finally:
            cur.close()
            conn.close()

    def list_machines(self, line_id: Optional[str] = None) -> List[Machine]:
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            if line_id:
                cur.execute(
                    "SELECT machine_id, line_id, machine_code, name, asset_type, criticality, "
                    "health_status, state, manufacturer, model, serial_number, commission_date, created_at "
                    "FROM FACTORY_CORE.MACHINE WHERE line_id = %s ORDER BY machine_id",
                    (line_id,),
                )
            else:
                cur.execute(
                    "SELECT machine_id, line_id, machine_code, name, asset_type, criticality, "
                    "health_status, state, manufacturer, model, serial_number, commission_date, created_at "
                    "FROM FACTORY_CORE.MACHINE ORDER BY machine_id"
                )
            rows = cur.fetchall()
            return [
                Machine(
                    machine_id=r[0],
                    line_id=r[1],
                    machine_code=r[2],
                    name=r[3],
                    asset_type=r[4],
                    criticality=r[5],
                    health_status=HealthStatus(r[6]),
                    state=MachineState(r[7]),
                    manufacturer=r[8],
                    model=r[9],
                    serial_number=r[10],
                    commission_date=r[11],
                    created_at=r[12],
                )
                for r in rows
            ]
        finally:
            cur.close()
            conn.close()

    def get_components(self, machine_id: str) -> List[Component]:
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT component_id, machine_id, name, component_type, criticality, installed_at, health_status "
                "FROM FACTORY_CORE.COMPONENT WHERE machine_id = %s ORDER BY component_id",
                (machine_id,),
            )
            rows = cur.fetchall()
            return [
                Component(
                    component_id=r[0],
                    machine_id=r[1],
                    name=r[2],
                    component_type=r[3],
                    criticality=r[4],
                    installed_at=r[5],
                    health_status=HealthStatus(r[6]),
                )
                for r in rows
            ]
        finally:
            cur.close()
            conn.close()

    def get_sensors(self, machine_id: str) -> List[Sensor]:
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT sensor_id, machine_id, component_id, sensor_type, name, unit, "
                "sampling_rate_hz, range_min, range_max, is_active "
                "FROM FACTORY_CORE.SENSOR WHERE machine_id = %s ORDER BY sensor_id",
                (machine_id,),
            )
            rows = cur.fetchall()
            return [
                Sensor(
                    sensor_id=r[0],
                    machine_id=r[1],
                    component_id=r[2],
                    sensor_type=SensorType(r[3]),
                    name=r[4],
                    unit=r[5],
                    sampling_rate_hz=r[6],
                    range_min=r[7],
                    range_max=r[8],
                    is_active=r[9],
                )
                for r in rows
            ]
        finally:
            cur.close()
            conn.close()

    def update_machine_health(
        self, machine_id: str, health_status: HealthStatus, state: Optional[MachineState] = None
    ) -> Machine:
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            if state:
                cur.execute(
                    "UPDATE FACTORY_CORE.MACHINE SET health_status = %s, state = %s WHERE machine_id = %s",
                    (health_status.value, state.value, machine_id),
                )
            else:
                cur.execute(
                    "UPDATE FACTORY_CORE.MACHINE SET health_status = %s WHERE machine_id = %s",
                    (health_status.value, machine_id),
                )
            conn.commit()
            m = self.get_machine(machine_id)
            if not m:
                raise ValueError(f"Machine {machine_id} not found after update")
            return m
        finally:
            cur.close()
            conn.close()

    # TelemetryRepository
    def save_measurements(self, measurements: List[TelemetryMeasurement]) -> None:
        if not measurements:
            return
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            params = [
                (
                    m.measurement_id,
                    m.machine_id,
                    m.sensor_id,
                    m.timestamp.isoformat(),
                    m.value,
                    m.unit,
                    m.quality,
                )
                for m in measurements
            ]
            cur.executemany(
                "INSERT INTO FACTORY_TELEMETRY.MEASUREMENT "
                "(measurement_id, machine_id, sensor_id, timestamp, value, unit, quality) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                params,
            )
            conn.commit()
        finally:
            cur.close()
            conn.close()

    def get_recent_measurements(
        self, machine_id: str, sensor_id: Optional[str] = None, limit: int = 100
    ) -> List[TelemetryMeasurement]:
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            if sensor_id:
                cur.execute(
                    "SELECT measurement_id, machine_id, sensor_id, timestamp, value, unit, quality "
                    "FROM FACTORY_TELEMETRY.MEASUREMENT "
                    "WHERE machine_id = %s AND sensor_id = %s "
                    "ORDER BY timestamp DESC LIMIT %s",
                    (machine_id, sensor_id, limit),
                )
            else:
                cur.execute(
                    "SELECT measurement_id, machine_id, sensor_id, timestamp, value, unit, quality "
                    "FROM FACTORY_TELEMETRY.MEASUREMENT "
                    "WHERE machine_id = %s "
                    "ORDER BY timestamp DESC LIMIT %s",
                    (machine_id, limit),
                )
            rows = cur.fetchall()
            return [
                TelemetryMeasurement(
                    measurement_id=r[0],
                    machine_id=r[1],
                    sensor_id=r[2],
                    timestamp=r[3],
                    value=float(r[4]),
                    unit=r[5],
                    quality=r[6],
                )
                for r in rows
            ]
        finally:
            cur.close()
            conn.close()

    def save_feature(self, feature: FeatureVector) -> None:
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT INTO FACTORY_TELEMETRY.FEATURE "
                "(feature_id, machine_id, timestamp, window_minutes, vibration_rms, vibration_peak, "
                "temperature_mean, temperature_slope, rpm_mean, rpm_variance, current_mean) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    feature.feature_id,
                    feature.machine_id,
                    feature.timestamp.isoformat(),
                    feature.window_minutes,
                    feature.vibration_rms,
                    feature.vibration_peak,
                    feature.temperature_mean,
                    feature.temperature_slope,
                    feature.rpm_mean,
                    feature.rpm_variance,
                    feature.current_mean,
                ),
            )
            conn.commit()
        finally:
            cur.close()
            conn.close()

    def get_latest_features(self, machine_id: str) -> Optional[FeatureVector]:
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT feature_id, machine_id, timestamp, window_minutes, vibration_rms, vibration_peak, "
                "temperature_mean, temperature_slope, rpm_mean, rpm_variance, current_mean "
                "FROM FACTORY_TELEMETRY.FEATURE WHERE machine_id = %s ORDER BY timestamp DESC LIMIT 1",
                (machine_id,),
            )
            r = cur.fetchone()
            if not r:
                return None
            return FeatureVector(
                feature_id=r[0],
                machine_id=r[1],
                timestamp=r[2],
                window_minutes=r[3],
                vibration_rms=float(r[4]),
                vibration_peak=float(r[5]),
                temperature_mean=float(r[6]),
                temperature_slope=float(r[7]),
                rpm_mean=float(r[8]),
                rpm_variance=float(r[9]),
                current_mean=float(r[10]),
            )
        finally:
            cur.close()
            conn.close()

    def get_baseline(self, machine_id: str, signal_name: str) -> Optional[Baseline]:
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT baseline_id, machine_id, signal_name, operating_regime, baseline_mean, "
                "baseline_std, warning_threshold, critical_threshold, unit "
                "FROM FACTORY_TELEMETRY.BASELINE WHERE machine_id = %s AND signal_name = %s",
                (machine_id, signal_name),
            )
            r = cur.fetchone()
            if not r:
                return None
            return Baseline(
                baseline_id=r[0],
                machine_id=r[1],
                signal_name=r[2],
                operating_regime=r[3],
                baseline_mean=float(r[4]),
                baseline_std=float(r[5]),
                warning_threshold=float(r[6]),
                critical_threshold=float(r[7]),
                unit=r[8],
            )
        finally:
            cur.close()
            conn.close()

    def save_anomaly(self, anomaly: Anomaly) -> None:
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT INTO FACTORY_TELEMETRY.ANOMALY "
                "(anomaly_id, machine_id, sensor_id, detected_at, severity, score, metric_name, "
                "observed_value, baseline_value, deviation_pct, status) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    anomaly.anomaly_id,
                    anomaly.machine_id,
                    anomaly.sensor_id,
                    anomaly.detected_at.isoformat(),
                    anomaly.severity.value,
                    anomaly.score,
                    anomaly.metric_name,
                    anomaly.observed_value,
                    anomaly.baseline_value,
                    anomaly.deviation_pct,
                    anomaly.status,
                ),
            )
            conn.commit()
        finally:
            cur.close()
            conn.close()

    def get_anomalies(self, machine_id: str, active_only: bool = True) -> List[Anomaly]:
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            sql = (
                "SELECT anomaly_id, machine_id, sensor_id, detected_at, severity, score, "
                "metric_name, observed_value, baseline_value, deviation_pct, status "
                "FROM FACTORY_TELEMETRY.ANOMALY WHERE machine_id = %s "
            )
            if active_only:
                sql += "AND status = 'ACTIVE' "
            sql += "ORDER BY detected_at DESC"
            cur.execute(sql, (machine_id,))
            rows = cur.fetchall()
            return [
                Anomaly(
                    anomaly_id=r[0],
                    machine_id=r[1],
                    sensor_id=r[2],
                    detected_at=r[3],
                    severity=Severity(r[4]),
                    score=float(r[5]),
                    metric_name=r[6],
                    observed_value=float(r[7]),
                    baseline_value=float(r[8]),
                    deviation_pct=float(r[9]),
                    status=r[10],
                )
                for r in rows
            ]
        finally:
            cur.close()
            conn.close()

    # MaintenanceRepository
    def get_maintenance_history(self, machine_id: str, limit: int = 20) -> List[MaintenanceEvent]:
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT maintenance_id, machine_id, component_id, maintenance_type, performed_at, "
                "technician_name, duration_hours, notes FROM FACTORY_MAINTENANCE.MAINTENANCE_EVENT "
                "WHERE machine_id = %s ORDER BY performed_at DESC LIMIT %s",
                (machine_id, limit),
            )
            rows = cur.fetchall()
            return [
                MaintenanceEvent(
                    maintenance_id=r[0],
                    machine_id=r[1],
                    component_id=r[2],
                    maintenance_type=r[3],
                    performed_at=r[4],
                    technician_name=r[5],
                    duration_hours=float(r[6]),
                    notes=r[7] or "",
                )
                for r in rows
            ]
        finally:
            cur.close()
            conn.close()

    def save_maintenance_event(self, event: MaintenanceEvent) -> None:
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT INTO FACTORY_MAINTENANCE.MAINTENANCE_EVENT "
                "(maintenance_id, machine_id, component_id, maintenance_type, performed_at, "
                "technician_name, duration_hours, notes) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    event.maintenance_id,
                    event.machine_id,
                    event.component_id,
                    event.maintenance_type,
                    event.performed_at.isoformat(),
                    event.technician_name,
                    event.duration_hours,
                    event.notes,
                ),
            )
            conn.commit()
        finally:
            cur.close()
            conn.close()

    def create_work_order(self, work_order: WorkOrder) -> WorkOrder:
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            if work_order.idempotency_key:
                cur.execute(
                    "SELECT work_order_id FROM FACTORY_MAINTENANCE.WORK_ORDER WHERE idempotency_key = %s",
                    (work_order.idempotency_key,),
                )
                existing = cur.fetchone()
                if existing:
                    wo = self.get_work_order(existing[0])
                    if wo:
                        return wo
            cur.execute(
                "INSERT INTO FACTORY_MAINTENANCE.WORK_ORDER "
                "(work_order_id, machine_id, component_id, investigation_id, recommendation_id, "
                "title, description, failure_mode, priority, status, assigned_to, created_at, idempotency_key) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    work_order.work_order_id,
                    work_order.machine_id,
                    work_order.component_id,
                    work_order.investigation_id,
                    work_order.recommendation_id,
                    work_order.title,
                    work_order.description,
                    work_order.failure_mode.value,
                    work_order.priority.value,
                    work_order.status.value,
                    work_order.assigned_to,
                    work_order.created_at.isoformat(),
                    work_order.idempotency_key,
                ),
            )
            conn.commit()
            return work_order
        finally:
            cur.close()
            conn.close()

    def get_work_order(self, work_order_id: str) -> Optional[WorkOrder]:
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT work_order_id, machine_id, component_id, investigation_id, recommendation_id, "
                "title, description, failure_mode, priority, status, assigned_to, created_at, scheduled_date, completed_at, idempotency_key "
                "FROM FACTORY_MAINTENANCE.WORK_ORDER WHERE work_order_id = %s",
                (work_order_id,),
            )
            r = cur.fetchone()
            if not r:
                return None
            return WorkOrder(
                work_order_id=r[0],
                machine_id=r[1],
                component_id=r[2],
                investigation_id=r[3],
                recommendation_id=r[4],
                title=r[5],
                description=r[6],
                failure_mode=FailureMode(r[7]),
                priority=Priority(r[8]),
                status=WorkOrderStatus(r[9]),
                assigned_to=r[10],
                created_at=r[11],
                scheduled_date=r[12],
                completed_at=r[13],
                idempotency_key=r[14],
            )
        finally:
            cur.close()
            conn.close()

    def list_work_orders(
        self, machine_id: Optional[str] = None, status: Optional[WorkOrderStatus] = None
    ) -> List[WorkOrder]:
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            sql = (
                "SELECT work_order_id, machine_id, component_id, investigation_id, recommendation_id, "
                "title, description, failure_mode, priority, status, assigned_to, created_at, scheduled_date, completed_at, idempotency_key "
                "FROM FACTORY_MAINTENANCE.WORK_ORDER WHERE 1=1 "
            )
            params: list = []
            if machine_id:
                sql += "AND machine_id = %s "
                params.append(machine_id)
            if status:
                sql += "AND status = %s "
                params.append(status.value)
            sql += "ORDER BY created_at DESC"
            cur.execute(sql, tuple(params))
            rows = cur.fetchall()
            return [
                WorkOrder(
                    work_order_id=r[0],
                    machine_id=r[1],
                    component_id=r[2],
                    investigation_id=r[3],
                    recommendation_id=r[4],
                    title=r[5],
                    description=r[6],
                    failure_mode=FailureMode(r[7]),
                    priority=Priority(r[8]),
                    status=WorkOrderStatus(r[9]),
                    assigned_to=r[10],
                    created_at=r[11],
                    scheduled_date=r[12],
                    completed_at=r[13],
                    idempotency_key=r[14],
                )
                for r in rows
            ]
        finally:
            cur.close()
            conn.close()

    def update_work_order_status(self, work_order_id: str, status: WorkOrderStatus) -> WorkOrder:
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                "UPDATE FACTORY_MAINTENANCE.WORK_ORDER SET status = %s WHERE work_order_id = %s",
                (status.value, work_order_id),
            )
            conn.commit()
            wo = self.get_work_order(work_order_id)
            if not wo:
                raise ValueError(f"WorkOrder {work_order_id} not found")
            return wo
        finally:
            cur.close()
            conn.close()

    # ReliabilityRepository
    def get_failure_history(self, machine_id: str) -> List[Failure]:
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT failure_id, machine_id, component_id, failure_mode, occurred_at, "
                "root_cause, downtime_hours, maintenance_action_taken, resolved_at "
                "FROM FACTORY_RELIABILITY.FAILURE WHERE machine_id = %s ORDER BY occurred_at DESC",
                (machine_id,),
            )
            rows = cur.fetchall()
            return [
                Failure(
                    failure_id=r[0],
                    machine_id=r[1],
                    component_id=r[2],
                    failure_mode=FailureMode(r[3]),
                    occurred_at=r[4],
                    root_cause=r[5],
                    downtime_hours=float(r[6]),
                    maintenance_action_taken=r[7] or "",
                    resolved_at=r[8],
                )
                for r in rows
            ]
        finally:
            cur.close()
            conn.close()

    def save_failure_risk(self, risk: FailureRisk) -> None:
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT INTO FACTORY_RELIABILITY.FAILURE_RISK "
                "(risk_id, machine_id, failure_mode, risk_score, prediction_horizon_hours, "
                "model_version, prediction_timestamp, confidence) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    risk.risk_id,
                    risk.machine_id,
                    risk.failure_mode.value,
                    risk.risk_score,
                    risk.prediction_horizon_hours,
                    risk.model_version,
                    risk.prediction_timestamp.isoformat(),
                    risk.confidence,
                ),
            )
            conn.commit()
        finally:
            cur.close()
            conn.close()

    def get_latest_failure_risk(self, machine_id: str) -> Optional[FailureRisk]:
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT risk_id, machine_id, failure_mode, risk_score, prediction_horizon_hours, "
                "model_version, prediction_timestamp, confidence "
                "FROM FACTORY_RELIABILITY.FAILURE_RISK WHERE machine_id = %s "
                "ORDER BY prediction_timestamp DESC LIMIT 1",
                (machine_id,),
            )
            r = cur.fetchone()
            if not r:
                return None
            return FailureRisk(
                risk_id=r[0],
                machine_id=r[1],
                failure_mode=FailureMode(r[2]),
                risk_score=float(r[3]),
                prediction_horizon_hours=r[4],
                model_version=r[5],
                prediction_timestamp=r[6],
                confidence=float(r[7]),
            )
        finally:
            cur.close()
            conn.close()

    def save_health_assessment(self, assessment: HealthAssessment) -> None:
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT INTO FACTORY_RELIABILITY.HEALTH_ASSESSMENT "
                "(assessment_id, machine_id, health_status, health_score, primary_concern, updated_at) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                (
                    assessment.assessment_id,
                    assessment.machine_id,
                    assessment.health_status.value,
                    assessment.health_score,
                    assessment.primary_concern,
                    assessment.updated_at.isoformat(),
                ),
            )
            conn.commit()
        finally:
            cur.close()
            conn.close()

    def get_latest_health_assessment(self, machine_id: str) -> Optional[HealthAssessment]:
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT assessment_id, machine_id, health_status, health_score, primary_concern, updated_at "
                "FROM FACTORY_RELIABILITY.HEALTH_ASSESSMENT WHERE machine_id = %s "
                "ORDER BY updated_at DESC LIMIT 1",
                (machine_id,),
            )
            r = cur.fetchone()
            if not r:
                return None
            return HealthAssessment(
                assessment_id=r[0],
                machine_id=r[1],
                health_status=HealthStatus(r[2]),
                health_score=float(r[3]),
                primary_concern=r[4],
                updated_at=r[5],
            )
        finally:
            cur.close()
            conn.close()

    # InvestigationRepository
    def create_alert(self, alert: Alert) -> Alert:
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT INTO FACTORY_INTELLIGENCE.ALERT "
                "(alert_id, machine_id, component_id, severity, status, trigger_reason, risk_score, failure_mode, created_at) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    alert.alert_id,
                    alert.machine_id,
                    alert.component_id,
                    alert.severity.value,
                    alert.status.value,
                    alert.trigger_reason,
                    alert.risk_score,
                    alert.failure_mode.value,
                    alert.created_at.isoformat(),
                ),
            )
            conn.commit()
            return alert
        finally:
            cur.close()
            conn.close()

    def get_alert(self, alert_id: str) -> Optional[Alert]:
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT alert_id, machine_id, component_id, severity, status, trigger_reason, risk_score, failure_mode, created_at, acknowledged_at, resolved_at "
                "FROM FACTORY_INTELLIGENCE.ALERT WHERE alert_id = %s",
                (alert_id,),
            )
            r = cur.fetchone()
            if not r:
                return None
            return Alert(
                alert_id=r[0],
                machine_id=r[1],
                component_id=r[2],
                severity=Severity(r[3]),
                status=AlertStatus(r[4]),
                trigger_reason=r[5],
                risk_score=float(r[6]),
                failure_mode=FailureMode(r[7]),
                created_at=r[8],
                acknowledged_at=r[9],
                resolved_at=r[10],
            )
        finally:
            cur.close()
            conn.close()

    def list_alerts(
        self, machine_id: Optional[str] = None, status: Optional[AlertStatus] = None
    ) -> List[Alert]:
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            sql = (
                "SELECT alert_id, machine_id, component_id, severity, status, trigger_reason, risk_score, failure_mode, created_at, acknowledged_at, resolved_at "
                "FROM FACTORY_INTELLIGENCE.ALERT WHERE 1=1 "
            )
            params: list = []
            if machine_id:
                sql += "AND machine_id = %s "
                params.append(machine_id)
            if status:
                sql += "AND status = %s "
                params.append(status.value)
            sql += "ORDER BY created_at DESC"
            cur.execute(sql, tuple(params))
            rows = cur.fetchall()
            return [
                Alert(
                    alert_id=r[0],
                    machine_id=r[1],
                    component_id=r[2],
                    severity=Severity(r[3]),
                    status=AlertStatus(r[4]),
                    trigger_reason=r[5],
                    risk_score=float(r[6]),
                    failure_mode=FailureMode(r[7]),
                    created_at=r[8],
                    acknowledged_at=r[9],
                    resolved_at=r[10],
                )
                for r in rows
            ]
        finally:
            cur.close()
            conn.close()

    def create_investigation(self, investigation: Investigation) -> Investigation:
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT INTO FACTORY_INTELLIGENCE.INVESTIGATION "
                "(investigation_id, alert_id, machine_id, status, failure_mode, confidence, created_at) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (
                    investigation.investigation_id,
                    investigation.alert_id,
                    investigation.machine_id,
                    investigation.status.value,
                    investigation.failure_mode.value,
                    investigation.confidence,
                    investigation.created_at.isoformat(),
                ),
            )
            conn.commit()
            return investigation
        finally:
            cur.close()
            conn.close()

    def get_investigation(self, investigation_id: str) -> Optional[Investigation]:
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT investigation_id, alert_id, machine_id, status, failure_mode, confidence, created_at, completed_at "
                "FROM FACTORY_INTELLIGENCE.INVESTIGATION WHERE investigation_id = %s",
                (investigation_id,),
            )
            r = cur.fetchone()
            if not r:
                return None
            return Investigation(
                investigation_id=r[0],
                alert_id=r[1],
                machine_id=r[2],
                status=r[3],
                failure_mode=FailureMode(r[4]),
                confidence=float(r[5]),
                created_at=r[6],
                completed_at=r[7],
            )
        finally:
            cur.close()
            conn.close()

    def save_evidence(self, evidence: List[Evidence]) -> None:
        if not evidence:
            return
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            params = [
                (
                    ev.evidence_id,
                    ev.investigation_id,
                    ev.evidence_type,
                    ev.source,
                    ev.metric,
                    str(ev.observed_value),
                    str(ev.baseline_value) if ev.baseline_value is not None else None,
                    ev.relationship,
                    ev.summary,
                    ev.timestamp.isoformat(),
                )
                for ev in evidence
            ]
            cur.executemany(
                "INSERT INTO FACTORY_INTELLIGENCE.EVIDENCE "
                "(evidence_id, investigation_id, evidence_type, source, metric, observed_value, baseline_value, relationship, summary, timestamp) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                params,
            )
            conn.commit()
        finally:
            cur.close()
            conn.close()

    def update_investigation(self, investigation: Investigation) -> Investigation:
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                "UPDATE FACTORY_INTELLIGENCE.INVESTIGATION "
                "SET status = %s, confidence = %s, completed_at = %s WHERE investigation_id = %s",
                (
                    investigation.status.value,
                    investigation.confidence,
                    investigation.completed_at.isoformat() if investigation.completed_at else None,
                    investigation.investigation_id,
                ),
            )
            conn.commit()
            return investigation
        finally:
            cur.close()
            conn.close()

    # GovernanceRepository
    def create_approval(self, approval: Approval) -> Approval:
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT INTO FACTORY_AGENT.APPROVAL "
                "(approval_id, action_id, investigation_id, machine_id, status, requested_by, created_at) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (
                    approval.approval_id,
                    approval.action_id,
                    approval.investigation_id,
                    approval.machine_id,
                    approval.status.value,
                    approval.requested_by,
                    approval.created_at.isoformat(),
                ),
            )
            conn.commit()
            return approval
        finally:
            cur.close()
            conn.close()

    def get_approval(self, approval_id: str) -> Optional[Approval]:
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT approval_id, action_id, investigation_id, machine_id, status, requested_by, reviewed_by, reviewed_at, decision_reason, created_at "
                "FROM FACTORY_AGENT.APPROVAL WHERE approval_id = %s",
                (approval_id,),
            )
            r = cur.fetchone()
            if not r:
                return None
            return Approval(
                approval_id=r[0],
                action_id=r[1],
                investigation_id=r[2],
                machine_id=r[3],
                status=ApprovalStatus(r[4]),
                requested_by=r[5],
                reviewed_by=r[6],
                reviewed_at=r[7],
                decision_reason=r[8],
                created_at=r[9],
            )
        finally:
            cur.close()
            conn.close()

    def list_approvals(
        self, machine_id: Optional[str] = None, status: Optional[ApprovalStatus] = None
    ) -> List[Approval]:
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            sql = (
                "SELECT approval_id, action_id, investigation_id, machine_id, status, requested_by, reviewed_by, reviewed_at, decision_reason, created_at "
                "FROM FACTORY_AGENT.APPROVAL WHERE 1=1 "
            )
            params: list = []
            if machine_id:
                sql += "AND machine_id = %s "
                params.append(machine_id)
            if status:
                sql += "AND status = %s "
                params.append(status.value)
            sql += "ORDER BY created_at DESC"
            cur.execute(sql, tuple(params))
            rows = cur.fetchall()
            return [
                Approval(
                    approval_id=r[0],
                    action_id=r[1],
                    investigation_id=r[2],
                    machine_id=r[3],
                    status=ApprovalStatus(r[4]),
                    requested_by=r[5],
                    reviewed_by=r[6],
                    reviewed_at=r[7],
                    decision_reason=r[8],
                    created_at=r[9],
                )
                for r in rows
            ]
        finally:
            cur.close()
            conn.close()

    def update_approval(
        self, approval_id: str, status: ApprovalStatus, reviewer: str, reason: str
    ) -> Approval:
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                "UPDATE FACTORY_AGENT.APPROVAL "
                "SET status = %s, reviewed_by = %s, decision_reason = %s, reviewed_at = CURRENT_TIMESTAMP() "
                "WHERE approval_id = %s",
                (status.value, reviewer, reason, approval_id),
            )
            conn.commit()
            app = self.get_approval(approval_id)
            if not app:
                raise ValueError(f"Approval {approval_id} not found")
            return app
        finally:
            cur.close()
            conn.close()

    def save_verification(self, verification: Verification) -> None:
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT INTO FACTORY_AGENT.VERIFICATION "
                "(verification_id, investigation_id, work_order_id, machine_id, verified_at, "
                "pre_vibration_rms, post_vibration_rms, pre_temperature_c, post_temperature_c, "
                "pre_risk_score, post_risk_score, is_recovered, oee_recovery_pct, notes) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    verification.verification_id,
                    verification.investigation_id,
                    verification.work_order_id,
                    verification.machine_id,
                    verification.verified_at.isoformat(),
                    verification.pre_vibration_rms,
                    verification.post_vibration_rms,
                    verification.pre_temperature_c,
                    verification.post_temperature_c,
                    verification.pre_risk_score,
                    verification.post_risk_score,
                    verification.is_recovered,
                    verification.oee_recovery_pct,
                    verification.notes,
                ),
            )
            conn.commit()
        finally:
            cur.close()
            conn.close()

    def get_verification(self, work_order_id: str) -> Optional[Verification]:
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT verification_id, investigation_id, work_order_id, machine_id, verified_at, "
                "pre_vibration_rms, post_vibration_rms, pre_temperature_c, post_temperature_c, "
                "pre_risk_score, post_risk_score, is_recovered, oee_recovery_pct, notes "
                "FROM FACTORY_AGENT.VERIFICATION WHERE work_order_id = %s",
                (work_order_id,),
            )
            r = cur.fetchone()
            if not r:
                return None
            return Verification(
                verification_id=r[0],
                investigation_id=r[1],
                work_order_id=r[2],
                machine_id=r[3],
                verified_at=r[4],
                pre_vibration_rms=float(r[5]),
                post_vibration_rms=float(r[6]),
                pre_temperature_c=float(r[7]),
                post_temperature_c=float(r[8]),
                pre_risk_score=float(r[9]),
                post_risk_score=float(r[10]),
                is_recovered=bool(r[11]),
                oee_recovery_pct=float(r[12]),
                notes=r[13] or "",
            )
        finally:
            cur.close()
            conn.close()

    def log_audit(self, event: AuditEvent) -> None:
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            import json

            cur.execute(
                "INSERT INTO FACTORY_AUDIT.AUDIT_EVENT "
                "(audit_id, actor, action_type, resource_id, resource_type, timestamp, details, status) "
                "VALUES (%s, %s, %s, %s, %s, %s, PARSE_JSON(%s), %s)",
                (
                    event.audit_id,
                    event.actor,
                    event.action_type,
                    event.resource_id,
                    event.resource_type,
                    event.timestamp.isoformat(),
                    json.dumps(event.details),
                    event.status,
                ),
            )
            conn.commit()
        finally:
            cur.close()
            conn.close()

    # KnowledgeRepository
    def get_manual(self, machine_model: str) -> Optional[Document]:
        # Minimal retrieval for technical manual
        return None

    def search_docs(self, query: str) -> List[str]:
        return []
