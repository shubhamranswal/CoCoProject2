-- 30_analytics_foundation.sql
-- Analytics Foundation Views for reporting, OEE, machine health, and inventory risk

USE DATABASE COCO_FACTORY;
USE SCHEMA ANALYTICS;

-- 1. Machine OEE Daily View
CREATE OR REPLACE VIEW MACHINE_OEE_DAILY AS
SELECT
    pr.machine_id,
    m.machine_name,
    m.line_id,
    pr.shift_date AS metric_date,
    COUNT(DISTINCT pr.run_id) AS total_runs,
    SUM(pr.planned_time_min) AS total_planned_time_min,
    SUM(pr.run_time_min) AS total_run_time_min,
    SUM(pr.unplanned_downtime_min) AS total_unplanned_downtime_min,
    SUM(pr.total_count) AS total_units_produced,
    SUM(pr.good_count) AS total_good_units,
    SUM(pr.reject_count) AS total_reject_units,
    -- Availability: Run Time / Planned Time
    ROUND(
        CASE WHEN SUM(pr.planned_time_min) > 0
             THEN LEAST(1.0, GREATEST(0.0, SUM(pr.run_time_min) / SUM(pr.planned_time_min)))
             ELSE 1.0 END, 4
    ) AS availability,
    -- Performance: (Total Count * Ideal Cycle Time Sec) / (Run Time Min * 60)
    ROUND(
        CASE WHEN SUM(pr.run_time_min) > 0
             THEN LEAST(1.0, GREATEST(0.0, (SUM(pr.total_count * pr.ideal_cycle_time_sec) / (SUM(pr.run_time_min) * 60.0))))
             ELSE 1.0 END, 4
    ) AS performance,
    -- Quality: Good Count / Total Count
    ROUND(
        CASE WHEN SUM(pr.total_count) > 0
             THEN LEAST(1.0, GREATEST(0.0, CAST(SUM(pr.good_count) AS FLOAT) / SUM(pr.total_count)))
             ELSE 1.0 END, 4
    ) AS quality,
    -- Overall OEE: Availability * Performance * Quality
    ROUND(
        (CASE WHEN SUM(pr.planned_time_min) > 0 THEN LEAST(1.0, GREATEST(0.0, SUM(pr.run_time_min) / SUM(pr.planned_time_min))) ELSE 1.0 END) *
        (CASE WHEN SUM(pr.run_time_min) > 0 THEN LEAST(1.0, GREATEST(0.0, (SUM(pr.total_count * pr.ideal_cycle_time_sec) / (SUM(pr.run_time_min) * 60.0)))) ELSE 1.0 END) *
        (CASE WHEN SUM(pr.total_count) > 0 THEN LEAST(1.0, GREATEST(0.0, CAST(SUM(pr.good_count) AS FLOAT) / SUM(pr.total_count))) ELSE 1.0 END), 4
    ) AS oee
FROM COCO_FACTORY.CORE.PRODUCTION_RUN pr
JOIN COCO_FACTORY.CORE.MACHINE m ON pr.machine_id = m.machine_id
GROUP BY pr.machine_id, m.machine_name, m.line_id, pr.shift_date;

-- 2. Machine Health Daily View
CREATE OR REPLACE VIEW MACHINE_HEALTH_DAILY AS
SELECT
    m.machine_id,
    m.machine_name,
    m.line_id,
    m.criticality,
    COALESCE(p.latest_failure_prob, 0.0) AS max_failure_probability_7d,
    COALESCE(p.risk_level, 'LOW') AS risk_level,
    COALESCE(a.open_alert_count, 0) AS open_alerts,
    COALESCE(a.critical_alert_count, 0) AS critical_alerts,
    COALESCE(d.downtime_minutes_30d, 0.0) AS downtime_minutes_30d,
    CASE
        WHEN COALESCE(p.latest_failure_prob, 0.0) >= 0.85 OR COALESCE(a.critical_alert_count, 0) > 0 THEN 'CRITICAL'
        WHEN COALESCE(p.latest_failure_prob, 0.0) >= 0.60 OR COALESCE(a.open_alert_count, 0) > 0 THEN 'WARNING'
        ELSE 'HEALTHY'
    END AS operational_health_status
FROM COCO_FACTORY.CORE.MACHINE m
LEFT JOIN (
    SELECT
        machine_id,
        failure_prob AS latest_failure_prob,
        risk_level,
        ROW_NUMBER() OVER (PARTITION BY machine_id ORDER BY scored_ts DESC) AS rn
    FROM COCO_FACTORY.CORE.PREDICTION
) p ON m.machine_id = p.machine_id AND p.rn = 1
LEFT JOIN (
    SELECT
        machine_id,
        COUNT(*) AS open_alert_count,
        COUNT(CASE WHEN severity = 'CRITICAL' THEN 1 END) AS critical_alert_count
    FROM COCO_FACTORY.CORE.ALERT
    WHERE status IN ('ACTIVE', 'OPEN', 'UNACKNOWLEDGED')
    GROUP BY machine_id
) a ON m.machine_id = a.machine_id
LEFT JOIN (
    SELECT
        machine_id,
        SUM(duration_min) AS downtime_minutes_30d
    FROM COCO_FACTORY.CORE.DOWNTIME_EVENT
    GROUP BY machine_id
) d ON m.machine_id = d.machine_id;

-- 3. Inventory Risk View
CREATE OR REPLACE VIEW INVENTORY_RISK AS
SELECT
    sp.part_id,
    sp.part_name,
    sp.part_category,
    sp.compatible_model,
    sp.stock_qty,
    sp.reorder_level,
    sp.reorder_qty,
    sp.lead_time_days,
    sp.warehouse_bin,
    s.supplier_id,
    s.supplier_name,
    s.on_time_delivery_pct,
    CASE
        WHEN sp.stock_qty = 0 THEN 'STOCKOUT'
        WHEN sp.stock_qty <= sp.reorder_level THEN 'BELOW_REORDER'
        ELSE 'SUFFICIENT'
    END AS stock_status,
    COALESCE(po_open.pending_order_qty, 0) AS pending_order_qty
FROM COCO_FACTORY.CORE.SPARE_PART sp
LEFT JOIN COCO_FACTORY.CORE.SUPPLIER s ON sp.supplier_id = s.supplier_id
LEFT JOIN (
    SELECT
        part_id,
        SUM(qty) AS pending_order_qty
    FROM COCO_FACTORY.CORE.PURCHASE_ORDER
    WHERE status IN ('PENDING', 'ORDERED', 'IN_TRANSIT')
    GROUP BY part_id
) po_open ON sp.part_id = po_open.part_id;

-- 4. Alert Summary View
CREATE OR REPLACE VIEW ALERT_SUMMARY AS
SELECT
    a.machine_id,
    m.machine_name,
    m.line_id,
    a.severity,
    a.status,
    a.alert_type,
    COUNT(*) AS alert_count,
    MIN(a.ts) AS first_triggered_at,
    MAX(a.ts) AS last_triggered_at
FROM COCO_FACTORY.CORE.ALERT a
JOIN COCO_FACTORY.CORE.MACHINE m ON a.machine_id = m.machine_id
GROUP BY a.machine_id, m.machine_name, m.line_id, a.severity, a.status, a.alert_type;
