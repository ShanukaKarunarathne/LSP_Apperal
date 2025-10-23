from pydantic import BaseModel, Field, root_validator
from typing import Optional, Any, Dict
from enum import Enum
from datetime import datetime

class ProductionStage(str, Enum):
    CUTTING = "cutting"
    SEWING = "sewing"
    IRONING = "ironing"

class ProductionStatus(str, Enum):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    PENDING = "pending"

class CrudAction(str, Enum):
    START_CUTTING = "START_CUTTING"
    COMPLETE_CUTTING = "COMPLETE_CUTTING"
    START_SEWING = "START_SEWING"
    COMPLETE_SEWING = "COMPLETE_SEWING"
    START_IRONING = "START_IRONING"
    COMPLETE_IRONING = "COMPLETE_IRONING"
    READ_ALL = "READ_ALL"
    GET_BY_DESIGN = "GET_BY_DESIGN"
    GET_BY_STAGE = "GET_BY_STAGE"
    GET_IN_PROGRESS = "GET_IN_PROGRESS"
    DELETE = "DELETE"

class ProductionOperationRequest(BaseModel):
    action: CrudAction = Field(..., description="The CRUD action to perform.")
    tracking_id: Optional[str] = Field(None, description="The document ID, required for some actions.")
    design_id: Optional[str] = Field(None, description="The design ID, required for some actions.")
    stage: Optional[ProductionStage] = Field(None, description="The production stage, required for some actions.")

    @root_validator(pre=True)
    def validate_required_fields(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        raw_action = values.get("action")
        tracking_id = values.get("tracking_id")
        design_id = values.get("design_id")
        stage = values.get("stage")

        if not raw_action:
            return values

        try:
            action = raw_action if isinstance(raw_action, CrudAction) else CrudAction(raw_action)
        except ValueError:
            return values

        actions_requiring_tracking = {
            CrudAction.COMPLETE_CUTTING,
            CrudAction.START_SEWING,
            CrudAction.COMPLETE_SEWING,
            CrudAction.START_IRONING,
            CrudAction.COMPLETE_IRONING,
            CrudAction.DELETE,
        }

        if action in actions_requiring_tracking and not tracking_id:
            raise ValueError(f"tracking_id is required when action is {action}.")

        if action == CrudAction.START_CUTTING and not (design_id or tracking_id):
            raise ValueError("design_id or tracking_id is required when starting cutting.")

        if action == CrudAction.GET_BY_DESIGN and not design_id:
            raise ValueError("design_id is required for this action.")

        if action == CrudAction.GET_BY_STAGE and not stage:
            raise ValueError("stage is required when filtering by stage.")

        return values

class ProductionTrackingCreate(BaseModel):
    design_id: str

class ProductionTrackingUpdate(BaseModel):
    status: ProductionStatus


class StageState(BaseModel):
    status: ProductionStatus
    arrived_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

class ProductionTrackingResponse(BaseModel):
    id: str
    design_id: str
    stage: ProductionStage
    status: ProductionStatus
    arrived_at: datetime
    completed_at: Optional[datetime] = None
    stages: Dict[str, StageState]
