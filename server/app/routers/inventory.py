from fastapi import APIRouter, HTTPException, status, Depends

from app.auth import get_current_user_with_access
from app.models.inventory import InventoryAction, InventoryOperationRequest
from app.models.user import AccessLevel
from app.services.firebase_service import db, INVENTORY_COLLECTION

router = APIRouter(
    prefix="/inventory",
    tags=["Inventory"]
)


@router.post("/operate", status_code=status.HTTP_200_OK)
def operate_inventory(
    request: InventoryOperationRequest,
    current_user: dict = Depends(get_current_user_with_access(AccessLevel.LEVEL_1))
):
    action = request.action
    design_id = request.design_id

    if action == InventoryAction.READ_ALL:
        docs = db.collection(INVENTORY_COLLECTION).stream()
        inventory = []
        for doc in docs:
            record = doc.to_dict()
            record["id"] = doc.id
            inventory.append(record)
        return inventory

    if action == InventoryAction.GET_BY_DESIGN:
        if not design_id:
            raise HTTPException(status_code=400, detail="design_id is required for GET_BY_DESIGN.")

        doc_ref = db.collection(INVENTORY_COLLECTION).document(design_id)
        doc = doc_ref.get()
        if not doc.exists:
            raise HTTPException(status_code=404, detail="Inventory record not found for the design.")

        record = doc.to_dict()
        record["id"] = doc.id
        return record

    raise HTTPException(status_code=400, detail="Invalid inventory action provided.")
