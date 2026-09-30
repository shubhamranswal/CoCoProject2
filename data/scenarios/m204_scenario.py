"""M204 Bearing Degradation Scenario Engine.

Follows AGENT.md:
- 100% deterministic physical progression (no uncontrolled random seeds or random.random())
- Precursor signal progression:
  NORMAL -> DEGRADING -> ANOMALOUS -> HIGH_RISK -> MAINTENANCE_REQUIRED -> MAINTENANCE_COMPLETED -> RECOVERED
- Reproducible deterministic pseudo-noise derived strictly from timestamp and sensor identity
- Generates valid TelemetryMeasurement, ProductionRun, and DowntimeEvent domain objects
- Integrated with TelemetryService and TelemetryRepository
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from domain.enums import FailureMode, HealthStatus, MachineState, SensorType, Severity
from domain.models import DowntimeEvent, ProductionRun, TelemetryMeasurement


class ScenarioPhase(str, Enum):
    NORMAL = "NORMAL"
    DEGRADING = "DEGRADING"
    ANOMALOUS = "ANOMALOUS"
    HIGH_RISK = "HIGH_RISK"
    MAINTENANCE_REQUIRED = "MAINTENANCE_REQUIRED"
    MAINTENANCE_COMPLETED = "MAINTENANCE_COMPLETED"
    RECOVERED = "RECOVERED"


def deterministic_noise(timestamp: datetime, sensor_id: str, amplitude: float = 1.0) -> float:
    """Calculate reproducible harmonic pseudo-noise without any pseudo-random state.

    Given the exact same timestamp and sensor_id, this returns the exact same float.
    """
    epoch_sec = timestamp.timestamp()
    sensor_seed = sum((idx + 1) * ord(c) for idx, c in enumerate(sensor_id)) % 1000
    h1 = math.sin(epoch_sec * 0.05 + sensor_seed * 0.1)
    h2 = math.cos(epoch_sec * 0.13 + sensor_seed * 0.3)
    h3 = math.sin(epoch_sec * 0.37 + sensor_seed * 0.7)
    return round((0.55 * h1 + 0.30 * h2 + 0.15 * h3) * amplitude, 4)


class M204ScenarioEngine:
    """Physical scenario engine for machine M204 Conveyor Drive Motor."""

    def __init__(self, machine_id: str = "M204") -> None:
        self.machine_id = machine_id
        self._current_phase: ScenarioPhase = ScenarioPhase.NORMAL
        self._phase_history: List[Dict[str, Any]] = [
            {"phase": ScenarioPhase.NORMAL.value, "timestamp": datetime.now(timezone.utc), "reason": "Initial healthy state"}
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
            {"phase": ScenarioPhase.NORMAL.value, "timestamp": datetime.now(timezone.utc), "reason": "Scenario reset to healthy"}
        )

    def get_phase_profile(self, phase: ScenarioPhase, timestamp: datetime) -> Dict[str, Any]:
        """Return physically grounded nominal values + deterministic noise for a given phase."""
        if phase == ScenarioPhase.NORMAL:
            # Healthy baseline: Vibration RMS ~0.45g, Temp ~58.5°C, RPM ~1750
            vib = round(0.450 + deterministic_noise(timestamp, "SEN-M204-VIB", amplitude=0.015), 4)
            vib_peak = round(vib * (1.414 + deterministic_noise(timestamp, "PEAK", amplitude=0.02)), 4)
            temp = round(58.50 + deterministic_noise(timestamp, "SEN-M204-TMP", amplitude=0.40), 2)
            rpm = round(1750.0 + deterministic_noise(timestamp, "SEN-M204-RPM", amplitude=3.5), 1)
            curr = round(18.50 + deterministic_noise(timestamp, "SEN-M204-CUR", amplitude=0.20), 2)
            state = MachineState.RUNNING
            health = HealthStatus.HEALTHY

        elif phase == ScenarioPhase.DEGRADING:
            # Early raceway fatigue: +35% vibration, slight temperature drift (+8°C)
            vib = round(0.610 + deterministic_noise(timestamp, "SEN-M204-VIB", amplitude=0.020), 4)
            vib_peak = round(vib * (1.550 + deterministic_noise(timestamp, "PEAK", amplitude=0.03)), 4)
            temp = round(66.50 + deterministic_noise(timestamp, "SEN-M204-TMP", amplitude=0.50), 2)
            rpm = round(1747.0 + deterministic_noise(timestamp, "SEN-M204-RPM", amplitude=5.0), 1)
            curr = round(19.20 + deterministic_noise(timestamp, "SEN-M204-CUR", amplitude=0.25), 2)
            state = MachineState.RUNNING
            health = HealthStatus.DEGRADING

        elif phase == ScenarioPhase.ANOMALOUS:
            # Warning threshold crossed (>0.70g), temperature climbing (>74°C)
            vib = round(0.780 + deterministic_noise(timestamp, "SEN-M204-VIB", amplitude=0.025), 4)
            vib_peak = round(vib * (1.750 + deterministic_noise(timestamp, "PEAK", amplitude=0.04)), 4)
            temp = round(74.50 + deterministic_noise(timestamp, "SEN-M204-TMP", amplitude=0.70), 2)
            rpm = round(1738.0 + deterministic_noise(timestamp, "SEN-M204-RPM", amplitude=10.0), 1)
            curr = round(20.60 + deterministic_noise(timestamp, "SEN-M204-CUR", amplitude=0.35), 2)
            state = MachineState.RUNNING
            health = HealthStatus.DEGRADING

        elif phase == ScenarioPhase.HIGH_RISK:
            # Severe bearing degradation (+95% above baseline), RTD probe > 81°C
            vib = round(0.890 + deterministic_noise(timestamp, "SEN-M204-VIB", amplitude=0.030), 4)
            vib_peak = round(vib * (2.050 + deterministic_noise(timestamp, "PEAK", amplitude=0.05)), 4)
            temp = round(82.00 + deterministic_noise(timestamp, "SEN-M204-TMP", amplitude=0.90), 2)
            rpm = round(1722.0 + deterministic_noise(timestamp, "SEN-M204-RPM", amplitude=15.0), 1)
            curr = round(22.40 + deterministic_noise(timestamp, "SEN-M204-CUR", amplitude=0.45), 2)
            state = MachineState.RUNNING
            health = HealthStatus.CRITICAL

        elif phase == ScenarioPhase.MAINTENANCE_REQUIRED:
            # Machine powered down / locked out for bearing replacement
            vib = 0.0
            vib_peak = 0.0
            temp = 42.0
            rpm = 0.0
            curr = 0.0
            state = MachineState.MAINTENANCE
            health = HealthStatus.CRITICAL

        elif phase == ScenarioPhase.MAINTENANCE_COMPLETED:
            # Fresh bearing mounted, initial cold test run
            vib = round(0.440 + deterministic_noise(timestamp, "SEN-M204-VIB", amplitude=0.010), 4)
            vib_peak = round(vib * 1.414, 4)
            temp = 48.0
            rpm = 1750.0
            curr = 18.20
            state = MachineState.STARTING
            health = HealthStatus.HEALTHY

        elif phase == ScenarioPhase.RECOVERED:
            # Steady-state post-repair: vibration returned to healthy 0.43g, temp 57.5°C
            vib = round(0.430 + deterministic_noise(timestamp, "SEN-M204-VIB", amplitude=0.015), 4)
            vib_peak = round(vib * (1.414 + deterministic_noise(timestamp, "PEAK", amplitude=0.02)), 4)
            temp = round(57.50 + deterministic_noise(timestamp, "SEN-M204-TMP", amplitude=0.40), 2)
            rpm = round(1750.0 + deterministic_noise(timestamp, "SEN-M204-RPM", amplitude=3.0), 1)
            curr = round(18.40 + deterministic_noise(timestamp, "SEN-M204-CUR", amplitude=0.20), 2)
            state = MachineState.RUNNING
            health = HealthStatus.HEALTHY

        return {
            "vibration_rms": vib,
            "vibration_peak": vib_peak,
            "temperature_c": temp,
            "rpm": rpm,
            "current_a": curr,
            "machine_state": state,
            "health_status": health,
        }

    def generate_current_telemetry_profile(self, timestamp: Optional[datetime] = None) -> Dict[str, Any]:
        """Return the current phase profile including expected nominal risk score for testing."""
        ts = timestamp or datetime.now(timezone.utc)
        profile = dict(self.get_phase_profile(self._current_phase, ts))
        if self._current_phase == ScenarioPhase.NORMAL:
            profile["risk_score"] = 0.10
        elif self._current_phase == ScenarioPhase.DEGRADING:
            profile["risk_score"] = 0.42
        elif self._current_phase == ScenarioPhase.ANOMALOUS:
            profile["risk_score"] = 0.68
        elif self._current_phase == ScenarioPhase.HIGH_RISK:
            profile["risk_score"] = 0.86
        else:
            profile["risk_score"] = 0.10
        return profile


    def generate_measurements(
        self,
        phase: Optional[ScenarioPhase] = None,
        timestamp: Optional[datetime] = None,
        temp_offset: float = 0.0,
        vib_offset: float = 0.0,
    ) -> List[TelemetryMeasurement]:
        """Generate a single time-slice of measurements across all 4 calibrated sensors."""
        active_phase = phase or self._current_phase
        ts = timestamp or datetime.now(timezone.utc)
        profile = self.get_phase_profile(active_phase, ts)

        time_str = ts.strftime("%Y%m%d%H%M%S")
        vib_val = max(0.0, round(profile["vibration_rms"] + vib_offset, 4)) if profile["vibration_rms"] > 0 else 0.0
        temp_val = round(profile["temperature_c"] + temp_offset, 2)

        return [
            TelemetryMeasurement(
                measurement_id=f"MEAS-M204-VIB-{time_str}",
                machine_id=self.machine_id,
                sensor_id="SEN-M204-VIB",
                timestamp=ts,
                value=vib_val,
                unit="g",
                quality="VALID",
            ),
            TelemetryMeasurement(
                measurement_id=f"MEAS-M204-TMP-{time_str}",
                machine_id=self.machine_id,
                sensor_id="SEN-M204-TMP",
                timestamp=ts,
                value=temp_val,
                unit="°C",
                quality="VALID",
            ),
            TelemetryMeasurement(
                measurement_id=f"MEAS-M204-RPM-{time_str}",
                machine_id=self.machine_id,
                sensor_id="SEN-M204-RPM",
                timestamp=ts,
                value=profile["rpm"],
                unit="RPM",
                quality="VALID",
            ),
            TelemetryMeasurement(
                measurement_id=f"MEAS-M204-CUR-{time_str}",
                machine_id=self.machine_id,
                sensor_id="SEN-M204-CUR",
                timestamp=ts,
                value=profile["current_a"],
                unit="A",
                quality="VALID",
            ),
        ]

    def generate_timeseries(
        self,
        phase: Optional[ScenarioPhase] = None,
        num_points: int = 12,
        start_time: Optional[datetime] = None,
        step_minutes: int = 5,
    ) -> List[TelemetryMeasurement]:
        """Generate a deterministic sequence of measurements over a time window."""
        active_phase = phase or self._current_phase
        t0 = start_time or (datetime.now(timezone.utc) - timedelta(minutes=num_points * step_minutes))
        all_measurements: List[TelemetryMeasurement] = []

        for i in range(num_points):
            pt_time = t0 + timedelta(minutes=i * step_minutes)
            progression_ratio = i / max(1, num_points - 1)
            temp_trend = 0.0
            vib_trend = 0.0
            if active_phase == ScenarioPhase.DEGRADING:
                temp_trend = progression_ratio * 1.5
                vib_trend = progression_ratio * 0.02
            elif active_phase == ScenarioPhase.ANOMALOUS:
                temp_trend = progression_ratio * 2.5
                vib_trend = progression_ratio * 0.04
            elif active_phase == ScenarioPhase.HIGH_RISK:
                temp_trend = progression_ratio * 4.0
                vib_trend = progression_ratio * 0.06

            all_measurements.extend(
                self.generate_measurements(
                    phase=active_phase,
                    timestamp=pt_time,
                    temp_offset=temp_trend,
                    vib_offset=vib_trend,
                )
            )

        return all_measurements

    def generate_operational_context(
        self,
        phase: Optional[ScenarioPhase] = None,
        run_date: Optional[datetime] = None,
    ) -> Tuple[ProductionRun, Optional[DowntimeEvent]]:
        """Generate deterministic production run and downtime events linked to current phase."""
        active_phase = phase or self._current_phase
        base_time = run_date or datetime.now(timezone.utc)
        start_time = base_time.replace(hour=8, minute=0, second=0, microsecond=0)
        end_time = start_time + timedelta(hours=8)
        run_id = f"RUN-M204-{start_time.strftime('%Y%m%d')}"

        if active_phase == ScenarioPhase.NORMAL:
            # 8 hours planned, 0 downtime, 100% rate, 0.5% scrap
            prod = ProductionRun(
                run_id=run_id,
                line_id="LINE-B",
                machine_id=self.machine_id,
                product_code="PRD-BOTTLE-500ML",
                start_time=start_time,
                end_time=end_time,
                planned_units=2800,  # 350 units/hr * 8 hrs
                actual_units=2810,
                good_units=2796,
                scrap_units=14,
                ideal_cycle_time_seconds=10.28,  # ~350 units/hr
            )
            return prod, None

        elif active_phase == ScenarioPhase.DEGRADING:
            # Minor micro-hesitations, 96% output, 1.2% scrap
            prod = ProductionRun(
                run_id=run_id,
                line_id="LINE-B",
                machine_id=self.machine_id,
                product_code="PRD-BOTTLE-500ML",
                start_time=start_time,
                end_time=end_time,
                planned_units=2800,
                actual_units=2688,
                good_units=2655,
                scrap_units=33,
                ideal_cycle_time_seconds=10.28,
            )
            return prod, None

        elif active_phase == ScenarioPhase.ANOMALOUS:
            # De-rated motor speed to prevent seizure, 15 min micro-stops, 2.5% scrap
            prod = ProductionRun(
                run_id=run_id,
                line_id="LINE-B",
                machine_id=self.machine_id,
                product_code="PRD-BOTTLE-500ML",
                start_time=start_time,
                end_time=end_time,
                planned_units=2800,
                actual_units=2380,
                good_units=2320,
                scrap_units=60,
                ideal_cycle_time_seconds=10.28,
            )
            downtime = DowntimeEvent(
                downtime_id=f"DT-M204-{start_time.strftime('%Y%m%d')}-01",
                machine_id=self.machine_id,
                line_id="LINE-B",
                start_time=start_time + timedelta(hours=3),
                end_time=start_time + timedelta(hours=3, minutes=18),
                duration_minutes=18.0,
                reason_code="MOTOR_VIBRATION_SPIKE",
                category="UNPLANNED",
                description="Conveyor motor vibration warning prompted operator inspection and belt check",
            )
            return prod, downtime

        elif active_phase in (ScenarioPhase.HIGH_RISK, ScenarioPhase.MAINTENANCE_REQUIRED):
            # 60 min unplanned stops, de-rated throughput, 5% scrap
            prod = ProductionRun(
                run_id=run_id,
                line_id="LINE-B",
                machine_id=self.machine_id,
                product_code="PRD-BOTTLE-500ML",
                start_time=start_time,
                end_time=end_time,
                planned_units=2800,
                actual_units=1750,
                good_units=1662,
                scrap_units=88,
                ideal_cycle_time_seconds=10.28,
            )
            downtime = DowntimeEvent(
                downtime_id=f"DT-M204-{start_time.strftime('%Y%m%d')}-02",
                machine_id=self.machine_id,
                line_id="LINE-B",
                start_time=start_time + timedelta(hours=2),
                end_time=start_time + timedelta(hours=3, minutes=15),
                duration_minutes=75.0,
                reason_code="BEARING_OVERHEATING_STOP",
                category="UNPLANNED",
                description="Emergency stop: Drive-end bearing temperature reached 82°C",
            )
            return prod, downtime

        else:  # MAINTENANCE_COMPLETED or RECOVERED
            # Replaced bearing, 100% capacity restored, < 0.5% scrap
            prod = ProductionRun(
                run_id=run_id,
                line_id="LINE-B",
                machine_id=self.machine_id,
                product_code="PRD-BOTTLE-500ML",
                start_time=start_time,
                end_time=end_time,
                planned_units=2800,
                actual_units=2820,
                good_units=2810,
                scrap_units=10,
                ideal_cycle_time_seconds=10.28,
            )
            return prod, None


def run_m204_simulation() -> None:
    """Execute the end-to-end M204 Bearing Degradation pipeline across all operational phases."""
    from repositories.memory.memory_repository import InMemoryRepository
    from services.pipeline_orchestrator import PipelineOrchestrator

    repo = InMemoryRepository()
    orchestrator = PipelineOrchestrator(repository=repo)
    engine = M204ScenarioEngine(machine_id="M204")

    phases = [
        ScenarioPhase.NORMAL,
        ScenarioPhase.DEGRADING,
        ScenarioPhase.ANOMALOUS,
        ScenarioPhase.HIGH_RISK,
        ScenarioPhase.MAINTENANCE_REQUIRED,
        ScenarioPhase.RECOVERED,
    ]

    print("=" * 110)
    print(" FACTORY RELIABILITY COMMAND CENTER - M204 DETERMINISTIC INTELLIGENCE SPINE DEMO")
    print(" Architecture: Telemetry -> Features -> Baseline -> Anomaly -> Failure Risk -> Alert -> OEE")
    print("=" * 110)
    header = (
        f"{'Phase':<22} | {'Vib RMS':<9} | {'Temp':<7} | {'Anomalies':<10} | "
        f"{'Risk Score':<11} | {'Risk Level':<10} | {'Alert Severity':<15} | {'OEE %':<7} | {'Health':<10}"
    )
    print(header)
    print("-" * 110)

    base_time = datetime(2026, 3, 30, 6, 0, 0, tzinfo=timezone.utc)

    for idx, phase in enumerate(phases):
        t_phase = base_time + timedelta(hours=idx * 2)
        measurements = engine.generate_timeseries(phase=phase, num_points=12, start_time=t_phase, step_minutes=5)
        prod_run, dt_event = engine.generate_operational_context(phase=phase, run_date=t_phase)
        dt_list = [dt_event] if dt_event else None

        result = orchestrator.run_reliability_pipeline(
            machine_id="M204",
            measurements=measurements,
            production_run=prod_run,
            downtime_events=dt_list,
        )

        vib_val = f"{result.features.vibration_rms:.3f} g"
        temp_val = f"{result.features.temperature_mean:.1f}°C"
        anom_str = f"{len(result.anomalies)} active"
        risk_str = f"{result.failure_risk.risk_score:.3f}"
        risk_lvl = result.failure_risk.risk_level.value if hasattr(result.failure_risk.risk_level, 'value') else str(result.failure_risk.risk_level)
        alert_str = result.alert.severity.value if result.alert else "NONE"
        oee_str = f"{result.oee.oee * 100:.1f}%" if result.oee else "N/A"
        health_str = result.machine_health.value if hasattr(result.machine_health, 'value') else str(result.machine_health)

        row = (
            f"{phase.value:<22} | {vib_val:<9} | {temp_val:<7} | {anom_str:<10} | "
            f"{risk_str:<11} | {risk_lvl:<10} | {alert_str:<15} | {oee_str:<7} | {health_str:<10}"
        )
        print(row)

    print("=" * 110)
    print(" Simulation completed deterministically. Zero stochastic/random state used.")
    print("=" * 110)


if __name__ == "__main__":
    run_m204_simulation()

