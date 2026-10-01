"""Domain models for Analytics, OEE, Inventory Risk, and Production Context.

Follows AGENT.md v2.0:
- Explicit typed domain representations for COCO_FACTORY.ANALYTICS.* views
- Machine health and OEE calculations with bounded [0, 1] metrics
- Inventory exposure and production financial context
- Rolling 7d/30d ML feature representations
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class MachineHealthDaily(BaseModel):
    machine_id: str
    metric_date: date
    machine_name: str
    machine_type: str
    line_id: str
    line_name: str
    reading_count: int = 0
    avg_vibration: Optional[float] = None
    max_vibration: Optional[float] = None
    avg_temperature: Optional[float] = None
    max_temperature: Optional[float] = None
    exceedance_count: int = 0
    downtime_minutes: float = 0.0
    breakdown_count: int = 0
    maintenance_count: int = 0
    open_alerts: int = 0
    latest_prediction_id: Optional[str] = None
    latest_failure_prob: Optional[float] = None
    latest_risk_level: Optional[str] = None
    health_status: str = "HEALTHY"


class MachineOEEDaily(BaseModel):
    machine_id: str
    metric_date: date
    machine_name: str
    line_id: str
    planned_production_minutes: float
    operating_minutes: float
    unplanned_downtime_minutes: float
    total_pieces: int
    good_pieces: int
    reject_pieces: int
    availability: float = Field(..., ge=0.0, le=1.0)
    performance: float = Field(..., ge=0.0, le=1.0)
    quality: float = Field(..., ge=0.0, le=1.0)
    oee: float = Field(..., ge=0.0, le=1.0)


class DowntimeSummary(BaseModel):
    machine_id: str
    metric_date: date
    machine_name: str
    line_id: str
    total_downtime_minutes: float
    breakdown_minutes: float
    changeover_minutes: float
    minor_stop_minutes: float
    no_material_minutes: float
    no_operator_minutes: float
    planned_maintenance_minutes: float
    breakdown_event_count: int
    total_event_count: int
    top_reason_code: Optional[str] = None
    top_downtime_category: Optional[str] = None


class MaintenanceSummary(BaseModel):
    machine_id: str
    metric_date: date
    machine_name: str
    line_id: str
    work_order_count: int
    corrective_count: int
    preventive_count: int
    breakdown_count: int
    total_labor_hours: float
    total_parts_cost_inr: float
    total_labor_cost_inr: float
    total_maintenance_cost_inr: float
    mean_time_to_repair_minutes: Optional[float] = None


class InventoryRisk(BaseModel):
    part_id: str
    part_name: str
    part_category: str
    compatible_model: str
    stock_qty: int
    reorder_level: int
    reorder_qty: int
    lead_time_days: int
    supplier_id: str
    supplier_name: str
    open_po_count: int
    open_po_qty: int
    stock_status: str  # STOCKOUT, LOW_STOCK, HEALTHY
    is_critical_exposure: bool


class ProductionContext(BaseModel):
    production_order_id: str
    machine_id: str
    machine_name: str
    line_id: str
    product_id: str
    product_name: str
    customer: str
    priority: str
    status: str
    planned_qty: int
    produced_qty: int
    progress_pct: float
    due_date: date
    days_until_due: int
    is_overdue: bool
    unit_price_inr: float
    order_value_inr: float
    unfulfilled_revenue_exposure_inr: float


class ReliabilityFeatures(BaseModel):
    machine_id: str
    feature_date: date
    vib_mean_7d: Optional[float] = None
    vib_max_7d: Optional[float] = None
    vib_std_7d: Optional[float] = None
    vib_rel30: Optional[float] = None
    vib_slope_7d: Optional[float] = None
    temp_mean_7d: Optional[float] = None
    temp_max_7d: Optional[float] = None
    temp_rel30: Optional[float] = None
    exceedance_ratio_7d: Optional[float] = None
    downtime_ratio_7d: Optional[float] = None
    unplanned_downtime_hours_7d: Optional[float] = None
    breakdown_count_30d: int = 0
    days_since_last_maint: Optional[int] = None
