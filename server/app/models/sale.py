from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, root_validator, validator


class PaymentType(str, Enum):
    CASH = "cash"
    CREDIT = "credit"


class SaleAction(str, Enum):
    CREATE = "CREATE"
    READ_ALL = "READ_ALL"
    GET_BY_ID = "GET_BY_ID"
    GET_BY_DESIGN = "GET_BY_DESIGN"
    GET_CREDIT_SALES = "GET_CREDIT_SALES"
    MAKE_PAYMENT = "MAKE_PAYMENT"
    GET_PAYMENT_HISTORY = "GET_PAYMENT_HISTORY"
    UPDATE = "UPDATE"
    DELETE = "DELETE"


class SaleItem(BaseModel):
    size: str = Field(..., description="Size identifier sold.")
    quantity: int = Field(..., gt=0, description="Quantity sold for the given size.")


class SaleCreatePayload(BaseModel):
    customer_name: str = Field(..., description="Customer full name.")
    customer_phone: str = Field(..., description="Customer contact number.")
    design_id: str = Field(..., description="Design identifier for the sold garment.")
    selling_price_per_piece: float = Field(..., gt=0, description="Fixed selling price per design piece.")
    items: List[SaleItem] = Field(..., min_items=1, description="List of sizes and quantities sold.")
    payment_type: PaymentType = Field(..., description="Payment type for the sale.")
    amount_paid: float = Field(0, ge=0, description="Initial payment amount received for the sale.")

    @validator("customer_phone")
    def validate_contact(cls, v: str) -> str:
        normalized = v.strip()
        if len(normalized) < 7:
            raise ValueError("customer_phone must contain at least 7 digits.")
        return normalized


class SaleUpdatePayload(BaseModel):
    customer_name: Optional[str] = Field(None, description="Updated customer full name.")
    customer_phone: Optional[str] = Field(None, description="Updated customer contact number.")
    items: Optional[List[SaleItem]] = Field(
        None, min_items=1, description="Replacement list of sizes and quantities sold."
    )

    @validator("customer_phone")
    def validate_contact(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        normalized = v.strip()
        if len(normalized) < 7:
            raise ValueError("customer_phone must contain at least 7 digits.")
        return normalized


class CreditPaymentPayload(BaseModel):
    payment_amount: float = Field(..., gt=0, description="Amount being paid towards the credit balance.")
    payment_note: Optional[str] = Field(None, description="Optional note providing context for the payment.")


class SaleOperationRequest(BaseModel):
    action: SaleAction
    sale_id: Optional[str] = None
    design_id: Optional[str] = None
    payload: Optional[Dict[str, Any]] = None

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

        if action in {
            SaleAction.GET_BY_ID,
            SaleAction.UPDATE,
            SaleAction.DELETE,
            SaleAction.MAKE_PAYMENT,
            SaleAction.GET_PAYMENT_HISTORY,
        } and not sale_id:
            raise ValueError(f"sale_id is required for {action} action.")

        if action == SaleAction.GET_BY_DESIGN and not design_id:
            raise ValueError("design_id is required for GET_BY_DESIGN action.")

        if action in {SaleAction.CREATE, SaleAction.UPDATE, SaleAction.MAKE_PAYMENT} and not payload:
            raise ValueError(f"payload is required for {action} action.")

        return values


class SaleRecord(BaseModel):
    id: str
    customer_name: str
    customer_phone: str
    design_id: str
    items: List[Dict[str, Any]]
    total_quantity: int
    total_amount: float
    payment_type: str
    amount_paid: float
    balance: float
    payment_history: List[Dict[str, Any]]
    created_at: datetime
    updated_at: Optional[datetime] = None
