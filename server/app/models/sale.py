from enum import Enum
from typing import List, Optional, Any, Dict
from datetime import datetime

from pydantic import BaseModel, Field, validator, root_validator


class SaleAction(str, Enum):
    CREATE = "CREATE"
    READ_ALL = "READ_ALL"
    GET_BY_ID = "GET_BY_ID"
    GET_BY_DESIGN = "GET_BY_DESIGN"
    UPDATE = "UPDATE"
    DELETE = "DELETE"


class SaleItem(BaseModel):
    size: str = Field(..., description="Size identifier sold.")
    quantity: int = Field(..., gt=0, description="Quantity sold for the given size.")


class SaleCreatePayload(BaseModel):
    customer_name: str = Field(..., description="Customer full name.")
    customer_phone: str = Field(..., description="Customer contact number.")
    design_id: str = Field(..., description="Design identifier for the sold garment.")
    items: List[SaleItem] = Field(..., min_items=1, description="List of sizes and quantities sold.")

    @validator("customer_phone")
    def validate_contact(cls, v: str) -> str:
        normalized = v.strip()
        if len(normalized) < 7:
            raise ValueError("customer_phone must contain at least 7 digits.")
        return normalized


class SaleOperationRequest(BaseModel):
    action: SaleAction
    sale_id: Optional[str] = None
    design_id: Optional[str] = None
    payload: Optional[SaleCreatePayload] = None

    @root_validator(pre=True)
    def validate_requirements(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        raw_action = values.get("action")
        if not raw_action:
            return values

        try:
            action = raw_action if isinstance(raw_action, SaleAction) else SaleAction(raw_action)
        except ValueError:
            return values

        sale_id = values.get("sale_id")
        design_id = values.get("design_id")
        payload = values.get("payload")

        if action in {SaleAction.GET_BY_ID, SaleAction.UPDATE, SaleAction.DELETE} and not sale_id:
            raise ValueError(f"sale_id is required for {action} action.")

        if action == SaleAction.GET_BY_DESIGN and not design_id:
            raise ValueError("design_id is required for GET_BY_DESIGN action.")

        if action in {SaleAction.CREATE, SaleAction.UPDATE} and not payload:
            raise ValueError(f"payload is required for {action} action.")

        return values


class SaleRecord(BaseModel):
    id: str
    customer_name: str
    customer_phone: str
    design_id: str
    items: List[SaleItem]
    total_quantity: int
    created_at: datetime
    updated_at: Optional[datetime] = None
