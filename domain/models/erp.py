"""Canonical factory domain models for ERP, Supply Chain, and Predictions.

Follows AGENT.md v2.0:
- Explicit typed domain representations for 19-table canonical dataset
- Stable primary and foreign keys
- Clean representation of spare parts, suppliers, and customer orders
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class Product:
    product_id: str
    product_name: str
    product_family: str
    unit_price_inr: float
    unit_margin_inr: float
    cycle_time_multiplier: float = 1.0


@dataclass(frozen=True)
class ProductionOrder:
    production_order_id: str
    machine_id: str
    product_id: str
    customer: str
    planned_qty: int
    produced_qty: int
    planned_start: datetime
    planned_end: datetime
    due_date: date
    priority: str
    status: str  # completed, in_progress, scheduled


@dataclass(frozen=True)
class SparePart:
    part_id: str
    part_name: str
    part_category: str
    compatible_model: str
    unit_cost_inr: float
    supplier_id: str
    lead_time_days: int
    stock_qty: int
    reorder_level: int
    reorder_qty: int
    warehouse_bin: str

    @property
    def is_in_stock(self) -> bool:
        return self.stock_qty > 0


@dataclass(frozen=True)
class Supplier:
    supplier_id: str
    supplier_name: str
    country: str
    avg_lead_time_days: int
    on_time_delivery_pct: float


@dataclass(frozen=True)
class PurchaseOrder:
    po_id: str
    supplier_id: str
    part_id: str
    qty: int
    unit_cost_inr: float
    order_date: date
    expected_delivery_date: date
    actual_delivery_date: Optional[date] = None
    status: str = "received"  # received, pending, in_transit
    order_type: str = "replenishment"  # replenishment, expedited
    linked_wo_id: Optional[str] = None


@dataclass(frozen=True)
class WorkOrderPartUsage:
    wo_id: str
    part_id: str
    qty: int
    unit_cost_inr: float
    line_cost_inr: float


@dataclass(frozen=True)
class CanonicalPrediction:
    prediction_id: str
    scored_ts: datetime
    machine_id: str
    suspected_component_id: str
    model_name: str
    horizon_days: int
    failure_prob: float
    risk_level: str  # high, medium, low
    top_features: str  # JSON string of top contributing features
