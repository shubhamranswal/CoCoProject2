"""End-to-end integration test for the M204 Deterministic Intelligence Spine.

Validates the full flow:
Telemetry -> Features -> Baseline -> Anomaly -> Failure Risk -> Alert -> OEE
across all degradation and recovery phases.
"""

from datetime import datetime, timedelta, timezone
import pytest

from data.scenarios.m204_scenario import M204ScenarioEngine, ScenarioPhase
from domain.enums import AlertStatus, HealthStatus, RiskLevel, Severity
from repositories.memory.memory_repository import InMemoryRepository
from services.pipeline_orchestrator import PipelineOrchestrator


def test_m204_pipeline_end_to_end():
    repo = InMemoryRepository()
    orchestrator = PipelineOrchestrator(repository=repo)
    engine = M204ScenarioEngine(machine_id="M204")

    base_time = datetime(2026, 3, 30, 8, 0, 0, tzinfo=timezone.utc)

    # -------------------------------------------------------------
    # 1. NORMAL PHASE
    # -------------------------------------------------------------
    meas_norm = engine.generate_timeseries(phase=ScenarioPhase.NORMAL, num_points=12, start_time=base_time)
    prod_norm, dt_norm = engine.generate_operational_context(phase=ScenarioPhase.NORMAL, run_date=base_time)

    res_norm = orchestrator.run_reliability_pipeline(
        machine_id="M204",
        measurements=meas_norm,
        production_run=prod_norm,
        downtime_events=[dt_norm] if dt_norm else None,
    )

    assert res_norm.machine_id == "M204"
    assert res_norm.measurements_count == 48
    assert res_norm.features.vibration_rms < 0.50
    assert len(res_norm.anomalies) == 0
    assert res_norm.failure_risk.risk_level == RiskLevel.LOW
    assert res_norm.alert is None
    assert res_norm.oee is not None
    assert res_norm.oee.oee > 0.95
    assert res_norm.machine_health == HealthStatus.HEALTHY

    # -------------------------------------------------------------
    # 2. ANOMALOUS PHASE
    # -------------------------------------------------------------
    t_anom = base_time + timedelta(hours=2)
    meas_anom = engine.generate_timeseries(phase=ScenarioPhase.ANOMALOUS, num_points=12, start_time=t_anom)
    prod_anom, dt_anom = engine.generate_operational_context(phase=ScenarioPhase.ANOMALOUS, run_date=t_anom)

    res_anom = orchestrator.run_reliability_pipeline(
        machine_id="M204",
        measurements=meas_anom,
        production_run=prod_anom,
        downtime_events=[dt_anom] if dt_anom else None,
    )

    assert len(res_anom.anomalies) > 0
    assert res_anom.failure_risk.risk_score >= 0.65
    assert res_anom.alert is not None
    assert res_anom.alert.status == AlertStatus.OPEN
    assert res_anom.alert.severity in (Severity.HIGH, Severity.CRITICAL)
    assert res_anom.oee.oee < res_norm.oee.oee  # OEE decline
    assert res_anom.machine_health == HealthStatus.DEGRADING

    # -------------------------------------------------------------
    # 3. HIGH RISK PHASE
    # -------------------------------------------------------------
    t_high = base_time + timedelta(hours=4)
    meas_high = engine.generate_timeseries(phase=ScenarioPhase.HIGH_RISK, num_points=12, start_time=t_high)
    prod_high, dt_high = engine.generate_operational_context(phase=ScenarioPhase.HIGH_RISK, run_date=t_high)

    res_high = orchestrator.run_reliability_pipeline(
        machine_id="M204",
        measurements=meas_high,
        production_run=prod_high,
        downtime_events=[dt_high] if dt_high else None,
    )

    assert res_high.failure_risk.risk_level == RiskLevel.CRITICAL
    assert res_high.alert is not None
    assert res_high.alert.severity == Severity.CRITICAL
    # Verify alert deduplication: still single alert in repo, escalated
    alerts = repo.list_alerts(machine_id="M204")
    assert len(alerts) == 1
    assert alerts[0].severity == Severity.CRITICAL
    assert res_high.oee.oee < 0.70  # Severe OEE loss

    # -------------------------------------------------------------
    # 4. RECOVERY PHASE
    # -------------------------------------------------------------
    t_rec = base_time + timedelta(hours=8)
    meas_rec = engine.generate_timeseries(phase=ScenarioPhase.RECOVERED, num_points=12, start_time=t_rec)
    prod_rec, dt_rec = engine.generate_operational_context(phase=ScenarioPhase.RECOVERED, run_date=t_rec)

    res_rec = orchestrator.run_reliability_pipeline(
        machine_id="M204",
        measurements=meas_rec,
        production_run=prod_rec,
        downtime_events=[dt_rec] if dt_rec else None,
    )

    assert len(res_rec.anomalies) == 0
    assert res_rec.failure_risk.risk_level == RiskLevel.LOW
    assert res_rec.failure_risk.risk_score <= 0.20
    assert res_rec.oee.oee > 0.95  # OEE restored
    assert res_rec.machine_health == HealthStatus.HEALTHY
    # Alert is now auto-resolved
    assert res_rec.alert is not None
    assert res_rec.alert.status == AlertStatus.RESOLVED
    alerts_after = repo.list_alerts(machine_id="M204")
    assert alerts_after[0].status == AlertStatus.RESOLVED

