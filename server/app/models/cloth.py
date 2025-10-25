from pydantic import BaseModel, Field
from typing import Optional, Any, Dict
from datetime import datetime
from enum import Enum

# --- No changes in this section ---
class CrudAction(str, Enum):
    CREATE = "CREATE"
    READ = "READ"
    READ_ALL = "READ_ALL"
    UPDATE = "UPDATE"
    DELETE = "DELETE"

class ClothOperationRequest(BaseModel):
    action: CrudAction = Field(..., description="The CRUD action to perform.")
    purchase_id: Optional[str] = Field(None, description="The document ID, required for READ, UPDATE, DELETE.")
    payload: Optional[Dict[str, Any]] = Field(None, description="The data payload, required for CREATE and UPDATE.")

# --- Changes are in the models below ---
class ClothPurchaseBase(BaseModel):
    cloth_name: str  # Added this field
    supplier_name: str
    total_yards: float
    number_of_rolls: int
    number_of_colors: int
    buying_price: float

class ClothPurchaseCreate(ClothPurchaseBase):
    pass

class ClothPurchaseUpdate(BaseModel):
    cloth_name: Optional[str] = None  # Added this field
    supplier_name: Optional[str] = None
    total_yards: Optional[float] = None
    number_of_rolls: Optional[int] = None
    number_of_colors: Optional[int] = None
    buying_price: Optional[float] = None

class ClothPurchaseResponse(ClothPurchaseBase):
    id: str
    created_at: datetime
