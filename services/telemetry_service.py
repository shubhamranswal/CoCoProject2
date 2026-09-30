"""Telemetry service for measurement recording and feature querying."""

from __future__ import annotations

from typing import List, Optional

from domain.models import FeatureVector, TelemetryMeasurement
from repositories.base import TelemetryRepository


class TelemetryService:
    def __init__(self, repository: TelemetryRepository) -> None:
        self.repo = repository

    def record_measurements(self, measurements: List[TelemetryMeasurement]) -> None:
        self.repo.save_measurements(measurements)

    def get_recent_measurements(
        self, machine_id: str, sensor_id: Optional[str] = None, limit: int = 100
    ) -> List[TelemetryMeasurement]:
        return self.repo.get_recent_measurements(machine_id, sensor_id=sensor_id, limit=limit)

    def get_latest_features(self, machine_id: str) -> Optional[FeatureVector]:
        return self.repo.get_latest_features(machine_id)
