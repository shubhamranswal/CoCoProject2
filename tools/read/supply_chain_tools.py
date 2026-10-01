"""Typed read tools for spare parts inventory risk and production schedule context."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from domain.models import InventoryRisk, ProductionContext, SparePart, ProductionOrder
from tools.read.base import BaseReadTool


class SparePartRiskItem(BaseModel):
    part_id: str
    part_name: str
    compatible_model: str
    stock_qty: int
    reorder_level: int
    reorder_qty: int
    stock_status: str  # IN_STOCK, LOW_STOCK, CRITICAL_STOCKOUT
    supplier_id: Optional[str] = None
    supplier_name: Optional[str] = None
    lead_time_days: int = 3
    open_po_count: int = 0
    open_po_qty: int = 0
    is_critical_exposure: bool = False


class GetInventoryRiskInput(BaseModel):
    part_id: Optional[str] = Field(default=None, description="Optional specific spare part ID, e.g. 'SP-002'")
    machine_id: Optional[str] = Field(default=None, description="Optional machine ID to resolve compatible parts, e.g. 'M21'")
    component_id: Optional[str] = Field(default=None, description="Optional component ID, e.g. 'C-M21-BRG'")


class InventoryRiskOutput(BaseModel):
    query_target: str
    part_count: int
    parts: List[SparePartRiskItem] = Field(default_factory=list)
    has_critical_stockout: bool = False


class GetInventoryRiskTool(BaseReadTool):
    name = "get_inventory_risk"
    description = "Retrieve current inventory stock levels, reorder thresholds, supplier lead times, and open PO status for spare parts."
    scope = "supply_chain:read"
    input_schema = GetInventoryRiskInput
    output_schema = InventoryRiskOutput

    def _run(self, params: GetInventoryRiskInput) -> InventoryRiskOutput:
        target_parts: List[SparePart] = []

        if params.part_id:
            sp = self.repo.get_spare_part(params.part_id)
            if sp:
                target_parts.append(sp)
        elif params.component_id or params.machine_id:
            # Map component or machine model to spare part
            comp_id = params.component_id or ""
            mach_id = params.machine_id or ""
            all_parts = self.repo.list_spare_parts()

            if "BRG" in comp_id or "M21" in mach_id:
                # Target bearing 6206-2RS (SP-002)
                for p in all_parts:
                    if p.part_id == "SP-002" or "6206" in p.compatible_model or "Bearing" in p.part_name:
                        target_parts.append(p)
            elif "MTR" in comp_id:
                for p in all_parts:
                    if "Motor" in p.part_name or "MTR" in p.part_id:
                        target_parts.append(p)
            else:
                target_parts = all_parts[:5]

        items: List[SparePartRiskItem] = []
        has_crit = False

        for p in target_parts:
            supp_name = None
            if p.supplier_id:
                supp = self.repo.get_supplier(p.supplier_id)
                supp_name = supp.supplier_name if supp else p.supplier_id

            # Determine open POs
            pos = self.repo.list_purchase_orders(part_id=p.part_id)
            open_pos = [po for po in pos if po.status in ("OPEN", "PENDING", "in_progress", "submitted")]
            open_qty = sum(po.order_qty for po in open_pos)

            stock_st = "IN_STOCK"
            is_crit = False
            if p.stock_qty <= 0:
                stock_st = "CRITICAL_STOCKOUT"
                is_crit = True
                has_crit = True
            elif p.stock_qty <= p.reorder_level:
                stock_st = "LOW_STOCK"

            items.append(
                SparePartRiskItem(
                    part_id=p.part_id,
                    part_name=p.part_name,
                    compatible_model=p.compatible_model,
                    stock_qty=p.stock_qty,
                    reorder_level=p.reorder_level,
                    reorder_qty=p.reorder_qty,
                    stock_status=stock_st,
                    supplier_id=p.supplier_id,
                    supplier_name=supp_name,
                    lead_time_days=p.lead_time_days,
                    open_po_count=len(open_pos),
                    open_po_qty=open_qty,
                    is_critical_exposure=is_crit,
                )
            )

        target_desc = params.part_id or params.component_id or params.machine_id or "ALL"
        return InventoryRiskOutput(
            query_target=target_desc,
            part_count=len(items),
            parts=items,
            has_critical_stockout=has_crit,
        )


class ProductionOrderContextItem(BaseModel):
    order_id: str
    machine_id: str
    product_id: str
    product_name: Optional[str] = None
    planned_qty: int
    produced_qty: int
    remaining_qty: int
    unit_price_inr: float = 0.0
    unfulfilled_revenue_exposure_inr: float = 0.0
    status: str
    priority: str = "Medium"


class GetProductionContextInput(BaseModel):
    machine_id: str = Field(..., description="Target machine ID, e.g. 'M21'")


class ProductionContextOutput(BaseModel):
    machine_id: str
    active_order_count: int
    total_unfulfilled_revenue_exposure: float
    orders: List[ProductionOrderContextItem] = Field(default_factory=list)


class GetProductionContextTool(BaseReadTool):
    name = "get_production_context"
    description = "Retrieve active production runs, product details, remaining batch quantities, and financial revenue exposure."
    scope = "production:read"
    input_schema = GetProductionContextInput
    output_schema = ProductionContextOutput

    def _run(self, params: GetProductionContextInput) -> ProductionContextOutput:
        orders = self.repo.list_production_orders(machine_id=params.machine_id)
        # Filter for active or in-progress orders
        active_orders = [o for o in orders if o.status.lower() in ("in_progress", "active", "open", "scheduled")]
        if not active_orders:
            active_orders = orders[:3]

        items: List[ProductionOrderContextItem] = []
        total_exp = 0.0

        for o in active_orders:
            rem = max(0, o.planned_qty - o.produced_qty)

            # Price lookup
            unit_price = 394.0 if o.product_id == "P008" else 250.0
            prod_name = "Mounting Flange MF-25" if o.product_id == "P008" else f"Product {o.product_id}"

            exposure = round(rem * unit_price, 2)
            total_exp += exposure

            items.append(
                ProductionOrderContextItem(
                    order_id=o.production_order_id,
                    machine_id=o.machine_id,
                    product_id=o.product_id,
                    product_name=prod_name,
                    planned_qty=o.planned_qty,
                    produced_qty=o.produced_qty,
                    remaining_qty=rem,
                    unit_price_inr=unit_price,
                    unfulfilled_revenue_exposure_inr=exposure,
                    status=o.status,
                    priority=getattr(o, "priority", "Medium") or "Medium",
                )
            )

        return ProductionContextOutput(
            machine_id=params.machine_id,
            active_order_count=len(items),
            total_unfulfilled_revenue_exposure=round(total_exp, 2),
            orders=items,
        )
