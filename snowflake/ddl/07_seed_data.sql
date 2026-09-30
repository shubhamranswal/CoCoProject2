-- Seed Reference Data for Snowflake
-- Plant 01, Line A/B/C, 10 Machines, and Primary Machine M204

INSERT INTO FACTORY_CORE.PLANT (plant_id, plant_code, name, location, timezone)
VALUES ('PLANT-01', 'PLT01', 'Pune Automotive Assembly & Packaging Plant', 'Pune, India', 'Asia/Kolkata')
ON CONFLICT (plant_id) DO NOTHING;

INSERT INTO FACTORY_CORE.PRODUCTION_LINE (line_id, plant_id, line_code, name, target_units_per_hour, status)
VALUES 
    ('LINE-A', 'PLANT-01', 'LINE-A', 'Stamping & Body Assembly Line A', 120.0, 'ACTIVE'),
    ('LINE-B', 'PLANT-01', 'LINE-B', 'High-Speed Packaging & Conveyor Line B', 350.0, 'ACTIVE'),
    ('LINE-C', 'PLANT-01', 'LINE-C', 'Final Inspection & Palletizing Line C', 200.0, 'ACTIVE')
ON CONFLICT (line_id) DO NOTHING;

INSERT INTO FACTORY_CORE.MACHINE (machine_id, line_id, machine_code, name, asset_type, criticality, health_status, state, manufacturer, model, serial_number)
VALUES
    ('M101', 'LINE-A', 'M101', 'Hydraulic Stamping Press 1', 'STAMPING_PRESS', 'HIGH', 'HEALTHY', 'RUNNING', 'Schuler', 'PRESS-500', 'SN-M101'),
    ('M102', 'LINE-A', 'M102', 'Transfer Feed Servo 1', 'FEEDER', 'MEDIUM', 'HEALTHY', 'RUNNING', 'Siemens', 'FEED-200', 'SN-M102'),
    ('M103', 'LINE-A', 'M103', 'Robotic Spot Welder Alpha', 'ROBOT', 'HIGH', 'HEALTHY', 'RUNNING', 'KUKA', 'KR-300', 'SN-M103'),
    ('M104', 'LINE-A', 'M104', 'Roller Hemming Station 1', 'HEMMER', 'LOW', 'HEALTHY', 'RUNNING', 'ABB', 'HEM-100', 'SN-M104'),
    ('M201', 'LINE-B', 'M201', 'Rotary Bottle Filler', 'FILLER', 'HIGH', 'HEALTHY', 'RUNNING', 'Krones', 'FILL-60', 'SN-M201'),
    ('M202', 'LINE-B', 'M202', 'High-Speed Capper Unit', 'CAPPER', 'MEDIUM', 'HEALTHY', 'RUNNING', 'Arol', 'CAP-12', 'SN-M202'),
    ('M203', 'LINE-B', 'M203', 'Continuous Induction Sealer', 'SEALER', 'MEDIUM', 'HEALTHY', 'RUNNING', 'Enercon', 'IND-400', 'SN-M203'),
    ('M204', 'LINE-B', 'M204', 'Conveyor Drive Motor B4', 'ELECTRIC_MOTOR', 'CRITICAL', 'HEALTHY', 'RUNNING', 'Siemens / Industrial Dynamics', 'DRV-5000', 'SN-DRV5000-2024-M204'),
    ('M301', 'LINE-C', 'M301', 'Vision Inspection Tunnel', 'VISION_SYSTEM', 'MEDIUM', 'HEALTHY', 'RUNNING', 'Cognex', 'VIS-800', 'SN-M301'),
    ('M302', 'LINE-C', 'M302', 'Automated Palletizer Robot', 'PALLETIZER', 'HIGH', 'HEALTHY', 'RUNNING', 'Fanuc', 'PAL-M410', 'SN-M302')
ON CONFLICT (machine_id) DO NOTHING;

INSERT INTO FACTORY_CORE.COMPONENT (component_id, machine_id, name, component_type, criticality, installed_at, health_status)
VALUES
    ('CMP-M204-BRG', 'M204', 'Drive-End Deep Groove Ball Bearing Assembly', 'BEARING', 'CRITICAL', '2025-04-10 00:00:00', 'HEALTHY'),
    ('CMP-M204-STR', 'M204', 'Stator Winding Assembly', 'STATOR', 'HIGH', '2023-01-15 00:00:00', 'HEALTHY'),
    ('CMP-M204-SHF', 'M204', 'Motor Drive Shaft', 'SHAFT', 'HIGH', '2023-01-15 00:00:00', 'HEALTHY'),
    ('CMP-M204-CPG', 'M204', 'Flexible Gearbox Coupling', 'COUPLING', 'MEDIUM', '2024-08-20 00:00:00', 'HEALTHY')
ON CONFLICT (component_id) DO NOTHING;

INSERT INTO FACTORY_CORE.SENSOR (sensor_id, machine_id, component_id, sensor_type, name, unit, sampling_rate_hz, range_min, range_max, is_active)
VALUES
    ('SEN-M204-VIB', 'M204', 'CMP-M204-BRG', 'VIBRATION', 'Drive-End Bearing Accelerometer', 'g', 100.0, 0.0, 5.0, TRUE),
    ('SEN-M204-TMP', 'M204', 'CMP-M204-BRG', 'TEMPERATURE', 'Drive-End Bearing RTD Probe', '°C', 1.0, -10.0, 150.0, TRUE),
    ('SEN-M204-RPM', 'M204', 'CMP-M204-SHF', 'RPM', 'Optical Shaft Tachometer', 'RPM', 10.0, 0.0, 3000.0, TRUE),
    ('SEN-M204-CUR', 'M204', 'CMP-M204-STR', 'CURRENT', 'CT Motor Phase Current Sensor', 'A', 10.0, 0.0, 60.0, TRUE)
ON CONFLICT (sensor_id) DO NOTHING;

INSERT INTO FACTORY_TELEMETRY.BASELINE (baseline_id, machine_id, signal_name, operating_regime, baseline_mean, baseline_std, warning_threshold, critical_threshold, unit)
VALUES
    ('BASE-M204-VIB', 'M204', 'vibration_rms', 'NORMAL_LOAD', 0.45, 0.04, 0.70, 1.00, 'g'),
    ('BASE-M204-TMP', 'M204', 'temperature', 'NORMAL_LOAD', 58.5, 2.1, 75.0, 90.0, '°C'),
    ('BASE-M204-RPM', 'M204', 'rpm', 'NORMAL_LOAD', 1750.0, 15.0, 1650.0, 1500.0, 'RPM'),
    ('BASE-M204-CUR', 'M204', 'current', 'NORMAL_LOAD', 18.5, 0.8, 24.0, 30.0, 'A')
ON CONFLICT (baseline_id) DO NOTHING;
