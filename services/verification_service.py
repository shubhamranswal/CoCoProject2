"""Verification service validating post-maintenance physical recovery.

Follows AGENT.md & architecture/architecture.md:
- Closed-loop verification: Work order completion != verification success
- Verification is measured strictly from post-maintenance physical telemetry
- Evaluates against deterministic VerificationPolicy thresholds
- Determines VERIFIED, PARTIALLY_VERIFIED, or FAILED
- Governs lifecycle transitions:
  * VERIFIED: Investigation -> CLOSED, WorkOrder -> VERIFIED, Machine -> HEALTHY
  * PARTIALLY_VERIFIED: Investigation -> REQUIRES_FOLLOW_UP
  * FAILED: Investigation -> VERIFICATION_FAILED (WorkOrder remains COMPLETED, not VERIFIED)
- Records Verification object and full audit trail
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from domain.enums import (
    HealthStatus,
    InvestigationStatus,
    MachineState,
    Severity,
    VerificationStatus,
    WorkOrderStatus,
)
from domain.models import (
    Anomaly,
    AuditEvent,
    FailureRisk,
    FeatureVector,
    Verification,
)
from services.oee_service import OEEResult
from repositories.base import (
    GovernanceRepository,
    InvestigationRepository,
    MachineRepository,
    MaintenanceRepository,
)


@dataclass(frozen=True)
class VerificationPolicy:
    """Configurable thresholds for post-maintenance physical verification."""

    max_acceptable_vibration_rms: float = 0.50  # Nominal baseline ~0.45g
    max_acceptable_temperature: float = 65.0    # Nominal baseline ~58.5°C
    max_acceptable_risk_score: float = 0.25     # Acceptable low operational risk
    min_vibration_reduction_pct: float = 30.0   # Must drop at least 30% from peak
    min_risk_reduction_pct: float = 50.0       # Must drop at least 50% from peak
    require_zero_active_critical_anomalies: bool = True
    min_oee_target: float = 0.75               # Expected minimum availability/OEE


class VerificationService:
    """Governed verification service evaluating telemetry recovery and closing the loop."""

    def __init__(
        self,
        repository: GovernanceRepository,
        maintenance_repo: Optional[MaintenanceRepository] = None,
        investigation_repo: Optional[InvestigationRepository] = None,
        machine_repo: Optional[MachineRepository] = None,
    ) -> None:
        self.repo = repository
        self.maintenance_repo = maintenance_repo
        self.investigation_repo = investigation_repo
        self.machine_repo = machine_repo

    def record_verification(self, verification: Verification) -> None:
        """Save verification record to repository."""
        self.repo.save_verification(verification)

    def get_verification(self, work_order_id: str) -> Optional[Verification]:
        """Retrieve verification record for a work order."""
        return self.repo.get_verification(work_order_id)

    def verify_recovery(
        self,
        work_order_id: str,
        investigation_id: str,
        machine_id: str,
        pre_features: FeatureVector,
        post_features: FeatureVector,
        pre_risk: FailureRisk,
        post_risk: FailureRisk,
        pre_oee: Optional[OEEResult] = None,
        post_oee: Optional[OEEResult] = None,
        active_anomalies: Optional[List[Anomaly]] = None,
        policy: Optional[VerificationPolicy] = None,
        verifier: str = "SYSTEM",
    ) -> Verification:
        """Evaluate post-maintenance telemetry against verification policy and update system state."""
        pol = policy or VerificationPolicy()
        now = datetime.now(timezone.utc)
        active_anoms = active_anomalies or []

        # 1. Calculate physical and operational deltas
        risk_delta = round(post_risk.risk_score - pre_risk.risk_score, 4)
        vib_delta = round(post_features.vibration_rms - pre_features.vibration_rms, 4)
        temp_delta = round(post_features.temperature_mean - pre_features.temperature_mean, 2)

        vib_reduction_pct = 0.0
        if pre_features.vibration_rms > 0:
            vib_reduction_pct = round(
                ((pre_features.vibration_rms - post_features.vibration_rms) / pre_features.vibration_rms) * 100.0,
                2,
            )

        risk_reduction_pct = 0.0
        if pre_risk.risk_score > 0:
            risk_reduction_pct = round(
                ((pre_risk.risk_score - post_risk.risk_score) / pre_risk.risk_score) * 100.0,
                2,
            )

        pre_oee_val = pre_oee.oee if pre_oee else 0.0
        post_oee_val = post_oee.oee if post_oee else 0.0
        oee_delta = round(post_oee_val - pre_oee_val, 4)

        has_critical_anomaly = any(
            a.severity in (Severity.CRITICAL, Severity.HIGH) and a.status == "ACTIVE"
            for a in active_anoms
        )

        # 2. Evaluate Policy
        vib_healthy = post_features.vibration_rms <= pol.max_acceptable_vibration_rms
        temp_healthy = post_features.temperature_mean <= pol.max_acceptable_temperature
        risk_healthy = post_risk.risk_score <= pol.max_acceptable_risk_score
        anomalies_cleared = (not has_critical_anomaly) if pol.require_zero_active_critical_anomalies else True

        if vib_healthy and temp_healthy and risk_healthy and anomalies_cleared:
            status = VerificationStatus.VERIFIED
            reason = (
                f"Physical verification PASSED: Vibration RMS reduced by {vib_reduction_pct}% "
                f"to {post_features.vibration_rms:.3f}g (threshold <= {pol.max_acceptable_vibration_rms}g). "
                f"Temperature normalized to {post_features.temperature_mean:.1f}°C. "
                f"Failure risk dropped by {risk_reduction_pct}% to {post_risk.risk_score:.2f}."
            )
        elif (
            (vib_reduction_pct >= 20.0 or risk_reduction_pct >= 30.0)
            and post_risk.risk_score <= 0.50
            and post_features.vibration_rms <= 0.65
        ):
            # Partial recovery: signals improved significantly but haven't met full nominal baseline
            status = VerificationStatus.PARTIALLY_VERIFIED
            reason = (
                f"Physical verification PARTIAL: Sensor signals improved (vibration reduced {vib_reduction_pct}%, "
                f"risk reduced {risk_reduction_pct}%), but signals remain above nominal healthy baseline. "
                f"Current vib: {post_features.vibration_rms:.3f}g, risk: {post_risk.risk_score:.2f}."
            )
        else:
            # Failed verification
            status = VerificationStatus.FAILED
            reason = (
                f"Physical verification FAILED: Post-maintenance telemetry indicates persisting abnormal operating "
                f"conditions. Vibration RMS: {post_features.vibration_rms:.3f}g (expected <= {pol.max_acceptable_vibration_rms}g), "
                f"Temperature: {post_features.temperature_mean:.1f}°C, Risk score: {post_risk.risk_score:.2f}."
            )

        # 3. Create Verification Record
        verification = Verification(
            verification_id=f"VERIF-{work_order_id}-{int(now.timestamp())}",
            investigation_id=investigation_id,
            work_order_id=work_order_id,
            machine_id=machine_id,
            verified_at=now,
            pre_vibration_rms=pre_features.vibration_rms,
            post_vibration_rms=post_features.vibration_rms,
            pre_temperature_c=pre_features.temperature_mean,
            post_temperature_c=post_features.temperature_mean,
            pre_risk_score=pre_risk.risk_score,
            post_risk_score=post_risk.risk_score,
            risk_delta=risk_delta,
            pre_oee=pre_oee_val,
            post_oee=post_oee_val,
            oee_delta=oee_delta,
            anomalies_before=1 if pre_risk.risk_score > 0.5 else 0,
            anomalies_after=len(active_anoms),
            is_recovered=(status == VerificationStatus.VERIFIED),
            verification_status=status,
            verification_reason=reason,
            oee_recovery_pct=round(oee_delta * 100.0, 2),
            notes=f"Evaluated with verifier '{verifier}' against VerificationPolicy.",
        )

        self.repo.save_verification(verification)

        # 4. Governed Lifecycle Transitions
        if status == VerificationStatus.VERIFIED:
            # Advance Work Order to VERIFIED
            if self.maintenance_repo:
                self.maintenance_repo.update_work_order_status(work_order_id, WorkOrderStatus.VERIFIED)

            # Advance Investigation to CLOSED
            if self.investigation_repo:
                inv = self.investigation_repo.get_investigation(investigation_id)
                if inv:
                    updated_inv = inv.model_copy(
                        update={
                            "status": InvestigationStatus.CLOSED,
                            "closed_at": now,
                            "summary": f"{inv.summary or ''} | Closed following successful physical verification.",
                        }
                    )
                    self.investigation_repo.update_investigation(updated_inv)

            # Update Machine Health to HEALTHY
            if self.machine_repo:
                self.machine_repo.update_machine_health(
                    machine_id=machine_id,
                    health_status=HealthStatus.HEALTHY,
                    state=MachineState.RUNNING,
                )

        elif status == VerificationStatus.PARTIALLY_VERIFIED:
            if self.investigation_repo:
                inv = self.investigation_repo.get_investigation(investigation_id)
                if inv:
                    updated_inv = inv.model_copy(
                        update={
                            "status": InvestigationStatus.REQUIRES_FOLLOW_UP,
                            "summary": f"{inv.summary or ''} | Verification partial: requires follow-up telemetry check.",
                        }
                    )
                    self.investigation_repo.update_investigation(updated_inv)

        elif status == VerificationStatus.FAILED:
            if self.investigation_repo:
                inv = self.investigation_repo.get_investigation(investigation_id)
                if inv:
                    updated_inv = inv.model_copy(
                        update={
                            "status": InvestigationStatus.VERIFICATION_FAILED,
                            "summary": f"{inv.summary or ''} | Post-maintenance verification failed: signals abnormal.",
                        }
                    )
                    self.investigation_repo.update_investigation(updated_inv)

        # 5. Governance Audit Event
        self._log_audit(
            actor=verifier,
            action_type="VERIFICATION_EVALUATED",
            resource_id=verification.verification_id,
            details={
                "work_order_id": work_order_id,
                "investigation_id": investigation_id,
                "verification_status": status.value,
                "is_recovered": verification.is_recovered,
                "risk_delta": risk_delta,
                "vib_reduction_pct": vib_reduction_pct,
                "reason": reason,
            },
        )

        return verification

    def _log_audit(self, actor: str, action_type: str, resource_id: str, details: Dict[str, Any]) -> None:
        if hasattr(self.repo, "log_audit"):
            event = AuditEvent(
                audit_id=f"AUD-{int(datetime.now(timezone.utc).timestamp() * 1000)}",
                actor=actor,
                action_type=action_type,
                resource_id=resource_id,
                resource_type="VERIFICATION",
                details=details,
            )
            self.repo.log_audit(event)
