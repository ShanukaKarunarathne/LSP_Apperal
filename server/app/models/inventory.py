from enum import Enum
from typing import Dict, Optional
from datetime import datetime

from pydantic import BaseModel, Field


class InventoryAction(str, Enum):
    READ_ALL = "READ_ALL"
    GET_BY_DESIGN = "GET_BY_DESIGN"


class InventoryOperationRequest(BaseModel):
    action: InventoryAction = Field(..., description="Operation to perform on inventory records.")
    design_id: Optional[str] = Field(None, description="Target design id for lookups.")


class InventoryRecord(BaseModel):
    design_id: str
    sizes: Dict[str, int]
    total_available: int
    created_at: datetime
    updated_at: datetime
