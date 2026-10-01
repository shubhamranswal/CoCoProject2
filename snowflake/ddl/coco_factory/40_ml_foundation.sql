-- 40_ml_foundation.sql
-- Milestone 2 ML Feature Store & Model Registry Foundation

USE DATABASE COCO_FACTORY;
USE SCHEMA ML;

-- 1. Model Registry Metadata
CREATE TABLE IF NOT EXISTS MODEL_REGISTRY (
    model_id                    VARCHAR(64) NOT NULL,
    model_name                  VARCHAR(128) NOT NULL,
    model_version               VARCHAR(32) NOT NULL,
    version                     VARCHAR(32),
    algorithm                   VARCHAR(64) NOT NULL,
    training_dataset_version    VARCHAR(64) NOT NULL DEFAULT 'v2026.03-canonical',
    feature_version             VARCHAR(32) NOT NULL DEFAULT 'v1.0-29feat',
    target_definition           VARCHAR(256) NOT NULL DEFAULT 'qualifying failure in (T, T + 7d]',
    horizon_hours               INT NOT NULL DEFAULT 168,
    horizon_days                INT NOT NULL DEFAULT 7,
    training_start_date         DATE,
    training_end_date           DATE,
    validation_start_date       DATE,
    validation_end_date         DATE,
    test_start_date             DATE,
    test_end_date               DATE,
    auc_roc                     FLOAT,
    pr_auc                      FLOAT,
    precision_at_threshold      FLOAT,
    recall_at_threshold         FLOAT,
    f1_score                    FLOAT,
    feature_count               INT DEFAULT 29,
    parameters_json             VARCHAR(4096),
    artifact_location           VARCHAR(512),
    artifact_checksum           VARCHAR(128),
    status                      VARCHAR(32) NOT NULL DEFAULT 'candidate', -- candidate, validated, active, retired
    trained_at                  TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    created_at                  TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    CONSTRAINT pk_ml_model_registry PRIMARY KEY (model_id)
);

-- 2. Daily Machine Feature Store Table
CREATE TABLE IF NOT EXISTS MACHINE_FEATURE_DAILY (
    machine_id                  VARCHAR(32) NOT NULL,
    feature_date                DATE NOT NULL,
    -- Vibration features
    vib_mean                    FLOAT,
    vib_max                     FLOAT,
    vib_std                     FLOAT,
    vib_rms                     FLOAT,
    vib_warn_exceed_count       INT DEFAULT 0,
    vib_crit_exceed_count       INT DEFAULT 0,
    vib_exceed_ratio            FLOAT DEFAULT 0.0,
    vib_mean_7d                 FLOAT,
    vib_max_7d                  FLOAT,
    vib_slope7                  FLOAT,
    vib_rel30                   FLOAT,
    -- Temperature features
    btmp_mean                   FLOAT,
    btmp_max                    FLOAT,
    btmp_std                    FLOAT,
    btmp_warn_exceed_count      INT DEFAULT 0,
    btmp_crit_exceed_count      INT DEFAULT 0,
    btmp_exceed_ratio           FLOAT DEFAULT 0.0,
    btmp_mean_7d                FLOAT,
    btmp_slope7                 FLOAT,
    btmp_rel30                  FLOAT,
    -- Auxiliary telemetry features
    cur_mean                    FLOAT,
    cur_max                     FLOAT,
    cur_slope7                  FLOAT,
    cur_rel30                   FLOAT,
    wtmp_mean                   FLOAT,
    wtmp_max                    FLOAT,
    wtmp_slope7                 FLOAT,
    wtmp_rel30                  FLOAT,
    rpm_mean                    FLOAT,
    rpm_max                     FLOAT,
    rpm_slope7                  FLOAT,
    rpm_rel30                   FLOAT,
    prs_mean                    FLOAT,
    prs_max                     FLOAT,
    prs_slope7                  FLOAT,
    prs_rel30                   FLOAT,
    flw_mean                    FLOAT,
    flw_max                     FLOAT,
    flw_slope7                  FLOAT,
    flw_rel30                   FLOAT,
    -- Temporal & Maintenance features
    days_since_maint            FLOAT,
    maintenance_count_30d       INT DEFAULT 0,
    downtime_minutes_7d         FLOAT DEFAULT 0.0,
    -- Machine context
    machine_criticality         VARCHAR(32),
    operating_hours_used        FLOAT,
    production_qty_7d           FLOAT DEFAULT 0.0,
    run_time_min_7d             FLOAT DEFAULT 0.0,
    -- Target label for training
    label_failure_next_7d       INT,
    created_at                  TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    CONSTRAINT pk_machine_feature_daily PRIMARY KEY (machine_id, feature_date)
);

-- 3. Analytical Feature Generation View (Derives features from CORE)
CREATE OR REPLACE VIEW V_MACHINE_FEATURE_DAILY AS
WITH sensor_daily AS (
    SELECT
        s.machine_id,
        DATE(h.ts) AS feature_date,
        -- Vibration metrics
        AVG(CASE WHEN s.sensor_type IN ('vibration_rms', 'vibration', 'VIBRATION') THEN h.avg_running END) AS vib_mean,
        MAX(CASE WHEN s.sensor_type IN ('vibration_rms', 'vibration', 'VIBRATION') THEN h.max_running END) AS vib_max,
        STDDEV(CASE WHEN s.sensor_type IN ('vibration_rms', 'vibration', 'VIBRATION') THEN h.avg_running END) AS vib_std,
        SQRT(AVG(CASE WHEN s.sensor_type IN ('vibration_rms', 'vibration', 'VIBRATION') THEN h.avg_running * h.avg_running END)) AS vib_rms,
        SUM(CASE WHEN s.sensor_type IN ('vibration_rms', 'vibration', 'VIBRATION') AND h.max_running > s.warn_threshold THEN 1 ELSE 0 END) AS vib_warn_exceed_count,
        SUM(CASE WHEN s.sensor_type IN ('vibration_rms', 'vibration', 'VIBRATION') AND h.max_running > s.crit_threshold THEN 1 ELSE 0 END) AS vib_crit_exceed_count,
        -- Temperature metrics
        AVG(CASE WHEN s.sensor_type IN ('bearing_temperature', 'temperature', 'TEMPERATURE') THEN h.avg_running END) AS btmp_mean,
        MAX(CASE WHEN s.sensor_type IN ('bearing_temperature', 'temperature', 'TEMPERATURE') THEN h.max_running END) AS btmp_max,
        STDDEV(CASE WHEN s.sensor_type IN ('bearing_temperature', 'temperature', 'TEMPERATURE') THEN h.avg_running END) AS btmp_std,
        SUM(CASE WHEN s.sensor_type IN ('bearing_temperature', 'temperature', 'TEMPERATURE') AND h.max_running > s.warn_threshold THEN 1 ELSE 0 END) AS btmp_warn_exceed_count,
        SUM(CASE WHEN s.sensor_type IN ('bearing_temperature', 'temperature', 'TEMPERATURE') AND h.max_running > s.crit_threshold THEN 1 ELSE 0 END) AS btmp_crit_exceed_count,
        -- Current metrics
        AVG(CASE WHEN s.sensor_type IN ('motor_current', 'current', 'CURRENT') THEN h.avg_running END) AS cur_mean,
        MAX(CASE WHEN s.sensor_type IN ('motor_current', 'current', 'CURRENT') THEN h.max_running END) AS cur_max,
        -- Winding temp
        AVG(CASE WHEN s.sensor_type IN ('winding_temperature') THEN h.avg_running END) AS wtmp_mean,
        MAX(CASE WHEN s.sensor_type IN ('winding_temperature') THEN h.max_running END) AS wtmp_max,
        -- RPM
        AVG(CASE WHEN s.sensor_type IN ('rotational_speed', 'rpm', 'RPM') THEN h.avg_running END) AS rpm_mean,
        MAX(CASE WHEN s.sensor_type IN ('rotational_speed', 'rpm', 'RPM') THEN h.max_running END) AS rpm_max,
        -- Hydraulic pressure
        AVG(CASE WHEN s.sensor_type IN ('hydraulic_pressure', 'pressure', 'PRESSURE') THEN h.avg_running END) AS prs_mean,
        MAX(CASE WHEN s.sensor_type IN ('hydraulic_pressure', 'pressure', 'PRESSURE') THEN h.max_running END) AS prs_max,
        -- Coolant flow
        AVG(CASE WHEN s.sensor_type IN ('coolant_flow', 'flow', 'FLOW') THEN h.avg_running END) AS flw_mean,
        MAX(CASE WHEN s.sensor_type IN ('coolant_flow', 'flow', 'FLOW') THEN h.max_running END) AS flw_max,
        COUNT(*) AS total_hourly_readings
    FROM COCO_FACTORY.CORE.SENSOR_READING_HOURLY h
    JOIN COCO_FACTORY.CORE.SENSOR s ON h.sensor_id = s.sensor_id
    GROUP BY s.machine_id, DATE(h.ts)
),
rolling_features AS (
    SELECT
        sd.*,
        AVG(sd.vib_mean) OVER (PARTITION BY sd.machine_id ORDER BY sd.feature_date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW) AS vib_mean_7d,
        MAX(sd.vib_max) OVER (PARTITION BY sd.machine_id ORDER BY sd.feature_date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW) AS vib_max_7d,
        AVG(sd.btmp_mean) OVER (PARTITION BY sd.machine_id ORDER BY sd.feature_date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW) AS btmp_mean_7d,
        -- 30-day baseline reference
        AVG(sd.vib_mean) OVER (PARTITION BY sd.machine_id ORDER BY sd.feature_date ROWS BETWEEN 29 PRECEDING AND 7 PRECEDING) AS vib_base30,
        AVG(sd.btmp_mean) OVER (PARTITION BY sd.machine_id ORDER BY sd.feature_date ROWS BETWEEN 29 PRECEDING AND 7 PRECEDING) AS btmp_base30
    FROM sensor_daily sd
),
downtime_7d AS (
    SELECT
        machine_id,
        DATE(start_ts) AS dt_date,
        SUM(duration_min) AS daily_downtime
    FROM COCO_FACTORY.CORE.DOWNTIME_EVENT
    GROUP BY machine_id, DATE(start_ts)
),
maint_prior AS (
    SELECT
        rf.machine_id,
        rf.feature_date,
        MAX(DATE(w.closed_ts)) AS last_maint_date
    FROM rolling_features rf
    LEFT JOIN COCO_FACTORY.CORE.MAINTENANCE_WORK_ORDER w
        ON rf.machine_id = w.machine_id
        AND w.status = 'closed'
        AND DATE(w.closed_ts) <= rf.feature_date
    GROUP BY rf.machine_id, rf.feature_date
)
SELECT
    rf.machine_id,
    rf.feature_date,
    ROUND(rf.vib_mean, 4) AS vib_mean,
    ROUND(rf.vib_max, 4) AS vib_max,
    ROUND(rf.vib_std, 4) AS vib_std,
    ROUND(rf.vib_rms, 4) AS vib_rms,
    rf.vib_warn_exceed_count,
    rf.vib_crit_exceed_count,
    ROUND(CASE WHEN rf.total_hourly_readings > 0 THEN CAST(rf.vib_warn_exceed_count AS FLOAT) / rf.total_hourly_readings ELSE 0.0 END, 4) AS vib_exceed_ratio,
    ROUND(rf.vib_mean_7d, 4) AS vib_mean_7d,
    ROUND(rf.vib_max_7d, 4) AS vib_max_7d,
    ROUND(rf.vib_mean - rf.vib_mean_7d, 4) AS vib_slope7,
    ROUND(CASE WHEN rf.vib_base30 > 0 THEN rf.vib_mean / rf.vib_base30 ELSE 1.0 END, 4) AS vib_rel30,
    ROUND(rf.btmp_mean, 4) AS btmp_mean,
    ROUND(rf.btmp_max, 4) AS btmp_max,
    ROUND(rf.btmp_std, 4) AS btmp_std,
    rf.btmp_warn_exceed_count,
    rf.btmp_crit_exceed_count,
    ROUND(CASE WHEN rf.total_hourly_readings > 0 THEN CAST(rf.btmp_warn_exceed_count AS FLOAT) / rf.total_hourly_readings ELSE 0.0 END, 4) AS btmp_exceed_ratio,
    ROUND(rf.btmp_mean_7d, 4) AS btmp_mean_7d,
    ROUND(rf.btmp_mean - rf.btmp_mean_7d, 4) AS btmp_slope7,
    ROUND(CASE WHEN rf.btmp_base30 > 0 THEN rf.btmp_mean / rf.btmp_base30 ELSE 1.0 END, 4) AS btmp_rel30,
    ROUND(rf.cur_mean, 4) AS cur_mean,
    ROUND(rf.cur_max, 4) AS cur_max,
    0.0 AS cur_slope7,
    1.0 AS cur_rel30,
    ROUND(rf.wtmp_mean, 4) AS wtmp_mean,
    ROUND(rf.wtmp_max, 4) AS wtmp_max,
    0.0 AS wtmp_slope7,
    1.0 AS wtmp_rel30,
    ROUND(rf.rpm_mean, 4) AS rpm_mean,
    ROUND(rf.rpm_max, 4) AS rpm_max,
    0.0 AS rpm_slope7,
    1.0 AS rpm_rel30,
    ROUND(rf.prs_mean, 4) AS prs_mean,
    ROUND(rf.prs_max, 4) AS prs_max,
    0.0 AS prs_slope7,
    1.0 AS prs_rel30,
    ROUND(rf.flw_mean, 4) AS flw_mean,
    ROUND(rf.flw_max, 4) AS flw_max,
    0.0 AS flw_slope7,
    1.0 AS flw_rel30,
    COALESCE(DATEDIFF(day, mp.last_maint_date, rf.feature_date), 120.0) AS days_since_maint,
    0 AS maintenance_count_30d,
    COALESCE(dt.daily_downtime, 0.0) AS downtime_minutes_7d,
    m.criticality AS machine_criticality,
    COALESCE(c.avg_operating_hours, 0.0) AS operating_hours_used,
    0.0 AS production_qty_7d,
    0.0 AS run_time_min_7d,
    0 AS label_failure_next_7d,
    CURRENT_TIMESTAMP() AS created_at
FROM rolling_features rf
JOIN COCO_FACTORY.CORE.MACHINE m ON rf.machine_id = m.machine_id
LEFT JOIN (
    SELECT machine_id, AVG(operating_hours_used) AS avg_operating_hours
    FROM COCO_FACTORY.CORE.COMPONENT
    GROUP BY machine_id
) c ON rf.machine_id = c.machine_id
LEFT JOIN downtime_7d dt ON rf.machine_id = dt.machine_id AND rf.feature_date = dt.dt_date
LEFT JOIN maint_prior mp ON rf.machine_id = mp.machine_id AND rf.feature_date = mp.feature_date;

-- 4. Inference Log
CREATE TABLE IF NOT EXISTS INFERENCE_LOG (
    inference_id                VARCHAR(64) NOT NULL,
    model_id                    VARCHAR(64),
    machine_id                  VARCHAR(32) NOT NULL,
    scored_ts                   TIMESTAMP_NTZ NOT NULL,
    failure_probability         FLOAT NOT NULL,
    risk_level                  VARCHAR(32) NOT NULL,
    suspected_component_id      VARCHAR(32),
    primary_feature_contributors VARCHAR(2048),
    created_at                  TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    CONSTRAINT pk_ml_inference_log PRIMARY KEY (inference_id)
);

-- 5. Model Evaluation Metrics
CREATE TABLE IF NOT EXISTS MODEL_EVALUATION (
    evaluation_id               VARCHAR(64) NOT NULL,
    model_id                    VARCHAR(64) NOT NULL,
    model_version               VARCHAR(32) NOT NULL,
    split_name                  VARCHAR(32) NOT NULL, -- train, validation, test
    sample_count                INT NOT NULL,
    positive_count              INT NOT NULL,
    roc_auc                     FLOAT,
    pr_auc                      FLOAT,
    precision_score             FLOAT,
    recall_score                FLOAT,
    f1_score                    FLOAT,
    confusion_matrix_json       VARCHAR(1024),
    evaluated_at                TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    CONSTRAINT pk_ml_model_evaluation PRIMARY KEY (evaluation_id),
    CONSTRAINT fk_ml_eval_model FOREIGN KEY (model_id) REFERENCES COCO_FACTORY.ML.MODEL_REGISTRY(model_id)
);

-- 6. Prediction Feature Snapshot
CREATE TABLE IF NOT EXISTS PREDICTION_FEATURE_SNAPSHOT (
    snapshot_id                 VARCHAR(64) NOT NULL,
    prediction_id               VARCHAR(64) NOT NULL,
    machine_id                  VARCHAR(32) NOT NULL,
    feature_timestamp           TIMESTAMP_NTZ NOT NULL,
    feature_version             VARCHAR(32) NOT NULL,
    features_json               VARCHAR(16384),
    source_window_start         TIMESTAMP_NTZ,
    source_window_end           TIMESTAMP_NTZ,
    created_at                  TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    CONSTRAINT pk_ml_pred_feat_snapshot PRIMARY KEY (snapshot_id)
);

-- 7. Prediction Lineage
CREATE TABLE IF NOT EXISTS PREDICTION_LINEAGE (
    lineage_id                  VARCHAR(64) NOT NULL,
    prediction_id               VARCHAR(64) NOT NULL,
    machine_id                  VARCHAR(32) NOT NULL,
    model_id                    VARCHAR(64) NOT NULL,
    model_version               VARCHAR(32) NOT NULL,
    feature_version             VARCHAR(32) NOT NULL,
    snapshot_id                 VARCHAR(64) NOT NULL,
    inference_timestamp         TIMESTAMP_NTZ NOT NULL,
    failure_probability         FLOAT NOT NULL,
    risk_level                  VARCHAR(32) NOT NULL,
    policy_version              VARCHAR(32) NOT NULL,
    created_at                  TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    CONSTRAINT pk_ml_pred_lineage PRIMARY KEY (lineage_id),
    CONSTRAINT fk_ml_lineage_snapshot FOREIGN KEY (snapshot_id) REFERENCES COCO_FACTORY.ML.PREDICTION_FEATURE_SNAPSHOT(snapshot_id)
);
