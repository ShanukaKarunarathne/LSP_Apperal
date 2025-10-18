from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
from enum import Enum
from datetime import datetime

class SizeInfo(BaseModel):
    size: str
    quantity: int

class Design(BaseModel):
    design_code: str = Field(..., description="The unique code for the design.")
    cloth_purchase_id: str = Field(..., description="The ID of the cloth purchase this design belongs to.")
    allocated_yards: float = Field(..., description="The amount of fabric in yards allocated to this design.")
    size_distribution: List[SizeInfo] = Field(..., description="The number of pieces for each size.")

class DesignCreatePayload(BaseModel):
    design_code: str
    cloth_purchase_id: str
    allocated_yards_per_piece: float
    number_of_pieces: int
    size_distribution: List[SizeInfo]

class DesignUpdate(BaseModel):
    allocated_yards: Optional[float] = None
    size_distribution: Optional[List[SizeInfo]] = None

class DesignResponse(Design):
    id: str
    created_at: datetime

class DesignOperationRequest(BaseModel):
    action: str # CREATE, READ, READ_ALL, UPDATE, DELETE, GET_TOTALS
    design_id: Optional[str] = None
    payload: Optional[Dict[str, Any]] = None