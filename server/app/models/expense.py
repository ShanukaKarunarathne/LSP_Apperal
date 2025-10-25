from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class ExpenseCrudAction(str, Enum):
    CREATE = "CREATE"
    READ = "READ"
    READ_ALL = "READ_ALL"
    UPDATE = "UPDATE"
    DELETE = "DELETE"


class ExpenseBase(BaseModel):
    expense_name: str = Field(..., description="Name of the expense.")
    price: float = Field(..., gt=0, description="Monetary amount of the expense.")
    description: str = Field(..., description="Additional details about the expense.")


class ExpenseModel(ExpenseBase):
    created_at: datetime = Field(..., description="Timestamp when the expense was created.")
    updated_at: Optional[datetime] = Field(None, description="Timestamp when the expense was last updated.")


class ExpenseCreate(ExpenseBase):
    pass


class ExpenseUpdate(BaseModel):
    expense_name: Optional[str] = Field(None, description="Updated name for the expense.")
    price: Optional[float] = Field(None, gt=0, description="Updated monetary amount of the expense.")
    description: Optional[str] = Field(None, description="Updated details about the expense.")


class ExpenseResponse(ExpenseModel):
    id: str = Field(..., description="Firestore document ID of the expense.")


class ExpenseOperationRequest(BaseModel):
    action: ExpenseCrudAction = Field(..., description="The CRUD action to perform.")
    expense_id: Optional[str] = Field(None, description="The expense document ID for actions that require it.")
    payload: Optional[Dict[str, Any]] = Field(None, description="Data payload used for create and update actions.")
