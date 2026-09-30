"""Read tools for machine and asset hierarchy context."""

from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field

from domain.models import Component, Machine, Sensor
from tools.read.base import BaseReadTool


class GetMachineContextInput(BaseModel):
    machine_id: str = Field(..., description="Unique machine identifier, e.g. 'M204'")


class MachineContextOutput(BaseModel):
    machine: Optional[Machine] = None
    components: List[Component] = Field(default_factory=list)
    sensors: List[Sensor] = Field(default_factory=list)
    line_name: Optional[str] = None
    plant_name: Optional[str] = None


class GetMachineContextTool(BaseReadTool):
    name = "get_machine_context"
    description = "Retrieve physical asset hierarchy, components, calibrated sensors, and status for a machine."
    scope = "asset:read"
    input_schema = GetMachineContextInput
    output_schema = MachineContextOutput

    def _run(self, params: GetMachineContextInput) -> MachineContextOutput:
        mach = self.repo.get_machine(params.machine_id)
        if not mach:
            return MachineContextOutput()

        comps = self.repo.get_components(params.machine_id)
        sensors = self.repo.get_sensors(params.machine_id)

        line_name = None
        plant_name = None
        plant = self.repo.get_plant("PLANT-01")
        if plant:
            plant_name = plant.name
            for line in self.repo.list_lines(plant.plant_id):
                if line.line_id == mach.line_id:
                    line_name = line.name
                    break

        return MachineContextOutput(
            machine=mach,
            components=comps,
            sensors=sensors,
            line_name=line_name,
            plant_name=plant_name,
        )
