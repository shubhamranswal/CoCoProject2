"""Governed Spare Parts Inventory action tools.

Follows Milestone 5 Zero-Trust Architecture:
- Requires verified Human Approval record in repository
- Enforces strict inventory reality: cannot reserve unavailable stock (e.g. SP-002)
- Rejects negative allocations or fabricated procurement
- Returns structured reservation status and replenishment lead times
- Fully audited and idempotent
"""

from __future__ import annotations

from typing import Any, Dict, Optional
from pydantic import BaseModel, Field

from repositories.base import GovernanceRepository, SupplyChainRepository
from services.approval_service import ApprovalService
from tools.actions.base import BaseActionTool


class ReserveSparePartInput(BaseModel):
    """Input payload for governed spare part reservation."""

    approval_id: str = Field(description="Repository approval ID granting authorization")
    machine_id: str = Field(description="Target machine ID")
    part_id: str = Field(description="Target spare part ID")
    qty: int = Field(default=1, description="Quantity to reserve")
    idempotency_key: Optional[str] = Field(default=None, description="Unique client key ensuring idempotent execution")


class ReserveSparePartResult(BaseModel):
    """Result of spare part reservation request."""

    success: bool
    part_id: str
    part_name: Optional[str] = None
    qty_requested: int
    qty_reserved: int
    remaining_stock: int
    lead_time_days: int
    status: str  # RESERVED, SHORTAGE, NOT_FOUND
    message: str


class ReserveSparePartAction(BaseActionTool):
    """Governed action tool to reserve spare parts from warehouse inventory."""

    name: str = "reserve_spare_part"
    description: str = "Reserve spare parts in CORE.SPARE_PART inventory following human approval."
    input_schema = ReserveSparePartInput
    output_schema = ReserveSparePartResult

    def __init__(
        self,
        approval_service: ApprovalService,
        supply_chain_repo: SupplyChainRepository,
        governance_repo: Optional[GovernanceRepository] = None,
    ) -> None:
        super().__init__(approval_service=approval_service, governance_repo=governance_repo)
        self.supply_chain_repo = supply_chain_repo

    def _run(self, params: ReserveSparePartInput, caller_actor: str) -> ReserveSparePartResult:
        """Reserve spare parts safely or return structured shortage diagnostics."""
        part = self.supply_chain_repo.get_spare_part(params.part_id)
        if not part:
            return ReserveSparePartResult(
                success=False,
                part_id=params.part_id,
                qty_requested=params.qty,
                qty_reserved=0,
                remaining_stock=0,
                lead_time_days=0,
                status="NOT_FOUND",
                message=f"Spare part '{params.part_id}' not found in inventory catalog.",
            )

        if part.stock_qty < params.qty:
            return ReserveSparePartResult(
                success=False,
                part_id=params.part_id,
                part_name=part.part_name,
                qty_requested=params.qty,
                qty_reserved=0,
                remaining_stock=part.stock_qty,
                lead_time_days=part.lead_time_days,
                status="SHORTAGE",
                message=(
                    f"Inventory shortage for part '{params.part_id}' ({part.part_name}). "
                    f"Requested {params.qty}, but available stock is {part.stock_qty}. "
                    f"Supplier replenishment lead time is {part.lead_time_days} days. "
                    f"Reservation rejected safely."
                ),
            )

        reserved = self.supply_chain_repo.reserve_spare_part(params.part_id, qty=params.qty)
        if not reserved:
            return ReserveSparePartResult(
                success=False,
                part_id=params.part_id,
                part_name=part.part_name,
                qty_requested=params.qty,
                qty_reserved=0,
                remaining_stock=part.stock_qty,
                lead_time_days=part.lead_time_days,
                status="RESERVATION_FAILED",
                message=f"Failed to reserve {params.qty} unit(s) of part '{params.part_id}'.",
            )

        # Successfully reserved
        new_part = self.supply_chain_repo.get_spare_part(params.part_id)
        new_stock = new_part.stock_qty if new_part else (part.stock_qty - params.qty)
        return ReserveSparePartResult(
            success=True,
            part_id=params.part_id,
            part_name=part.part_name,
            qty_requested=params.qty,
            qty_reserved=params.qty,
            remaining_stock=new_stock,
            lead_time_days=part.lead_time_days,
            status="RESERVED",
            message=f"Successfully reserved {params.qty} unit(s) of '{part.part_name}' (part_id={params.part_id}). Remaining stock: {new_stock}.",
        )
