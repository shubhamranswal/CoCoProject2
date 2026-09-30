"""Tests verifying AlertService deduplication, escalation, and lifecycle."""

from datetime import datetime, timezone
import pytest

from domain.enums import AlertStatus, FailureMode, Severity
from domain.models import FailureRisk
from repositories.memory.memory_repository import InMemoryRepository
from services.alert_service import AlertService


def test_alert_creation_and_deduplication():
    repo = InMemoryRepository()
    service = AlertService(repository=repo, alert_threshold=0.65)
    now = datetime.now(timezone.utc)

    # 1. Risk >= 0.65 triggers HIGH severity alert
    risk_high = FailureRisk(
        risk_id="RISK-1",
        machine_id="M204",
        prediction_timestamp=now,
        failure_mode=FailureMode.BEARING_DEGRADATION,
        risk_score=0.70,
        confidence=0.88,
        contributing_signals=["SEN-M204-VIB", "SEN-M204-TMP"],
    )

    alert1 = service.evaluate_risk_for_alert(risk_high)
    assert alert1 is not None
    assert alert1.status == AlertStatus.OPEN
    assert alert1.severity == Severity.HIGH
    assert alert1.risk_score == 0.70

    # 2. Subsequent elevated risk (0.88) should update and escalate existing alert rather than duplicate
    risk_critical = FailureRisk(
        risk_id="RISK-2",
        machine_id="M204",
        prediction_timestamp=now,
        failure_mode=FailureMode.BEARING_DEGRADATION,
        risk_score=0.88,
        confidence=0.92,
        contributing_signals=["SEN-M204-VIB", "SEN-M204-TMP"],
    )

    alert2 = service.evaluate_risk_for_alert(risk_critical)
    assert alert2 is not None
    assert alert2.alert_id == alert1.alert_id  # Same deduplicated alert ID
    assert alert2.severity == Severity.CRITICAL
    assert alert2.risk_score == 0.88

    # Verify repository only holds one alert for M204
    all_alerts = repo.list_alerts(machine_id="M204")
    assert len(all_alerts) == 1


def test_alert_auto_resolution_when_risk_subsides():
    repo = InMemoryRepository()
    service = AlertService(repository=repo, alert_threshold=0.65)
    now = datetime.now(timezone.utc)

    # Trigger alert
    risk_trigger = FailureRisk(
        risk_id="R-TRIG",
        machine_id="M204",
        prediction_timestamp=now,
        failure_mode=FailureMode.BEARING_DEGRADATION,
        risk_score=0.75,
        confidence=0.9,
    )
    service.evaluate_risk_for_alert(risk_trigger)

    # Risk subsides to 0.10
    risk_low = FailureRisk(
        risk_id="R-LOW",
        machine_id="M204",
        prediction_timestamp=now,
        failure_mode=FailureMode.BEARING_DEGRADATION,
        risk_score=0.10,
        confidence=0.9,
    )
    res_alert = service.evaluate_risk_for_alert(risk_low)
    assert res_alert is not None
    assert res_alert.status == AlertStatus.RESOLVED

    # Alert in repository should be RESOLVED
    stored_alerts = repo.list_alerts(machine_id="M204")
    assert len(stored_alerts) == 1
    assert stored_alerts[0].status == AlertStatus.RESOLVED
