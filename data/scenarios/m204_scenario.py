"""M204 Bearing Degradation Scenario Skeleton.

Follows AGENT.md:
- Precursor signal progression, not just a boolean failure=true
- State transition: NORMAL -> DEGRADING -> ANOMALOUS -> HIGH_RISK -> MAINTENANCE_REQUIRED -> MAINTENANCE_COMPLETED -> RECOVERED
- Resettable demo capability (reset_demo)
- Isolated from Streamlit rendering code
"""

from __future__ import annotations

from enum import Enum
from typing import Dict, Any, List
from datetime import datetime, timezone
import random

from domain.enums import FailureMode, HealthStatus, MachineState, Severity
from domain.models import Anomaly, FailureRisk, FeatureVector, TelemetryMeasurement


class ScenarioPhase(str, Enum):
    NORMAL = "NORMAL"
    DEGRADING = "DEGRADING"
    ANOMALOUS = "ANOMALOUS"
    HIGH_RISK = "HIGH_RISK"
    MAINTENANCE_REQUIRED = "MAINTENANCE_REQUIRED"
    MAINTENANCE_COMPLETED = "MAINTENANCE_COMPLETED"
    RECOVERED = "RECOVERED"


class M204ScenarioEngine:
    def __init__(self, machine_id: str = "M204") -> None:
        self.machine_id = machine_id
        self._current_phase: ScenarioPhase = ScenarioPhase.NORMAL
        self._phase_history: List[Dict[str, Any]] = [
            {"phase": ScenarioPhase.NORMAL.value, "timestamp": datetime.now(timezone.utc)}
        ]

    @property
    def current_phase(self) -> ScenarioPhase:
        return self._current_phase

    def get_phase_history(self) -> List[Dict[str, Any]]:
        return list(self._phase_history)

    def transition_to(self, phase: ScenarioPhase, reason: str = "") -> None:
        self._current_phase = phase
        self._phase_history.append(
            {"phase": phase.value, "timestamp": datetime.now(timezone.utc), "reason": reason}
        )

    def reset_to_healthy(self) -> None:
        """Reset scenario back to baseline healthy state."""
        self._current_phase = ScenarioPhase.NORMAL
        self._phase_history.append(
            {"phase": ScenarioPhase.NORMAL.value, "timestamp": datetime.now(timezone.utc), "reason": "Manual scenario reset"}
        )

    def generate_current_telemetry_profile(self, timestamp: datetime | None = None) -> Dict[str, Any]:
        """Return realistic physical telemetry values consistent with current degradation phase."""
        ts = timestamp or datetime.now(timezone.utc)

        if self._current_phase == ScenarioPhase.NORMAL:
            vib_rms = round(random.gauss(0.45, 0.02), 3)
            vib_peak = round(vib_rms * 1.45, 3)
            temp = round(random.gauss(58.5, 0.5), 1)
            rpm = round(random.gauss(1750.0, 5.0), 1)
            current = round(random.gauss(18.5, 0.2), 1)
            risk = 0.12
            health_status = HealthStatus.HEALTHY
            machine_state = MachineState.RUNNING

        elif self._current_phase == ScenarioPhase.DEGRADING:
            # Subtly elevated vibration (+35%) and temperature drift
            vib_rms = round(random.gauss(0.62, 0.03), 3)
            vib_peak = round(vib_rms * 1.6, 3)
            temp = round(random.gauss(66.5, 0.8), 1)
            rpm = round(random.gauss(1746.0, 7.0), 1)
            current = round(random.gauss(19.2, 0.3), 1)
            risk = 0.45
            health_status = HealthStatus.DEGRADING
            machine_state = MachineState.RUNNING

        elif self._current_phase == ScenarioPhase.ANOMALOUS:
            # Crossed warning threshold (0.70g), noticeable temperature slope
            vib_rms = round(random.gauss(0.78, 0.04), 3)
            vib_peak = round(vib_rms * 1.8, 3)
            temp = round(random.gauss(74.2, 1.0), 1)
            rpm = round(random.gauss(1738.0, 12.0), 1)
            current = round(random.gauss(20.5, 0.4), 1)
            risk = 0.72
            health_status = HealthStatus.DEGRADING
            machine_state = MachineState.RUNNING

        elif self._current_phase == ScenarioPhase.HIGH_RISK:
            # Severe bearing degradation (+95% above baseline), RTD probe near 82°C
            vib_rms = round(random.gauss(0.88, 0.04), 3)
            vib_peak = round(vib_rms * 2.1, 3)
            temp = round(random.gauss(81.5, 1.2), 1)
            rpm = round(random.gauss(1725.0, 18.0), 1)
            current = round(random.gauss(21.8, 0.5), 1)
            risk = 0.87
            health_status = HealthStatus.CRITICAL
            machine_state = MachineState.RUNNING

        elif self._current_phase == ScenarioPhase.MAINTENANCE_REQUIRED:
            vib_rms = 0.0
            vib_peak = 0.0
            temp = 42.0
            rpm = 0.0
            current = 0.0
            risk = 0.87
            health_status = HealthStatus.CRITICAL
            machine_state = MachineState.MAINTENANCE

        elif self._current_phase == ScenarioPhase.MAINTENANCE_COMPLETED:
            # Bearing replaced, preliminary test spin
            vib_rms = round(random.gauss(0.44, 0.01), 3)
            vib_peak = round(vib_rms * 1.4, 3)
            temp = 48.0
            rpm = 1750.0
            current = 18.2
            risk = 0.15
            health_status = HealthStatus.HEALTHY
            machine_state = MachineState.STARTING

        elif self._current_phase == ScenarioPhase.RECOVERED:
            # Fully operational after maintenance, steady state
            vib_rms = round(random.gauss(0.43, 0.02), 3)
            vib_peak = round(vib_rms * 1.42, 3)
            temp = round(random.gauss(57.5, 0.5), 1)
            rpm = round(random.gauss(1750.0, 4.0), 1)
            current = round(random.gauss(18.4, 0.2), 1)
            risk = 0.08
            health_status = HealthStatus.HEALTHY
            machine_state = MachineState.RUNNING

        return {
            "machine_id": self.machine_id,
            "timestamp": ts,
            "phase": self._current_phase.value,
            "vibration_rms": vib_rms,
            "vibration_peak": vib_peak,
            "temperature_c": temp,
            "rpm": rpm,
            "current_a": current,
            "risk_score": risk,
            "health_status": health_status,
            "machine_state": machine_state,
        }
