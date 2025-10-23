from fastapi import APIRouter, HTTPException, status, Depends
from typing import Any, Dict
from datetime import datetime

from app.models.production import (
    ProductionOperationRequest,
    CrudAction,
    ProductionStage,
    ProductionStatus,
)
from app.services.firebase_service import (
    db,
    PRODUCTION_COLLECTION,
    DESIGN_COLLECTION,
    INVENTORY_COLLECTION,
)
from app.auth import get_current_user_with_access
from app.models.user import AccessLevel
from google.cloud.firestore_v1.base_query import FieldFilter

router = APIRouter(
    prefix="/production",
    tags=["Production Tracking"]
)

STAGE_SEQUENCE = [
    ProductionStage.CUTTING,
    ProductionStage.SEWING,
    ProductionStage.IRONING,
]


def _default_stage_payload() -> Dict[str, Dict[str, Any]]:
    """Initialise stage metadata for a new tracking record."""
    now = datetime.utcnow()
    return {
        ProductionStage.CUTTING.value: {
            "status": ProductionStatus.IN_PROGRESS.value,
            "arrived_at": now,
            "completed_at": None,
        },
        ProductionStage.SEWING.value: {
            "status": ProductionStatus.PENDING.value,
            "arrived_at": None,
            "completed_at": None,
        },
        ProductionStage.IRONING.value: {
            "status": ProductionStatus.PENDING.value,
            "arrived_at": None,
            "completed_at": None,
        },
    }


def _get_tracking_by_design(design_id: str):
    docs = db.collection(PRODUCTION_COLLECTION).where(
        filter=FieldFilter("design_id", "==", design_id)
    ).limit(1).get()
    return docs[0] if docs else None


def _get_tracking_by_id(tracking_id: str):
    doc_ref = db.collection(PRODUCTION_COLLECTION).document(tracking_id)
    doc = doc_ref.get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Tracking record not found.")
    return doc_ref, doc


def _ensure_cutting_completed(stage_data: Dict[str, Any]):
    cutting_data = stage_data.get(ProductionStage.CUTTING.value, {})
    if cutting_data.get("status") != ProductionStatus.COMPLETED.value:
        raise HTTPException(status_code=400, detail="Cannot proceed: Cutting stage not completed.")


def _ensure_sewing_completed(stage_data: Dict[str, Any]):
    sewing_data = stage_data.get(ProductionStage.SEWING.value, {})
    if sewing_data.get("status") != ProductionStatus.COMPLETED.value:
        raise HTTPException(status_code=400, detail="Cannot proceed: Sewing stage not completed.")


def _get_design_size_map(design_id: str) -> Dict[str, int]:
    design_doc = db.collection(DESIGN_COLLECTION).document(design_id).get()
    if not design_doc.exists:
        raise HTTPException(status_code=404, detail="Design not found for inventory update.")
    design_data = design_doc.to_dict()
    distribution = design_data.get("size_distribution") or []
    size_map: Dict[str, int] = {}
    for entry in distribution:
        size = entry.get("size")
        quantity = int(entry.get("quantity", 0))
        if not size:
            continue
        size_map[size] = size_map.get(size, 0) + quantity
    return size_map


def _adjust_inventory(design_id: str, multiplier: int):
    if multiplier == 0:
        return

    size_map = _get_design_size_map(design_id)
    if not size_map:
        return

    total_delta = sum(size_map.values()) * multiplier
    now = datetime.utcnow()

    doc_ref = db.collection(INVENTORY_COLLECTION).document(design_id)
    doc = doc_ref.get()

    if doc.exists:
        data = doc.to_dict()
        current_sizes = data.get("sizes", {})
        updated_sizes: Dict[str, int] = {}
        for size, base_qty in size_map.items():
            new_qty = int(current_sizes.get(size, 0)) + base_qty * multiplier
            if new_qty < 0:
                raise HTTPException(status_code=400, detail="Inventory cannot go below zero for size {}".format(size))
            updated_sizes[size] = new_qty

        # preserve any extra sizes that are not part of the current design distribution
        for size, qty in current_sizes.items():
            if size not in updated_sizes:
                updated_sizes[size] = int(qty)

        new_total = int(data.get("total_available", 0)) + total_delta
        if new_total < 0:
            raise HTTPException(status_code=400, detail="Inventory cannot be negative.")

        doc_ref.update({
            "sizes": updated_sizes,
            "total_available": new_total,
            "updated_at": now,
        })
    else:
        if multiplier < 0:
            raise HTTPException(status_code=400, detail="Cannot subtract from inventory that does not exist.")
        doc_ref.set({
            "design_id": design_id,
            "sizes": {size: int(qty) for size, qty in size_map.items()},
            "total_available": sum(size_map.values()),
            "created_at": now,
            "updated_at": now,
        })

@router.post("/operate", response_model=Any, status_code=status.HTTP_200_OK)
def operate_production(
    request: ProductionOperationRequest,
    current_user: dict = Depends(get_current_user_with_access(AccessLevel.LEVEL_1))
):
    action = request.action
    design_id = request.design_id
    tracking_id = request.tracking_id
    now = datetime.utcnow()

    def _tracking_response(doc_ref):
        refreshed = doc_ref.get()
        data = refreshed.to_dict()
        data["id"] = doc_ref.id
        return data

    # --- START_CUTTING Operation ---
    if action == CrudAction.START_CUTTING:
        if not design_id and not tracking_id:
            raise HTTPException(
                status_code=400,
                detail="design_id or tracking_id required for START_CUTTING action."
            )

        doc_ref = None

        if tracking_id:
            doc_ref, _ = _get_tracking_by_id(tracking_id)
        else:
            design_ref = db.collection(DESIGN_COLLECTION).document(design_id)
            if not design_ref.get().exists:
                raise HTTPException(status_code=404, detail="Design not found")

            existing = _get_tracking_by_design(design_id)
            if existing:
                doc_ref = existing.reference

        if doc_ref:
            updates = {
                "stage": ProductionStage.CUTTING.value,
                "status": ProductionStatus.IN_PROGRESS.value,
                "arrived_at": now,
                "completed_at": None,
                "stages.cutting.status": ProductionStatus.IN_PROGRESS.value,
                "stages.cutting.arrived_at": now,
                "stages.cutting.completed_at": None,
                "stages.sewing.status": ProductionStatus.PENDING.value,
                "stages.sewing.arrived_at": None,
                "stages.sewing.completed_at": None,
                "stages.ironing.status": ProductionStatus.PENDING.value,
                "stages.ironing.arrived_at": None,
                "stages.ironing.completed_at": None,
                "updated_at": now,
            }
            doc_ref.update(updates)
            return _tracking_response(doc_ref)

        stage_payload = _default_stage_payload()
        tracking_data = {
            "design_id": design_id,
            "stage": ProductionStage.CUTTING.value,
            "status": ProductionStatus.IN_PROGRESS.value,
            "stages": stage_payload,
            "arrived_at": now,
            "completed_at": None,
            "created_at": now,
            "updated_at": now,
        }
        doc_ref = db.collection(PRODUCTION_COLLECTION).document()
        doc_ref.set(tracking_data)
        tracking_data["id"] = doc_ref.id
        return tracking_data

    # --- COMPLETE_CUTTING Operation ---
    elif action == CrudAction.COMPLETE_CUTTING:
        if not tracking_id:
            raise HTTPException(status_code=400, detail="tracking_id is required for COMPLETE_CUTTING action.")
        
        doc_ref = db.collection(PRODUCTION_COLLECTION).document(tracking_id)
        doc = doc_ref.get()
        
        if not doc.exists:
            raise HTTPException(status_code=404, detail="Cutting tracking record not found.")
        
        tracking_data = doc.to_dict()
        if tracking_data.get("stage") != ProductionStage.CUTTING.value:
            raise HTTPException(status_code=400, detail="This action is only for cutting stage.")

        if tracking_data.get("status") != ProductionStatus.IN_PROGRESS.value:
            raise HTTPException(status_code=400, detail="Cutting stage is not in progress.")

        doc_ref.update({
            "stage": ProductionStage.SEWING.value,
            "status": ProductionStatus.PENDING.value,
            "arrived_at": None,
            "completed_at": None,
            "stages.cutting.status": ProductionStatus.COMPLETED.value,
            "stages.cutting.completed_at": now,
            "stages.sewing.status": ProductionStatus.PENDING.value,
            "stages.sewing.arrived_at": None,
            "stages.sewing.completed_at": None,
            "updated_at": now,
        })

        return _tracking_response(doc_ref)

    # --- START_SEWING Operation ---
    elif action == CrudAction.START_SEWING:
        if not tracking_id:
            raise HTTPException(status_code=400, detail="tracking_id is required for START_SEWING action.")

        doc_ref = db.collection(PRODUCTION_COLLECTION).document(tracking_id)
        doc = doc_ref.get()

        if not doc.exists:
            raise HTTPException(status_code=404, detail="Sewing tracking record not found.")

        tracking_data = doc.to_dict()

        stage_data = tracking_data.get("stages") or {}
        _ensure_cutting_completed(stage_data)

        sewing_stage = stage_data.get(ProductionStage.SEWING.value, {})
        current_stage = tracking_data.get("stage")
        current_status = tracking_data.get("status")

        allowed_state = (
            (current_stage == ProductionStage.SEWING.value and current_status in {
                ProductionStatus.PENDING.value,
                ProductionStatus.COMPLETED.value,
            })
            or (current_stage == ProductionStage.CUTTING.value and current_status == ProductionStatus.COMPLETED.value)
        )

        if sewing_stage.get("status") != ProductionStatus.PENDING.value or not allowed_state:
            raise HTTPException(status_code=400, detail="Sewing stage is not ready to start.")

        doc_ref.update({
            "stage": ProductionStage.SEWING.value,
            "status": ProductionStatus.IN_PROGRESS.value,
            "arrived_at": now,
            "completed_at": None,
            "stages.sewing.status": ProductionStatus.IN_PROGRESS.value,
            "stages.sewing.arrived_at": now,
            "updated_at": now,
        })

        return _tracking_response(doc_ref)

    # --- COMPLETE_SEWING Operation ---
    elif action == CrudAction.COMPLETE_SEWING:
        if not tracking_id:
            raise HTTPException(status_code=400, detail="tracking_id is required for COMPLETE_SEWING action.")
        
        doc_ref = db.collection(PRODUCTION_COLLECTION).document(tracking_id)
        doc = doc_ref.get()
        
        if not doc.exists:
            raise HTTPException(status_code=404, detail="Sewing tracking record not found.")
        
        tracking_data = doc.to_dict()
        if tracking_data.get("stage") != ProductionStage.SEWING.value:
            raise HTTPException(status_code=400, detail="This action is only for sewing stage.")

        if tracking_data.get("status") != ProductionStatus.IN_PROGRESS.value:
            raise HTTPException(status_code=400, detail="Sewing stage is not in progress.")
        
        doc_ref.update({
            "stage": ProductionStage.IRONING.value,
            "status": ProductionStatus.PENDING.value,
            "arrived_at": None,
            "completed_at": None,
            "stages.sewing.status": ProductionStatus.COMPLETED.value,
            "stages.sewing.completed_at": now,
            "stages.ironing.status": ProductionStatus.PENDING.value,
            "stages.ironing.arrived_at": None,
            "stages.ironing.completed_at": None,
            "updated_at": now,
        })
        
        return _tracking_response(doc_ref)

    # --- START_IRONING Operation ---
    elif action == CrudAction.START_IRONING:
        if not tracking_id:
            raise HTTPException(status_code=400, detail="tracking_id is required for START_IRONING action.")

        doc_ref = db.collection(PRODUCTION_COLLECTION).document(tracking_id)
        doc = doc_ref.get()

        if not doc.exists:
            raise HTTPException(status_code=404, detail="Ironing tracking record not found.")

        tracking_data = doc.to_dict()

        stage_data = tracking_data.get("stages") or {}
        _ensure_cutting_completed(stage_data)
        _ensure_sewing_completed(stage_data)

        ironing_stage = stage_data.get(ProductionStage.IRONING.value, {})
        current_stage = tracking_data.get("stage")
        current_status = tracking_data.get("status")

        allowed_state = (
            (current_stage == ProductionStage.IRONING.value and current_status == ProductionStatus.PENDING.value)
            or (current_stage == ProductionStage.SEWING.value and current_status == ProductionStatus.COMPLETED.value)
        )

        if ironing_stage.get("status") != ProductionStatus.PENDING.value or not allowed_state:
            raise HTTPException(status_code=400, detail="Ironing stage is not ready to start.")

        doc_ref.update({
            "stage": ProductionStage.IRONING.value,
            "status": ProductionStatus.IN_PROGRESS.value,
            "arrived_at": now,
            "completed_at": None,
            "stages.ironing.status": ProductionStatus.IN_PROGRESS.value,
            "stages.ironing.arrived_at": now,
            "updated_at": now,
        })
        
        return _tracking_response(doc_ref)

    # --- COMPLETE_IRONING Operation ---
    elif action == CrudAction.COMPLETE_IRONING:
        if not tracking_id:
            raise HTTPException(status_code=400, detail="tracking_id is required for COMPLETE_IRONING action.")
        
        doc_ref = db.collection(PRODUCTION_COLLECTION).document(tracking_id)
        doc = doc_ref.get()
        
        if not doc.exists:
            raise HTTPException(status_code=404, detail="Ironing tracking record not found.")
        
        tracking_data = doc.to_dict()
        if tracking_data.get("stage") != ProductionStage.IRONING.value:
            raise HTTPException(status_code=400, detail="This action is only for ironing stage.")

        if tracking_data.get("status") != ProductionStatus.IN_PROGRESS.value:
            raise HTTPException(status_code=400, detail="Ironing stage is not in progress.")
        
        doc_ref.update({
            "status": ProductionStatus.COMPLETED.value,
            "stages.ironing.status": ProductionStatus.COMPLETED.value,
            "stages.ironing.completed_at": now,
            "updated_at": now,
            "completed_at": now,
        })

        design_id = tracking_data.get("design_id")
        if design_id:
            _adjust_inventory(design_id, multiplier=1)
        
        return _tracking_response(doc_ref)

    # --- READ_ALL Operation ---
    elif action == CrudAction.READ_ALL:
        docs = db.collection(PRODUCTION_COLLECTION).stream()
        results = []
        for doc in docs:
            data = doc.to_dict()
            data["id"] = doc.id
            results.append(data)
        return results

    # --- GET_BY_DESIGN Operation ---
    elif action == CrudAction.GET_BY_DESIGN:
        if not design_id:
            raise HTTPException(status_code=400, detail="design_id is required for GET_BY_DESIGN action.")
        
        design_ref = db.collection(DESIGN_COLLECTION).document(design_id)
        if not design_ref.get().exists:
            raise HTTPException(status_code=404, detail="Design not found")
            
        docs = db.collection(PRODUCTION_COLLECTION).where(filter=FieldFilter("design_id", "==", design_id)).stream()
        results = []
        for doc in docs:
            data = doc.to_dict()
            data["id"] = doc.id
            results.append(data)
        return results

    # --- GET_BY_STAGE Operation ---
    elif action == CrudAction.GET_BY_STAGE:
        stage = request.stage
        if not stage:
            raise HTTPException(status_code=400, detail="stage is required for GET_BY_STAGE action.")
        
        docs = db.collection(PRODUCTION_COLLECTION).where(filter=FieldFilter("stage", "==", stage.value)).stream()
        results = []
        for doc in docs:
            data = doc.to_dict()
            data["id"] = doc.id
            results.append(data)
        return results

    # --- GET_IN_PROGRESS Operation ---
    elif action == CrudAction.GET_IN_PROGRESS:
        docs = db.collection(PRODUCTION_COLLECTION).where(filter=FieldFilter(
            "status", "in", [ProductionStatus.IN_PROGRESS.value, ProductionStatus.PENDING.value]
        )).stream()
        results = []
        for doc in docs:
            data = doc.to_dict()
            data["id"] = doc.id
            results.append(data)
        return results

    # --- DELETE Operation --- (Revert to Previous Stage)
    elif action == CrudAction.DELETE:
        if not tracking_id:
            raise HTTPException(status_code=400, detail="tracking_id is required for DELETE action.")
        
        if current_user["access_level"] != AccessLevel.LEVEL_2.value:
            raise HTTPException(status_code=403, detail="You do not have permission to perform this action")
        
        doc_ref, doc = _get_tracking_by_id(tracking_id)
        tracking_data = doc.to_dict()
        stage_data = tracking_data.get("stages") or {}
        current_stage_value = tracking_data.get("stage")
        current_stage = ProductionStage(current_stage_value)
        current_index = STAGE_SEQUENCE.index(current_stage)

        if current_index == 0:
            raise HTTPException(
                status_code=400,
                detail="Cannot revert: production is at cutting start. Delete the design to remove this tracking record."
            )

        previous_stage = STAGE_SEQUENCE[current_index - 1]
        previous_key = previous_stage.value
        current_key = current_stage.value

        if stage_data.get(previous_key, {}).get("status") == ProductionStatus.PENDING.value:
            raise HTTPException(status_code=400, detail=f"Cannot revert: {previous_key} has not been started.")

        design_id = tracking_data.get("design_id")
        current_stage_state = stage_data.get(current_key, {})

        if (
            current_stage == ProductionStage.IRONING
            and current_stage_state.get("status") == ProductionStatus.COMPLETED.value
            and design_id
        ):
            _adjust_inventory(design_id, multiplier=-1)

        updates = {
            "stage": previous_stage.value,
            "status": ProductionStatus.PENDING.value,
            "arrived_at": None,
            "completed_at": None,
            f"stages.{previous_key}.status": ProductionStatus.PENDING.value,
            f"stages.{previous_key}.arrived_at": None,
            f"stages.{previous_key}.completed_at": None,
            f"stages.{current_key}.status": ProductionStatus.PENDING.value,
            f"stages.{current_key}.arrived_at": None,
            f"stages.{current_key}.completed_at": None,
            "updated_at": now,
        }

        doc_ref.update(updates)
        return {
            "status": "success",
            "message": f"Reverted to {previous_key} stage for design {tracking_data.get('design_id')}.",
            "tracking": _tracking_response(doc_ref)
        }

    else:
        raise HTTPException(status_code=400, detail="Invalid action specified.")
