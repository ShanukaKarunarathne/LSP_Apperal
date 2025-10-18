from fastapi import APIRouter, HTTPException, status, Depends
from typing import List
from datetime import datetime

from app.models.production import (
    ProductionTrackingCreate, 
    ProductionTrackingUpdate, 
    ProductionTrackingResponse,
    ProductionStage,
    ProductionStatus
)
from app.services.firebase_service import db
from app.auth import get_current_user_with_access
from app.models.user import AccessLevel

router = APIRouter(
    prefix="/production",
    tags=["Production Tracking"]
)

PRODUCTION_COLLECTION = "production_tracking"

@router.post("/add", status_code=status.HTTP_201_CREATED)
def add_to_stage(
    tracking: ProductionTrackingCreate,
    current_user: dict = Depends(get_current_user_with_access(AccessLevel.LEVEL_1))
):
    design_ref = db.collection("designs").document(tracking.design_id)
    if not design_ref.get().exists:
        raise HTTPException(status_code=404, detail="Design not found")
    
    # Validate workflow: Check if previous stage is completed
    if tracking.stage == ProductionStage.SEWING:
        cutting_docs = db.collection(PRODUCTION_COLLECTION).where(
            "design_id", "==", tracking.design_id
        ).where("stage", "==", ProductionStage.CUTTING.value).get()
        
        if not cutting_docs:
            raise HTTPException(
                status_code=400, 
                detail="Cannot start sewing: Cutting stage not started"
            )
        
        cutting_completed = any(
            doc.to_dict().get("status") == ProductionStatus.COMPLETED.value 
            for doc in cutting_docs
        )
        
        if not cutting_completed:
            raise HTTPException(
                status_code=400, 
                detail="Cannot start sewing: Cutting stage not completed"
            )
    
    if tracking.stage == ProductionStage.IRONING:
        sewing_docs = db.collection(PRODUCTION_COLLECTION).where(
            "design_id", "==", tracking.design_id
        ).where("stage", "==", ProductionStage.SEWING.value).get()
        
        if not sewing_docs:
            raise HTTPException(
                status_code=400, 
                detail="Cannot start ironing: Sewing stage not started"
            )
        
        sewing_completed = any(
            doc.to_dict().get("status") == ProductionStatus.COMPLETED.value 
            for doc in sewing_docs
        )
        
        if not sewing_completed:
            raise HTTPException(
                status_code=400, 
                detail="Cannot start ironing: Sewing stage not completed"
            )
    
    tracking_data = {
        "design_id": tracking.design_id,
        "stage": tracking.stage.value,
        "status": ProductionStatus.IN_PROGRESS.value,
        "arrived_at": datetime.utcnow(),
        "completed_at": None
    }
    
    _, doc_ref = db.collection(PRODUCTION_COLLECTION).add(tracking_data)
    tracking_data["id"] = doc_ref.id
    return tracking_data

@router.patch("/{tracking_id}/complete", status_code=status.HTTP_200_OK)
def mark_completed(
    tracking_id: str,
    current_user: dict = Depends(get_current_user_with_access(AccessLevel.LEVEL_1))
):
    doc_ref = db.collection(PRODUCTION_COLLECTION).document(tracking_id)
    doc = doc_ref.get()
    
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Tracking record not found")
    
    tracking_data = doc.to_dict()
    
    if tracking_data.get("status") == ProductionStatus.COMPLETED.value:
        raise HTTPException(
            status_code=400, 
            detail="This stage is already completed"
        )
    
    doc_ref.update({
        "status": ProductionStatus.COMPLETED.value,
        "completed_at": datetime.utcnow()
    })
    
    updated_doc = doc_ref.get().to_dict()
    updated_doc["id"] = tracking_id
    return updated_doc

@router.delete("/{tracking_id}", status_code=status.HTTP_200_OK)
def delete_tracking(
    tracking_id: str,
    current_user: dict = Depends(get_current_user_with_access(AccessLevel.LEVEL_2))
):
    doc_ref = db.collection(PRODUCTION_COLLECTION).document(tracking_id)
    doc = doc_ref.get()
    
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Tracking record not found")
    
    tracking_data = doc.to_dict()
    
    # Check if stage is completed
    if tracking_data.get("status") == ProductionStatus.COMPLETED.value:
        # Check if next stage has started
        design_id = tracking_data.get("design_id")
        current_stage = tracking_data.get("stage")
        
        if current_stage == ProductionStage.CUTTING.value:
            # Check if sewing has started
            sewing_docs = db.collection(PRODUCTION_COLLECTION).where(
                "design_id", "==", design_id
            ).where("stage", "==", ProductionStage.SEWING.value).get()
            
            if sewing_docs:
                raise HTTPException(
                    status_code=400, 
                    detail="Cannot delete cutting: Sewing stage has already started"
                )
        
        elif current_stage == ProductionStage.SEWING.value:
            # Check if ironing has started
            ironing_docs = db.collection(PRODUCTION_COLLECTION).where(
                "design_id", "==", design_id
            ).where("stage", "==", ProductionStage.IRONING.value).get()
            
            if ironing_docs:
                raise HTTPException(
                    status_code=400, 
                    detail="Cannot delete sewing: Ironing stage has already started"
                )
    
    doc_ref.delete()
    return {"status": "success", "message": f"Tracking record {tracking_id} deleted"}

@router.get("/by-design/{design_id}", response_model=List[dict])
def get_by_design(
    design_id: str,
    current_user: dict = Depends(get_current_user_with_access(AccessLevel.LEVEL_1))
):
    docs = db.collection(PRODUCTION_COLLECTION).where("design_id", "==", design_id).stream()
    results = []
    for doc in docs:
        data = doc.to_dict()
        data["id"] = doc.id
        results.append(data)
    return results

@router.get("/by-stage/{stage}", response_model=List[dict])
def get_by_stage(
    stage: ProductionStage,
    current_user: dict = Depends(get_current_user_with_access(AccessLevel.LEVEL_1))
):
    docs = db.collection(PRODUCTION_COLLECTION).where("stage", "==", stage.value).stream()
    results = []
    for doc in docs:
        data = doc.to_dict()
        data["id"] = doc.id
        results.append(data)
    return results

@router.get("/in-progress", response_model=List[dict])
def get_in_progress(
    current_user: dict = Depends(get_current_user_with_access(AccessLevel.LEVEL_1))
):
    docs = db.collection(PRODUCTION_COLLECTION).where(
        "status", "==", ProductionStatus.IN_PROGRESS.value
    ).stream()
    results = []
    for doc in docs:
        data = doc.to_dict()
        data["id"] = doc.id
        results.append(data)
    return results