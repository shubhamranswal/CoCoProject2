"""Deterministic and explainable industrial anomaly detection service.

Follows AGENT.md & architecture/architecture.md:
- Detects threshold deviation, rolling deviation, trend deviation, and multi-signal coupling
- Answers: What is normal? What is observed? How far from normal? How fast is it changing?
- Produces structured, explainable Anomaly domain models
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Optional

from domain.enums import Severity
from domain.models import Anomaly, Baseline, FeatureVector
from repositories.base import TelemetryRepository


class AnomalyService:
    def __init__(self, repository: TelemetryRepository) -> None:
        self.repo = repository

    def detect_anomalies(
        self,
        features: FeatureVector,
        baselines: Optional[Dict[str, Baseline]] = None,
    ) -> List[Anomaly]:
        """Detect equipment anomalies using deterministic statistical and engineering rules."""
        machine_id = features.machine_id
        ts = features.timestamp

        # Load baselines from repository if not directly provided
        b_dict = baselines or {}
        if not b_dict:
            for sig in ("vibration_rms", "temperature", "rpm", "current"):
                b = self.repo.get_baseline(machine_id, sig)
                if b:
                    b_dict[sig] = b

        anomalies: List[Anomaly] = []

        # 1. Vibration Anomaly Detection (Threshold + Rolling RMS)
        vib_base = b_dict.get("vibration_rms")
        if vib_base:
            observed_vib = features.vibration_rms
            if observed_vib >= vib_base.warning_threshold:
                # Calculate z-score deviation
                z_score = round((observed_vib - vib_base.baseline_mean) / max(vib_base.baseline_std, 1e-4), 2)
                dev_pct = round(((observed_vib - vib_base.baseline_mean) / vib_base.baseline_mean) * 100.0, 2)

                if observed_vib >= vib_base.critical_threshold:
                    sev = Severity.CRITICAL
                elif observed_vib >= 0.85:
                    sev = Severity.HIGH
                else:
                    sev = Severity.MEDIUM

                anomaly_vib = Anomaly(
                    anomaly_id=f"ANOM-{machine_id}-VIB-{ts.strftime('%Y%m%d%H%M%S')}",
                    machine_id=machine_id,
                    sensor_id="SEN-M204-VIB",
                    detected_at=ts,
                    severity=sev,
                    score=z_score,
                    metric_name="vibration_rms",
                    observed_value=observed_vib,
                    baseline_value=vib_base.baseline_mean,
                    deviation_pct=dev_pct,
                    detection_method="baseline_threshold + rolling_rms",
                    status="ACTIVE",
                )
                anomalies.append(anomaly_vib)
                self.repo.save_anomaly(anomaly_vib)

        # 2. Temperature Anomaly Detection (Threshold + Gradient)
        tmp_base = b_dict.get("temperature")
        if tmp_base:
            observed_tmp = features.temperature_mean
            slope = features.temperature_slope
            is_threshold_exceeded = observed_tmp >= tmp_base.warning_threshold
            is_gradient_abnormal = slope >= 1.5  # Rising faster than +1.5°C per hour under nominal load

            if is_threshold_exceeded or is_gradient_abnormal:
                z_score = round((observed_tmp - tmp_base.baseline_mean) / max(tmp_base.baseline_std, 1e-4), 2)
                dev_pct = round(((observed_tmp - tmp_base.baseline_mean) / tmp_base.baseline_mean) * 100.0, 2)

                if observed_tmp >= tmp_base.critical_threshold or slope >= 3.5:
                    sev = Severity.CRITICAL
                elif observed_tmp >= 80.0 or slope >= 2.0:
                    sev = Severity.HIGH
                else:
                    sev = Severity.MEDIUM

                method = "trend_gradient" if is_gradient_abnormal and not is_threshold_exceeded else "baseline_threshold + trend"

                anomaly_tmp = Anomaly(
                    anomaly_id=f"ANOM-{machine_id}-TMP-{ts.strftime('%Y%m%d%H%M%S')}",
                    machine_id=machine_id,
                    sensor_id="SEN-M204-TMP",
                    detected_at=ts,
                    severity=sev,
                    score=z_score,
                    metric_name="temperature",
                    observed_value=observed_tmp,
                    baseline_value=tmp_base.baseline_mean,
                    deviation_pct=dev_pct,
                    detection_method=method,
                    status="ACTIVE",
                )
                anomalies.append(anomaly_tmp)
                self.repo.save_anomaly(anomaly_tmp)

        # 3. Multi-Signal Coupled Anomaly (High vibration coupled with rising temperature)
        if vib_base and tmp_base:
            if features.vibration_rms >= 0.70 and (features.temperature_mean >= 70.0 or features.temperature_slope >= 1.2):
                coupled_score = round(
                    ((features.vibration_rms / vib_base.baseline_mean) + (features.temperature_mean / tmp_base.baseline_mean)) / 2.0, 2
                )
                sev = Severity.HIGH if features.vibration_rms >= 0.85 else Severity.MEDIUM
                coupled_anom = Anomaly(
                    anomaly_id=f"ANOM-{machine_id}-MULTI-{ts.strftime('%Y%m%d%H%M%S')}",
                    machine_id=machine_id,
                    sensor_id="SEN-M204-VIB",
                    detected_at=ts,
                    severity=sev,
                    score=coupled_score,
                    metric_name="bearing_thermal_vibrational_coupling",
                    observed_value=features.vibration_rms,
                    baseline_value=vib_base.baseline_mean,
                    deviation_pct=round(((features.vibration_rms - vib_base.baseline_mean) / vib_base.baseline_mean) * 100.0, 2),
                    detection_method="multi_signal_coupling",
                    status="ACTIVE",
                )
                anomalies.append(coupled_anom)
                self.repo.save_anomaly(coupled_anom)

        return anomalies
