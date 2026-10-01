-- 40_ml_foundation.sql
-- ML Foundation: feature store, model registry metadata, and inference logging

USE DATABASE COCO_FACTORY;
USE SCHEMA ML;

-- 1. Model Registry Metadata
CREATE TABLE IF NOT EXISTS MODEL_REGISTRY (
    model_id                    VARCHAR(64) NOT NULL,
    model_name                  VARCHAR(128) NOT NULL,
    version                     VARCHAR(32) NOT NULL,
    algorithm                   VARCHAR(64) NOT NULL,
    horizon_days                INT NOT NULL DEFAULT 7,
    training_start_date         DATE,
    training_end_date           DATE,
    auc_roc                     FLOAT,
    pr_auc                      FLOAT,
    precision_at_threshold      FLOAT,
    recall_at_threshold         FLOAT,
    feature_count               INT,
    parameters_json             VARCHAR(4096),
    created_at                  TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    CONSTRAINT pk_ml_model_registry PRIMARY KEY (model_id)
);

-- 2. Daily Machine Feature Store (Computed from CORE Telemetry and Work Orders)
CREATE TABLE IF NOT EXISTS MACHINE_FEATURE_DAILY (
    machine_id                  VARCHAR(32) NOT NULL,
    feature_date                DATE NOT NULL,
    vib_mean                    FLOAT,
    vib_max                     FLOAT,
    vib_slope7                  FLOAT,
    vib_rel30                   FLOAT,
    btmp_mean                   FLOAT,
    btmp_max                    FLOAT,
    btmp_slope7                 FLOAT,
    btmp_rel30                  FLOAT,
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
    prs_rel30                  FLOAT,
    flw_mean                    FLOAT,
    flw_max                     FLOAT,
    flw_slope7                  FLOAT,
    flw_rel30                   FLOAT,
    days_since_maint            FLOAT,
    label_failure_next_7d       INT,
    created_at                  TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    CONSTRAINT pk_machine_feature_daily PRIMARY KEY (machine_id, feature_date)
);

-- 3. Inference Log
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
