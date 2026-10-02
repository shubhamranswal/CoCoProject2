"""Asset hierarchy domain models following ontology.md."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field

from domain.enums import HealthStatus, MachineState, SensorType


class Plant(BaseModel):
    plant_id: str
    plant_code: str
    name: str
    location: str
    timezone: str = "UTC"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ProductionLine(BaseModel):
    line_id: str
    plant_id: str
    line_code: str
    name: str
    target_units_per_hour: float = 100.0
    status: str = "ACTIVE"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Machine(BaseModel):
    machine_id: str
    line_id: str
    machine_code: str
    name: str
    asset_type: str = "MOTOR"
    criticality: str = "HIGH"
    health_status: HealthStatus = HealthStatus.HEALTHY
    state: MachineState = MachineState.RUNNING
    manufacturer: str = "Industrial Dynamics"
    model: str = "DRV-5000"
    serial_number: str = "SN-2024-M204"
    commission_date: Optional[datetime] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    plant_id: Optional[str] = None


class Component(BaseModel):
    component_id: str
    machine_id: str
    name: str
    component_type: str  # e.g. BEARING, STATOR, ROTOR, GEARBOX
    criticality: str = "HIGH"
    installed_at: Optional[datetime] = None
    health_status: HealthStatus = HealthStatus.HEALTHY


class Sensor(BaseModel):
    sensor_id: str
    machine_id: str
    component_id: Optional[str] = None
    sensor_type: SensorType
    name: str
    unit: str  # e.g. "g", "°C", "RPM", "A"
    sampling_rate_hz: float = 1.0
    range_min: float
    range_max: float
    is_active: bool = True
    warn_threshold: Optional[float] = None
    crit_threshold: Optional[float] = None
    signal_name: Optional[str] = None

