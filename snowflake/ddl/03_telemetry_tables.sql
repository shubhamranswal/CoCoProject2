-- FACTORY_TELEMETRY: Measurements, Engineered Features, Baselines, and Anomalies

CREATE TABLE IF NOT EXISTS FACTORY_TELEMETRY.MEASUREMENT (
    measurement_id VARCHAR(64) PRIMARY KEY,
    machine_id VARCHAR(64) NOT NULL REFERENCES FACTORY_CORE.MACHINE(machine_id),
    sensor_id VARCHAR(64) NOT NULL REFERENCES FACTORY_CORE.SENSOR(sensor_id),
    timestamp TIMESTAMP_NTZ NOT NULL,
    value FLOAT NOT NULL,
    unit VARCHAR(32) NOT NULL,
    quality VARCHAR(32) DEFAULT 'VALID' -- VALID, SUSPECT, OUT_OF_RANGE
);

CREATE TABLE IF NOT EXISTS FACTORY_TELEMETRY.FEATURE (
    feature_id VARCHAR(64) PRIMARY KEY,
    machine_id VARCHAR(64) NOT NULL REFERENCES FACTORY_CORE.MACHINE(machine_id),
    timestamp TIMESTAMP_NTZ NOT NULL,
    window_minutes INT DEFAULT 15,
    vibration_rms FLOAT NOT NULL,
    vibration_peak FLOAT NOT NULL,
    temperature_mean FLOAT NOT NULL,
    temperature_slope FLOAT NOT NULL,
    rpm_mean FLOAT NOT NULL,
    rpm_variance FLOAT NOT NULL,
    current_mean FLOAT NOT NULL
);

CREATE TABLE IF NOT EXISTS FACTORY_TELEMETRY.BASELINE (
    baseline_id VARCHAR(64) PRIMARY KEY,
    machine_id VARCHAR(64) NOT NULL REFERENCES FACTORY_CORE.MACHINE(machine_id),
    signal_name VARCHAR(64) NOT NULL,
    operating_regime VARCHAR(64) DEFAULT 'NORMAL_LOAD',
    baseline_mean FLOAT NOT NULL,
    baseline_std FLOAT NOT NULL,
    warning_threshold FLOAT NOT NULL,
    critical_threshold FLOAT NOT NULL,
    unit VARCHAR(32) NOT NULL,
    CONSTRAINT uk_machine_signal UNIQUE (machine_id, signal_name, operating_regime)
);

CREATE TABLE IF NOT EXISTS FACTORY_TELEMETRY.ANOMALY (
    anomaly_id VARCHAR(64) PRIMARY KEY,
    machine_id VARCHAR(64) NOT NULL REFERENCES FACTORY_CORE.MACHINE(machine_id),
    sensor_id VARCHAR(64) NOT NULL REFERENCES FACTORY_CORE.SENSOR(sensor_id),
    detected_at TIMESTAMP_NTZ NOT NULL,
    severity VARCHAR(32) NOT NULL, -- LOW, MEDIUM, HIGH, CRITICAL
    score FLOAT NOT NULL,
    metric_name VARCHAR(64) NOT NULL,
    observed_value FLOAT NOT NULL,
    baseline_value FLOAT NOT NULL,
    deviation_pct FLOAT NOT NULL,
    status VARCHAR(32) DEFAULT 'ACTIVE' -- ACTIVE, RESOLVED
);
