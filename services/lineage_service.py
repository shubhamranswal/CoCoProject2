"""Lineage tracking service connecting physical sensors to operational closed-loop outcomes.

Follows Phase 23:
Trace from:
Sensor -> Telemetry -> Feature -> Anomaly -> Risk -> Prediction -> Alert ->
Investigation -> Evidence -> Finding -> Recommendation -> Approval ->
Work Order -> Maintenance -> Verification -> Outcome.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from domain.models import DecisionLineage
from repositories import get_repository


class LineageService:
    """Reconstructs end-to-end audit lineage across the operational reliability lifecycle."""

    def __init__(self, repository: Any = None) -> None:
        self.repo = repository or get_repository()

    def trace_lineage(
        self,
        machine_id: str,
        investigation_id: Optional[str] = None,
        work_order_id: Optional[str] = None,
    ) -> DecisionLineage:
        # 1. Resolve Investigation
        inv = None
        if investigation_id:
            inv = self.repo.get_investigation(investigation_id)
        elif work_order_id:
            wo = self.repo.get_work_order(work_order_id)
            if wo and wo.investigation_id:
                inv = self.repo.get_investigation(wo.investigation_id)
        if not inv:
            invs = self.repo.list_investigations(machine_id=machine_id)
            inv = invs[0] if invs else None

        # 2. Resolve Alert
        alert_id = inv.alert_id if inv else None
        if not alert_id:
            alerts = self.repo.list_alerts(machine_id=machine_id)
            alert_id = alerts[0].alert_id if alerts else None

        # 3. Resolve Evidence & Findings
        evidence_ids = []
        finding_id = None
        recommendation_id = None
        if inv:
            evidence = self.repo.get_evidence(inv.investigation_id)
            evidence_ids = [e.evidence_id for e in evidence]
            finding_id = f"FIND-{inv.investigation_id}"
            recommendation_id = f"REC-{inv.investigation_id}"

        # 4. Resolve Approval & Work Order
        wo_id = work_order_id
        app_id = None
        if not wo_id:
            wos = self.repo.list_work_orders(machine_id=machine_id)
            if wos:
                wo_id = wos[0].work_order_id
                app_id = wos[0].approval_id

        if not app_id:
            apps = self.repo.list_approvals(machine_id=machine_id)
            app_id = apps[0].approval_id if apps else None

        # 5. Resolve Verification & Outcome
        ver_id = None
        if wo_id:
            ver = self.repo.get_verification(wo_id)
            if ver:
                ver_id = ver.verification_id

        # 6. Resolve ML Prediction & Outcome
        pred = self.repo.get_latest_prediction(machine_id)
        pred_id = pred.prediction_id if pred else None
        outcome_id = None
        if pred_id:
            outcome = self.repo.get_prediction_outcome(pred_id)
            outcome_id = outcome.outcome_id if outcome else None

        # 7. Resolve Features, Risk, and Anomalies
        features = self.repo.get_latest_features(machine_id)
        feat_id = features.feature_id if features else None

        anomalies = self.repo.get_anomalies(machine_id)
        anomaly_ids = [a.anomaly_id for a in anomalies]

        risk = self.repo.get_latest_failure_risk(machine_id)
        risk_id = risk.risk_id if risk else None

        return DecisionLineage(
            lineage_id=f"LIN-{uuid.uuid4().hex[:8].upper()}",
            machine_id=machine_id,
            sensor_id=f"{machine_id}-VIB-01",
            feature_id=feat_id,
            anomaly_ids=anomaly_ids,
            risk_id=risk_id,
            prediction_id=pred_id,
            alert_id=alert_id,
            investigation_id=inv.investigation_id if inv else None,
            evidence_ids=evidence_ids,
            finding_id=finding_id,
            recommendation_id=recommendation_id,
            approval_id=app_id,
            work_order_id=wo_id,
            verification_id=ver_id,
            outcome_id=outcome_id,
        )
