from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, root_validator


class QuotationAction(str, Enum):
    GENERATE = "GENERATE"


class QuotationItem(BaseModel):
    size: str = Field(..., description="Size identifier for the quotation line.")
    quantity: int = Field(..., gt=0, description="Requested quantity for the given size.")


class QuotationCreatePayload(BaseModel):
    design_id: str = Field(..., description="Design identifier to generate a quotation for.")
    selling_price_per_piece: float = Field(..., gt=0, description="Unit selling price used to compute totals.")
    items: List[QuotationItem] = Field(..., min_items=1, description="List of sizes and requested quantities.")


class QuotationOperationRequest(BaseModel):
    action: QuotationAction
    payload: Optional[Dict[str, Any]] = None

    @root_validator(pre=True)
    def validate_payload(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        raw_action = values.get("action")
        if not raw_action:
            return values

        try:
            action = raw_action if isinstance(raw_action, QuotationAction) else QuotationAction(raw_action)
        except ValueError:
            return values

        if action == QuotationAction.GENERATE and not values.get("payload"):
            raise ValueError("payload is required for GENERATE action.")
        return values


class QuotationLine(BaseModel):
    size: str
    requested_quantity: int
    available_quantity: int
    selling_price: float
    line_total: float


class QuotationResponse(BaseModel):
    design_id: str
    total_requested_quantity: int
    total_amount: float
    unit_price: float
    items: List[QuotationLine]
    available_inventory: Dict[str, int]
    generated_at: datetime
