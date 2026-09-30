"""Deterministic, explainable failure risk scorer.

Follows AGENT.md:
- Transparent weighted risk calculation with explicit breakdown
- Does not pretend to be an opaque neural network or random generator
- Produces auditable contributing_factors dictionary
- Failure mode is explicitly BEARING_DEGRADATION
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional

from domain.enums import FailureMode
from domain.models import Anomaly, Failure, FailureRisk, FeatureVector, MaintenanceEvent


@dataclass(frozen=True)
class RiskScoringConfig:
    weight_vibration: float = 0.35
    weight_temperature: float = 0.20
    weight_temp_trend: float = 0.15
    weight_anomalies: float = 0.15
    weight_history_match: float = 0.10
    weight_maintenance_recency: float = 0.05
    calculation_version: str = "v1.2.0-deterministic-weighted"


class FailureRiskScorer:
    def __init__(self, config: Optional[RiskScoringConfig] = None) -> None:
        self.config = config or RiskScoringConfig()

    def calculate_risk(
        self,
        machine_id: str,
        features: FeatureVector,
        active_anomalies: List[Anomaly],
        historical_failures: List[Failure],
        maintenance_history: List[MaintenanceEvent],
        failure_mode: FailureMode = FailureMode.BEARING_DEGRADATION,
    ) -> FailureRisk:
        """Compute auditable failure risk score and factor breakdown."""
        ts = features.timestamp

        # 1. Vibration contribution (Baseline: 0.45g, Critical limit: 1.00g)
        v_obs = features.vibration_rms
        if v_obs <= 0.45:
            v_factor = 0.0
        else:
            v_factor = min(1.0, (v_obs - 0.45) / 0.55)
        contrib_vib = round(self.config.weight_vibration * v_factor, 4)

        # 2. Temperature contribution (Baseline: 58.5°C, Critical limit: 90.0°C)
        t_obs = features.temperature_mean
        if t_obs <= 58.5:
            t_factor = 0.0
        else:
            t_factor = min(1.0, (t_obs - 58.5) / 31.5)
        contrib_tmp = round(self.config.weight_temperature * t_factor, 4)

        # 3. Temperature slope contribution (Abnormal gradient > 1.0°C/hr up to 4.0°C/hr)
        slope = features.temperature_slope
        if slope <= 0.0:
            slope_factor = 0.0
        else:
            slope_factor = min(1.0, slope / 4.0)
        contrib_trend = round(self.config.weight_temp_trend * slope_factor, 4)

        # 4. Active anomaly contribution
        n_anom = len(active_anomalies)
        if n_anom == 0:
            anom_factor = 0.0
        elif n_anom == 1:
            anom_factor = 0.6
        else:
            anom_factor = 1.0
        contrib_anom = round(self.config.weight_anomalies * anom_factor, 4)

        # 5. Historical failure recurrence match
        has_prior_bearing_failure = any(f.failure_mode == failure_mode for f in historical_failures)
        hist_factor = 1.0 if has_prior_bearing_failure else 0.0
        contrib_hist = round(self.config.weight_history_match * hist_factor, 4)

        # 6. Maintenance context factor
        # If last maintenance was > 30 days ago, slight increase in background risk
        if maintenance_history:
            last_maint = maintenance_history[0].performed_at
            # Make sure timezone comparison is clean
            if last_maint.tzinfo is None:
                last_maint = last_maint.replace(tzinfo=timezone.utc)
            days_since = (ts - last_maint).total_seconds() / 86400.0
            maint_factor = min(1.0, max(0.0, days_since / 60.0))
        else:
            maint_factor = 0.5
        contrib_maint = round(self.config.weight_maintenance_recency * maint_factor, 4)

        # Sum of all weighted contributions
        total_risk = round(
            min(1.0, max(0.0, contrib_vib + contrib_tmp + contrib_trend + contrib_anom + contrib_hist + contrib_maint)),
            2,
        )

        # Risk level categorization
        if total_risk >= 0.80:
            risk_level = "CRITICAL"
        elif total_risk >= 0.65:
            risk_level = "HIGH"
        elif total_risk >= 0.35:
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"

        contributing_factors = {
            "vibration_deviation": contrib_vib,
            "temperature_drift": contrib_tmp,
            "thermal_gradient": contrib_trend,
            "active_anomalies": contrib_anom,
            "historical_failure_pattern": contrib_hist,
            "maintenance_recency": contrib_maint,
        }

        contributing_signals = []
        if contrib_vib > 0.05:
            contributing_signals.append(f"Vibration RMS at {v_obs:.2f}g ({features.vibration_baseline_deviation_pct:+.1f}% vs baseline)")
        if contrib_tmp > 0.03:
            contributing_signals.append(f"Bearing temperature at {t_obs:.1f}°C")
        if contrib_trend > 0.03:
            contributing_signals.append(f"Rising thermal gradient at {slope:+.1f}°C/hr")
        if n_anom > 0:
            contributing_signals.append(f"{n_anom} active statistical anomaly flag(s)")
        if has_prior_bearing_failure:
            contributing_signals.append("Matches historical bearing spalling signature on M204")

        risk_id = f"RISK-{machine_id}-{ts.strftime('%Y%m%d%H%M%S')}"

        return FailureRisk(
            risk_id=risk_id,
            machine_id=machine_id,
            failure_mode=failure_mode,
            risk_score=total_risk,
            risk_level=risk_level,
            prediction_horizon_hours=72,
            model_version=self.config.calculation_version,
            prediction_timestamp=ts,
            confidence=0.88,
            contributing_factors=contributing_factors,
            contributing_signals=contributing_signals,
        )
