"""Snowflake-backed repository implementation for production operations.

Follows AGENT.md:
- Queries governed Snowflake schemas in COCO_FACTORY: CORE, ANALYTICS, ML, KNOWLEDGE, APP.
- Uses parameterized queries to prevent SQL injection.
- Does not move entire tables into Python memory.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from datetime import date, datetime, timezone
import json

from domain.exceptions import UnsupportedOperationError
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
    Finding,
    HealthAssessment,
    Hypothesis,
    Investigation,
    Machine,
    MaintenanceEvent,
    MLFailurePrediction,
    Plant,
    PredictionOutcome,
    ProductionLine,
    Recommendation,
    Sensor,
    TelemetryMeasurement,
    ToolCall,
    Verification,
    VerificationResult,
    VerificationPolicy,
    ActionProposal,
    ActionExecution,
    ActionOutcome,
    WorkOrder,
    CanonicalPrediction,
    Product,
    ProductionOrder,
    PurchaseOrder,
    SparePart,
    Supplier,
    WorkOrderPartUsage,
    KnowledgeDocument,
    FailureModeTaxonomy,
    MachineHealthDaily,
    MachineOEEDaily,
    DowntimeSummary,
    MaintenanceSummary,
    InventoryRisk,
    ProductionContext,
    ReliabilityFeatures,
    ModelRegistryRecord,
    ModelEvaluationRecord,
    PredictionFeatureSnapshot,
    PredictionLineage,
)
from repositories.base import (
    GovernanceRepository,
    InvestigationRepository,
    KnowledgeRepository,
    MachineRepository,
    MaintenanceRepository,
    ReliabilityRepository,
    SupplyChainRepository,
    TelemetryRepository,
    AnalyticsRepository,
    KnowledgeSearchRepository,
    MLRepository,
)
from repositories.snowflake.connection import SnowflakeConnectionManager


def _canonical_to_ml_prediction(cp: CanonicalPrediction) -> MLFailurePrediction:
    """Map canonical CORE.PREDICTION record into domain MLFailurePrediction."""
    comp_id = cp.suspected_component_id or ""
    if "BRG" in comp_id:
        fmode = FailureMode.BEARING_DEGRADATION
    elif "MTR" in comp_id:
        fmode = FailureMode.MOTOR_OVERHEAT
    elif "HYD" in comp_id:
        fmode = FailureMode.HYDRAULIC_LOSS
    elif "GRB" in comp_id:
        fmode = FailureMode.GEARBOX_WEAR
    else:
        fmode = FailureMode.BEARING_DEGRADATION

    top_feats: Dict[str, float] = {}
    if cp.top_features:
        try:
            parsed = json.loads(cp.top_features)
            if isinstance(parsed, dict):
                top_feats = {str(k): float(v) for k, v in parsed.items()}
            elif isinstance(parsed, list):
                for item in parsed:
                    if isinstance(item, dict) and "feature" in item and "share" in item:
                        top_feats[str(item["feature"])] = float(item["share"])
                    elif isinstance(item, dict) and len(item) == 1:
                        k, v = next(iter(item.items()))
                        top_feats[str(k)] = float(v)
        except Exception:
            top_feats = {}

    horizon_hours = int(cp.horizon_days) * 24 if cp.horizon_days else 168
    scored_ts = cp.scored_ts
    if isinstance(scored_ts, str):
        try:
            scored_ts = datetime.fromisoformat(scored_ts)
        except Exception:
            scored_ts = datetime.now()

    prob = float(cp.failure_prob)
    return MLFailurePrediction(
        prediction_id=cp.prediction_id,
        machine_id=cp.machine_id,
        component_id=cp.suspected_component_id,
        failure_mode=fmode,
        failure_probability=prob,
        prediction_horizon_hours=horizon_hours,
        model_name=cp.model_name,
        model_version="1.0.0",
        training_dataset_version="v2026.03-canonical",
        feature_schema_version="v1.0-29feat",
        confidence=0.95 if prob >= 0.70 else 0.88,
        threshold_exceeded=prob >= 0.40,
        top_contributing_features=top_feats,
        feature_timestamp=scored_ts,
        prediction_timestamp=scored_ts,
    )


def map_alert_severity(raw_severity: Optional[str]) -> Severity:
    """Explicit mapping from canonical Snowflake/database severity strings to domain Severity enum.

    Canonical CORE.ALERT values:
    - 'critical' -> Severity.CRITICAL
    - 'warning' -> Severity.HIGH (active condition-monitoring threshold exceedance)

    Standard fallback for unknown/None values is Severity.MEDIUM.
    """
    if not raw_severity:
        return Severity.MEDIUM
    val = str(raw_severity).strip().lower()
    if val == "critical":
        return Severity.CRITICAL
    elif val in ("warning", "warn", "high"):
        return Severity.HIGH
    elif val in ("medium", "med"):
        return Severity.MEDIUM
    elif val == "low":
        return Severity.LOW
    return Severity.MEDIUM


def map_alert_status(raw_status: Optional[str]) -> AlertStatus:
    """Explicit mapping from canonical Snowflake/database alert status strings to domain AlertStatus enum.

    Canonical CORE.ALERT values:
    - 'open' -> AlertStatus.OPEN
    - 'acknowledged' -> AlertStatus.INVESTIGATING
    - 'closed' -> AlertStatus.RESOLVED

    Standard fallback for unknown/None values is AlertStatus.OPEN.
    """
    if not raw_status:
        return AlertStatus.OPEN
    val = str(raw_status).strip().lower()
    if val == "open":
        return AlertStatus.OPEN
    elif val in ("closed", "resolved"):
        return AlertStatus.RESOLVED
    elif val in ("acknowledged", "investigating"):
        return AlertStatus.INVESTIGATING
    elif val == "action_proposed":
        return AlertStatus.ACTION_PROPOSED
    elif val == "dismissed":
        return AlertStatus.DISMISSED
    return AlertStatus.OPEN


class SnowflakeRepository(
    MachineRepository,
    TelemetryRepository,
    MaintenanceRepository,
    ReliabilityRepository,
    InvestigationRepository,
    GovernanceRepository,
    KnowledgeRepository,
    SupplyChainRepository,
    AnalyticsRepository,
    KnowledgeSearchRepository,
    MLRepository,
):
    is_derived_health: bool = True

    def __init__(self, connection_manager: Optional[SnowflakeConnectionManager] = None) -> None:
        self.conn_mgr = connection_manager or SnowflakeConnectionManager()

    # MachineRepository
    def get_plant(self, plant_id: str) -> Optional[Plant]:
        if not plant_id or not str(plant_id).strip():
            return None
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT DISTINCT plant_id "
                "FROM COCO_FACTORY.CORE.MACHINE WHERE plant_id = %s AND plant_id IS NOT NULL",
                (plant_id.strip(),),
            )
            row = cur.fetchone()
            if not row or not row[0]:
                return None
            p_id = row[0]
            return Plant(
                plant_id=p_id,
                plant_code=p_id,
                name="Pune Automotive Assembly & Machining Plant" if p_id == "PLT01" else f"Plant {p_id}",
                location="Pune, India",
                timezone="Asia/Kolkata",
            )
        finally:
            cur.close()
            conn.close()

    def list_lines(self, plant_id: str) -> List[ProductionLine]:
        if not plant_id or not str(plant_id).strip():
            return []
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT DISTINCT line_id, plant_id "
                "FROM COCO_FACTORY.CORE.MACHINE WHERE plant_id = %s "
                "AND line_id IS NOT NULL AND TRIM(line_id) != '' ORDER BY line_id",
                (plant_id.strip(),),
            )
            rows = cur.fetchall()
            canonical_line_meta = {
                "L1": ("Heavy Machining Line 1", 80.0),
                "L2": ("Precision Lathe & Turning Line 2", 100.0),
                "L3": ("Stamping & Press Line 3", 150.0),
                "L4": ("Assembly & Injection Molding Line 4", 120.0),
                "L5": ("Grinding & Finishing Line 5", 90.0),
            }
            res = []
            for r in rows:
                line_id = r[0]
                meta_name, target_uph = canonical_line_meta.get(line_id, (f"Line {line_id}", 100.0))
                res.append(
                    ProductionLine(
                        line_id=line_id,
                        plant_id=r[1],
                        line_code=line_id,
                        name=meta_name,
                        target_units_per_hour=target_uph,
                        status="ACTIVE",
                    )
                )
            return res
        finally:
            cur.close()
            conn.close()

    def get_machine(self, machine_id: str) -> Optional[Machine]:
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                SELECT m.machine_id, m.line_id, m.machine_name, m.machine_type, m.criticality,
                       m.model, m.install_date, m._loaded_at,
                       COALESCE(h.health_status, 'HEALTHY') AS current_health_status,
                       m.plant_id
                FROM COCO_FACTORY.CORE.MACHINE m
                LEFT JOIN (
                    SELECT machine_id, health_status,
                           ROW_NUMBER() OVER (PARTITION BY machine_id ORDER BY metric_date DESC) as rn
                    FROM COCO_FACTORY.ANALYTICS.MACHINE_HEALTH_DAILY
                ) h ON m.machine_id = h.machine_id AND h.rn = 1
                WHERE m.machine_id = %s
                """,
                (machine_id,),
            )
            r = cur.fetchone()
            if not r:
                return None
            m_id = r[0]
            health_val = r[8] if len(r) > 8 and r[8] else "HEALTHY"
            curr_health = (
                HealthStatus(health_val)
                if health_val in HealthStatus._value2member_map_
                else (
                    HealthStatus.DEGRADING
                    if health_val in ("WARNING", "DEGRADING")
                    else HealthStatus.HEALTHY
                )
            )
            plant_id_val = r[9] if len(r) > 9 and r[9] else None
            return Machine(
                machine_id=m_id,
                line_id=r[1],
                machine_code=m_id,
                name=r[2],
                asset_type=r[3],
                criticality=r[4],
                health_status=curr_health,
                state=MachineState.RUNNING,
                manufacturer="Industrial Dynamics",
                model=r[5] or "DRV-5000",
                serial_number=f"SN-{m_id}",
                commission_date=r[6],
                created_at=r[7] if r[7] else datetime.now(),
                plant_id=plant_id_val,
            )
        finally:
            cur.close()
            conn.close()

    def list_machines(self, line_id: Optional[str] = None) -> List[Machine]:
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            query = """
                SELECT m.machine_id, m.line_id, m.machine_name, m.machine_type, m.criticality,
                       m.model, m.install_date, m._loaded_at,
                       COALESCE(h.health_status, 'HEALTHY') AS current_health_status,
                       m.plant_id
                FROM COCO_FACTORY.CORE.MACHINE m
                LEFT JOIN (
                    SELECT machine_id, health_status,
                           ROW_NUMBER() OVER (PARTITION BY machine_id ORDER BY metric_date DESC) as rn
                    FROM COCO_FACTORY.ANALYTICS.MACHINE_HEALTH_DAILY
                ) h ON m.machine_id = h.machine_id AND h.rn = 1
            """
            params: list = []
            if line_id:
                query += " WHERE m.line_id = %s"
                params.append(line_id)
            query += " ORDER BY m.machine_id"
            cur.execute(query, tuple(params) if params else None)
            rows = cur.fetchall()
            machines = []
            for r in rows:
                m_id = r[0]
                health_val = r[8] if len(r) > 8 and r[8] else "HEALTHY"
                curr_health = (
                    HealthStatus(health_val)
                    if health_val in HealthStatus._value2member_map_
                    else (
                        HealthStatus.DEGRADING
                        if health_val in ("WARNING", "DEGRADING")
                        else HealthStatus.HEALTHY
                    )
                )
                plant_id_val = r[9] if len(r) > 9 and r[9] else None
                machines.append(
                    Machine(
                        machine_id=m_id,
                        line_id=r[1],
                        machine_code=m_id,
                        name=r[2],
                        asset_type=r[3],
                        criticality=r[4],
                        health_status=curr_health,
                        state=MachineState.RUNNING,
                        manufacturer="Industrial Dynamics",
                        model=r[5] or "DRV-5000",
                        serial_number=f"SN-{m_id}",
                        commission_date=r[6],
                        created_at=r[7] if r[7] else datetime.now(),
                        plant_id=plant_id_val,
                    )
                )
            return machines
        finally:
            cur.close()
            conn.close()

    def get_components(self, machine_id: str) -> List[Component]:
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT component_id, machine_id, COALESCE(model, component_type), "
                "component_type, install_date "
                "FROM COCO_FACTORY.CORE.COMPONENT WHERE machine_id = %s ORDER BY component_id",
                (machine_id,),
            )
            rows = cur.fetchall()
            return [
                Component(
                    component_id=r[0],
                    machine_id=r[1],
                    name=r[2],
                    component_type=r[3],
                    criticality="HIGH",
                    installed_at=r[4],
                    health_status=HealthStatus.HEALTHY,
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
                "SELECT sensor_id, machine_id, component_id, sensor_type, unit, "
                "sampling_rate_hz, warn_threshold, crit_threshold "
                "FROM COCO_FACTORY.CORE.SENSOR WHERE machine_id = %s ORDER BY sensor_id",
                (machine_id,),
            )
            rows = cur.fetchall()
            return [
                Sensor(
                    sensor_id=r[0],
                    machine_id=r[1],
                    component_id=r[2],
                    sensor_type=SensorType(r[3]) if r[3] in SensorType._value2member_map_ else SensorType.VIBRATION,
                    name=r[0],
                    unit=r[4],
                    sampling_rate_hz=float(r[5]) if r[5] is not None else 1.0,
                    range_min=0.0,
                    range_max=float(r[7] or r[6] or 100.0),
                    is_active=True,
                )
                for r in rows
            ]
        finally:
            cur.close()
            conn.close()

    def update_machine_health(
        self, machine_id: str, health_status: HealthStatus, state: Optional[MachineState] = None
    ) -> Machine:
        """Explicitly reject unsupported direct machine health mutation on Snowflake backend.

        Canonical Architectural Contract:
        In COCO_FACTORY, CORE.MACHINE is an immutable asset master dimension.
        Operational machine health is derived authoritatively from predictions (CORE.PREDICTION),
        telemetry (CORE.SENSOR_READING_HOURLY), and alerts (CORE.ALERT) in
        COCO_FACTORY.ANALYTICS.MACHINE_HEALTH_DAILY.
        Direct DML against machine health is not supported.
        """
        raise UnsupportedOperationError(
            f"update_machine_health is unsupported on SnowflakeRepository: "
            f"COCO_FACTORY.CORE.MACHINE is an immutable master dimension. "
            f"Operational machine health is derived authoritatively from telemetry, alerts, and predictions "
            f"via COCO_FACTORY.ANALYTICS.MACHINE_HEALTH_DAILY."
        )

    # TelemetryRepository
    def save_measurements(self, measurements: List[TelemetryMeasurement]) -> None:
        if not measurements:
            return
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            params = [
                (
                    m.sensor_id,
                    m.timestamp.isoformat() if hasattr(m.timestamp, "isoformat") else str(m.timestamp),
                    m.value,
                )
                for m in measurements
            ]
            cur.executemany(
                "INSERT INTO COCO_FACTORY.CORE.SENSOR_READING (sensor_id, ts, value) "
                "VALUES (%s, %s, %s)",
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
                    "SELECT 'MSR-' || r.sensor_id, r.sensor_id, s.machine_id, r.ts, r.value, 'GOOD' "
                    "FROM COCO_FACTORY.CORE.SENSOR_READING r "
                    "JOIN COCO_FACTORY.CORE.SENSOR s ON r.sensor_id = s.sensor_id "
                    "WHERE s.machine_id = %s AND r.sensor_id = %s "
                    "ORDER BY r.ts DESC LIMIT %s",
                    (machine_id, sensor_id, limit),
                )
            else:
                cur.execute(
                    "SELECT 'MSR-' || r.sensor_id, r.sensor_id, s.machine_id, r.ts, r.value, 'GOOD' "
                    "FROM COCO_FACTORY.CORE.SENSOR_READING r "
                    "JOIN COCO_FACTORY.CORE.SENSOR s ON r.sensor_id = s.sensor_id "
                    "WHERE s.machine_id = %s "
                    "ORDER BY r.ts DESC LIMIT %s",
                    (machine_id, limit),
                )
            rows = cur.fetchall()
            return [
                TelemetryMeasurement(
                    measurement_id=r[0],
                    sensor_id=r[1],
                    machine_id=r[2],
                    timestamp=r[3],
                    value=float(r[4]),
                    unit="RMS_G",
                    quality=r[5],
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
            f_date = feature.timestamp.date() if hasattr(feature.timestamp, "date") else feature.timestamp
            cur.execute(
                "MERGE INTO COCO_FACTORY.ML.MACHINE_FEATURE_DAILY target "
                "USING (SELECT %s AS machine_id, %s AS feature_date, %s AS vib_rms, %s AS vib_max, "
                "%s AS btmp_mean, %s AS cur_mean, %s AS rpm_mean) source "
                "ON target.machine_id = source.machine_id AND target.feature_date = source.feature_date "
                "WHEN MATCHED THEN UPDATE SET "
                "vib_rms = source.vib_rms, vib_max = source.vib_max, btmp_mean = source.btmp_mean, "
                "cur_mean = source.cur_mean, rpm_mean = source.rpm_mean "
                "WHEN NOT MATCHED THEN INSERT "
                "(machine_id, feature_date, vib_rms, vib_max, btmp_mean, cur_mean, rpm_mean) "
                "VALUES (source.machine_id, source.feature_date, source.vib_rms, source.vib_max, source.btmp_mean, source.cur_mean, source.rpm_mean)",
                (
                    feature.machine_id,
                    str(f_date),
                    feature.vibration_rms,
                    feature.vibration_peak,
                    feature.temperature_mean,
                    feature.current_mean,
                    feature.rpm_mean,
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
                "SELECT machine_id, feature_date, vib_rms, vib_max, btmp_mean, btmp_slope7, rpm_mean, cur_mean "
                "FROM COCO_FACTORY.ML.V_MACHINE_FEATURE_DAILY WHERE machine_id = %s ORDER BY feature_date DESC LIMIT 1",
                (machine_id,),
            )
            r = cur.fetchone()
            if not r:
                return None
            return FeatureVector(
                feature_id=f"FEAT-{r[0]}-{r[1]}",
                machine_id=r[0],
                timestamp=datetime.combine(r[1], datetime.min.time()) if isinstance(r[1], date) else r[1],
                window_minutes=1440,
                vibration_rms=float(r[2] or 0.0),
                vibration_peak=float(r[3] or 0.0),
                temperature_mean=float(r[4] or 0.0),
                temperature_slope=float(r[5] or 0.0),
                rpm_mean=float(r[6] or 0.0),
                rpm_variance=0.0,
                current_mean=float(r[7] or 0.0),
            )
        finally:
            cur.close()
            conn.close()

    def get_baseline(self, machine_id: str, signal_name: str) -> Optional[Baseline]:
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT sensor_id, machine_id, sensor_type, warn_threshold, crit_threshold, unit "
                "FROM COCO_FACTORY.CORE.SENSOR WHERE machine_id = %s AND (sensor_type ILIKE %s OR sensor_id = %s) LIMIT 1",
                (machine_id, f"%{signal_name}%", signal_name),
            )
            r = cur.fetchone()
            if not r:
                return None
            return Baseline(
                baseline_id=f"BASE-{r[0]}",
                machine_id=r[1],
                signal_name=r[2],
                operating_regime="NORMAL",
                baseline_mean=0.0,
                baseline_std=0.0,
                warning_threshold=float(r[3] or 0.0),
                critical_threshold=float(r[4] or 0.0),
                unit=r[5] or "",
            )
        finally:
            cur.close()
            conn.close()

    def save_anomaly(self, anomaly: Anomaly) -> None:
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            ts_str = anomaly.detected_at.isoformat() if hasattr(anomaly.detected_at, "isoformat") else str(anomaly.detected_at)
            cur.execute(
                "MERGE INTO COCO_FACTORY.CORE.ALERT target "
                "USING (SELECT %s AS alert_id, %s AS machine_id, %s AS sensor_id, %s AS ts, "
                "%s AS severity, %s AS alert_type, %s AS reading_value, %s AS threshold_value, "
                "%s AS status, %s AS priority_score) source "
                "ON target.alert_id = source.alert_id "
                "WHEN MATCHED THEN UPDATE SET "
                "severity = source.severity, status = source.status, priority_score = source.priority_score "
                "WHEN NOT MATCHED THEN INSERT "
                "(alert_id, machine_id, sensor_id, ts, severity, alert_type, reading_value, threshold_value, status, priority_score) "
                "VALUES (source.alert_id, source.machine_id, source.sensor_id, source.ts, source.severity, source.alert_type, source.reading_value, source.threshold_value, source.status, source.priority_score)",
                (
                    anomaly.anomaly_id,
                    anomaly.machine_id,
                    anomaly.sensor_id,
                    ts_str,
                    anomaly.severity.value,
                    anomaly.metric_name,
                    anomaly.observed_value,
                    anomaly.baseline_value,
                    anomaly.status,
                    anomaly.score,
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
                "SELECT alert_id, machine_id, sensor_id, ts, severity, priority_score, "
                "alert_type, reading_value, threshold_value, status "
                "FROM COCO_FACTORY.CORE.ALERT WHERE machine_id = %s "
            )
            if active_only:
                sql += "AND LOWER(status) IN ('active', 'open') "
            sql += "ORDER BY ts DESC"
            cur.execute(sql, (machine_id,))
            rows = cur.fetchall()
            return [
                Anomaly(
                    anomaly_id=r[0],
                    machine_id=r[1],
                    sensor_id=r[2] or "UNKNOWN",
                    detected_at=r[3],
                    severity=map_alert_severity(r[4]),
                    score=float(r[5] or 0.5),
                    metric_name=r[6] or "vibration_rms",
                    observed_value=float(r[7] or 0.0),
                    baseline_value=float(r[8] or 0.0),
                    deviation_pct=0.0,
                    status=r[9] or "ACTIVE",
                )
                for r in rows
            ]
        finally:
            cur.close()
            conn.close()

    def list_anomalies(self, machine_id: Optional[str] = None, active_only: bool = True) -> List[Anomaly]:
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            sql = (
                "SELECT alert_id, machine_id, sensor_id, ts, severity, priority_score, "
                "alert_type, reading_value, threshold_value, status "
                "FROM COCO_FACTORY.CORE.ALERT WHERE 1=1 "
            )
            params: list = []
            if machine_id:
                sql += "AND machine_id = %s "
                params.append(machine_id)
            if active_only:
                sql += "AND LOWER(status) IN ('active', 'open') "
            sql += "ORDER BY ts DESC"
            cur.execute(sql, tuple(params))
            rows = cur.fetchall()
            return [
                Anomaly(
                    anomaly_id=r[0],
                    machine_id=r[1],
                    sensor_id=r[2] or "UNKNOWN",
                    detected_at=r[3],
                    severity=map_alert_severity(r[4]),
                    score=float(r[5] or 0.5),
                    metric_name=r[6] or "vibration_rms",
                    observed_value=float(r[7] or 0.0),
                    baseline_value=float(r[8] or 0.0),
                    deviation_pct=0.0,
                    status=r[9] or "ACTIVE",
                )
                for r in rows
            ]
        finally:
            cur.close()
            conn.close()

    # MaintenanceRepository
    def get_maintenance_history(self, machine_id: str, limit: int = 50) -> List[MaintenanceEvent]:
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT log_id, machine_id, component_id, COALESCE(wo_type, 'PREVENTIVE'), "
                "log_ts, COALESCE(technician_id, 'Technician'), COALESCE(downtime_min / 60.0, 1.0), "
                "COALESCE(action_taken || ' ' || COALESCE(note_text, ''), '') "
                "FROM COCO_FACTORY.CORE.MAINTENANCE_LOG WHERE machine_id = %s "
                "ORDER BY log_ts DESC LIMIT %s",
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
            ts_str = event.performed_at.isoformat() if hasattr(event.performed_at, "isoformat") else str(event.performed_at)
            cur.execute(
                "INSERT INTO COCO_FACTORY.CORE.MAINTENANCE_LOG "
                "(log_id, machine_id, component_id, wo_type, log_ts, technician_id, downtime_min, action_taken) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    event.maintenance_id,
                    event.machine_id,
                    event.component_id,
                    event.maintenance_type,
                    ts_str,
                    event.technician_name,
                    event.duration_hours * 60.0,
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
                    "SELECT wo_id FROM COCO_FACTORY.CORE.MAINTENANCE_WORK_ORDER WHERE wo_id = %s",
                    (work_order.idempotency_key,),
                )
                existing = cur.fetchone()
                if existing:
                    wo = self.get_work_order(existing[0])
                    if wo:
                        return wo
            opened_str = work_order.created_at.isoformat() if hasattr(work_order.created_at, "isoformat") else str(work_order.created_at)
            sched_str = work_order.scheduled_date.isoformat() if work_order.scheduled_date and hasattr(work_order.scheduled_date, "isoformat") else str(work_order.scheduled_date) if work_order.scheduled_date else None
            cur.execute(
                "INSERT INTO COCO_FACTORY.CORE.MAINTENANCE_WORK_ORDER "
                "(wo_id, machine_id, component_id, wo_type, source, priority, failure_code, status, assigned_to, opened_ts, scheduled_date, prediction_id) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    work_order.work_order_id,
                    work_order.machine_id,
                    work_order.component_id,
                    work_order.title,
                    work_order.description,
                    work_order.priority.value,
                    work_order.failure_mode.value,
                    work_order.status.value,
                    work_order.assigned_to,
                    opened_str,
                    sched_str,
                    work_order.investigation_id,
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
                "SELECT wo_id, machine_id, component_id, prediction_id, '' AS recommendation_id, "
                "wo_type AS title, COALESCE(source, '') AS description, failure_code, priority, status, "
                "COALESCE(assigned_to, '') AS assigned_to, opened_ts AS created_at, scheduled_date, closed_ts AS completed_at, wo_id AS idempotency_key "
                "FROM COCO_FACTORY.CORE.MAINTENANCE_WORK_ORDER WHERE wo_id = %s",
                (work_order_id,),
            )
            r = cur.fetchone()
            if not r:
                return None
            from domain.enums import Priority
            return WorkOrder(
                work_order_id=r[0],
                machine_id=r[1],
                component_id=r[2],
                investigation_id=r[3],
                recommendation_id=r[4],
                title=r[5],
                description=r[6],
                failure_mode=FailureMode(r[7]) if r[7] in FailureMode._value2member_map_ else FailureMode.BEARING_DEGRADATION,
                priority=Priority(r[8]) if r[8] in Priority._value2member_map_ else Priority.HIGH,
                status=WorkOrderStatus(r[9]) if r[9] in WorkOrderStatus._value2member_map_ else WorkOrderStatus.OPEN,
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
            from domain.enums import Priority
            sql = (
                "SELECT wo_id, machine_id, component_id, prediction_id, '' AS recommendation_id, "
                "wo_type AS title, COALESCE(source, '') AS description, failure_code, priority, status, "
                "COALESCE(assigned_to, '') AS assigned_to, opened_ts AS created_at, scheduled_date, closed_ts AS completed_at, wo_id AS idempotency_key "
                "FROM COCO_FACTORY.CORE.MAINTENANCE_WORK_ORDER WHERE 1=1 "
            )
            params: list = []
            if machine_id:
                sql += "AND machine_id = %s "
                params.append(machine_id)
            if status:
                sql += "AND status = %s "
                params.append(status.value)
            sql += "ORDER BY opened_ts DESC"
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
                    failure_mode=FailureMode(r[7]) if r[7] in FailureMode._value2member_map_ else FailureMode.BEARING_DEGRADATION,
                    priority=Priority(r[8]) if r[8] in Priority._value2member_map_ else Priority.HIGH,
                    status=WorkOrderStatus(r[9]) if r[9] in WorkOrderStatus._value2member_map_ else WorkOrderStatus.OPEN,
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
                "UPDATE COCO_FACTORY.CORE.MAINTENANCE_WORK_ORDER "
                "SET status = %s, closed_ts = CASE WHEN %s IN ('COMPLETED', 'CLOSED') THEN CURRENT_TIMESTAMP() ELSE closed_ts END "
                "WHERE wo_id = %s",
                (status.value, status.value, work_order_id),
            )
            conn.commit()
            wo = self.get_work_order(work_order_id)
            if not wo:
                raise ValueError(f"WorkOrder {work_order_id} not found")
            return wo
        finally:
            cur.close()
            conn.close()

    def update_work_order(self, work_order: WorkOrder) -> WorkOrder:
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                "UPDATE COCO_FACTORY.CORE.MAINTENANCE_WORK_ORDER SET "
                "status = %s, assigned_to = %s, scheduled_date = %s, closed_ts = %s "
                "WHERE wo_id = %s",
                (
                    work_order.status.value,
                    work_order.assigned_to,
                    work_order.scheduled_date.isoformat() if work_order.scheduled_date and hasattr(work_order.scheduled_date, "isoformat") else str(work_order.scheduled_date) if work_order.scheduled_date else None,
                    work_order.completed_at.isoformat() if work_order.completed_at and hasattr(work_order.completed_at, "isoformat") else str(work_order.completed_at) if work_order.completed_at else None,
                    work_order.work_order_id,
                ),
            )
            conn.commit()
            wo = self.get_work_order(work_order.work_order_id)
            if not wo:
                raise ValueError(f"WorkOrder {work_order.work_order_id} not found")
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
                "SELECT event_id, machine_id, '' AS component_id, 'BEARING_DEGRADATION' AS failure_mode, "
                "start_ts, COALESCE(reason_description, reason_code), COALESCE(duration_min / 60.0, 0.0), "
                "COALESCE(notes, ''), end_ts "
                "FROM COCO_FACTORY.CORE.DOWNTIME_EVENT WHERE machine_id = %s ORDER BY start_ts DESC",
                (machine_id,),
            )
            rows = cur.fetchall()
            return [
                Failure(
                    failure_id=r[0],
                    machine_id=r[1],
                    component_id=r[2],
                    failure_mode=FailureMode.BEARING_DEGRADATION,
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
            ts_str = risk.prediction_timestamp.isoformat() if hasattr(risk.prediction_timestamp, "isoformat") else str(risk.prediction_timestamp)
            risk_lvl = "CRITICAL" if risk.risk_score >= 0.85 else ("HIGH" if risk.risk_score >= 0.70 else ("MEDIUM" if risk.risk_score >= 0.40 else "LOW"))
            cur.execute(
                "MERGE INTO COCO_FACTORY.CORE.PREDICTION target "
                "USING (SELECT %s AS prediction_id, %s AS scored_ts, %s AS machine_id, %s AS failure_prob, "
                "%s AS risk_level, %s AS model_name, %s AS horizon_days) source "
                "ON target.prediction_id = source.prediction_id "
                "WHEN MATCHED THEN UPDATE SET "
                "failure_prob = source.failure_prob, risk_level = source.risk_level "
                "WHEN NOT MATCHED THEN INSERT "
                "(prediction_id, scored_ts, machine_id, failure_prob, risk_level, model_name, horizon_days) "
                "VALUES (source.prediction_id, source.scored_ts, source.machine_id, source.failure_prob, source.risk_level, source.model_name, source.horizon_days)",
                (
                    risk.risk_id,
                    ts_str,
                    risk.machine_id,
                    risk.risk_score,
                    risk_lvl,
                    risk.model_version,
                    max(1, risk.prediction_horizon_hours // 24),
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
                "SELECT prediction_id, machine_id, 'BEARING_DEGRADATION', failure_prob, "
                "horizon_days * 24, model_name, scored_ts, 0.95 "
                "FROM COCO_FACTORY.CORE.PREDICTION WHERE machine_id = %s "
                "ORDER BY scored_ts DESC LIMIT 1",
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
                prediction_horizon_hours=int(r[4]),
                model_version=r[5],
                prediction_timestamp=r[6],
                confidence=float(r[7]),
            )
        finally:
            cur.close()
            conn.close()

    def save_health_assessment(self, assessment: HealthAssessment) -> None:
        """Explicitly reject unsupported direct health assessment write on Snowflake backend.

        Canonical Architectural Contract:
        In COCO_FACTORY, MACHINE_HEALTH_DAILY is an analytics foundation SQL view derived
        from CORE.PREDICTION, CORE.ALERT, and telemetry exceedances. Direct INSERT into
        ANALYTICS.MACHINE_HEALTH_DAILY is physically unsupported by Snowflake views.
        Persistent failure risk is stored via `save_failure_risk` / `save_canonical_prediction` in
        COCO_FACTORY.CORE.PREDICTION.
        """
        raise UnsupportedOperationError(
            "save_health_assessment is unsupported on SnowflakeRepository: "
            "health assessments are derived analytical state computed in "
            "COCO_FACTORY.ANALYTICS.MACHINE_HEALTH_DAILY. Persistent reliability state must be "
            "persisted via save_failure_risk / save_canonical_prediction to COCO_FACTORY.CORE.PREDICTION."
        )

    def get_latest_health_assessment(self, machine_id: str) -> Optional[HealthAssessment]:
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                SELECT 'HA-' || machine_id || '-' || TO_CHAR(metric_date, 'YYYYMMDD'),
                       machine_id,
                       health_status,
                       COALESCE(latest_failure_prob, 0.0),
                       COALESCE(latest_risk_level, 'low'),
                       COALESCE(open_alerts, 0),
                       metric_date
                FROM COCO_FACTORY.ANALYTICS.MACHINE_HEALTH_DAILY
                WHERE machine_id = %s
                ORDER BY metric_date DESC LIMIT 1
                """,
                (machine_id,),
            )
            r = cur.fetchone()
            if not r:
                return None
            assessment_id = r[0]
            m_id = r[1]
            raw_status = str(r[2] or "HEALTHY").strip()
            fail_prob = float(r[3] or 0.0)
            risk_level = str(r[4] or "low").strip()
            open_alerts = int(r[5] or 0)
            metric_dt = r[6]

            if raw_status in HealthStatus._value2member_map_:
                curr_health = HealthStatus(raw_status)
            elif raw_status in ("WARNING", "DEGRADING"):
                curr_health = HealthStatus.DEGRADING
            else:
                curr_health = HealthStatus.HEALTHY

            # Authoritative derived health score bounded [0.0, 100.0]
            if fail_prob > 0.0:
                health_score = round(max(0.0, min(100.0, (1.0 - fail_prob) * 100.0)), 1)
            elif curr_health == HealthStatus.CRITICAL:
                health_score = 15.0
            elif curr_health == HealthStatus.DEGRADING:
                health_score = round(max(0.0, 100.0 - (open_alerts * 15.0)), 1)
            else:
                health_score = 100.0

            if curr_health == HealthStatus.CRITICAL:
                primary_concern = f"Critical condition detected: Failure probability {fail_prob:.2f}, risk level '{risk_level}'"
            elif curr_health == HealthStatus.DEGRADING:
                primary_concern = f"Degradation condition: Open alerts {open_alerts}, failure probability {fail_prob:.2f}"
            else:
                primary_concern = "Nominal operation"

            updated_dt = (
                datetime.combine(metric_dt, datetime.min.time(), tzinfo=timezone.utc)
                if isinstance(metric_dt, date)
                else (metric_dt if isinstance(metric_dt, datetime) else datetime.now(timezone.utc))
            )

            return HealthAssessment(
                assessment_id=assessment_id,
                machine_id=m_id,
                health_status=curr_health,
                health_score=health_score,
                primary_concern=primary_concern,
                updated_at=updated_dt,
            )
        finally:
            cur.close()
            conn.close()

    def save_prediction(self, prediction: MLFailurePrediction) -> None:
        prob = float(prediction.failure_probability)
        if prob >= 0.85:
            risk_lvl = "CRITICAL"
        elif prob >= 0.70:
            risk_lvl = "HIGH"
        elif prob >= 0.40:
            risk_lvl = "MEDIUM"
        else:
            risk_lvl = "LOW"

        if isinstance(prediction.top_contributing_features, dict):
            top_feats_json = json.dumps([
                {"feature": k, "share": float(v)}
                for k, v in prediction.top_contributing_features.items()
            ])
        else:
            top_feats_json = json.dumps(prediction.top_contributing_features)

        horizon_days = max(1, prediction.prediction_horizon_hours // 24)

        cp = CanonicalPrediction(
            prediction_id=prediction.prediction_id,
            scored_ts=prediction.prediction_timestamp,
            machine_id=prediction.machine_id,
            suspected_component_id=prediction.component_id or "",
            model_name=prediction.model_name,
            horizon_days=horizon_days,
            failure_prob=prob,
            risk_level=risk_lvl,
            top_features=top_feats_json,
        )
        self.save_canonical_prediction(cp)

    def get_latest_prediction(self, machine_id: str) -> Optional[MLFailurePrediction]:
        preds = self.list_predictions(machine_id=machine_id, limit=1)
        return preds[0] if preds else None

    def list_predictions(self, machine_id: Optional[str] = None, limit: int = 50) -> List[MLFailurePrediction]:
        cpreds = self.list_canonical_predictions(machine_id=machine_id, limit=limit)
        return [_canonical_to_ml_prediction(cp) for cp in cpreds]

    def save_prediction_outcome(self, outcome: PredictionOutcome) -> None:
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            ts_str = outcome.evaluated_at.isoformat() if hasattr(outcome.evaluated_at, "isoformat") else str(outcome.evaluated_at)
            cur.execute(
                "INSERT INTO COCO_FACTORY.APP.ACTION_OUTCOME "
                "(outcome_id, action_proposal_id, work_order_id, prediction_id, machine_id, "
                "failure_mode, observed_failure_confirmed, downtime_avoided_hours, verification_status, feedback_notes, recorded_at) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    outcome.outcome_id,
                    f"PROP-{outcome.prediction_id}",
                    outcome.verification_id or f"WO-{outcome.prediction_id}",
                    outcome.prediction_id,
                    outcome.machine_id,
                    "BEARING_DEGRADATION",
                    outcome.actual_failure,
                    outcome.lead_time_hours or 0.0,
                    "VERIFIED" if outcome.is_correct else "FAILED",
                    outcome.notes,
                    ts_str,
                ),
            )
            conn.commit()
        finally:
            cur.close()
            conn.close()

    def get_prediction_outcome(self, prediction_id: str) -> Optional[PredictionOutcome]:
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT outcome_id, prediction_id, machine_id, TRUE, observed_failure_confirmed, "
                "168, downtime_avoided_hours, work_order_id, recorded_at, "
                "CASE WHEN observed_failure_confirmed THEN TRUE ELSE FALSE END, feedback_notes "
                "FROM COCO_FACTORY.APP.ACTION_OUTCOME WHERE prediction_id = %s",
                (prediction_id,),
            )
            r = cur.fetchone()
            if not r:
                return None
            return PredictionOutcome(
                outcome_id=r[0],
                prediction_id=r[1],
                machine_id=r[2],
                predicted_failure=bool(r[3]),
                actual_failure=bool(r[4]),
                prediction_horizon_hours=int(r[5]),
                lead_time_hours=float(r[6]) if r[6] is not None else None,
                verification_id=r[7],
                evaluated_at=r[8],
                is_correct=bool(r[9]),
                notes=r[10],
            )
        finally:
            cur.close()
            conn.close()

    def list_prediction_outcomes(self, machine_id: Optional[str] = None) -> List[PredictionOutcome]:
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            sql = (
                "SELECT outcome_id, prediction_id, machine_id, TRUE, observed_failure_confirmed, "
                "168, downtime_avoided_hours, work_order_id, recorded_at, "
                "CASE WHEN observed_failure_confirmed THEN TRUE ELSE FALSE END, feedback_notes "
                "FROM COCO_FACTORY.APP.ACTION_OUTCOME WHERE 1=1 "
            )
            params: list = []
            if machine_id:
                sql += "AND machine_id = %s "
                params.append(machine_id)
            sql += "ORDER BY recorded_at DESC"
            cur.execute(sql, tuple(params))
            rows = cur.fetchall()
            return [
                PredictionOutcome(
                    outcome_id=r[0],
                    prediction_id=r[1],
                    machine_id=r[2],
                    predicted_failure=bool(r[3]),
                    actual_failure=bool(r[4]),
                    prediction_horizon_hours=int(r[5]),
                    lead_time_hours=float(r[6]) if r[6] is not None else None,
                    verification_id=r[7],
                    evaluated_at=r[8],
                    is_correct=bool(r[9]),
                    notes=r[10],
                )
                for r in rows
            ]
        finally:
            cur.close()
            conn.close()

    # InvestigationRepository
    def create_alert(self, alert: Alert) -> Alert:
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            ts_str = alert.created_at.isoformat() if hasattr(alert.created_at, "isoformat") else str(alert.created_at)
            cur.execute(
                "INSERT INTO COCO_FACTORY.CORE.ALERT "
                "(alert_id, machine_id, component_id, severity, status, message, priority_score, alert_type, ts) "
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
                    ts_str,
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
                "SELECT alert_id, machine_id, component_id, severity, status, "
                "COALESCE(message, alert_type), COALESCE(priority_score, 0.5), "
                "COALESCE(alert_type, 'BEARING_DEGRADATION'), ts, acknowledged_ts, closed_ts "
                "FROM COCO_FACTORY.CORE.ALERT WHERE alert_id = %s",
                (alert_id,),
            )
            r = cur.fetchone()
            if not r:
                return None
            return Alert(
                alert_id=r[0],
                machine_id=r[1],
                component_id=r[2],
                severity=map_alert_severity(r[3]),
                status=map_alert_status(r[4]),
                trigger_reason=r[5],
                risk_score=float(r[6]),
                failure_mode=FailureMode(r[7]) if r[7] in FailureMode._value2member_map_ else FailureMode.BEARING_DEGRADATION,
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
                "SELECT alert_id, machine_id, component_id, severity, status, "
                "COALESCE(message, alert_type), COALESCE(priority_score, 0.5), "
                "COALESCE(alert_type, 'BEARING_DEGRADATION'), ts, acknowledged_ts, closed_ts "
                "FROM COCO_FACTORY.CORE.ALERT WHERE 1=1 "
            )
            params: list = []
            if machine_id:
                sql += "AND machine_id = %s "
                params.append(machine_id)
            if status:
                if status == AlertStatus.OPEN:
                    sql += "AND LOWER(status) = 'open' "
                elif status == AlertStatus.RESOLVED:
                    sql += "AND LOWER(status) IN ('closed', 'resolved') "
                elif status == AlertStatus.INVESTIGATING:
                    sql += "AND LOWER(status) IN ('acknowledged', 'investigating') "
                elif status == AlertStatus.ACTION_PROPOSED:
                    sql += "AND LOWER(status) = 'action_proposed' "
                elif status == AlertStatus.DISMISSED:
                    sql += "AND LOWER(status) = 'dismissed' "
                else:
                    sql += "AND (status = %s OR LOWER(status) = %s) "
                    params.extend([status.value, status.value.lower()])
            sql += "ORDER BY ts DESC"
            cur.execute(sql, tuple(params) if params else None)
            rows = cur.fetchall()
            return [
                Alert(
                    alert_id=r[0],
                    machine_id=r[1],
                    component_id=r[2],
                    severity=map_alert_severity(r[3]),
                    status=map_alert_status(r[4]),
                    trigger_reason=r[5],
                    risk_score=float(r[6]),
                    failure_mode=FailureMode(r[7]) if r[7] in FailureMode._value2member_map_ else FailureMode.BEARING_DEGRADATION,
                    created_at=r[8],
                    acknowledged_at=r[9],
                    resolved_at=r[10],
                )
                for r in rows
            ]
        finally:
            cur.close()
            conn.close()

    def _merge_investigation_record(self, cur: Any, investigation: Investigation) -> None:
        trig_type = investigation.trigger_type.value if hasattr(investigation.trigger_type, "value") else str(investigation.trigger_type or "PREDICTION")
        status_val = investigation.status.value if hasattr(investigation.status, "value") else str(investigation.status or "COMPLETED")
        fmode_val = investigation.failure_mode.value if hasattr(investigation.failure_mode, "value") else str(investigation.failure_mode or "BEARING_DEGRADATION")
        start_ts = investigation.started_at.isoformat() if investigation.started_at else None
        comp_ts = investigation.completed_at.isoformat() if investigation.completed_at else None
        created_ts = investigation.created_at.isoformat() if hasattr(investigation.created_at, "isoformat") else str(investigation.created_at)

        limitations_json = json.dumps(investigation.limitations) if investigation.limitations else None
        provenance_json = json.dumps(investigation.provenance) if investigation.provenance else None

        cur.execute(
            """
            MERGE INTO COCO_FACTORY.APP.INVESTIGATION target
            USING (SELECT %s AS investigation_id) src
            ON target.investigation_id = src.investigation_id
            WHEN MATCHED THEN UPDATE SET
                trigger_type = %s,
                trigger_id = %s,
                prediction_id = %s,
                alert_id = %s,
                machine_id = %s,
                component_id = %s,
                scope = %s,
                status = %s,
                failure_mode = %s,
                confidence = %s,
                summary = %s,
                limitations = TRY_PARSE_JSON(%s),
                provenance = TRY_PARSE_JSON(%s),
                started_at = %s,
                completed_at = %s
            WHEN NOT MATCHED THEN INSERT (
                investigation_id, trigger_type, trigger_id, prediction_id, alert_id,
                machine_id, component_id, scope, status, failure_mode, confidence,
                summary, limitations, provenance, started_at, completed_at, created_at
            ) VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s,
                %s, TRY_PARSE_JSON(%s), TRY_PARSE_JSON(%s), %s, %s, %s
            )
            """,
            (
                investigation.investigation_id,
                trig_type,
                investigation.trigger_id or investigation.prediction_id,
                investigation.prediction_id,
                investigation.alert_id,
                investigation.machine_id,
                investigation.component_id,
                investigation.scope or "EQUIPMENT_RELIABILITY",
                status_val,
                fmode_val,
                investigation.confidence,
                investigation.summary,
                limitations_json,
                provenance_json,
                start_ts,
                comp_ts,
                # INSERT bindings
                investigation.investigation_id,
                trig_type,
                investigation.trigger_id or investigation.prediction_id,
                investigation.prediction_id,
                investigation.alert_id,
                investigation.machine_id,
                investigation.component_id,
                investigation.scope or "EQUIPMENT_RELIABILITY",
                status_val,
                fmode_val,
                investigation.confidence,
                investigation.summary,
                limitations_json,
                provenance_json,
                start_ts,
                comp_ts,
                created_ts,
            ),
        )

    def _merge_evidence_records(self, cur: Any, evidence: List[Evidence]) -> None:
        for ev in evidence:
            coll_ts = ev.timestamp.isoformat() if hasattr(ev.timestamp, "isoformat") else str(ev.timestamp) if ev.timestamp else None
            obs_str = str(ev.observed_value)[:512] if ev.observed_value is not None else None
            claim_str = ev.claim[:2048] if ev.claim else None
            summary_str = ev.summary[:2048] if ev.summary else None
            src_ref = ev.source_reference[:256] if ev.source_reference else None
            cur.execute(
                """
                MERGE INTO COCO_FACTORY.APP.INVESTIGATION_EVIDENCE target
                USING (SELECT %s AS evidence_id) src
                ON target.evidence_id = src.evidence_id
                WHEN MATCHED THEN UPDATE SET
                    investigation_id = %s,
                    evidence_type = %s,
                    category = %s,
                    source = %s,
                    source_type = %s,
                    source_id = %s,
                    metric = %s,
                    observed_value = %s,
                    unit = %s,
                    severity = %s,
                    relationship = %s,
                    machine_id = %s,
                    component_id = %s,
                    claim = %s,
                    summary = %s,
                    source_reference = %s,
                    collected_at = %s
                WHEN NOT MATCHED THEN INSERT (
                    evidence_id, investigation_id, evidence_type, category, source,
                    source_type, source_id, metric, observed_value, unit, severity,
                    relationship, machine_id, component_id, claim, summary, source_reference, collected_at
                ) VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s
                )
                """,
                (
                    ev.evidence_id,
                    ev.investigation_id,
                    ev.evidence_type,
                    ev.category or ev.evidence_type or "TELEMETRY",
                    ev.source,
                    ev.source_type,
                    ev.source_id,
                    ev.metric,
                    obs_str,
                    ev.unit,
                    ev.severity,
                    ev.relationship or "SUPPORTS",
                    ev.machine_id,
                    ev.component_id,
                    claim_str,
                    summary_str,
                    src_ref,
                    coll_ts,
                    # INSERT bindings
                    ev.evidence_id,
                    ev.investigation_id,
                    ev.evidence_type,
                    ev.category or ev.evidence_type or "TELEMETRY",
                    ev.source,
                    ev.source_type,
                    ev.source_id,
                    ev.metric,
                    obs_str,
                    ev.unit,
                    ev.severity,
                    ev.relationship or "SUPPORTS",
                    ev.machine_id,
                    ev.component_id,
                    claim_str,
                    summary_str,
                    src_ref,
                    coll_ts,
                ),
            )

    def _merge_hypothesis_records(self, cur: Any, hypotheses: List[Hypothesis]) -> None:
        for hyp in hypotheses:
            fmode = hyp.failure_mode.value if hasattr(hyp.failure_mode, "value") else str(hyp.failure_mode or "BEARING_DEGRADATION")
            supp_json = json.dumps(hyp.supporting_evidence_ids) if hyp.supporting_evidence_ids else None
            contra_json = json.dumps(hyp.contradicting_evidence_ids) if hyp.contradicting_evidence_ids else None
            cur.execute(
                """
                MERGE INTO COCO_FACTORY.APP.INVESTIGATION_HYPOTHESIS target
                USING (SELECT %s AS hypothesis_id) src
                ON target.hypothesis_id = src.hypothesis_id
                WHEN MATCHED THEN UPDATE SET
                    investigation_id = %s,
                    hypothesis_name = %s,
                    statement = %s,
                    failure_mode = %s,
                    confidence = %s,
                    status = %s,
                    rationale = %s,
                    supporting_evidence_ids = TRY_PARSE_JSON(%s),
                    contradicting_evidence_ids = TRY_PARSE_JSON(%s)
                WHEN NOT MATCHED THEN INSERT (
                    hypothesis_id, investigation_id, hypothesis_name, statement,
                    failure_mode, confidence, status, rationale,
                    supporting_evidence_ids, contradicting_evidence_ids
                ) VALUES (
                    %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    TRY_PARSE_JSON(%s), TRY_PARSE_JSON(%s)
                )
                """,
                (
                    hyp.hypothesis_id,
                    hyp.investigation_id,
                    hyp.hypothesis_name[:256] if hyp.hypothesis_name else "Hypothesis",
                    hyp.statement[:2048] if hyp.statement else None,
                    fmode,
                    hyp.confidence,
                    str(hyp.status or "EVALUATED"),
                    hyp.rationale[:2048] if hyp.rationale else None,
                    supp_json,
                    contra_json,
                    # INSERT bindings
                    hyp.hypothesis_id,
                    hyp.investigation_id,
                    hyp.hypothesis_name[:256] if hyp.hypothesis_name else "Hypothesis",
                    hyp.statement[:2048] if hyp.statement else None,
                    fmode,
                    hyp.confidence,
                    str(hyp.status or "EVALUATED"),
                    hyp.rationale[:2048] if hyp.rationale else None,
                    supp_json,
                    contra_json,
                ),
            )

    def _merge_finding_records(self, cur: Any, findings: List[Finding]) -> None:
        for f in findings:
            fmode = f.failure_mode.value if hasattr(f.failure_mode, "value") else str(f.failure_mode or "BEARING_DEGRADATION")
            ev_refs_list = f.evidence_refs or f.supporting_evidence_ids
            ev_refs_json = json.dumps(ev_refs_list) if ev_refs_list else None
            obs_json = json.dumps(f.observed_facts) if f.observed_facts else None
            inf_json = json.dumps(f.inferences) if f.inferences else None
            cur.execute(
                """
                MERGE INTO COCO_FACTORY.APP.INVESTIGATION_FINDING target
                USING (SELECT %s AS finding_id) src
                ON target.finding_id = src.finding_id
                WHEN MATCHED THEN UPDATE SET
                    investigation_id = %s,
                    summary = %s,
                    statement = %s,
                    failure_mode = %s,
                    confidence = %s,
                    evidence_refs = TRY_PARSE_JSON(%s),
                    observed_facts = TRY_PARSE_JSON(%s),
                    inferences = TRY_PARSE_JSON(%s)
                WHEN NOT MATCHED THEN INSERT (
                    finding_id, investigation_id, summary, statement,
                    failure_mode, confidence, evidence_refs, observed_facts, inferences
                ) VALUES (
                    %s, %s, %s, %s,
                    %s, %s, TRY_PARSE_JSON(%s), TRY_PARSE_JSON(%s), TRY_PARSE_JSON(%s)
                )
                """,
                (
                    f.finding_id,
                    f.investigation_id,
                    f.summary[:2048] if f.summary else "Finding summary",
                    f.statement[:2048] if f.statement else None,
                    fmode,
                    f.confidence,
                    ev_refs_json,
                    obs_json,
                    inf_json,
                    # INSERT bindings
                    f.finding_id,
                    f.investigation_id,
                    f.summary[:2048] if f.summary else "Finding summary",
                    f.statement[:2048] if f.statement else None,
                    fmode,
                    f.confidence,
                    ev_refs_json,
                    obs_json,
                    inf_json,
                ),
            )

    def _merge_recommendation_records(self, cur: Any, recommendations: List[Recommendation]) -> None:
        for r in recommendations:
            prio = r.priority.value if hasattr(r.priority, "value") else str(r.priority or "HIGH")
            ev_refs_list = r.evidence_refs or r.evidence_ids
            ev_refs_json = json.dumps(ev_refs_list) if ev_refs_list else None
            parts_json = json.dumps(r.suggested_parts) if r.suggested_parts else None
            check_json = json.dumps(r.suggested_checklist) if r.suggested_checklist else None
            cur.execute(
                """
                MERGE INTO COCO_FACTORY.APP.INVESTIGATION_RECOMMENDATION target
                USING (SELECT %s AS recommendation_id) src
                ON target.recommendation_id = src.recommendation_id
                WHEN MATCHED THEN UPDATE SET
                    investigation_id = %s,
                    title = %s,
                    statement = %s,
                    action_type = %s,
                    priority = %s,
                    rationale = %s,
                    suggested_next_step = %s,
                    action_required = %s,
                    status = %s,
                    estimated_downtime_hours = %s,
                    suggested_parts = TRY_PARSE_JSON(%s),
                    suggested_checklist = TRY_PARSE_JSON(%s),
                    evidence_refs = TRY_PARSE_JSON(%s)
                WHEN NOT MATCHED THEN INSERT (
                    recommendation_id, investigation_id, title, statement, action_type,
                    priority, rationale, suggested_next_step, action_required, status,
                    estimated_downtime_hours, suggested_parts, suggested_checklist, evidence_refs
                ) VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s,
                    %s, TRY_PARSE_JSON(%s), TRY_PARSE_JSON(%s), TRY_PARSE_JSON(%s)
                )
                """,
                (
                    r.recommendation_id,
                    r.investigation_id,
                    r.title[:256] if r.title else "Recommendation",
                    r.statement[:2048] if r.statement else None,
                    str(r.action_type or "INSPECT_BEARING_ASSEMBLY")[:64],
                    prio,
                    r.rationale[:2048] if r.rationale else None,
                    r.suggested_next_step[:1024] if r.suggested_next_step else None,
                    bool(r.action_required),
                    str(r.status or "ADVISORY")[:32],
                    float(r.estimated_downtime_hours or 0.0),
                    parts_json,
                    check_json,
                    ev_refs_json,
                    # INSERT bindings
                    r.recommendation_id,
                    r.investigation_id,
                    r.title[:256] if r.title else "Recommendation",
                    r.statement[:2048] if r.statement else None,
                    str(r.action_type or "INSPECT_BEARING_ASSEMBLY")[:64],
                    prio,
                    r.rationale[:2048] if r.rationale else None,
                    r.suggested_next_step[:1024] if r.suggested_next_step else None,
                    bool(r.action_required),
                    str(r.status or "ADVISORY")[:32],
                    float(r.estimated_downtime_hours or 0.0),
                    parts_json,
                    check_json,
                    ev_refs_json,
                ),
            )

    def _merge_tool_call_records(self, cur: Any, tool_calls: List[ToolCall], investigation_id: Optional[str] = None) -> None:
        for tc in tool_calls:
            inv_id = investigation_id or tc.execution_id or "ADHOC"
            params_str = json.dumps(tc.arguments)[:4096] if tc.arguments else None
            err_str = tc.error_message[:2048] if tc.error_message else None
            call_ts = tc.started_at.isoformat() if hasattr(tc.started_at, "isoformat") else str(tc.started_at) if tc.started_at else None
            rec_count = 0
            if tc.result and isinstance(tc.result, dict):
                if "record_count" in tc.result:
                    rec_count = int(tc.result["record_count"])
                elif "data" in tc.result and isinstance(tc.result["data"], list):
                    rec_count = len(tc.result["data"])
            elif tc.result and isinstance(tc.result, (list, tuple)):
                rec_count = len(tc.result)
            cur.execute(
                """
                MERGE INTO COCO_FACTORY.APP.INVESTIGATION_TOOL_CALL target
                USING (SELECT %s AS call_id) src
                ON target.call_id = src.call_id
                WHEN MATCHED THEN UPDATE SET
                    investigation_id = %s,
                    tool_name = %s,
                    tool_mode = 'READ',
                    scope = %s,
                    parameters = %s,
                    record_count = %s,
                    duration_ms = %s,
                    success = %s,
                    error_message = %s,
                    called_at = %s
                WHEN NOT MATCHED THEN INSERT (
                    call_id, investigation_id, tool_name, tool_mode, scope,
                    parameters, record_count, duration_ms, success, error_message, called_at
                ) VALUES (
                    %s, %s, %s, 'READ', %s,
                    %s, %s, %s, %s, %s, %s
                )
                """,
                (
                    tc.tool_call_id,
                    inv_id,
                    tc.tool_name[:64],
                    "investigation:read",
                    params_str,
                    rec_count,
                    float(tc.duration_ms or 0.0),
                    bool(tc.is_success),
                    err_str,
                    call_ts,
                    # INSERT bindings
                    tc.tool_call_id,
                    inv_id,
                    tc.tool_name[:64],
                    "investigation:read",
                    params_str,
                    rec_count,
                    float(tc.duration_ms or 0.0),
                    bool(tc.is_success),
                    err_str,
                    call_ts,
                ),
            )

    def create_investigation(self, investigation: Investigation) -> Investigation:
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            self._merge_investigation_record(cur, investigation)
            if investigation.evidence:
                self._merge_evidence_records(cur, investigation.evidence)
            if investigation.hypotheses:
                self._merge_hypothesis_records(cur, investigation.hypotheses)
            if investigation.findings:
                self._merge_finding_records(cur, investigation.findings)
            elif investigation.finding:
                self._merge_finding_records(cur, [investigation.finding])
            if investigation.recommendations:
                self._merge_recommendation_records(cur, investigation.recommendations)
            elif investigation.recommendation:
                self._merge_recommendation_records(cur, [investigation.recommendation])
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
                """
                SELECT investigation_id, trigger_type, trigger_id, prediction_id, alert_id,
                       machine_id, component_id, scope, status, failure_mode, confidence,
                       summary, limitations, provenance, started_at, completed_at, created_at
                FROM COCO_FACTORY.APP.INVESTIGATION
                WHERE investigation_id = %s
                """,
                (investigation_id,),
            )
            r = cur.fetchone()
            if not r:
                return None

            from domain.enums import InvestigationStatus, TriggerType, FailureMode

            limitations = []
            if r[12]:
                if isinstance(r[12], list):
                    limitations = r[12]
                elif isinstance(r[12], str):
                    try:
                        parsed = json.loads(r[12])
                        limitations = parsed if isinstance(parsed, list) else [parsed]
                    except Exception:
                        limitations = [r[12]]

            provenance = {}
            if r[13]:
                if isinstance(r[13], dict):
                    provenance = r[13]
                elif isinstance(r[13], str):
                    try:
                        parsed = json.loads(r[13])
                        provenance = parsed if isinstance(parsed, dict) else {"raw": parsed}
                    except Exception:
                        provenance = {"raw": r[13]}

            trig_type = TriggerType(r[1]) if r[1] in TriggerType._value2member_map_ else TriggerType.PREDICTION
            status_val = InvestigationStatus(r[8]) if r[8] in InvestigationStatus._value2member_map_ else InvestigationStatus.COMPLETED
            fmode_val = FailureMode(r[9]) if r[9] in FailureMode._value2member_map_ else FailureMode.BEARING_DEGRADATION

            inv = Investigation(
                investigation_id=r[0],
                trigger_type=trig_type,
                trigger_id=r[2],
                prediction_id=r[3],
                alert_id=r[4],
                machine_id=r[5],
                component_id=r[6],
                scope=r[7],
                status=status_val,
                failure_mode=fmode_val,
                confidence=float(r[10]) if r[10] is not None else 0.88,
                summary=r[11],
                limitations=limitations,
                provenance=provenance,
                started_at=r[14],
                completed_at=r[15],
                created_at=r[16],
            )
            return inv
        finally:
            cur.close()
            conn.close()

    def save_evidence(self, evidence: List[Evidence]) -> None:
        if not evidence:
            return
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            self._merge_evidence_records(cur, evidence)
            conn.commit()
        finally:
            cur.close()
            conn.close()

    def get_evidence(self, investigation_id: str) -> List[Evidence]:
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                SELECT evidence_id, investigation_id, evidence_type, category, source,
                       source_type, source_id, metric, observed_value, unit, severity,
                       relationship, machine_id, component_id, claim, summary, source_reference, collected_at
                FROM COCO_FACTORY.APP.INVESTIGATION_EVIDENCE
                WHERE investigation_id = %s
                ORDER BY collected_at
                """,
                (investigation_id,),
            )
            rows = cur.fetchall()
            return [
                Evidence(
                    evidence_id=r[0],
                    investigation_id=r[1],
                    evidence_type=r[2] or "TELEMETRY",
                    category=r[3],
                    source=r[4] or "",
                    source_type=r[5],
                    source_id=r[6],
                    metric=r[7] or "",
                    observed_value=r[8],
                    unit=r[9],
                    severity=r[10],
                    relationship=r[11] or "SUPPORTS",
                    machine_id=r[12],
                    component_id=r[13],
                    claim=r[14],
                    summary=r[15] or "",
                    source_reference=r[16],
                    timestamp=r[17],
                )
                for r in rows
            ]
        finally:
            cur.close()
            conn.close()

    def save_hypotheses(self, hypotheses: List[Hypothesis]) -> None:
        if not hypotheses:
            return
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            self._merge_hypothesis_records(cur, hypotheses)
            conn.commit()
        finally:
            cur.close()
            conn.close()

    def get_hypotheses(self, investigation_id: str) -> List[Hypothesis]:
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                SELECT hypothesis_id, investigation_id, hypothesis_name, statement,
                       failure_mode, confidence, status, rationale,
                       supporting_evidence_ids, contradicting_evidence_ids, created_at
                FROM COCO_FACTORY.APP.INVESTIGATION_HYPOTHESIS
                WHERE investigation_id = %s
                ORDER BY created_at
                """,
                (investigation_id,),
            )
            rows = cur.fetchall()
            from domain.enums import FailureMode
            items = []
            for r in rows:
                supp = r[8] if isinstance(r[8], list) else (json.loads(r[8]) if isinstance(r[8], str) else [])
                contra = r[9] if isinstance(r[9], list) else (json.loads(r[9]) if isinstance(r[9], str) else [])
                fmode = FailureMode(r[4]) if r[4] in FailureMode._value2member_map_ else FailureMode.BEARING_DEGRADATION
                items.append(
                    Hypothesis(
                        hypothesis_id=r[0],
                        investigation_id=r[1],
                        hypothesis_name=r[2],
                        statement=r[3],
                        failure_mode=fmode,
                        confidence=float(r[5]) if r[5] is not None else 0.8,
                        status=r[6] or "EVALUATED",
                        rationale=r[7] or "",
                        supporting_evidence_ids=supp,
                        contradicting_evidence_ids=contra,
                    )
                )
            return items
        finally:
            cur.close()
            conn.close()

    def save_findings(self, findings: List[Finding]) -> None:
        if not findings:
            return
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            self._merge_finding_records(cur, findings)
            conn.commit()
        finally:
            cur.close()
            conn.close()

    def get_findings(self, investigation_id: str) -> List[Finding]:
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                SELECT finding_id, investigation_id, summary, statement,
                       failure_mode, confidence, evidence_refs, observed_facts, inferences, created_at
                FROM COCO_FACTORY.APP.INVESTIGATION_FINDING
                WHERE investigation_id = %s
                ORDER BY created_at
                """,
                (investigation_id,),
            )
            rows = cur.fetchall()
            from domain.enums import FailureMode
            items = []
            for r in rows:
                ev_refs = r[6] if isinstance(r[6], list) else (json.loads(r[6]) if isinstance(r[6], str) else [])
                obs = r[7] if isinstance(r[7], list) else (json.loads(r[7]) if isinstance(r[7], str) else [])
                inf = r[8] if isinstance(r[8], list) else (json.loads(r[8]) if isinstance(r[8], str) else [])
                fmode = FailureMode(r[4]) if r[4] in FailureMode._value2member_map_ else FailureMode.BEARING_DEGRADATION
                items.append(
                    Finding(
                        finding_id=r[0],
                        investigation_id=r[1],
                        summary=r[2],
                        statement=r[3],
                        failure_mode=fmode,
                        confidence=float(r[5]) if r[5] is not None else 0.85,
                        evidence_refs=ev_refs,
                        observed_facts=obs,
                        inferences=inf,
                        created_at=r[9],
                    )
                )
            return items
        finally:
            cur.close()
            conn.close()

    def save_recommendations(self, recommendations: List[Recommendation]) -> None:
        if not recommendations:
            return
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            self._merge_recommendation_records(cur, recommendations)
            conn.commit()
        finally:
            cur.close()
            conn.close()

    def get_recommendations(self, investigation_id: str) -> List[Recommendation]:
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                SELECT recommendation_id, investigation_id, title, statement, action_type,
                       priority, rationale, suggested_next_step, action_required, status,
                       estimated_downtime_hours, suggested_parts, suggested_checklist, evidence_refs, created_at
                FROM COCO_FACTORY.APP.INVESTIGATION_RECOMMENDATION
                WHERE investigation_id = %s
                ORDER BY created_at
                """,
                (investigation_id,),
            )
            rows = cur.fetchall()
            from domain.enums import Priority
            items = []
            for r in rows:
                prio = Priority(r[5]) if r[5] in Priority._value2member_map_ else Priority.HIGH
                parts = r[11] if isinstance(r[11], list) else (json.loads(r[11]) if isinstance(r[11], str) else [])
                checklist = r[12] if isinstance(r[12], list) else (json.loads(r[12]) if isinstance(r[12], str) else [])
                ev_refs = r[13] if isinstance(r[13], list) else (json.loads(r[13]) if isinstance(r[13], str) else [])
                items.append(
                    Recommendation(
                        recommendation_id=r[0],
                        investigation_id=r[1],
                        title=r[2],
                        statement=r[3],
                        action_type=r[4] or "INSPECT_BEARING_ASSEMBLY",
                        priority=prio,
                        rationale=r[6] or "",
                        suggested_next_step=r[7],
                        action_required=bool(r[8]),
                        status=r[9] or "ADVISORY",
                        estimated_downtime_hours=float(r[10]) if r[10] is not None else 0.0,
                        suggested_parts=parts,
                        suggested_checklist=checklist,
                        evidence_refs=ev_refs,
                    )
                )
            return items
        finally:
            cur.close()
            conn.close()

    def save_tool_calls(self, tool_calls: List[ToolCall], investigation_id: Optional[str] = None) -> None:
        if not tool_calls:
            return
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            self._merge_tool_call_records(cur, tool_calls, investigation_id=investigation_id)
            conn.commit()
        finally:
            cur.close()
            conn.close()

    def get_tool_calls(self, investigation_id: str) -> List[ToolCall]:
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                SELECT call_id, investigation_id, tool_name, tool_mode, scope,
                       parameters, record_count, duration_ms, success, error_message, called_at
                FROM COCO_FACTORY.APP.INVESTIGATION_TOOL_CALL
                WHERE investigation_id = %s
                ORDER BY called_at
                """,
                (investigation_id,),
            )
            rows = cur.fetchall()
            items = []
            for r in rows:
                args = json.loads(r[5]) if r[5] and isinstance(r[5], str) else (r[5] if isinstance(r[5], dict) else {})
                items.append(
                    ToolCall(
                        tool_call_id=r[0],
                        execution_id=r[1],
                        tool_name=r[2],
                        arguments=args,
                        duration_ms=float(r[7]) if r[7] is not None else 0.0,
                        is_success=bool(r[8]),
                        error_message=r[9],
                        started_at=r[10],
                    )
                )
            return items
        finally:
            cur.close()
            conn.close()

    def save_investigation_bundle(
        self,
        investigation: Investigation,
        evidence: Optional[List[Evidence]] = None,
        hypotheses: Optional[List[Hypothesis]] = None,
        findings: Optional[List[Finding]] = None,
        recommendations: Optional[List[Recommendation]] = None,
        tool_calls: Optional[List[ToolCall]] = None,
    ) -> Investigation:
        """Atomically persist a complete investigation and its child records inside a single Snowflake transaction."""
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            cur.execute("BEGIN")
            self._merge_investigation_record(cur, investigation)
            if evidence:
                self._merge_evidence_records(cur, evidence)
            if hypotheses:
                self._merge_hypothesis_records(cur, hypotheses)
            if findings:
                self._merge_finding_records(cur, findings)
            if recommendations:
                self._merge_recommendation_records(cur, recommendations)
            if tool_calls:
                self._merge_tool_call_records(cur, tool_calls, investigation_id=investigation.investigation_id)
            cur.execute("COMMIT")
            conn.commit()
            return investigation
        except Exception:
            try:
                cur.execute("ROLLBACK")
                conn.rollback()
            except Exception:
                pass
            raise
        finally:
            cur.close()
            conn.close()

    def update_investigation(self, investigation: Investigation) -> Investigation:
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            comp_str = investigation.completed_at.isoformat() if investigation.completed_at and hasattr(investigation.completed_at, "isoformat") else str(investigation.completed_at) if investigation.completed_at else None
            status_val = investigation.status.value if hasattr(investigation.status, "value") else str(investigation.status)
            cur.execute(
                "UPDATE COCO_FACTORY.APP.INVESTIGATION "
                "SET status = %s, confidence = %s, summary = %s, completed_at = %s WHERE investigation_id = %s",
                (
                    status_val,
                    investigation.confidence,
                    investigation.summary,
                    comp_str,
                    investigation.investigation_id,
                ),
            )
            conn.commit()
            return investigation
        finally:
            cur.close()
            conn.close()

    def list_investigations(self, machine_id: Optional[str] = None) -> List[Investigation]:
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            from domain.enums import InvestigationStatus
            sql = (
                "SELECT investigation_id, alert_id, machine_id, status, failure_mode, confidence, created_at, completed_at "
                "FROM COCO_FACTORY.APP.INVESTIGATION WHERE 1=1 "
            )
            params: list = []
            if machine_id:
                sql += "AND machine_id = %s "
                params.append(machine_id)
            sql += "ORDER BY created_at DESC"
            cur.execute(sql, tuple(params))
            rows = cur.fetchall()
            return [
                Investigation(
                    investigation_id=r[0],
                    alert_id=r[1] or "",
                    machine_id=r[2],
                    status=InvestigationStatus(r[3]) if r[3] in InvestigationStatus._value2member_map_ else InvestigationStatus.IN_PROGRESS,
                    failure_mode=FailureMode(r[4]) if r[4] in FailureMode._value2member_map_ else FailureMode.BEARING_DEGRADATION,
                    confidence=float(r[5] or 0.9),
                    created_at=r[6],
                    completed_at=r[7],
                )
                for r in rows
            ]
        finally:
            cur.close()
            conn.close()

    def get_investigation_by_alert(self, alert_id: str) -> Optional[Investigation]:
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            from domain.enums import InvestigationStatus
            cur.execute(
                "SELECT investigation_id, alert_id, machine_id, status, failure_mode, confidence, created_at, completed_at "
                "FROM COCO_FACTORY.APP.INVESTIGATION WHERE alert_id = %s ORDER BY created_at DESC",
                (alert_id,),
            )
            r = cur.fetchone()
            if not r:
                return None
            return Investigation(
                investigation_id=r[0],
                alert_id=r[1] or "",
                machine_id=r[2],
                status=InvestigationStatus(r[3]) if r[3] in InvestigationStatus._value2member_map_ else InvestigationStatus.IN_PROGRESS,
                failure_mode=FailureMode(r[4]) if r[4] in FailureMode._value2member_map_ else FailureMode.BEARING_DEGRADATION,
                confidence=float(r[5] or 0.9),
                created_at=r[6],
                completed_at=r[7],
            )
        finally:
            cur.close()
            conn.close()

    # GovernanceRepository
    def create_approval(self, approval: Approval) -> Approval:
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            ts_str = approval.created_at.isoformat() if hasattr(approval.created_at, "isoformat") else str(approval.created_at)
            cur.execute(
                "INSERT INTO COCO_FACTORY.APP.ACTION_APPROVAL "
                "(approval_id, action_proposal_id, investigation_id, machine_id, requested_action, status, requested_by, created_at) "
                "VALUES (%s, %s, %s, %s, 'DISPATCH_TECHNICIAN', %s, %s, %s)",
                (
                    approval.approval_id,
                    approval.action_id,
                    approval.investigation_id,
                    approval.machine_id,
                    approval.status.value,
                    approval.requested_by,
                    ts_str,
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
                "SELECT approval_id, COALESCE(action_proposal_id, '') AS action_id, investigation_id, "
                "machine_id, status, requested_by, decision_by, decision_at, decision_reason, created_at "
                "FROM COCO_FACTORY.APP.ACTION_APPROVAL WHERE approval_id = %s",
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
                status=ApprovalStatus(r[4]) if r[4] in ApprovalStatus._value2member_map_ else ApprovalStatus.PENDING,
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
                "SELECT approval_id, COALESCE(action_proposal_id, '') AS action_id, investigation_id, "
                "machine_id, status, requested_by, decision_by, decision_at, decision_reason, created_at "
                "FROM COCO_FACTORY.APP.ACTION_APPROVAL WHERE 1=1 "
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
                    status=ApprovalStatus(r[4]) if r[4] in ApprovalStatus._value2member_map_ else ApprovalStatus.PENDING,
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
                "UPDATE COCO_FACTORY.APP.ACTION_APPROVAL "
                "SET status = %s, decision_by = %s, decision_reason = %s, decision_at = CURRENT_TIMESTAMP() "
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
            ts_str = verification.verified_at.isoformat() if hasattr(verification.verified_at, "isoformat") else str(verification.verified_at)
            status_val = verification.verification_status.value if hasattr(verification.verification_status, "value") else str(verification.verification_status)
            cur.execute(
                "INSERT INTO COCO_FACTORY.APP.VERIFICATION_RESULT "
                "(verification_id, investigation_id, work_order_id, machine_id, verified_at, "
                "pre_vibration_rms, post_vibration_rms, pre_temperature_c, post_temperature_c, "
                "pre_risk_score, post_risk_score, risk_delta, is_recovered, status, verification_reason) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    verification.verification_id,
                    verification.investigation_id,
                    verification.work_order_id,
                    verification.machine_id,
                    ts_str,
                    verification.pre_vibration_rms,
                    verification.post_vibration_rms,
                    verification.pre_temperature_c,
                    verification.post_temperature_c,
                    verification.pre_risk_score,
                    verification.post_risk_score,
                    verification.risk_delta,
                    verification.is_recovered,
                    status_val,
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
                "pre_risk_score, post_risk_score, risk_delta, 0.0, 0, 0, "
                "is_recovered, status, 0.0, verification_reason "
                "FROM COCO_FACTORY.APP.VERIFICATION_RESULT WHERE work_order_id = %s",
                (work_order_id,),
            )
            r = cur.fetchone()
            if not r:
                return None
            from domain.enums import VerificationStatus
            return Verification(
                verification_id=r[0],
                investigation_id=r[1],
                work_order_id=r[2],
                machine_id=r[3],
                verified_at=r[4],
                pre_vibration_rms=float(r[5] or 0.0),
                post_vibration_rms=float(r[6] or 0.0),
                pre_temperature_c=float(r[7] or 0.0),
                post_temperature_c=float(r[8] or 0.0),
                pre_risk_score=float(r[9] or 0.0),
                post_risk_score=float(r[10] or 0.0),
                risk_delta=float(r[11] or 0.0),
                oee_delta=float(r[12] or 0.0),
                anomalies_before=int(r[13] or 0),
                anomalies_after=int(r[14] or 0),
                is_recovered=bool(r[15]),
                verification_status=VerificationStatus(r[16]) if r[16] in VerificationStatus._value2member_map_ else VerificationStatus.VERIFIED,
                oee_recovery_pct=float(r[17] or 0.0),
                notes=r[18] or "",
            )
        finally:
            cur.close()
            conn.close()

    def get_verification_by_investigation(self, investigation_id: str) -> Optional[Verification]:
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT verification_id, investigation_id, work_order_id, machine_id, verified_at, "
                "pre_vibration_rms, post_vibration_rms, pre_temperature_c, post_temperature_c, "
                "pre_risk_score, post_risk_score, risk_delta, 0.0, 0, 0, "
                "is_recovered, status, 0.0, verification_reason "
                "FROM COCO_FACTORY.APP.VERIFICATION_RESULT WHERE investigation_id = %s ORDER BY verified_at DESC",
                (investigation_id,),
            )
            r = cur.fetchone()
            if not r:
                return None
            from domain.enums import VerificationStatus
            return Verification(
                verification_id=r[0],
                investigation_id=r[1],
                work_order_id=r[2],
                machine_id=r[3],
                verified_at=r[4],
                pre_vibration_rms=float(r[5] or 0.0),
                post_vibration_rms=float(r[6] or 0.0),
                pre_temperature_c=float(r[7] or 0.0),
                post_temperature_c=float(r[8] or 0.0),
                pre_risk_score=float(r[9] or 0.0),
                post_risk_score=float(r[10] or 0.0),
                risk_delta=float(r[11] or 0.0),
                oee_delta=float(r[12] or 0.0),
                anomalies_before=int(r[13] or 0),
                anomalies_after=int(r[14] or 0),
                is_recovered=bool(r[15]),
                verification_status=VerificationStatus(r[16]) if r[16] in VerificationStatus._value2member_map_ else VerificationStatus.VERIFIED,
                oee_recovery_pct=float(r[17] or 0.0),
                notes=r[18] or "",
            )
        finally:
            cur.close()
            conn.close()

    def list_verifications(self, machine_id: Optional[str] = None) -> List[Verification]:
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            from domain.enums import VerificationStatus
            sql = (
                "SELECT verification_id, investigation_id, work_order_id, machine_id, verified_at, "
                "pre_vibration_rms, post_vibration_rms, pre_temperature_c, post_temperature_c, "
                "pre_risk_score, post_risk_score, risk_delta, 0.0, 0, 0, "
                "is_recovered, status, 0.0, verification_reason "
                "FROM COCO_FACTORY.APP.VERIFICATION_RESULT WHERE 1=1 "
            )
            params: list = []
            if machine_id:
                sql += "AND machine_id = %s "
                params.append(machine_id)
            sql += "ORDER BY verified_at DESC"
            cur.execute(sql, tuple(params))
            rows = cur.fetchall()
            return [
                Verification(
                    verification_id=r[0],
                    investigation_id=r[1],
                    work_order_id=r[2],
                    machine_id=r[3],
                    verified_at=r[4],
                    pre_vibration_rms=float(r[5] or 0.0),
                    post_vibration_rms=float(r[6] or 0.0),
                    pre_temperature_c=float(r[7] or 0.0),
                    post_temperature_c=float(r[8] or 0.0),
                    pre_risk_score=float(r[9] or 0.0),
                    post_risk_score=float(r[10] or 0.0),
                    risk_delta=float(r[11] or 0.0),
                    oee_delta=float(r[12] or 0.0),
                    anomalies_before=int(r[13] or 0),
                    anomalies_after=int(r[14] or 0),
                    is_recovered=bool(r[15]),
                    verification_status=VerificationStatus(r[16]) if r[16] in VerificationStatus._value2member_map_ else VerificationStatus.VERIFIED,
                    oee_recovery_pct=float(r[17] or 0.0),
                    notes=r[18] or "",
                )
                for r in rows
            ]
        finally:
            cur.close()
            conn.close()

    def log_audit(self, event: AuditEvent) -> None:
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT INTO COCO_FACTORY.APP.ACTION_AUDIT "
                "(audit_id, actor, action_type, resource_id, resource_type, timestamp, details, status) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    event.audit_id,
                    event.actor,
                    event.action_type,
                    event.resource_id,
                    event.resource_type,
                    event.timestamp.isoformat() if hasattr(event.timestamp, "isoformat") else str(event.timestamp),
                    json.dumps(event.details),
                    event.status,
                ),
            )
            conn.commit()
        finally:
            cur.close()
            conn.close()

    def list_audit_events(self, limit: int = 50) -> List[AuditEvent]:
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT audit_id, actor, action_type, resource_id, resource_type, timestamp, details, status "
                "FROM COCO_FACTORY.APP.ACTION_AUDIT ORDER BY timestamp DESC LIMIT %s",
                (limit,),
            )
            rows = cur.fetchall()
            res: List[AuditEvent] = []
            for r in rows:
                dt_dict = r[6] if isinstance(r[6], dict) else (json.loads(r[6]) if r[6] else {})
                res.append(
                    AuditEvent(
                        audit_id=r[0],
                        actor=r[1],
                        action_type=r[2],
                        resource_id=r[3],
                        resource_type=r[4],
                        timestamp=r[5],
                        details=dt_dict,
                        status=r[7],
                    )
                )
            return res
        finally:
            cur.close()
            conn.close()

    def save_action_proposal(self, proposal: ActionProposal) -> ActionProposal:
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            import json
            cur.execute(
                """
                MERGE INTO COCO_FACTORY.APP.ACTION_PROPOSAL target
                USING (SELECT %s AS action_proposal_id) src
                ON target.action_proposal_id = src.action_proposal_id
                WHEN MATCHED THEN UPDATE SET
                    status = %s,
                    approval_id = %s,
                    updated_at = CURRENT_TIMESTAMP()
                WHEN NOT MATCHED THEN INSERT
                    (action_proposal_id, investigation_id, recommendation_id, machine_id, component_id,
                     action_type, priority, risk_level, reason, parameters, status, idempotency_key, approval_id, requires_approval)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    proposal.action_proposal_id,
                    proposal.status if isinstance(proposal.status, str) else proposal.status.value,
                    proposal.approval_id,
                    proposal.action_proposal_id,
                    proposal.investigation_id,
                    proposal.recommendation_id,
                    proposal.machine_id,
                    proposal.component_id,
                    proposal.action_type,
                    proposal.priority.value if hasattr(proposal.priority, "value") else str(proposal.priority),
                    proposal.risk_level,
                    proposal.reason,
                    json.dumps(proposal.parameters),
                    proposal.status if isinstance(proposal.status, str) else proposal.status.value,
                    proposal.idempotency_key,
                    proposal.approval_id,
                    proposal.requires_approval,
                ),
            )
            conn.commit()
            return proposal
        finally:
            cur.close()
            conn.close()

    def get_action_proposal(self, action_proposal_id: str) -> Optional[ActionProposal]:
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            import json
            cur.execute(
                """
                SELECT action_proposal_id, investigation_id, recommendation_id, machine_id, component_id,
                       action_type, priority, risk_level, reason, parameters, status, idempotency_key,
                       approval_id, requires_approval, created_at, updated_at
                FROM COCO_FACTORY.APP.ACTION_PROPOSAL WHERE action_proposal_id = %s
                """,
                (action_proposal_id,),
            )
            r = cur.fetchone()
            if not r:
                return None
            params = json.loads(r[9]) if r[9] else {}
            return ActionProposal(
                action_proposal_id=r[0],
                investigation_id=r[1],
                recommendation_id=r[2],
                machine_id=r[3],
                component_id=r[4],
                action_type=r[5],
                priority=Priority(r[6]) if r[6] in ("LOW", "MEDIUM", "HIGH", "CRITICAL") else Priority.HIGH,
                risk_level=r[7],
                reason=r[8],
                parameters=params,
                status=r[10],
                idempotency_key=r[11],
                approval_id=r[12],
                requires_approval=bool(r[13]),
                created_at=r[14],
                updated_at=r[15],
            )
        finally:
            cur.close()
            conn.close()

    def list_action_proposals(
        self, machine_id: Optional[str] = None, status: Optional[str] = None
    ) -> List[ActionProposal]:
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            import json
            query = """
                SELECT action_proposal_id, investigation_id, recommendation_id, machine_id, component_id,
                       action_type, priority, risk_level, reason, parameters, status, idempotency_key,
                       approval_id, requires_approval, created_at, updated_at
                FROM COCO_FACTORY.APP.ACTION_PROPOSAL WHERE 1=1
            """
            params = []
            if machine_id:
                query += " AND machine_id = %s"
                params.append(machine_id)
            if status:
                query += " AND status = %s"
                params.append(status)
            query += " ORDER BY created_at DESC"
            cur.execute(query, tuple(params) if params else None)
            rows = cur.fetchall()
            return [
                ActionProposal(
                    action_proposal_id=r[0],
                    investigation_id=r[1],
                    recommendation_id=r[2],
                    machine_id=r[3],
                    component_id=r[4],
                    action_type=r[5],
                    priority=Priority(r[6]) if r[6] in ("LOW", "MEDIUM", "HIGH", "CRITICAL") else Priority.HIGH,
                    risk_level=r[7],
                    reason=r[8],
                    parameters=json.loads(r[9]) if r[9] else {},
                    status=r[10],
                    idempotency_key=r[11],
                    approval_id=r[12],
                    requires_approval=bool(r[13]),
                    created_at=r[14],
                    updated_at=r[15],
                )
                for r in rows
            ]
        finally:
            cur.close()
            conn.close()

    def update_action_proposal(self, proposal: ActionProposal) -> ActionProposal:
        return self.save_action_proposal(proposal)

    def save_action_execution(self, execution: ActionExecution) -> ActionExecution:
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            import json
            if execution.idempotency_key:
                cur.execute(
                    """
                    SELECT execution_id, action_proposal_id, approval_id, action_type, machine_id, executed_by,
                           status, idempotency_key, result_data, error_message, started_at, completed_at
                    FROM COCO_FACTORY.APP.ACTION_EXECUTION WHERE idempotency_key = %s
                    LIMIT 1
                    """,
                    (execution.idempotency_key,),
                )
                r = cur.fetchone()
                if r:
                    return ActionExecution(
                        execution_id=r[0],
                        action_proposal_id=r[1],
                        approval_id=r[2],
                        action_type=r[3],
                        machine_id=r[4],
                        executed_by=r[5],
                        status=r[6],
                        idempotency_key=r[7],
                        result_data=json.loads(r[8]) if r[8] else {},
                        error_message=r[9],
                        started_at=r[10],
                        completed_at=r[11],
                    )

            cur.execute(
                """
                INSERT INTO COCO_FACTORY.APP.ACTION_EXECUTION
                (execution_id, action_proposal_id, approval_id, action_type, machine_id, executed_by,
                 status, idempotency_key, result_data, error_message, started_at, completed_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    execution.execution_id,
                    execution.action_proposal_id,
                    execution.approval_id,
                    execution.action_type,
                    execution.machine_id,
                    execution.executed_by,
                    execution.status,
                    execution.idempotency_key,
                    json.dumps(execution.result_data),
                    execution.error_message,
                    execution.started_at.isoformat() if execution.started_at else None,
                    execution.completed_at.isoformat() if execution.completed_at else None,
                ),
            )
            conn.commit()
            return execution
        finally:
            cur.close()
            conn.close()

    def get_action_execution(self, execution_id: str) -> Optional[ActionExecution]:
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            import json
            cur.execute(
                """
                SELECT execution_id, action_proposal_id, approval_id, action_type, machine_id, executed_by,
                       status, idempotency_key, result_data, error_message, started_at, completed_at
                FROM COCO_FACTORY.APP.ACTION_EXECUTION WHERE execution_id = %s
                """,
                (execution_id,),
            )
            r = cur.fetchone()
            if not r:
                return None
            return ActionExecution(
                execution_id=r[0],
                action_proposal_id=r[1],
                approval_id=r[2],
                action_type=r[3],
                machine_id=r[4],
                executed_by=r[5],
                status=r[6],
                idempotency_key=r[7],
                result_data=json.loads(r[8]) if r[8] else {},
                error_message=r[9],
                started_at=r[10],
                completed_at=r[11],
            )
        finally:
            cur.close()
            conn.close()

    def list_action_executions(
        self, action_proposal_id: Optional[str] = None
    ) -> List[ActionExecution]:
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            import json
            query = """
                SELECT execution_id, action_proposal_id, approval_id, action_type, machine_id, executed_by,
                       status, idempotency_key, result_data, error_message, started_at, completed_at
                FROM COCO_FACTORY.APP.ACTION_EXECUTION WHERE 1=1
            """
            params = []
            if action_proposal_id:
                query += " AND action_proposal_id = %s"
                params.append(action_proposal_id)
            query += " ORDER BY started_at DESC"
            cur.execute(query, tuple(params) if params else None)
            rows = cur.fetchall()
            return [
                ActionExecution(
                    execution_id=r[0],
                    action_proposal_id=r[1],
                    approval_id=r[2],
                    action_type=r[3],
                    machine_id=r[4],
                    executed_by=r[5],
                    status=r[6],
                    idempotency_key=r[7],
                    result_data=json.loads(r[8]) if r[8] else {},
                    error_message=r[9],
                    started_at=r[10],
                    completed_at=r[11],
                )
                for r in rows
            ]
        finally:
            cur.close()
            conn.close()

    def save_action_outcome(self, outcome: ActionOutcome) -> ActionOutcome:
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                INSERT INTO COCO_FACTORY.APP.ACTION_OUTCOME
                (outcome_id, action_proposal_id, work_order_id, prediction_id, machine_id,
                 failure_mode, observed_failure_confirmed, downtime_avoided_hours, verification_status,
                 feedback_notes, recorded_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    outcome.outcome_id,
                    outcome.action_proposal_id,
                    outcome.work_order_id,
                    outcome.prediction_id,
                    outcome.machine_id,
                    outcome.failure_mode if isinstance(outcome.failure_mode, str) else outcome.failure_mode.value,
                    outcome.observed_failure_confirmed,
                    outcome.downtime_avoided_hours,
                    outcome.verification_status.value if hasattr(outcome.verification_status, "value") else str(outcome.verification_status),
                    outcome.feedback_notes,
                    outcome.recorded_at.isoformat() if outcome.recorded_at else None,
                ),
            )
            conn.commit()
            return outcome
        finally:
            cur.close()
            conn.close()

    def get_action_outcome(self, outcome_id: str) -> Optional[ActionOutcome]:
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                SELECT outcome_id, action_proposal_id, work_order_id, prediction_id, machine_id,
                       failure_mode, observed_failure_confirmed, downtime_avoided_hours, verification_status,
                       feedback_notes, recorded_at
                FROM COCO_FACTORY.APP.ACTION_OUTCOME WHERE outcome_id = %s
                """,
                (outcome_id,),
            )
            r = cur.fetchone()
            if not r:
                return None
            return ActionOutcome(
                outcome_id=r[0],
                action_proposal_id=r[1],
                work_order_id=r[2],
                prediction_id=r[3],
                machine_id=r[4],
                failure_mode=r[5],
                observed_failure_confirmed=bool(r[6]),
                downtime_avoided_hours=float(r[7] or 0.0),
                verification_status=VerificationStatus(r[8]),
                feedback_notes=r[9] or "",
                recorded_at=r[10],
            )
        finally:
            cur.close()
            conn.close()

    def list_action_outcomes(
        self, machine_id: Optional[str] = None
    ) -> List[ActionOutcome]:
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            query = """
                SELECT outcome_id, action_proposal_id, work_order_id, prediction_id, machine_id,
                       failure_mode, observed_failure_confirmed, downtime_avoided_hours, verification_status,
                       feedback_notes, recorded_at
                FROM COCO_FACTORY.APP.ACTION_OUTCOME WHERE 1=1
            """
            params = []
            if machine_id:
                query += " AND machine_id = %s"
                params.append(machine_id)
            query += " ORDER BY recorded_at DESC"
            cur.execute(query, tuple(params) if params else None)
            rows = cur.fetchall()
            return [
                ActionOutcome(
                    outcome_id=r[0],
                    action_proposal_id=r[1],
                    work_order_id=r[2],
                    prediction_id=r[3],
                    machine_id=r[4],
                    failure_mode=r[5],
                    observed_failure_confirmed=bool(r[6]),
                    downtime_avoided_hours=float(r[7] or 0.0),
                    verification_status=VerificationStatus(r[8]),
                    feedback_notes=r[9] or "",
                    recorded_at=r[10],
                )
                for r in rows
            ]
        finally:
            cur.close()
            conn.close()

    def save_verification_policy(self, policy: VerificationPolicy) -> None:
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                MERGE INTO COCO_FACTORY.APP.VERIFICATION_POLICY target
                USING (SELECT %s AS policy_id) src
                ON target.policy_id = src.policy_id
                WHEN MATCHED THEN UPDATE SET
                    max_acceptable_vibration_rms = %s,
                    max_acceptable_temperature = %s,
                    max_acceptable_risk_score = %s,
                    min_vibration_reduction_pct = %s,
                    min_risk_reduction_pct = %s
                WHEN NOT MATCHED THEN INSERT
                    (policy_id, machine_id, failure_mode, max_acceptable_vibration_rms, max_acceptable_temperature,
                     max_acceptable_risk_score, min_vibration_reduction_pct, min_risk_reduction_pct,
                     baseline_window_hours, verification_window_hours)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    policy.policy_id,
                    policy.max_acceptable_vibration_rms,
                    policy.max_acceptable_temperature,
                    policy.max_acceptable_risk_score,
                    policy.min_vibration_reduction_pct,
                    policy.min_risk_reduction_pct,
                    policy.policy_id,
                    policy.machine_id,
                    policy.failure_mode,
                    policy.max_acceptable_vibration_rms,
                    policy.max_acceptable_temperature,
                    policy.max_acceptable_risk_score,
                    policy.min_vibration_reduction_pct,
                    policy.min_risk_reduction_pct,
                    policy.baseline_window_hours,
                    policy.verification_window_hours,
                ),
            )
            conn.commit()
        finally:
            cur.close()
            conn.close()

    def get_verification_policy(
        self, machine_id: Optional[str] = None, failure_mode: Optional[str] = None
    ) -> Optional[VerificationPolicy]:
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            query = "SELECT policy_id, machine_id, failure_mode, max_acceptable_vibration_rms, max_acceptable_temperature, max_acceptable_risk_score, min_vibration_reduction_pct, min_risk_reduction_pct, baseline_window_hours, verification_window_hours FROM COCO_FACTORY.APP.VERIFICATION_POLICY WHERE 1=1"
            params = []
            if machine_id:
                query += " AND machine_id = %s"
                params.append(machine_id)
            if failure_mode:
                query += " AND failure_mode = %s"
                params.append(failure_mode)
            query += " LIMIT 1"
            cur.execute(query, tuple(params) if params else None)
            r = cur.fetchone()
            if not r:
                return VerificationPolicy()
            return VerificationPolicy(
                policy_id=r[0],
                machine_id=r[1],
                failure_mode=r[2],
                max_acceptable_vibration_rms=float(r[3] or 0.50),
                max_acceptable_temperature=float(r[4] or 65.0),
                max_acceptable_risk_score=float(r[5] or 0.25),
                min_vibration_reduction_pct=float(r[6] or 30.0),
                min_risk_reduction_pct=float(r[7] or 50.0),
                baseline_window_hours=int(r[8] or 24),
                verification_window_hours=int(r[9] or 24),
            )
        finally:
            cur.close()
            conn.close()

    # KnowledgeRepository
    def get_manual(self, machine_model: str) -> Optional[Document]:
        # Minimal retrieval for technical manual
        return None

    def search_docs(self, query: str) -> List[str]:
        return []

    def list_documents(self) -> List[Document]:
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT doc_id AS document_id, title, doc_type, machine_type AS machine_model, '1.0' AS version, _loaded_at AS created_at "
                "FROM COCO_FACTORY.CORE.KNOWLEDGE_DOC ORDER BY doc_id"
            )
            rows = cur.fetchall()
            return [
                Document(
                    document_id=r[0],
                    title=r[1],
                    doc_type=r[2],
                    machine_model=r[3],
                    version=r[4],
                    created_at=r[5],
                )
                for r in rows
            ]
        finally:
            cur.close()
            conn.close()

    # Canonical Prediction implementations
    def save_canonical_prediction(self, prediction: CanonicalPrediction) -> None:
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                MERGE INTO COCO_FACTORY.CORE.PREDICTION target
                USING (SELECT %s AS prediction_id) src
                ON target.prediction_id = src.prediction_id
                WHEN MATCHED THEN UPDATE SET
                    scored_ts = %s,
                    machine_id = %s,
                    suspected_component_id = %s,
                    model_name = %s,
                    horizon_days = %s,
                    failure_prob = %s,
                    risk_level = %s,
                    top_features = %s
                WHEN NOT MATCHED THEN INSERT
                    (prediction_id, scored_ts, machine_id, suspected_component_id, model_name, horizon_days, failure_prob, risk_level, top_features)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    prediction.prediction_id,
                    prediction.scored_ts,
                    prediction.machine_id,
                    prediction.suspected_component_id,
                    prediction.model_name,
                    prediction.horizon_days,
                    prediction.failure_prob,
                    prediction.risk_level,
                    prediction.top_features,
                    prediction.prediction_id,
                    prediction.scored_ts,
                    prediction.machine_id,
                    prediction.suspected_component_id,
                    prediction.model_name,
                    prediction.horizon_days,
                    prediction.failure_prob,
                    prediction.risk_level,
                    prediction.top_features,
                ),
            )
            conn.commit()
        finally:
            cur.close()
            conn.close()

    def get_canonical_prediction(self, prediction_id: str) -> Optional[CanonicalPrediction]:
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                SELECT prediction_id, scored_ts, machine_id, suspected_component_id, model_name, horizon_days, failure_prob, risk_level, top_features
                FROM COCO_FACTORY.CORE.PREDICTION WHERE prediction_id = %s
                """,
                (prediction_id,),
            )
            r = cur.fetchone()
            if not r:
                return None
            return CanonicalPrediction(
                prediction_id=r[0],
                scored_ts=r[1],
                machine_id=r[2],
                suspected_component_id=r[3],
                model_name=r[4],
                horizon_days=r[5],
                failure_prob=float(r[6]),
                risk_level=r[7],
                top_features=r[8],
            )
        finally:
            cur.close()
            conn.close()

    def list_canonical_predictions(
        self, machine_id: Optional[str] = None, limit: int = 50
    ) -> List[CanonicalPrediction]:
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            query = """
                SELECT prediction_id, scored_ts, machine_id, suspected_component_id, model_name, horizon_days, failure_prob, risk_level, top_features
                FROM COCO_FACTORY.CORE.PREDICTION
            """
            params = []
            if machine_id:
                query += " WHERE machine_id = %s"
                params.append(machine_id)
            query += " ORDER BY scored_ts DESC LIMIT %s"
            params.append(limit)
            cur.execute(query, tuple(params))
            rows = cur.fetchall()
            return [
                CanonicalPrediction(
                    prediction_id=r[0],
                    scored_ts=r[1],
                    machine_id=r[2],
                    suspected_component_id=r[3],
                    model_name=r[4],
                    horizon_days=r[5],
                    failure_prob=float(r[6]),
                    risk_level=r[7],
                    top_features=r[8],
                )
                for r in rows
            ]
        finally:
            cur.close()
            conn.close()

    # SupplyChainRepository implementations
    def get_spare_part(self, part_id: str) -> Optional[SparePart]:
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                SELECT part_id, part_name, part_category, compatible_model, unit_cost_inr, supplier_id, lead_time_days, stock_qty, reorder_level, reorder_qty, warehouse_bin
                FROM COCO_FACTORY.CORE.SPARE_PART WHERE part_id = %s
                """,
                (part_id,),
            )
            r = cur.fetchone()
            if not r:
                return None
            return SparePart(
                part_id=r[0],
                part_name=r[1],
                part_category=r[2],
                compatible_model=r[3],
                unit_cost_inr=float(r[4]),
                supplier_id=r[5],
                lead_time_days=int(r[6]),
                stock_qty=int(r[7]),
                reorder_level=int(r[8]),
                reorder_qty=int(r[9]),
                warehouse_bin=r[10],
            )
        finally:
            cur.close()
            conn.close()

    def list_spare_parts(
        self, category: Optional[str] = None, supplier_id: Optional[str] = None
    ) -> List[SparePart]:
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            query = """
                SELECT part_id, part_name, part_category, compatible_model, unit_cost_inr, supplier_id, lead_time_days, stock_qty, reorder_level, reorder_qty, warehouse_bin
                FROM COCO_FACTORY.CORE.SPARE_PART
            """
            conditions = []
            params = []
            if category:
                conditions.append("part_category = %s")
                params.append(category)
            if supplier_id:
                conditions.append("supplier_id = %s")
                params.append(supplier_id)
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
            query += " ORDER BY part_id"
            cur.execute(query, tuple(params) if params else None)
            rows = cur.fetchall()
            return [
                SparePart(
                    part_id=r[0],
                    part_name=r[1],
                    part_category=r[2],
                    compatible_model=r[3],
                    unit_cost_inr=float(r[4]),
                    supplier_id=r[5],
                    lead_time_days=int(r[6]),
                    stock_qty=int(r[7]),
                    reorder_level=int(r[8]),
                    reorder_qty=int(r[9]),
                    warehouse_bin=r[10],
                )
                for r in rows
            ]
        finally:
            cur.close()
            conn.close()

    def get_supplier(self, supplier_id: str) -> Optional[Supplier]:
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                SELECT supplier_id, supplier_name, country, avg_lead_time_days, on_time_delivery_pct
                FROM COCO_FACTORY.CORE.SUPPLIER WHERE supplier_id = %s
                """,
                (supplier_id,),
            )
            r = cur.fetchone()
            if not r:
                return None
            return Supplier(
                supplier_id=r[0],
                supplier_name=r[1],
                country=r[2],
                avg_lead_time_days=int(r[3]),
                on_time_delivery_pct=float(r[4]),
            )
        finally:
            cur.close()
            conn.close()

    def list_suppliers(self) -> List[Supplier]:
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                SELECT supplier_id, supplier_name, country, avg_lead_time_days, on_time_delivery_pct
                FROM COCO_FACTORY.CORE.SUPPLIER ORDER BY supplier_id
                """
            )
            rows = cur.fetchall()
            return [
                Supplier(
                    supplier_id=r[0],
                    supplier_name=r[1],
                    country=r[2],
                    avg_lead_time_days=int(r[3]),
                    on_time_delivery_pct=float(r[4]),
                )
                for r in rows
            ]
        finally:
            cur.close()
            conn.close()

    def get_purchase_order(self, po_id: str) -> Optional[PurchaseOrder]:
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                SELECT po_id, supplier_id, part_id, qty, unit_cost_inr, order_date, expected_delivery_date, actual_delivery_date, status, order_type, linked_wo_id
                FROM COCO_FACTORY.CORE.PURCHASE_ORDER WHERE po_id = %s
                """,
                (po_id,),
            )
            r = cur.fetchone()
            if not r:
                return None
            return PurchaseOrder(
                po_id=r[0],
                supplier_id=r[1],
                part_id=r[2],
                qty=int(r[3]),
                unit_cost_inr=float(r[4]),
                order_date=r[5],
                expected_delivery_date=r[6],
                actual_delivery_date=r[7],
                status=r[8],
                order_type=r[9],
                linked_wo_id=r[10],
            )
        finally:
            cur.close()
            conn.close()

    def list_purchase_orders(
        self, part_id: Optional[str] = None, supplier_id: Optional[str] = None
    ) -> List[PurchaseOrder]:
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            query = """
                SELECT po_id, supplier_id, part_id, qty, unit_cost_inr, order_date, expected_delivery_date, actual_delivery_date, status, order_type, linked_wo_id
                FROM COCO_FACTORY.CORE.PURCHASE_ORDER
            """
            conditions = []
            params = []
            if part_id:
                conditions.append("part_id = %s")
                params.append(part_id)
            if supplier_id:
                conditions.append("supplier_id = %s")
                params.append(supplier_id)
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
            query += " ORDER BY order_date DESC"
            cur.execute(query, tuple(params) if params else None)
            rows = cur.fetchall()
            return [
                PurchaseOrder(
                    po_id=r[0],
                    supplier_id=r[1],
                    part_id=r[2],
                    qty=int(r[3]),
                    unit_cost_inr=float(r[4]),
                    order_date=r[5],
                    expected_delivery_date=r[6],
                    actual_delivery_date=r[7],
                    status=r[8],
                    order_type=r[9],
                    linked_wo_id=r[10],
                )
                for r in rows
            ]
        finally:
            cur.close()
            conn.close()

    def get_production_order(self, order_id: str) -> Optional[ProductionOrder]:
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                SELECT production_order_id, machine_id, product_id, customer, planned_qty, produced_qty, planned_start, planned_end, due_date, priority, status
                FROM COCO_FACTORY.CORE.PRODUCTION_ORDER WHERE production_order_id = %s
                """,
                (order_id,),
            )
            r = cur.fetchone()
            if not r:
                return None
            return ProductionOrder(
                production_order_id=r[0],
                machine_id=r[1],
                product_id=r[2],
                customer=r[3],
                planned_qty=int(r[4]),
                produced_qty=int(r[5]),
                planned_start=r[6],
                planned_end=r[7],
                due_date=r[8],
                priority=r[9],
                status=r[10],
            )
        finally:
            cur.close()
            conn.close()

    def list_production_orders(
        self, machine_id: Optional[str] = None, status: Optional[str] = None
    ) -> List[ProductionOrder]:
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            query = """
                SELECT production_order_id, machine_id, product_id, customer, planned_qty, produced_qty, planned_start, planned_end, due_date, priority, status
                FROM COCO_FACTORY.CORE.PRODUCTION_ORDER
            """
            conditions = []
            params = []
            if machine_id:
                conditions.append("machine_id = %s")
                params.append(machine_id)
            if status:
                conditions.append("status = %s")
                params.append(status)
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
            query += " ORDER BY due_date"
            cur.execute(query, tuple(params) if params else None)
            rows = cur.fetchall()
            return [
                ProductionOrder(
                    production_order_id=r[0],
                    machine_id=r[1],
                    product_id=r[2],
                    customer=r[3],
                    planned_qty=int(r[4]),
                    produced_qty=int(r[5]),
                    planned_start=r[6],
                    planned_end=r[7],
                    due_date=r[8],
                    priority=r[9],
                    status=r[10],
                )
                for r in rows
            ]
        finally:
            cur.close()
            conn.close()

    def reserve_spare_part(self, part_id: str, qty: int = 1) -> bool:
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                UPDATE COCO_FACTORY.CORE.SPARE_PART
                SET stock_qty = stock_qty - %s
                WHERE part_id = %s AND stock_qty >= %s
                """,
                (qty, part_id, qty),
            )
            rows_affected = cur.rowcount
            conn.commit()
            return rows_affected > 0
        except Exception:
            conn.rollback()
            return False
        finally:
            cur.close()
            conn.close()

    # AnalyticsRepository implementations
    def get_machine_health_daily(
        self, machine_id: str, metric_date: Optional[date] = None
    ) -> Optional[MachineHealthDaily]:
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            query = """
                SELECT machine_id, metric_date, machine_name, machine_type, line_id, line_name,
                       reading_count, avg_vibration, max_vibration, avg_temperature, max_temperature,
                       exceedance_count, downtime_minutes, breakdown_count, maintenance_count,
                       open_alerts, latest_prediction_id, latest_failure_prob, latest_risk_level, health_status
                FROM COCO_FACTORY.ANALYTICS.MACHINE_HEALTH_DAILY
                WHERE machine_id = %s
            """
            params = [machine_id]
            if metric_date:
                query += " AND metric_date = %s"
                params.append(metric_date)
            query += " ORDER BY metric_date DESC LIMIT 1"
            cur.execute(query, tuple(params))
            r = cur.fetchone()
            if not r:
                return None
            return MachineHealthDaily(
                machine_id=r[0],
                metric_date=r[1],
                machine_name=r[2],
                machine_type=r[3],
                line_id=r[4],
                line_name=r[5],
                reading_count=int(r[6] or 0),
                avg_vibration=float(r[7]) if r[7] is not None else None,
                max_vibration=float(r[8]) if r[8] is not None else None,
                avg_temperature=float(r[9]) if r[9] is not None else None,
                max_temperature=float(r[10]) if r[10] is not None else None,
                exceedance_count=int(r[11] or 0),
                downtime_minutes=float(r[12] or 0.0),
                breakdown_count=int(r[13] or 0),
                maintenance_count=int(r[14] or 0),
                open_alerts=int(r[15] or 0),
                latest_prediction_id=r[16],
                latest_failure_prob=float(r[17]) if r[17] is not None else None,
                latest_risk_level=r[18],
                health_status=r[19] or "HEALTHY",
            )
        finally:
            cur.close()
            conn.close()

    def list_machine_health_daily(
        self, metric_date: Optional[date] = None, line_id: Optional[str] = None
    ) -> List[MachineHealthDaily]:
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            query = """
                SELECT machine_id, metric_date, machine_name, machine_type, line_id, line_name,
                       reading_count, avg_vibration, max_vibration, avg_temperature, max_temperature,
                       exceedance_count, downtime_minutes, breakdown_count, maintenance_count,
                       open_alerts, latest_prediction_id, latest_failure_prob, latest_risk_level, health_status
                FROM COCO_FACTORY.ANALYTICS.MACHINE_HEALTH_DAILY
            """
            conditions = []
            params = []
            if metric_date:
                conditions.append("metric_date = %s")
                params.append(metric_date)
            if line_id:
                conditions.append("line_id = %s")
                params.append(line_id)
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
            query += " ORDER BY metric_date DESC, machine_id ASC"
            cur.execute(query, tuple(params) if params else None)
            rows = cur.fetchall()
            return [
                MachineHealthDaily(
                    machine_id=r[0],
                    metric_date=r[1],
                    machine_name=r[2],
                    machine_type=r[3],
                    line_id=r[4],
                    line_name=r[5],
                    reading_count=int(r[6] or 0),
                    avg_vibration=float(r[7]) if r[7] is not None else None,
                    max_vibration=float(r[8]) if r[8] is not None else None,
                    avg_temperature=float(r[9]) if r[9] is not None else None,
                    max_temperature=float(r[10]) if r[10] is not None else None,
                    exceedance_count=int(r[11] or 0),
                    downtime_minutes=float(r[12] or 0.0),
                    breakdown_count=int(r[13] or 0),
                    maintenance_count=int(r[14] or 0),
                    open_alerts=int(r[15] or 0),
                    latest_prediction_id=r[16],
                    latest_failure_prob=float(r[17]) if r[17] is not None else None,
                    latest_risk_level=r[18],
                    health_status=r[19] or "HEALTHY",
                )
                for r in rows
            ]
        finally:
            cur.close()
            conn.close()

    def get_machine_oee_daily(
        self, machine_id: str, metric_date: Optional[date] = None
    ) -> Optional[MachineOEEDaily]:
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            query = """
                SELECT machine_id, metric_date, machine_name, line_id,
                       planned_production_minutes, operating_minutes, unplanned_downtime_minutes,
                       total_pieces, good_pieces, reject_pieces,
                       availability, performance, quality, oee
                FROM COCO_FACTORY.ANALYTICS.MACHINE_OEE_DAILY
                WHERE machine_id = %s
            """
            params = [machine_id]
            if metric_date:
                query += " AND metric_date = %s"
                params.append(metric_date)
            query += " ORDER BY metric_date DESC LIMIT 1"
            cur.execute(query, tuple(params))
            r = cur.fetchone()
            if not r:
                return None
            return MachineOEEDaily(
                machine_id=r[0],
                metric_date=r[1],
                machine_name=r[2],
                line_id=r[3],
                planned_production_minutes=float(r[4] or 0.0),
                operating_minutes=float(r[5] or 0.0),
                unplanned_downtime_minutes=float(r[6] or 0.0),
                total_pieces=int(r[7] or 0),
                good_pieces=int(r[8] or 0),
                reject_pieces=int(r[9] or 0),
                availability=float(r[10] or 0.0),
                performance=float(r[11] or 0.0),
                quality=float(r[12] or 0.0),
                oee=float(r[13] or 0.0),
            )
        finally:
            cur.close()
            conn.close()

    def list_machine_oee_daily(
        self, metric_date: Optional[date] = None, line_id: Optional[str] = None
    ) -> List[MachineOEEDaily]:
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            query = """
                SELECT machine_id, metric_date, machine_name, line_id,
                       planned_production_minutes, operating_minutes, unplanned_downtime_minutes,
                       total_pieces, good_pieces, reject_pieces,
                       availability, performance, quality, oee
                FROM COCO_FACTORY.ANALYTICS.MACHINE_OEE_DAILY
            """
            conditions = []
            params = []
            if metric_date:
                conditions.append("metric_date = %s")
                params.append(metric_date)
            if line_id:
                conditions.append("line_id = %s")
                params.append(line_id)
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
            query += " ORDER BY metric_date DESC, machine_id ASC"
            cur.execute(query, tuple(params) if params else None)
            rows = cur.fetchall()
            return [
                MachineOEEDaily(
                    machine_id=r[0],
                    metric_date=r[1],
                    machine_name=r[2],
                    line_id=r[3],
                    planned_production_minutes=float(r[4] or 0.0),
                    operating_minutes=float(r[5] or 0.0),
                    unplanned_downtime_minutes=float(r[6] or 0.0),
                    total_pieces=int(r[7] or 0),
                    good_pieces=int(r[8] or 0),
                    reject_pieces=int(r[9] or 0),
                    availability=float(r[10] or 0.0),
                    performance=float(r[11] or 0.0),
                    quality=float(r[12] or 0.0),
                    oee=float(r[13] or 0.0),
                )
                for r in rows
            ]
        finally:
            cur.close()
            conn.close()

    def get_downtime_daily(
        self, machine_id: str, metric_date: Optional[date] = None
    ) -> Optional[DowntimeSummary]:
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            query = """
                SELECT machine_id, metric_date, machine_name, line_id,
                       total_downtime_minutes, breakdown_minutes, changeover_minutes,
                       minor_stop_minutes, no_material_minutes, no_operator_minutes,
                       planned_maintenance_minutes, breakdown_event_count, total_event_count,
                       top_reason_code, top_downtime_category
                FROM COCO_FACTORY.ANALYTICS.DOWNTIME_DAILY
                WHERE machine_id = %s
            """
            params = [machine_id]
            if metric_date:
                query += " AND metric_date = %s"
                params.append(metric_date)
            query += " ORDER BY metric_date DESC LIMIT 1"
            cur.execute(query, tuple(params))
            r = cur.fetchone()
            if not r:
                return None
            return DowntimeSummary(
                machine_id=r[0],
                metric_date=r[1],
                machine_name=r[2],
                line_id=r[3],
                total_downtime_minutes=float(r[4] or 0.0),
                breakdown_minutes=float(r[5] or 0.0),
                changeover_minutes=float(r[6] or 0.0),
                minor_stop_minutes=float(r[7] or 0.0),
                no_material_minutes=float(r[8] or 0.0),
                no_operator_minutes=float(r[9] or 0.0),
                planned_maintenance_minutes=float(r[10] or 0.0),
                breakdown_event_count=int(r[11] or 0),
                total_event_count=int(r[12] or 0),
                top_reason_code=r[13],
                top_downtime_category=r[14],
            )
        finally:
            cur.close()
            conn.close()

    def list_downtime_daily(
        self, metric_date: Optional[date] = None
    ) -> List[DowntimeSummary]:
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            query = """
                SELECT machine_id, metric_date, machine_name, line_id,
                       total_downtime_minutes, breakdown_minutes, changeover_minutes,
                       minor_stop_minutes, no_material_minutes, no_operator_minutes,
                       planned_maintenance_minutes, breakdown_event_count, total_event_count,
                       top_reason_code, top_downtime_category
                FROM COCO_FACTORY.ANALYTICS.DOWNTIME_DAILY
            """
            params = []
            if metric_date:
                query += " WHERE metric_date = %s"
                params.append(metric_date)
            query += " ORDER BY metric_date DESC, machine_id ASC"
            cur.execute(query, tuple(params) if params else None)
            rows = cur.fetchall()
            return [
                DowntimeSummary(
                    machine_id=r[0],
                    metric_date=r[1],
                    machine_name=r[2],
                    line_id=r[3],
                    total_downtime_minutes=float(r[4] or 0.0),
                    breakdown_minutes=float(r[5] or 0.0),
                    changeover_minutes=float(r[6] or 0.0),
                    minor_stop_minutes=float(r[7] or 0.0),
                    no_material_minutes=float(r[8] or 0.0),
                    no_operator_minutes=float(r[9] or 0.0),
                    planned_maintenance_minutes=float(r[10] or 0.0),
                    breakdown_event_count=int(r[11] or 0),
                    total_event_count=int(r[12] or 0),
                    top_reason_code=r[13],
                    top_downtime_category=r[14],
                )
                for r in rows
            ]
        finally:
            cur.close()
            conn.close()

    def get_maintenance_daily(
        self, machine_id: str, metric_date: Optional[date] = None
    ) -> Optional[MaintenanceSummary]:
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            query = """
                SELECT machine_id, metric_date, machine_name, line_id,
                       work_order_count, corrective_count, preventive_count, breakdown_count,
                       total_labor_hours, total_parts_cost_inr, total_labor_cost_inr,
                       total_maintenance_cost_inr, mean_time_to_repair_minutes
                FROM COCO_FACTORY.ANALYTICS.MAINTENANCE_DAILY
                WHERE machine_id = %s
            """
            params = [machine_id]
            if metric_date:
                query += " AND metric_date = %s"
                params.append(metric_date)
            query += " ORDER BY metric_date DESC LIMIT 1"
            cur.execute(query, tuple(params))
            r = cur.fetchone()
            if not r:
                return None
            return MaintenanceSummary(
                machine_id=r[0],
                metric_date=r[1],
                machine_name=r[2],
                line_id=r[3],
                work_order_count=int(r[4] or 0),
                corrective_count=int(r[5] or 0),
                preventive_count=int(r[6] or 0),
                breakdown_count=int(r[7] or 0),
                total_labor_hours=float(r[8] or 0.0),
                total_parts_cost_inr=float(r[9] or 0.0),
                total_labor_cost_inr=float(r[10] or 0.0),
                total_maintenance_cost_inr=float(r[11] or 0.0),
                mean_time_to_repair_minutes=float(r[12]) if r[12] is not None else None,
            )
        finally:
            cur.close()
            conn.close()

    def list_maintenance_daily(
        self, metric_date: Optional[date] = None
    ) -> List[MaintenanceSummary]:
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            query = """
                SELECT machine_id, metric_date, machine_name, line_id,
                       work_order_count, corrective_count, preventive_count, breakdown_count,
                       total_labor_hours, total_parts_cost_inr, total_labor_cost_inr,
                       total_maintenance_cost_inr, mean_time_to_repair_minutes
                FROM COCO_FACTORY.ANALYTICS.MAINTENANCE_DAILY
            """
            params = []
            if metric_date:
                query += " WHERE metric_date = %s"
                params.append(metric_date)
            query += " ORDER BY metric_date DESC, machine_id ASC"
            cur.execute(query, tuple(params) if params else None)
            rows = cur.fetchall()
            return [
                MaintenanceSummary(
                    machine_id=r[0],
                    metric_date=r[1],
                    machine_name=r[2],
                    line_id=r[3],
                    work_order_count=int(r[4] or 0),
                    corrective_count=int(r[5] or 0),
                    preventive_count=int(r[6] or 0),
                    breakdown_count=int(r[7] or 0),
                    total_labor_hours=float(r[8] or 0.0),
                    total_parts_cost_inr=float(r[9] or 0.0),
                    total_labor_cost_inr=float(r[10] or 0.0),
                    total_maintenance_cost_inr=float(r[11] or 0.0),
                    mean_time_to_repair_minutes=float(r[12]) if r[12] is not None else None,
                )
                for r in rows
            ]
        finally:
            cur.close()
            conn.close()

    def get_inventory_risk(self, part_id: str) -> Optional[InventoryRisk]:
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            query = """
                SELECT part_id, part_name, part_category, compatible_model,
                       stock_qty, reorder_level, reorder_qty, lead_time_days,
                       supplier_id, supplier_name, open_po_count, open_po_qty,
                       stock_status, is_critical_exposure
                FROM COCO_FACTORY.ANALYTICS.INVENTORY_RISK
                WHERE part_id = %s
            """
            cur.execute(query, (part_id,))
            r = cur.fetchone()
            if not r:
                return None
            return InventoryRisk(
                part_id=r[0],
                part_name=r[1],
                part_category=r[2],
                compatible_model=r[3],
                stock_qty=int(r[4] or 0),
                reorder_level=int(r[5] or 0),
                reorder_qty=int(r[6] or 0),
                lead_time_days=int(r[7] or 0),
                supplier_id=r[8],
                supplier_name=r[9],
                open_po_count=int(r[10] or 0),
                open_po_qty=int(r[11] or 0),
                stock_status=r[12] or "HEALTHY",
                is_critical_exposure=bool(r[13]),
            )
        finally:
            cur.close()
            conn.close()

    def list_inventory_risks(
        self, critical_only: bool = False
    ) -> List[InventoryRisk]:
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            query = """
                SELECT part_id, part_name, part_category, compatible_model,
                       stock_qty, reorder_level, reorder_qty, lead_time_days,
                       supplier_id, supplier_name, open_po_count, open_po_qty,
                       stock_status, is_critical_exposure
                FROM COCO_FACTORY.ANALYTICS.INVENTORY_RISK
            """
            if critical_only:
                query += " WHERE is_critical_exposure = TRUE"
            query += " ORDER BY part_id ASC"
            cur.execute(query)
            rows = cur.fetchall()
            return [
                InventoryRisk(
                    part_id=r[0],
                    part_name=r[1],
                    part_category=r[2],
                    compatible_model=r[3],
                    stock_qty=int(r[4] or 0),
                    reorder_level=int(r[5] or 0),
                    reorder_qty=int(r[6] or 0),
                    lead_time_days=int(r[7] or 0),
                    supplier_id=r[8],
                    supplier_name=r[9],
                    open_po_count=int(r[10] or 0),
                    open_po_qty=int(r[11] or 0),
                    stock_status=r[12] or "HEALTHY",
                    is_critical_exposure=bool(r[13]),
                )
                for r in rows
            ]
        finally:
            cur.close()
            conn.close()

    def get_production_context(
        self, production_order_id: str
    ) -> Optional[ProductionContext]:
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            query = """
                SELECT production_order_id, machine_id, machine_name, line_id,
                       product_id, product_name, customer, priority, status,
                       planned_qty, produced_qty, progress_pct, due_date,
                       days_until_due, is_overdue, unit_price_inr, order_value_inr,
                       unfulfilled_revenue_exposure_inr
                FROM COCO_FACTORY.ANALYTICS.PRODUCTION_CONTEXT
                WHERE production_order_id = %s
            """
            cur.execute(query, (production_order_id,))
            r = cur.fetchone()
            if not r:
                return None
            return ProductionContext(
                production_order_id=r[0],
                machine_id=r[1],
                machine_name=r[2],
                line_id=r[3],
                product_id=r[4],
                product_name=r[5],
                customer=r[6],
                priority=r[7],
                status=r[8],
                planned_qty=int(r[9] or 0),
                produced_qty=int(r[10] or 0),
                progress_pct=float(r[11] or 0.0),
                due_date=r[12],
                days_until_due=int(r[13] or 0),
                is_overdue=bool(r[14]),
                unit_price_inr=float(r[15] or 0.0),
                order_value_inr=float(r[16] or 0.0),
                unfulfilled_revenue_exposure_inr=float(r[17] or 0.0),
            )
        finally:
            cur.close()
            conn.close()

    def list_production_contexts(
        self, machine_id: Optional[str] = None, status: Optional[str] = None
    ) -> List[ProductionContext]:
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            query = """
                SELECT production_order_id, machine_id, machine_name, line_id,
                       product_id, product_name, customer, priority, status,
                       planned_qty, produced_qty, progress_pct, due_date,
                       days_until_due, is_overdue, unit_price_inr, order_value_inr,
                       unfulfilled_revenue_exposure_inr
                FROM COCO_FACTORY.ANALYTICS.PRODUCTION_CONTEXT
            """
            conditions = []
            params = []
            if machine_id:
                conditions.append("machine_id = %s")
                params.append(machine_id)
            if status:
                conditions.append("status = %s")
                params.append(status)
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
            query += " ORDER BY due_date ASC"
            cur.execute(query, tuple(params) if params else None)
            rows = cur.fetchall()
            return [
                ProductionContext(
                    production_order_id=r[0],
                    machine_id=r[1],
                    machine_name=r[2],
                    line_id=r[3],
                    product_id=r[4],
                    product_name=r[5],
                    customer=r[6],
                    priority=r[7],
                    status=r[8],
                    planned_qty=int(r[9] or 0),
                    produced_qty=int(r[10] or 0),
                    progress_pct=float(r[11] or 0.0),
                    due_date=r[12],
                    days_until_due=int(r[13] or 0),
                    is_overdue=bool(r[14]),
                    unit_price_inr=float(r[15] or 0.0),
                    order_value_inr=float(r[16] or 0.0),
                    unfulfilled_revenue_exposure_inr=float(r[17] or 0.0),
                )
                for r in rows
            ]
        finally:
            cur.close()
            conn.close()

    def get_reliability_features(
        self, machine_id: str, feature_date: Optional[date] = None
    ) -> Optional[ReliabilityFeatures]:
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            query = """
                SELECT machine_id, feature_date,
                       vib_mean_7d, vib_max_7d, vib_std_7d, vib_rel30, vib_slope_7d,
                       temp_mean_7d, temp_max_7d, temp_rel30,
                       exceedance_ratio_7d, downtime_ratio_7d, unplanned_downtime_hours_7d,
                       breakdown_count_30d, days_since_last_maint
                FROM COCO_FACTORY.ML.V_MACHINE_FEATURE_DAILY
                WHERE machine_id = %s
            """
            params = [machine_id]
            if feature_date:
                query += " AND feature_date = %s"
                params.append(feature_date)
            query += " ORDER BY feature_date DESC LIMIT 1"
            cur.execute(query, tuple(params))
            r = cur.fetchone()
            if not r:
                return None
            return ReliabilityFeatures(
                machine_id=r[0],
                feature_date=r[1],
                vib_mean_7d=float(r[2]) if r[2] is not None else None,
                vib_max_7d=float(r[3]) if r[3] is not None else None,
                vib_std_7d=float(r[4]) if r[4] is not None else None,
                vib_rel30=float(r[5]) if r[5] is not None else None,
                vib_slope_7d=float(r[6]) if r[6] is not None else None,
                temp_mean_7d=float(r[7]) if r[7] is not None else None,
                temp_max_7d=float(r[8]) if r[8] is not None else None,
                temp_rel30=float(r[9]) if r[9] is not None else None,
                exceedance_ratio_7d=float(r[10]) if r[10] is not None else None,
                downtime_ratio_7d=float(r[11]) if r[11] is not None else None,
                unplanned_downtime_hours_7d=float(r[12]) if r[12] is not None else None,
                breakdown_count_30d=int(r[13] or 0),
                days_since_last_maint=int(r[14]) if r[14] is not None else None,
            )
        finally:
            cur.close()
            conn.close()

    # KnowledgeSearchRepository implementations
    def get_document(self, document_id: str) -> Optional[KnowledgeDocument]:
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            query = """
                SELECT doc_id, title, doc_type, failure_code, machine_type, component_type, content, metadata_json
                FROM COCO_FACTORY.KNOWLEDGE.CORPUS
                WHERE doc_id = %s
            """
            cur.execute(query, (document_id,))
            r = cur.fetchone()
            if not r:
                return None
            meta = {}
            if r[7]:
                try:
                    meta = json.loads(r[7]) if isinstance(r[7], str) else r[7]
                except Exception:
                    meta = {}
            return KnowledgeDocument(
                document_id=r[0],
                title=r[1],
                doc_type=r[2],
                failure_code=r[3],
                model=r[4],
                component_type=r[5],
                content=r[6],
                metadata=meta,
            )
        finally:
            cur.close()
            conn.close()

    def list_documents(
        self, doc_type: Optional[str] = None, failure_code: Optional[str] = None
    ) -> List[KnowledgeDocument]:
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            query = """
                SELECT doc_id, title, doc_type, failure_code, machine_type, component_type, content, metadata_json
                FROM COCO_FACTORY.KNOWLEDGE.CORPUS
            """
            conditions = []
            params = []
            if doc_type:
                conditions.append("doc_type = %s")
                params.append(doc_type)
            if failure_code:
                conditions.append("failure_code = %s")
                params.append(failure_code)
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
            query += " ORDER BY doc_id ASC"
            cur.execute(query, tuple(params) if params else None)
            rows = cur.fetchall()
            docs = []
            for r in rows:
                meta = {}
                if r[7]:
                    try:
                        meta = json.loads(r[7]) if isinstance(r[7], str) else r[7]
                    except Exception:
                        meta = {}
                docs.append(
                    KnowledgeDocument(
                        document_id=r[0],
                        title=r[1],
                        doc_type=r[2],
                        failure_code=r[3],
                        model=r[4],
                        component_type=r[5],
                        content=r[6],
                        metadata=meta,
                    )
                )
            return docs
        finally:
            cur.close()
            conn.close()

    def search_corpus(
        self, query: str, limit: int = 5, failure_code: Optional[str] = None
    ) -> List[KnowledgeDocument]:
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            sql = """
                SELECT doc_id, title, doc_type, failure_code, machine_type, component_type, content, metadata_json
                FROM COCO_FACTORY.KNOWLEDGE.CORPUS
                WHERE (title ILIKE %s OR content ILIKE %s)
            """
            search_param = f"%{query}%"
            params = [search_param, search_param]
            if failure_code:
                sql += " AND failure_code = %s"
                params.append(failure_code)
            sql += f" LIMIT {int(limit)}"
            cur.execute(sql, tuple(params))
            rows = cur.fetchall()
            docs = []
            for r in rows:
                meta = {}
                if r[7]:
                    try:
                        meta = json.loads(r[7]) if isinstance(r[7], str) else r[7]
                    except Exception:
                        meta = {}
                docs.append(
                    KnowledgeDocument(
                        document_id=r[0],
                        title=r[1],
                        doc_type=r[2],
                        failure_code=r[3],
                        model=r[4],
                        component_type=r[5],
                        content=r[6],
                        metadata=meta,
                    )
                )
            return docs
        finally:
            cur.close()
            conn.close()

    def get_failure_mode(self, failure_code: str) -> Optional[FailureModeTaxonomy]:
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            query = """
                SELECT failure_code, name, category, component_type, symptoms, related_sensor_types, recommended_action_template
                FROM COCO_FACTORY.KNOWLEDGE.FAILURE_MODE_TAXONOMY
                WHERE failure_code = %s
            """
            cur.execute(query, (failure_code,))
            r = cur.fetchone()
            if not r:
                return None
            sensors = [s.strip() for s in (r[5] or "").split(",") if s.strip()]
            return FailureModeTaxonomy(
                failure_code=r[0],
                failure_name=r[1],
                category=r[2],
                component_type=r[3],
                typical_symptoms=r[4],
                primary_sensors=sensors,
                recommended_action=r[6],
            )
        finally:
            cur.close()
            conn.close()

    def list_failure_modes(
        self, category: Optional[str] = None
    ) -> List[FailureModeTaxonomy]:
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            query = """
                SELECT failure_code, name, category, component_type, symptoms, related_sensor_types, recommended_action_template
                FROM COCO_FACTORY.KNOWLEDGE.FAILURE_MODE_TAXONOMY
            """
            params = []
            if category:
                query += " WHERE category = %s"
                params.append(category)
            query += " ORDER BY failure_code ASC"
            cur.execute(query, tuple(params) if params else None)
            rows = cur.fetchall()
            return [
                FailureModeTaxonomy(
                    failure_code=r[0],
                    failure_name=r[1],
                    category=r[2],
                    component_type=r[3],
                    typical_symptoms=r[4],
                    primary_sensors=[s.strip() for s in (r[5] or "").split(",") if s.strip()],
                    recommended_action=r[6],
                )
                for r in rows
            ]
        finally:
            cur.close()
            conn.close()

    # MLRepository implementations
    def save_model_metadata(self, record: ModelRegistryRecord) -> None:
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                MERGE INTO COCO_FACTORY.ML.MODEL_REGISTRY target
                USING (SELECT %s AS model_id) src
                ON target.model_id = src.model_id
                WHEN MATCHED THEN UPDATE SET
                    model_name = %s, model_version = %s, algorithm = %s, training_dataset_version = %s,
                    feature_version = %s, target_definition = %s, horizon_hours = %s, horizon_days = %s,
                    training_start_date = %s, training_end_date = %s, validation_start_date = %s, validation_end_date = %s,
                    test_start_date = %s, test_end_date = %s, auc_roc = %s, pr_auc = %s,
                    precision_at_threshold = %s, recall_at_threshold = %s, f1_score = %s,
                    feature_count = %s, parameters_json = %s, artifact_location = %s,
                    artifact_checksum = %s, status = %s, trained_at = %s
                WHEN NOT MATCHED THEN INSERT (
                    model_id, model_name, model_version, version, algorithm, training_dataset_version,
                    feature_version, target_definition, horizon_hours, horizon_days,
                    training_start_date, training_end_date, validation_start_date, validation_end_date,
                    test_start_date, test_end_date, auc_roc, pr_auc,
                    precision_at_threshold, recall_at_threshold, f1_score,
                    feature_count, parameters_json, artifact_location, artifact_checksum, status, trained_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s, %s, %s, %s
                )
                """,
                (
                    record.model_id,
                    record.model_name, record.model_version, record.algorithm, record.training_dataset_version,
                    record.feature_version, record.target_definition, record.horizon_hours, int(record.horizon_hours / 24),
                    record.training_start_date, record.training_end_date, record.validation_start_date, record.validation_end_date,
                    record.test_start_date, record.test_end_date, record.auc_roc, record.pr_auc,
                    record.precision_at_threshold, record.recall_at_threshold, record.f1_score,
                    record.feature_count, json.dumps(record.parameters), record.artifact_location,
                    record.artifact_checksum, record.status, record.trained_at.isoformat(),
                    # insert values
                    record.model_id, record.model_name, record.model_version, record.model_version, record.algorithm, record.training_dataset_version,
                    record.feature_version, record.target_definition, record.horizon_hours, int(record.horizon_hours / 24),
                    record.training_start_date, record.training_end_date, record.validation_start_date, record.validation_end_date,
                    record.test_start_date, record.test_end_date, record.auc_roc, record.pr_auc,
                    record.precision_at_threshold, record.recall_at_threshold, record.f1_score,
                    record.feature_count, json.dumps(record.parameters), record.artifact_location, record.artifact_checksum, record.status, record.trained_at.isoformat(),
                ),
            )
            conn.commit()
        finally:
            cur.close()
            conn.close()

    def get_model(self, model_id: str) -> Optional[ModelRegistryRecord]:
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                SELECT model_id, model_name, model_version, algorithm, training_dataset_version,
                       feature_version, target_definition, horizon_hours, training_start_date,
                       training_end_date, validation_start_date, validation_end_date,
                       test_start_date, test_end_date, auc_roc, pr_auc, precision_at_threshold,
                       recall_at_threshold, f1_score, feature_count, parameters_json,
                       artifact_location, artifact_checksum, status, trained_at
                FROM COCO_FACTORY.ML.MODEL_REGISTRY
                WHERE model_id = %s
                """,
                (model_id,),
            )
            r = cur.fetchone()
            if not r:
                return None
            params = json.loads(r[20]) if r[20] else {}
            return ModelRegistryRecord(
                model_id=r[0],
                model_name=r[1],
                model_version=r[2] or "",
                algorithm=r[3],
                training_dataset_version=r[4] or "v2026.03-canonical",
                feature_version=r[5] or "v1.0-29feat",
                target_definition=r[6] or "",
                horizon_hours=int(r[7] or 168),
                training_start_date=r[8],
                training_end_date=r[9],
                validation_start_date=r[10],
                validation_end_date=r[11],
                test_start_date=r[12],
                test_end_date=r[13],
                auc_roc=float(r[14]) if r[14] is not None else None,
                pr_auc=float(r[15]) if r[15] is not None else None,
                precision_at_threshold=float(r[16]) if r[16] is not None else None,
                recall_at_threshold=float(r[17]) if r[17] is not None else None,
                f1_score=float(r[18]) if r[18] is not None else None,
                feature_count=int(r[19] or 29),
                parameters=params,
                artifact_location=r[21],
                artifact_checksum=r[22],
                status=r[23] or "candidate",
                trained_at=r[24],
            )
        finally:
            cur.close()
            conn.close()

    def get_active_model(self) -> Optional[ModelRegistryRecord]:
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                SELECT model_id, model_name, model_version, algorithm, training_dataset_version,
                       feature_version, target_definition, horizon_hours, training_start_date,
                       training_end_date, validation_start_date, validation_end_date,
                       test_start_date, test_end_date, auc_roc, pr_auc, precision_at_threshold,
                       recall_at_threshold, f1_score, feature_count, parameters_json,
                       artifact_location, artifact_checksum, status, trained_at
                FROM COCO_FACTORY.ML.MODEL_REGISTRY
                WHERE status = 'active'
                ORDER BY trained_at DESC
                LIMIT 1
                """
            )
            r = cur.fetchone()
            if not r:
                return None
            params = json.loads(r[20]) if r[20] else {}
            return ModelRegistryRecord(
                model_id=r[0],
                model_name=r[1],
                model_version=r[2] or "",
                algorithm=r[3],
                training_dataset_version=r[4] or "v2026.03-canonical",
                feature_version=r[5] or "v1.0-29feat",
                target_definition=r[6] or "",
                horizon_hours=int(r[7] or 168),
                training_start_date=r[8],
                training_end_date=r[9],
                validation_start_date=r[10],
                validation_end_date=r[11],
                test_start_date=r[12],
                test_end_date=r[13],
                auc_roc=float(r[14]) if r[14] is not None else None,
                pr_auc=float(r[15]) if r[15] is not None else None,
                precision_at_threshold=float(r[16]) if r[16] is not None else None,
                recall_at_threshold=float(r[17]) if r[17] is not None else None,
                f1_score=float(r[18]) if r[18] is not None else None,
                feature_count=int(r[19] or 29),
                parameters=params,
                artifact_location=r[21],
                artifact_checksum=r[22],
                status=r[23] or "active",
                trained_at=r[24],
            )
        finally:
            cur.close()
            conn.close()

    def list_models(self, status: Optional[str] = None) -> List[ModelRegistryRecord]:
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            sql = """
                SELECT model_id, model_name, model_version, algorithm, training_dataset_version,
                       feature_version, target_definition, horizon_hours, training_start_date,
                       training_end_date, validation_start_date, validation_end_date,
                       test_start_date, test_end_date, auc_roc, pr_auc, precision_at_threshold,
                       recall_at_threshold, f1_score, feature_count, parameters_json,
                       artifact_location, artifact_checksum, status, trained_at
                FROM COCO_FACTORY.ML.MODEL_REGISTRY
            """
            params = []
            if status:
                sql += " WHERE status = %s"
                params.append(status)
            sql += " ORDER BY trained_at DESC"
            cur.execute(sql, tuple(params) if params else None)
            rows = cur.fetchall()
            res = []
            for r in rows:
                p_map = json.loads(r[20]) if r[20] else {}
                res.append(
                    ModelRegistryRecord(
                        model_id=r[0],
                        model_name=r[1],
                        model_version=r[2] or "",
                        algorithm=r[3],
                        training_dataset_version=r[4] or "v2026.03-canonical",
                        feature_version=r[5] or "v1.0-29feat",
                        target_definition=r[6] or "",
                        horizon_hours=int(r[7] or 168),
                        training_start_date=r[8],
                        training_end_date=r[9],
                        validation_start_date=r[10],
                        validation_end_date=r[11],
                        test_start_date=r[12],
                        test_end_date=r[13],
                        auc_roc=float(r[14]) if r[14] is not None else None,
                        pr_auc=float(r[15]) if r[15] is not None else None,
                        precision_at_threshold=float(r[16]) if r[16] is not None else None,
                        recall_at_threshold=float(r[17]) if r[17] is not None else None,
                        f1_score=float(r[18]) if r[18] is not None else None,
                        feature_count=int(r[19] or 29),
                        parameters=p_map,
                        artifact_location=r[21],
                        artifact_checksum=r[22],
                        status=r[23] or "candidate",
                        trained_at=r[24],
                    )
                )
            return res
        finally:
            cur.close()
            conn.close()

    def promote_model(self, model_id: str, target_status: str = "active") -> Optional[ModelRegistryRecord]:
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            if target_status == "active":
                cur.execute(
                    "UPDATE COCO_FACTORY.ML.MODEL_REGISTRY SET status = 'validated' WHERE status = 'active'"
                )
            cur.execute(
                "UPDATE COCO_FACTORY.ML.MODEL_REGISTRY SET status = %s WHERE model_id = %s",
                (target_status, model_id),
            )
            conn.commit()
            return self.get_model(model_id)
        finally:
            cur.close()
            conn.close()

    def save_evaluation(self, eval_record: ModelEvaluationRecord) -> None:
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                INSERT INTO COCO_FACTORY.ML.MODEL_EVALUATION (
                    evaluation_id, model_id, model_version, split_name, sample_count,
                    positive_count, roc_auc, pr_auc, precision_score, recall_score,
                    f1_score, confusion_matrix_json, evaluated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    eval_record.evaluation_id,
                    eval_record.model_id,
                    eval_record.model_version,
                    eval_record.split_name,
                    eval_record.sample_count,
                    eval_record.positive_count,
                    eval_record.roc_auc,
                    eval_record.pr_auc,
                    eval_record.precision_score,
                    eval_record.recall_score,
                    eval_record.f1_score,
                    json.dumps(eval_record.confusion_matrix),
                    eval_record.evaluated_at.isoformat(),
                ),
            )
            conn.commit()
        finally:
            cur.close()
            conn.close()

    def list_evaluations(self, model_id: Optional[str] = None) -> List[ModelEvaluationRecord]:
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            sql = """
                SELECT evaluation_id, model_id, model_version, split_name, sample_count,
                       positive_count, roc_auc, pr_auc, precision_score, recall_score,
                       f1_score, confusion_matrix_json, evaluated_at
                FROM COCO_FACTORY.ML.MODEL_EVALUATION
            """
            params = []
            if model_id:
                sql += " WHERE model_id = %s"
                params.append(model_id)
            sql += " ORDER BY evaluated_at DESC"
            cur.execute(sql, tuple(params) if params else None)
            rows = cur.fetchall()
            return [
                ModelEvaluationRecord(
                    evaluation_id=r[0],
                    model_id=r[1],
                    model_version=r[2],
                    split_name=r[3],
                    sample_count=int(r[4]),
                    positive_count=int(r[5]),
                    roc_auc=float(r[6]),
                    pr_auc=float(r[7]),
                    precision_score=float(r[8]),
                    recall_score=float(r[9]),
                    f1_score=float(r[10]),
                    confusion_matrix=json.loads(r[11]) if r[11] else {},
                    evaluated_at=r[12],
                )
                for r in rows
            ]
        finally:
            cur.close()
            conn.close()

    def save_prediction_feature_snapshot(self, snapshot: PredictionFeatureSnapshot) -> None:
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                INSERT INTO COCO_FACTORY.ML.PREDICTION_FEATURE_SNAPSHOT (
                    snapshot_id, prediction_id, machine_id, feature_timestamp,
                    feature_version, features_json, source_window_start, source_window_end, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    snapshot.snapshot_id,
                    snapshot.prediction_id,
                    snapshot.machine_id,
                    snapshot.feature_timestamp.isoformat(),
                    snapshot.feature_version,
                    json.dumps(snapshot.features),
                    snapshot.source_window_start.isoformat() if snapshot.source_window_start else None,
                    snapshot.source_window_end.isoformat() if snapshot.source_window_end else None,
                    snapshot.created_at.isoformat(),
                ),
            )
            conn.commit()
        finally:
            cur.close()
            conn.close()

    def get_prediction_feature_snapshot(self, snapshot_id: str) -> Optional[PredictionFeatureSnapshot]:
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                SELECT snapshot_id, prediction_id, machine_id, feature_timestamp,
                       feature_version, features_json, source_window_start, source_window_end, created_at
                FROM COCO_FACTORY.ML.PREDICTION_FEATURE_SNAPSHOT
                WHERE snapshot_id = %s
                """,
                (snapshot_id,),
            )
            r = cur.fetchone()
            if not r:
                return None
            return PredictionFeatureSnapshot(
                snapshot_id=r[0],
                prediction_id=r[1],
                machine_id=r[2],
                feature_timestamp=r[3],
                feature_version=r[4],
                features=json.loads(r[5]) if r[5] else {},
                source_window_start=r[6],
                source_window_end=r[7],
                created_at=r[8],
            )
        finally:
            cur.close()
            conn.close()

    def save_prediction_lineage(self, lineage: PredictionLineage) -> None:
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                INSERT INTO COCO_FACTORY.ML.PREDICTION_LINEAGE (
                    lineage_id, prediction_id, machine_id, model_id, model_version,
                    feature_version, snapshot_id, inference_timestamp, failure_probability,
                    risk_level, policy_version, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    lineage.lineage_id,
                    lineage.prediction_id,
                    lineage.machine_id,
                    lineage.model_id,
                    lineage.model_version,
                    lineage.feature_version,
                    lineage.snapshot_id,
                    lineage.inference_timestamp.isoformat(),
                    lineage.failure_probability,
                    lineage.risk_level,
                    lineage.policy_version,
                    lineage.created_at.isoformat(),
                ),
            )
            conn.commit()
        finally:
            cur.close()
            conn.close()

    def get_prediction_lineage(self, prediction_id: str) -> Optional[PredictionLineage]:
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                SELECT lineage_id, prediction_id, machine_id, model_id, model_version,
                       feature_version, snapshot_id, inference_timestamp, failure_probability,
                       risk_level, policy_version, created_at
                FROM COCO_FACTORY.ML.PREDICTION_LINEAGE
                WHERE prediction_id = %s
                """,
                (prediction_id,),
            )
            r = cur.fetchone()
            if not r:
                return None
            return PredictionLineage(
                lineage_id=r[0],
                prediction_id=r[1],
                machine_id=r[2],
                model_id=r[3],
                model_version=r[4],
                feature_version=r[5],
                snapshot_id=r[6],
                inference_timestamp=r[7],
                failure_probability=float(r[8]),
                risk_level=r[9],
                policy_version=r[10],
                created_at=r[11],
            )
        finally:
            cur.close()
            conn.close()

    def get_prediction_by_id(self, prediction_id: str) -> Optional[MLFailurePrediction]:
        cp = self.get_canonical_prediction(prediction_id)
        if not cp:
            return None
        return _canonical_to_ml_prediction(cp)

    def get_predictions_for_machine(self, machine_id: str, limit: int = 50) -> List[MLFailurePrediction]:
        return self.list_predictions(machine_id=machine_id, limit=limit)

    # COCO_FACTORY.APP Investigation Persistence (Milestone 4)
    def save_app_investigation(self, investigation: Investigation) -> None:
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                MERGE INTO COCO_FACTORY.APP.INVESTIGATION target
                USING (SELECT %s AS investigation_id) src
                ON target.investigation_id = src.investigation_id
                WHEN MATCHED THEN UPDATE SET
                    status = %s,
                    confidence = %s,
                    summary = %s,
                    completed_at = %s
                WHEN NOT MATCHED THEN INSERT (
                    investigation_id, trigger_type, trigger_id, prediction_id, alert_id,
                    machine_id, component_id, scope, status, failure_mode, confidence,
                    summary, started_at, completed_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    investigation.investigation_id,
                    investigation.status.value if hasattr(investigation.status, "value") else str(investigation.status),
                    investigation.confidence,
                    investigation.summary,
                    investigation.completed_at.isoformat() if investigation.completed_at else None,
                    investigation.investigation_id,
                    investigation.trigger_type.value if hasattr(investigation.trigger_type, "value") else str(investigation.trigger_type or "PREDICTION"),
                    investigation.trigger_id or investigation.prediction_id,
                    investigation.prediction_id,
                    investigation.alert_id,
                    investigation.machine_id,
                    investigation.component_id,
                    investigation.scope or "EQUIPMENT_RELIABILITY",
                    investigation.status.value if hasattr(investigation.status, "value") else str(investigation.status),
                    investigation.failure_mode.value if hasattr(investigation.failure_mode, "value") else str(investigation.failure_mode),
                    investigation.confidence,
                    investigation.summary,
                    investigation.started_at.isoformat() if investigation.started_at else None,
                    investigation.completed_at.isoformat() if investigation.completed_at else None,
                ),
            )
            conn.commit()
        finally:
            cur.close()
            conn.close()

    def get_app_investigation(self, investigation_id: str) -> Optional[Investigation]:
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                SELECT investigation_id, trigger_type, trigger_id, prediction_id, alert_id,
                       machine_id, component_id, scope, status, failure_mode, confidence,
                       summary, started_at, completed_at, created_at
                FROM COCO_FACTORY.APP.INVESTIGATION
                WHERE investigation_id = %s
                """,
                (investigation_id,),
            )
            r = cur.fetchone()
            if not r:
                return None
            return Investigation(
                investigation_id=r[0],
                trigger_id=r[2],
                prediction_id=r[3],
                alert_id=r[4],
                machine_id=r[5],
                component_id=r[6],
                scope=r[7],
                status=r[8],
                failure_mode=FailureMode(r[9]) if r[9] else FailureMode.BEARING_DEGRADATION,
                confidence=float(r[10]) if r[10] is not None else 0.88,
                summary=r[11],
                started_at=r[12],
                completed_at=r[13],
                created_at=r[14],
            )
        finally:
            cur.close()
            conn.close()

    def save_app_evidence(self, evidence: List[Evidence]) -> None:
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
                    ev.category or ev.evidence_type,
                    ev.source,
                    ev.source_type,
                    ev.source_id,
                    ev.metric,
                    str(ev.observed_value) if ev.observed_value is not None else None,
                    ev.unit,
                    ev.severity,
                    ev.relationship,
                    ev.machine_id,
                    ev.component_id,
                    ev.claim,
                    ev.summary,
                    ev.source_reference,
                )
                for ev in evidence
            ]
            cur.executemany(
                """
                MERGE INTO COCO_FACTORY.APP.INVESTIGATION_EVIDENCE target
                USING (SELECT %s AS evidence_id) src
                ON target.evidence_id = src.evidence_id
                WHEN NOT MATCHED THEN INSERT (
                    evidence_id, investigation_id, evidence_type, category, source,
                    source_type, source_id, metric, observed_value, unit, severity,
                    relationship, machine_id, component_id, claim, summary, source_reference
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                [(p[0], *p) for p in params],
            )
            conn.commit()
        finally:
            cur.close()
            conn.close()

    def save_app_tool_call(self, call_id: str, investigation_id: str, tool_name: str, scope: str, parameters: str, record_count: int, duration_ms: float, success: bool = True, error_message: Optional[str] = None) -> None:
        conn = self.conn_mgr.get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                INSERT INTO COCO_FACTORY.APP.INVESTIGATION_TOOL_CALL (
                    call_id, investigation_id, tool_name, tool_mode, scope,
                    parameters, record_count, duration_ms, success, error_message
                ) VALUES (%s, %s, %s, 'READ', %s, %s, %s, %s, %s, %s)
                """,
                (call_id, investigation_id, tool_name, scope, parameters, record_count, duration_ms, success, error_message),
            )
            conn.commit()
        finally:
            cur.close()
            conn.close()

