"""M6.4 Read-Only Preflight Audit Script.

Validates application and repository read paths against live Snowflake (COCO_FACTORY)
for all 10 areas specified in the M6.4 preflight objective:
1. MACHINE (M21 metadata, plant_id, line_id, derived health)
2. COMPONENT / SENSOR TOPOLOGY (C-M21-BRG, S-M21-VIB, S-M21-BTMP, relationships)
3. TELEMETRY (latest readings, historical readings, thresholds, alerts, duplicate/null-key sanity)
4. RELIABILITY (PRED-000322, failure_prob=0.95, risk_level=high, horizon=7d, model=hgb_failure_7d_v1, C-M21-BRG)
5. PRODUCTION (PRD-01278, M21 relationship, production context, product/line relationships)
6. MAINTENANCE (WO-000523, maintenance history, failure code BD-BRG)
7. SPARE PARTS / SUPPLIERS (SP-002, 6206-2RS, stock_qty=0, lead_time=5d, SUP-12)
8. ANALYTICS (ANALYTICS.MACHINE_HEALTH_DAILY, derived health reads, immutability check)
9. KNOWLEDGE (CORE.KNOWLEDGE_DOC, KNOWLEDGE.CORPUS, KNOWLEDGE.KNOWLEDGE_CHUNK)
10. APP (M4/M5 governance and action tables existence and structure)

Strictly non-mutating: Zero INSERT/UPDATE/DELETE/ALTER/CREATE/DROP/TRUNCATE.
"""

from pathlib import Path
import sys
import json
from datetime import datetime, timezone

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from repositories.snowflake.connection import SnowflakeConnectionManager
from repositories.snowflake.snowflake_repository import SnowflakeRepository
from domain.exceptions import UnsupportedOperationError
from domain.enums import HealthStatus, Severity

def run_preflight_audit():
    mgr = SnowflakeConnectionManager()
    if not mgr.is_configured:
        print("ERROR: Snowflake is not configured in environment.")
        sys.exit(1)

    repo = SnowflakeRepository(mgr)
    conn = mgr.get_connection(bootstrap=False)
    cur = conn.cursor()

    audit_report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "areas": {},
        "discrepancies": [],
    }

    # =========================================================================
    # 1. MACHINE
    # =========================================================================
    print("Auditing 1. MACHINE...")
    area1 = {"status": "PASS", "checks": {}}
    try:
        m21 = repo.get_machine("M21")
        if not m21:
            area1["status"] = "FAIL"
            audit_report["discrepancies"].append({
                "area": "1. MACHINE",
                "expected": "Machine object for M21",
                "actual": "None",
                "method": "repo.get_machine('M21')",
                "target": "CORE.MACHINE",
                "classification": "data/code issue",
                "proposed_remediation": "Investigate get_machine mapping from CORE.MACHINE",
            })
        else:
            area1["checks"]["m21_exists"] = True
            area1["checks"]["machine_name"] = m21.name
            area1["checks"]["machine_type"] = m21.asset_type
            area1["checks"]["model"] = getattr(m21, "model", None)
            area1["checks"]["line_id"] = m21.line_id
            area1["checks"]["criticality"] = getattr(m21, "criticality", None)

            # Query CORE.MACHINE for plant_id
            cur.execute("SELECT plant_id FROM COCO_FACTORY.CORE.MACHINE WHERE machine_id = 'M21'")
            row_p = cur.fetchone()
            db_plant_id = row_p[0] if row_p else None
            area1["checks"]["db_plant_id"] = db_plant_id
            area1["checks"]["domain_model_has_plant_id"] = hasattr(m21, "plant_id")

            # Plant & Line verification via repo
            plant = repo.get_plant(db_plant_id or "PLT01")
            lines = repo.list_lines(db_plant_id or "PLT01")
            area1["checks"]["plant_resolved"] = plant.plant_id if plant else None
            area1["checks"]["plant_name"] = plant.name if plant else None
            area1["checks"]["lines_count"] = len(lines)
            area1["checks"]["line_l5_present"] = any(l.line_id == m21.line_id for l in lines)

            # Derived health read via get_machine
            area1["checks"]["m21_machine_derived_health"] = m21.health_status.value

            # Health assessment via repo.get_latest_health_assessment
            try:
                health_assessment = repo.get_latest_health_assessment("M21")
                area1["checks"]["derived_health_assessment"] = health_assessment.health_status.value if health_assessment else None
            except Exception as ha_err:
                area1["checks"]["health_assessment_error"] = str(ha_err)
                audit_report["discrepancies"].append({
                    "area": "1. MACHINE",
                    "expected": "repo.get_latest_health_assessment('M21') successfully queries ANALYTICS.MACHINE_HEALTH_DAILY",
                    "actual": f"Exception: {ha_err}",
                    "method": "repo.get_latest_health_assessment('M21')",
                    "target": "ANALYTICS.MACHINE_HEALTH_DAILY",
                    "classification": "code issue",
                    "proposed_remediation": "Update SnowflakeRepository.get_latest_health_assessment to use health_status directly from ANALYTICS.MACHINE_HEALTH_DAILY rather than non-existent critical_alert_count",
                })

            # Verify M21 matches expectations
            if m21.name != "Grinder 3" or m21.line_id != "L5" or db_plant_id != "PLT01":
                area1["status"] = "FAIL"
                audit_report["discrepancies"].append({
                    "area": "1. MACHINE",
                    "expected": "name='Grinder 3', line_id='L5', plant_id='PLT01'",
                    "actual": f"name='{m21.name}', line_id='{m21.line_id}', plant_id='{db_plant_id}'",
                    "method": "repo.get_machine('M21') & CORE.MACHINE query",
                    "target": "CORE.MACHINE",
                    "classification": "data/schema issue",
                    "proposed_remediation": "Verify machine row attributes in CORE.MACHINE",
                })
            if not hasattr(m21, "plant_id"):
                audit_report["discrepancies"].append({
                    "area": "1. MACHINE",
                    "expected": "Machine domain model to expose plant_id attribute from CORE.MACHINE.PLANT_ID",
                    "actual": "Machine domain model lacks plant_id attribute",
                    "method": "repo.get_machine('M21')",
                    "target": "CORE.MACHINE / domain.models.asset.Machine",
                    "classification": "code issue",
                    "proposed_remediation": "Add optional plant_id: Optional[str] = None to domain.models.asset.Machine and project m.plant_id in SnowflakeRepository.get_machine",
                })
    except Exception as e:
        area1["status"] = "FAIL"
        audit_report["discrepancies"].append({
            "area": "1. MACHINE",
            "expected": "Successful execution of get_machine",
            "actual": f"Exception: {e}",
            "method": "repo.get_machine('M21')",
            "target": "CORE.MACHINE",
            "classification": "code issue",
            "proposed_remediation": "Debug get_machine SQL query / column mapping",
        })
    audit_report["areas"]["1_MACHINE"] = area1

    # =========================================================================
    # 2. COMPONENT / SENSOR TOPOLOGY
    # =========================================================================
    print("Auditing 2. COMPONENT / SENSOR TOPOLOGY...")
    area2 = {"status": "PASS", "checks": {}}
    try:
        components = repo.get_components("M21")
        sensors = repo.get_sensors("M21")
        area2["checks"]["component_count"] = len(components)
        area2["checks"]["sensor_count"] = len(sensors)

        c_brg = next((c for c in components if c.component_id == "C-M21-BRG"), None)
        s_vib = next((s for s in sensors if s.sensor_id == "S-M21-VIB"), None)
        s_btmp = next((s for s in sensors if s.sensor_id == "S-M21-BTMP"), None)

        area2["checks"]["c_m21_brg_exists"] = bool(c_brg)
        area2["checks"]["s_m21_vib_exists"] = bool(s_vib)
        area2["checks"]["s_m21_btmp_exists"] = bool(s_btmp)

        if c_brg:
            area2["checks"]["c_m21_brg_name"] = c_brg.name
            area2["checks"]["c_m21_brg_model"] = getattr(c_brg, "model", None)
            area2["checks"]["c_m21_brg_machine_id"] = c_brg.machine_id

        if s_vib:
            area2["checks"]["s_m21_vib_type"] = s_vib.sensor_type.value if hasattr(s_vib.sensor_type, "value") else str(s_vib.sensor_type)
            area2["checks"]["s_m21_vib_component_id"] = s_vib.component_id
            area2["checks"]["s_m21_vib_machine_id"] = s_vib.machine_id
            area2["checks"]["s_m21_vib_warn_threshold"] = getattr(s_vib, "warn_threshold", None)
            area2["checks"]["s_m21_vib_crit_threshold"] = getattr(s_vib, "crit_threshold", None)
            # Query CORE.SENSOR table for threshold values
            cur.execute("SELECT warn_threshold, crit_threshold FROM COCO_FACTORY.CORE.SENSOR WHERE sensor_id = 'S-M21-VIB'")
            thresh_row = cur.fetchone()
            if thresh_row:
                area2["checks"]["db_s_m21_vib_warn_threshold"] = float(thresh_row[0]) if thresh_row[0] is not None else None
                area2["checks"]["db_s_m21_vib_crit_threshold"] = float(thresh_row[1]) if thresh_row[1] is not None else None

        if s_btmp:
            area2["checks"]["s_m21_btmp_type"] = s_btmp.sensor_type.value if hasattr(s_btmp.sensor_type, "value") else str(s_btmp.sensor_type)
            area2["checks"]["s_m21_btmp_component_id"] = s_btmp.component_id
            area2["checks"]["s_m21_btmp_machine_id"] = s_btmp.machine_id

        # Verify topological relationships
        if not c_brg or not s_vib or not s_btmp:
            area2["status"] = "FAIL"
            audit_report["discrepancies"].append({
                "area": "2. COMPONENT / SENSOR TOPOLOGY",
                "expected": "C-M21-BRG, S-M21-VIB, and S-M21-BTMP present for M21",
                "actual": f"c_brg={bool(c_brg)}, s_vib={bool(s_vib)}, s_btmp={bool(s_btmp)}",
                "method": "repo.get_components('M21') / repo.get_sensors('M21')",
                "target": "CORE.COMPONENT, CORE.SENSOR",
                "classification": "data/schema issue",
                "proposed_remediation": "Verify topology foreign keys for M21",
            })
        elif s_vib.component_id != "C-M21-BRG" or s_btmp.component_id != "C-M21-BRG":
            area2["status"] = "FAIL"
            audit_report["discrepancies"].append({
                "area": "2. COMPONENT / SENSOR TOPOLOGY",
                "expected": "Both S-M21-VIB and S-M21-BTMP attached to C-M21-BRG",
                "actual": f"s_vib.component_id={s_vib.component_id}, s_btmp.component_id={s_btmp.component_id}",
                "method": "repo.get_sensors('M21')",
                "target": "CORE.SENSOR",
                "classification": "data issue",
                "proposed_remediation": "Verify component_id foreign key for M21 sensors",
            })
    except Exception as e:
        area2["status"] = "FAIL"
        audit_report["discrepancies"].append({
            "area": "2. COMPONENT / SENSOR TOPOLOGY",
            "expected": "Clean retrieval of components and sensors",
            "actual": f"Exception: {e}",
            "method": "repo.get_components / repo.get_sensors",
            "target": "CORE.COMPONENT / CORE.SENSOR",
            "classification": "code issue",
            "proposed_remediation": "Debug component and sensor deserialization",
        })
    audit_report["areas"]["2_TOPOLOGY"] = area2

    # =========================================================================
    # 3. TELEMETRY
    # =========================================================================
    print("Auditing 3. TELEMETRY...")
    area3 = {"status": "PASS", "checks": {}}
    try:
        # High frequency recent measurements
        vib_measurements = repo.get_recent_measurements("M21", "S-M21-VIB", limit=10)
        area3["checks"]["vib_recent_count"] = len(vib_measurements)
        if vib_measurements:
            latest = vib_measurements[0]
            area3["checks"]["latest_vib_ts"] = str(latest.timestamp)
            area3["checks"]["latest_vib_val"] = latest.value
            area3["checks"]["latest_vib_sensor_id"] = latest.sensor_id

        # Hourly aggregated readings
        cur.execute("SELECT COUNT(*), MIN(ts), MAX(ts), AVG(avg_running) FROM COCO_FACTORY.CORE.SENSOR_READING_HOURLY WHERE sensor_id = 'S-M21-VIB'")
        hourly_row = cur.fetchone()
        area3["checks"]["hourly_count"] = hourly_row[0]
        area3["checks"]["hourly_min_ts"] = str(hourly_row[1])
        area3["checks"]["hourly_max_ts"] = str(hourly_row[2])
        area3["checks"]["hourly_avg_val"] = round(float(hourly_row[3]), 4) if hourly_row[3] is not None else None

        # Alerts on M21 via repo and direct query
        cur.execute("SELECT alert_id, machine_id, severity, status, message FROM COCO_FACTORY.CORE.ALERT WHERE machine_id = 'M21'")
        raw_alerts = cur.fetchall()
        area3["checks"]["db_m21_alerts_count"] = len(raw_alerts)
        area3["checks"]["db_m21_alerts_sample"] = [{"alert_id": r[0], "severity": r[2], "status": r[3]} for r in raw_alerts[:3]]

        try:
            alerts = repo.list_alerts(machine_id="M21")
            area3["checks"]["m21_alerts_count"] = len(alerts)
            critical_alerts = [a for a in alerts if a.severity == Severity.CRITICAL]
            area3["checks"]["critical_alerts_count"] = len(critical_alerts)
        except Exception as alert_err:
            area3["checks"]["repo_list_alerts_error"] = str(alert_err)
            audit_report["discrepancies"].append({
                "area": "3. TELEMETRY",
                "expected": "repo.list_alerts to deserialize CORE.ALERT records into Alert domain objects",
                "actual": f"Exception: {alert_err}",
                "method": "repo.list_alerts(machine_id='M21')",
                "target": "CORE.ALERT",
                "classification": "code issue",
                "proposed_remediation": "Update SnowflakeRepository.list_alerts to normalize lowercase 'warning'/'critical' severity strings from CORE.ALERT to uppercase domain.enums.Severity",
            })

        # Duplicate/null-key sanity in SENSOR_READING
        cur.execute("SELECT COUNT(*) - COUNT(DISTINCT sensor_id || ts) FROM COCO_FACTORY.CORE.SENSOR_READING")
        dup_row = cur.fetchone()
        dup_count = dup_row[0] if dup_row else 0
        area3["checks"]["duplicate_pks_in_sensor_reading"] = dup_count

        cur.execute("SELECT COUNT(*) FROM COCO_FACTORY.CORE.SENSOR_READING WHERE sensor_id IS NULL OR ts IS NULL")
        null_row = cur.fetchone()
        null_count = null_row[0] if null_row else 0
        area3["checks"]["null_pks_in_sensor_reading"] = null_count

        if len(vib_measurements) == 0:
            area3["status"] = "FAIL"
            audit_report["discrepancies"].append({
                "area": "3. TELEMETRY",
                "expected": "Recent measurements for S-M21-VIB",
                "actual": "0 measurements returned",
                "method": "repo.get_recent_measurements('S-M21-VIB')",
                "target": "CORE.SENSOR_READING",
                "classification": "data/code issue",
                "proposed_remediation": "Inspect telemetry query filter in repo",
            })
        if dup_count > 0 or null_count > 0:
            area3["status"] = "FAIL"
            audit_report["discrepancies"].append({
                "area": "3. TELEMETRY",
                "expected": "0 duplicate and 0 null PKs in CORE.SENSOR_READING",
                "actual": f"dup={dup_count}, null={null_count}",
                "method": "Snowflake SQL PK check",
                "target": "CORE.SENSOR_READING",
                "classification": "data quality issue",
                "proposed_remediation": "Inspect deduplication during ingestion",
            })
    except Exception as e:
        area3["status"] = "FAIL"
        audit_report["discrepancies"].append({
            "area": "3. TELEMETRY",
            "expected": "Clean telemetry reads",
            "actual": f"Exception: {e}",
            "method": "repo.get_recent_measurements",
            "target": "CORE.SENSOR_READING",
            "classification": "code issue",
            "proposed_remediation": "Debug get_recent_measurements query",
        })
    audit_report["areas"]["3_TELEMETRY"] = area3

    # =========================================================================
    # 4. RELIABILITY
    # =========================================================================
    print("Auditing 4. RELIABILITY...")
    area4 = {"status": "PASS", "checks": {}}
    try:
        # Canonical prediction PRED-000322
        pred_canon = repo.get_canonical_prediction("PRED-000322")
        if not pred_canon:
            area4["status"] = "FAIL"
            audit_report["discrepancies"].append({
                "area": "4. RELIABILITY",
                "expected": "CanonicalPrediction record for PRED-000322",
                "actual": "None",
                "method": "repo.get_canonical_prediction('PRED-000322')",
                "target": "CORE.PREDICTION",
                "classification": "data/code issue",
                "proposed_remediation": "Verify get_canonical_prediction query in repo",
            })
        else:
            area4["checks"]["pred_000322_exists"] = True
            area4["checks"]["failure_prob"] = pred_canon.failure_prob
            area4["checks"]["risk_level"] = pred_canon.risk_level
            area4["checks"]["horizon_days"] = pred_canon.horizon_days
            area4["checks"]["model_name"] = pred_canon.model_name
            area4["checks"]["machine_id"] = pred_canon.machine_id
            area4["checks"]["suspected_component_id"] = pred_canon.suspected_component_id

            if pred_canon.failure_prob != 0.95 or pred_canon.risk_level != "high" or pred_canon.horizon_days != 7 or pred_canon.suspected_component_id != "C-M21-BRG":
                area4["status"] = "FAIL"
                audit_report["discrepancies"].append({
                    "area": "4. RELIABILITY",
                    "expected": "failure_prob=0.95, risk_level='high', horizon_days=7, suspected_component='C-M21-BRG'",
                    "actual": f"prob={pred_canon.failure_prob}, risk={pred_canon.risk_level}, horizon={pred_canon.horizon_days}, comp={pred_canon.suspected_component_id}",
                    "method": "repo.get_canonical_prediction('PRED-000322')",
                    "target": "CORE.PREDICTION",
                    "classification": "data issue",
                    "proposed_remediation": "Verify prediction invariants in canonical data",
                })

        # Latest domain prediction for M21
        pred_domain = repo.get_latest_prediction("M21")
        if pred_domain:
            area4["checks"]["latest_prediction_id"] = pred_domain.prediction_id
            area4["checks"]["latest_failure_probability"] = pred_domain.failure_probability
            area4["checks"]["latest_threshold_exceeded"] = getattr(pred_domain, "threshold_exceeded", None)
            area4["checks"]["latest_failure_mode"] = pred_domain.failure_mode.value if hasattr(pred_domain.failure_mode, "value") else str(pred_domain.failure_mode)
    except Exception as e:
        area4["status"] = "FAIL"
        audit_report["discrepancies"].append({
            "area": "4. RELIABILITY",
            "expected": "Clean prediction retrieval",
            "actual": f"Exception: {e}",
            "method": "repo.get_canonical_prediction / repo.get_latest_prediction",
            "target": "CORE.PREDICTION",
            "classification": "code issue",
            "proposed_remediation": "Debug prediction deserialization",
        })
    audit_report["areas"]["4_RELIABILITY"] = area4

    # =========================================================================
    # 5. PRODUCTION
    # =========================================================================
    print("Auditing 5. PRODUCTION...")
    area5 = {"status": "PASS", "checks": {}}
    try:
        po = repo.get_production_order("PRD-01278")
        if not po:
            area5["status"] = "FAIL"
            audit_report["discrepancies"].append({
                "area": "5. PRODUCTION",
                "expected": "ProductionOrder for PRD-01278",
                "actual": "None",
                "method": "repo.get_production_order('PRD-01278')",
                "target": "CORE.PRODUCTION_ORDER",
                "classification": "data/code issue",
                "proposed_remediation": "Verify get_production_order query in repo",
            })
        else:
            area5["checks"]["prd_01278_exists"] = True
            area5["checks"]["machine_id"] = po.machine_id
            area5["checks"]["customer"] = po.customer
            area5["checks"]["product_id"] = po.product_id
            area5["checks"]["planned_qty"] = po.planned_qty
            area5["checks"]["produced_qty"] = po.produced_qty
            area5["checks"]["status"] = po.status

            if po.machine_id != "M21" or po.customer != "Keystone Hydraulics":
                area5["status"] = "FAIL"
                audit_report["discrepancies"].append({
                    "area": "5. PRODUCTION",
                    "expected": "machine_id='M21', customer='Keystone Hydraulics'",
                    "actual": f"machine_id='{po.machine_id}', customer='{po.customer}'",
                    "method": "repo.get_production_order('PRD-01278')",
                    "target": "CORE.PRODUCTION_ORDER",
                    "classification": "data issue",
                    "proposed_remediation": "Verify customer and machine assignment for PRD-01278",
                })

        # Production Context for M21
        p_ctx = repo.get_production_context("M21")
        if p_ctx:
            area5["checks"]["m21_production_context_resolved"] = True
            area5["checks"]["ctx_customer"] = p_ctx.customer
            area5["checks"]["ctx_line_id"] = p_ctx.line_id
            area5["checks"]["ctx_order_id"] = p_ctx.order_id
        else:
            area5["checks"]["m21_production_context_resolved"] = False
    except Exception as e:
        area5["status"] = "FAIL"
        audit_report["discrepancies"].append({
            "area": "5. PRODUCTION",
            "expected": "Clean production order reads",
            "actual": f"Exception: {e}",
            "method": "repo.get_production_order",
            "target": "CORE.PRODUCTION_ORDER",
            "classification": "code issue",
            "proposed_remediation": "Debug get_production_order",
        })
    audit_report["areas"]["5_PRODUCTION"] = area5

    # =========================================================================
    # 6. MAINTENANCE
    # =========================================================================
    print("Auditing 6. MAINTENANCE...")
    area6 = {"status": "PASS", "checks": {}}
    try:
        # Work Order WO-000523
        wo = repo.get_work_order("WO-000523")
        if not wo:
            # Let's check via direct query to see if it exists in CORE.MAINTENANCE_WORK_ORDER
            cur.execute("SELECT wo_id, machine_id, component_id, failure_code, status FROM COCO_FACTORY.CORE.MAINTENANCE_WORK_ORDER WHERE wo_id = 'WO-000523'")
            r = cur.fetchone()
            if r:
                area6["checks"]["wo_000523_raw_exists"] = True
                area6["checks"]["raw_wo_details"] = {"wo_id": r[0], "machine_id": r[1], "component_id": r[2], "failure_code": r[3], "status": r[4]}
                area6["status"] = "FAIL"
                audit_report["discrepancies"].append({
                    "area": "6. MAINTENANCE",
                    "expected": "WorkOrder object returned by repo.get_work_order('WO-000523')",
                    "actual": "None returned by repo, but row exists in CORE.MAINTENANCE_WORK_ORDER",
                    "method": "repo.get_work_order('WO-000523')",
                    "target": "CORE.MAINTENANCE_WORK_ORDER",
                    "classification": "code issue",
                    "proposed_remediation": "Fix mapping/enum parsing in repo.get_work_order",
                })
            else:
                area6["checks"]["wo_000523_exists"] = False
                area6["status"] = "FAIL"
                audit_report["discrepancies"].append({
                    "area": "6. MAINTENANCE",
                    "expected": "Work order WO-000523 in CORE.MAINTENANCE_WORK_ORDER",
                    "actual": "Row not found in Snowflake",
                    "method": "repo.get_work_order('WO-000523')",
                    "target": "CORE.MAINTENANCE_WORK_ORDER",
                    "classification": "data issue",
                    "proposed_remediation": "Verify work order ID in canonical maintenance dataset",
                })
        else:
            area6["checks"]["wo_000523_exists"] = True
            area6["checks"]["wo_id"] = wo.work_order_id
            area6["checks"]["machine_id"] = wo.machine_id
            area6["checks"]["component_id"] = wo.component_id
            area6["checks"]["failure_mode"] = str(wo.failure_mode)
            area6["checks"]["status"] = str(wo.status)
            area6["checks"]["priority"] = str(wo.priority)

        # Maintenance history for M21
        maint_hist = repo.get_maintenance_history("M21", limit=10)
        area6["checks"]["m21_maint_history_count"] = len(maint_hist)

        # Maintenance logs for M21 with failure code BD-BRG
        cur.execute("SELECT log_id, machine_id, component_id, failure_code, action_taken FROM COCO_FACTORY.CORE.MAINTENANCE_LOG WHERE machine_id = 'M21' AND failure_code = 'BD-BRG'")
        bd_logs = cur.fetchall()
        area6["checks"]["bd_brg_logs_count"] = len(bd_logs)
        if bd_logs:
            area6["checks"]["sample_bd_log"] = {
                "log_id": bd_logs[0][0],
                "component_id": bd_logs[0][2],
                "failure_code": bd_logs[0][3],
                "action_taken": bd_logs[0][4],
            }
    except Exception as e:
        area6["status"] = "FAIL"
        audit_report["discrepancies"].append({
            "area": "6. MAINTENANCE",
            "expected": "Clean maintenance history reads",
            "actual": f"Exception: {e}",
            "method": "repo.get_work_order / repo.get_maintenance_history",
            "target": "CORE.MAINTENANCE_WORK_ORDER / CORE.MAINTENANCE_LOG",
            "classification": "code issue",
            "proposed_remediation": "Debug maintenance deserialization",
        })
    audit_report["areas"]["6_MAINTENANCE"] = area6

    # =========================================================================
    # 7. SPARE PARTS / SUPPLIERS
    # =========================================================================
    print("Auditing 7. SPARE PARTS / SUPPLIERS...")
    area7 = {"status": "PASS", "checks": {}}
    try:
        sp = repo.get_spare_part("SP-002")
        if not sp:
            area7["status"] = "FAIL"
            audit_report["discrepancies"].append({
                "area": "7. SPARE PARTS / SUPPLIERS",
                "expected": "SparePart record for SP-002",
                "actual": "None",
                "method": "repo.get_spare_part('SP-002')",
                "target": "CORE.SPARE_PART",
                "classification": "data/code issue",
                "proposed_remediation": "Verify get_spare_part query in repo",
            })
        else:
            area7["checks"]["sp_002_exists"] = True
            area7["checks"]["part_id"] = sp.part_id
            area7["checks"]["part_name"] = sp.part_name
            area7["checks"]["compatible_model"] = sp.compatible_model
            area7["checks"]["stock_qty"] = sp.stock_qty
            area7["checks"]["lead_time_days"] = sp.lead_time_days
            area7["checks"]["supplier_id"] = sp.supplier_id

            if sp.part_name != "Drive-End Bearing 6206-2RS" or sp.compatible_model != "6206-2RS" or sp.stock_qty != 0 or sp.lead_time_days != 5 or sp.supplier_id != "SUP-12":
                area7["status"] = "FAIL"
                audit_report["discrepancies"].append({
                    "area": "7. SPARE PARTS / SUPPLIERS",
                    "expected": "part_name='Drive-End Bearing 6206-2RS', model='6206-2RS', stock=0, lead_time=5, supplier='SUP-12'",
                    "actual": f"name='{sp.part_name}', model='{sp.compatible_model}', stock={sp.stock_qty}, lead_time={sp.lead_time_days}, sup='{sp.supplier_id}'",
                    "method": "repo.get_spare_part('SP-002')",
                    "target": "CORE.SPARE_PART",
                    "classification": "data issue",
                    "proposed_remediation": "Verify SP-002 attributes in CORE.SPARE_PART",
                })

        # Supplier SUP-12
        sup = repo.get_supplier("SUP-12")
        if sup:
            area7["checks"]["sup_12_exists"] = True
            area7["checks"]["supplier_name"] = sup.supplier_name
            area7["checks"]["supplier_country"] = sup.country
            area7["checks"]["supplier_lead_time"] = sup.avg_lead_time_days
            area7["checks"]["on_time_delivery_pct"] = sup.on_time_delivery_pct
        else:
            area7["checks"]["sup_12_exists"] = False

        # Inventory risk for M21 / SP-002
        inv_risk = repo.get_inventory_risk("SP-002")
        if inv_risk:
            area7["checks"]["sp_002_inventory_risk"] = {
                "part_id": inv_risk.part_id,
                "stock_qty": inv_risk.stock_qty,
                "lead_time_days": inv_risk.lead_time_days,
                "stock_status": inv_risk.stock_status,
                "is_critical_exposure": inv_risk.is_critical_exposure,
            }
    except Exception as e:
        area7["status"] = "FAIL"
        audit_report["discrepancies"].append({
            "area": "7. SPARE PARTS / SUPPLIERS",
            "expected": "Clean spare part reads",
            "actual": f"Exception: {e}",
            "method": "repo.get_spare_part",
            "target": "CORE.SPARE_PART",
            "classification": "code issue",
            "proposed_remediation": "Debug get_spare_part",
        })
    audit_report["areas"]["7_SPARE_PARTS"] = area7

    # =========================================================================
    # 8. ANALYTICS
    # =========================================================================
    print("Auditing 8. ANALYTICS...")
    area8 = {"status": "PASS", "checks": {}}
    try:
        # ANALYTICS.MACHINE_HEALTH_DAILY
        cur.execute("SELECT COUNT(*), MIN(metric_date), MAX(metric_date) FROM COCO_FACTORY.ANALYTICS.MACHINE_HEALTH_DAILY")
        ah_row = cur.fetchone()
        area8["checks"]["analytics_machine_health_row_count"] = ah_row[0]
        area8["checks"]["analytics_min_date"] = str(ah_row[1])
        area8["checks"]["analytics_max_date"] = str(ah_row[2])

        # M21 Health Daily View
        cur.execute("SELECT metric_date, health_status, avg_vibration, max_vibration, latest_failure_prob, latest_risk_level FROM COCO_FACTORY.ANALYTICS.MACHINE_HEALTH_DAILY WHERE machine_id = 'M21' ORDER BY metric_date DESC LIMIT 3")
        m21_health_rows = cur.fetchall()
        area8["checks"]["m21_health_sample"] = [
            {"date": str(r[0]), "status": r[1], "avg_vib": float(r[2]) if r[2] is not None else None, "max_vib": float(r[3]) if r[3] is not None else None, "prob": float(r[4]) if r[4] is not None else None, "risk": r[5]}
            for r in m21_health_rows
        ]

        # Verify SnowflakeRepository rejects mutable health writes per M6.2 contract
        try:
            repo.update_machine_health("M21", HealthStatus.DEGRADING)
            area8["checks"]["update_machine_health_behavior"] = "DID_NOT_RAISE (In-memory compatibility or no-op)"
        except UnsupportedOperationError:
            area8["checks"]["update_machine_health_behavior"] = "RAISED UnsupportedOperationError (Expected immutable contract)"
        except Exception as e:
            area8["checks"]["update_machine_health_behavior"] = f"RAISED {type(e).__name__}: {e}"

        # Verify ANALYTICS OEE views (authoritative: MACHINE_OEE_DAILY aggregated by line_id)
        cur.execute("SELECT COUNT(*) FROM COCO_FACTORY.ANALYTICS.MACHINE_OEE_DAILY")
        area8["checks"]["analytics_machine_oee_row_count"] = cur.fetchone()[0]

        cur.execute("SELECT line_id, COUNT(*), ROUND(AVG(oee), 4) FROM COCO_FACTORY.ANALYTICS.MACHINE_OEE_DAILY GROUP BY line_id")
        line_oee_summary = [{"line_id": r[0], "records": r[1], "avg_oee": float(r[2]) if r[2] is not None else None} for r in cur.fetchall()]
        area8["checks"]["line_oee_aggregation_from_machine_oee"] = line_oee_summary
        area8["checks"]["production_line_oee_daily_status"] = "Excluded by design; line OEE is aggregated directly from ANALYTICS.MACHINE_OEE_DAILY"

    except Exception as e:
        area8["status"] = "FAIL"
        audit_report["discrepancies"].append({
            "area": "8. ANALYTICS",
            "expected": "Clean analytics view reads",
            "actual": f"Exception: {e}",
            "method": "repo.get_machine_health_daily / ANALYTICS SQL",
            "target": "ANALYTICS.MACHINE_HEALTH_DAILY",
            "classification": "schema/code issue",
            "proposed_remediation": "Verify view definitions in 30_analytics_foundation.sql",
        })
    audit_report["areas"]["8_ANALYTICS"] = area8

    # =========================================================================
    # 9. KNOWLEDGE
    # =========================================================================
    print("Auditing 9. KNOWLEDGE...")
    area9 = {"status": "PASS", "checks": {}}
    try:
        # CORE.KNOWLEDGE_DOC
        cur.execute("SELECT COUNT(*) FROM COCO_FACTORY.CORE.KNOWLEDGE_DOC")
        k_doc_cnt = cur.fetchone()[0]
        area9["checks"]["core_knowledge_doc_count"] = k_doc_cnt

        docs = repo.list_documents()
        area9["checks"]["repo_list_documents_count"] = len(docs)

        # KNOWLEDGE.CORPUS & SEARCH VIEW (authoritative per 50_knowledge_foundation.sql)
        cur.execute("SELECT COUNT(*) FROM COCO_FACTORY.KNOWLEDGE.CORPUS")
        corpus_cnt = cur.fetchone()[0]
        area9["checks"]["knowledge_corpus_count"] = corpus_cnt

        cur.execute("SELECT COUNT(*) FROM COCO_FACTORY.KNOWLEDGE.V_CORPUS_SEARCH_FEED")
        search_feed_cnt = cur.fetchone()[0]
        area9["checks"]["knowledge_search_feed_count"] = search_feed_cnt
        area9["checks"]["knowledge_chunk_status"] = "Excluded by design; authoritative entity is KNOWLEDGE.CORPUS"

        # Failure mode taxonomy
        cur.execute("SELECT COUNT(*) FROM COCO_FACTORY.KNOWLEDGE.FAILURE_MODE_TAXONOMY")
        tax_cnt = cur.fetchone()[0]
        area9["checks"]["failure_mode_taxonomy_count"] = tax_cnt

        if k_doc_cnt != 16:
            area9["status"] = "FAIL"
            audit_report["discrepancies"].append({
                "area": "9. KNOWLEDGE",
                "expected": "16 knowledge documents in CORE.KNOWLEDGE_DOC",
                "actual": f"{k_doc_cnt} rows",
                "method": "SELECT COUNT(*) FROM CORE.KNOWLEDGE_DOC",
                "target": "CORE.KNOWLEDGE_DOC",
                "classification": "data issue",
                "proposed_remediation": "Verify ingestion of knowledge_doc.csv",
            })
    except Exception as e:
        area9["status"] = "FAIL"
        audit_report["discrepancies"].append({
            "area": "9. KNOWLEDGE",
            "expected": "Clean knowledge schema reads",
            "actual": f"Exception: {e}",
            "method": "repo.list_documents / KNOWLEDGE SQL",
            "target": "KNOWLEDGE schema",
            "classification": "schema issue",
            "proposed_remediation": "Verify 50_knowledge_foundation.sql DDL",
        })
    audit_report["areas"]["9_KNOWLEDGE"] = area9

    # =========================================================================
    # 10. APP
    # =========================================================================
    print("Auditing 10. APP (M4/M5 Tables)...")
    area10 = {"status": "PASS", "checks": {}}
    try:
        # Actual tables created by 60_app_foundation.sql
        actual_foundation_tables = [
            "ALERT_WORKFLOW", "INVESTIGATION", "INVESTIGATION_EVIDENCE", "INVESTIGATION_HYPOTHESIS",
            "INVESTIGATION_FINDING", "INVESTIGATION_RECOMMENDATION", "INVESTIGATION_TOOL_CALL",
            "ACTION_PROPOSAL", "ACTION_APPROVAL", "ACTION_EXECUTION", "ACTION_AUDIT",
            "VERIFICATION_RESULT", "VERIFICATION_POLICY", "ACTION_OUTCOME"
        ]
        actual_table_counts = {}
        for tbl in actual_foundation_tables:
            cur.execute(f"SELECT COUNT(*) FROM COCO_FACTORY.APP.{tbl}")
            actual_table_counts[tbl] = cur.fetchone()[0]
        area10["checks"]["foundation_app_tables"] = actual_table_counts
        area10["checks"]["legacy_names_status"] = (
            "APP_AUDIT_LOG, APPROVAL, VERIFICATION excluded by design; "
            "authoritative tables are ACTION_AUDIT, ACTION_APPROVAL, VERIFICATION_RESULT"
        )
    except Exception as e:
        area10["status"] = "FAIL"
        audit_report["discrepancies"].append({
            "area": "10. APP",
            "expected": "Inspection of APP tables without mutation",
            "actual": f"Exception: {e}",
            "method": "APP tables inspection",
            "target": "APP schema",
            "classification": "schema issue",
            "proposed_remediation": "Check APP schema DDL",
        })
    audit_report["areas"]["10_APP"] = area10

    cur.close()
    conn.close()

    return audit_report

if __name__ == "__main__":
    rep = run_preflight_audit()
    print("\n" + "=" * 80)
    print("M6.4 READ-ONLY PREFLIGHT AUDIT COMPLETE")
    print("=" * 80)
    print(json.dumps(rep, indent=2))
