from pydantic import BaseModel
from typing import Optional
from enum import Enum
from datetime import datetime

class ProductionStage(str, Enum):
    CUTTING = "cutting"
    SEWING = "sewing"
    IRONING = "ironing"

class ProductionStatus(str, Enum):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"

class ProductionTrackingCreate(BaseModel):
    design_id: str
    stage: ProductionStage

class ProductionTrackingUpdate(BaseModel):
    status: ProductionStatus

class ProductionTrackingResponse(BaseModel):
    id: str
    design_id: str
    stage: ProductionStage
    status: ProductionStatus
    arrived_at: datetime
    completed_at: Optional[datetime] = None