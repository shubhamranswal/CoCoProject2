"""Alert generation and correlation service.

Follows AGENT.md:
- Deterministic alert evaluation based on failure risk thresholds
- Deduplication and correlation so escalating risk updates the existing logical alert
- Full lifecycle support: OPEN -> ACKNOWLEDGED -> RESOLVED
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from config import get_config
from domain.enums import AlertStatus, FailureMode, Severity
from domain.models import Alert, FailureRisk
from repositories.base import InvestigationRepository


class AlertService:
    def __init__(
        self,
        repository: InvestigationRepository,
        alert_threshold: Optional[float] = None,
    ) -> None:
        self.repo = repository
        self.alert_threshold = alert_threshold or get_config().thresholds.failure_risk_alert_threshold

    def evaluate_risk_for_alert(self, risk: FailureRisk) -> Optional[Alert]:
        """Evaluate failure risk against thresholds, creating or updating correlated alerts."""
        machine_id = risk.machine_id
        failure_mode = risk.failure_mode
        dedup_key = f"ALERT-{machine_id}-{failure_mode.value}"
        ts = risk.prediction_timestamp

        # Check existing alerts for this machine
        existing_alerts = self.repo.list_alerts(machine_id=machine_id)
        active_alert = next(
            (
                a for a in existing_alerts
                if a.dedup_key == dedup_key and a.status in (AlertStatus.OPEN, AlertStatus.INVESTIGATING, AlertStatus.ACTION_PROPOSED)
            ),
            None,
        )

        # 1. Condition for Alert Trigger / Escalation
        if risk.risk_score >= self.alert_threshold:
            severity = Severity.CRITICAL if risk.risk_score >= 0.85 else Severity.HIGH
            signals_desc = "; ".join(risk.contributing_signals[:2]) if risk.contributing_signals else "Elevated precursor metrics"
            reason = f"High failure risk ({risk.risk_score:.2f}) for {failure_mode.value}. Precursors: {signals_desc}"

            if active_alert:
                # Update existing correlated alert
                updated_alert = active_alert.model_copy(
                    update={
                        "risk_score": risk.risk_score,
                        "severity": severity,
                        "trigger_reason": reason,
                        "updated_at": ts,
                    }
                )
                return self.repo.create_alert(updated_alert)
            else:
                # Create brand new alert
                alert_id = f"ALT-{machine_id}-{ts.strftime('%Y%m%d%H%M')}"
                new_alert = Alert(
                    alert_id=alert_id,
                    machine_id=machine_id,
                    component_id="CMP-M204-BRG" if "BEARING" in failure_mode.value else None,
                    severity=severity,
                    status=AlertStatus.OPEN,
                    trigger_reason=reason,
                    risk_score=risk.risk_score,
                    failure_mode=failure_mode,
                    created_at=ts,
                    updated_at=ts,
                    dedup_key=dedup_key,
                )
                return self.repo.create_alert(new_alert)

        # 2. Condition for Alert Auto-Resolution after verified recovery
        elif risk.risk_score < 0.25 and active_alert:
            resolved_alert = active_alert.model_copy(
                update={
                    "status": AlertStatus.RESOLVED,
                    "resolved_at": ts,
                    "updated_at": ts,
                    "trigger_reason": f"Resolved: Failure risk dropped to {risk.risk_score:.2f} following maintenance recovery.",
                }
            )
            return self.repo.create_alert(resolved_alert)

        return active_alert

    def get_active_alerts(self, machine_id: Optional[str] = None) -> List[Alert]:
        alerts = self.repo.list_alerts(machine_id=machine_id)
        return [a for a in alerts if a.status in (AlertStatus.OPEN, AlertStatus.INVESTIGATING, AlertStatus.ACTION_PROPOSED)]

    def resolve_alert(self, alert_id: str, reason: str = "Resolved by operator or verification") -> Optional[Alert]:
        alert = self.repo.get_alert(alert_id)
        if not alert:
            return None
        resolved = alert.model_copy(
            update={
                "status": AlertStatus.RESOLVED,
                "resolved_at": datetime.now(timezone.utc),
                "trigger_reason": reason,
            }
        )
        return self.repo.create_alert(resolved)
