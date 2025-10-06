from fastapi import APIRouter, HTTPException, status, Depends
from typing import List, Any
from datetime import datetime
from pydantic import ValidationError

from app.models.cloth import ClothOperationRequest, CrudAction, ClothPurchaseCreate, ClothPurchaseUpdate, ClothPurchaseResponse
from app.services.firebase_service import db, CLOTH_COLLECTION
from app.auth import get_current_user_with_access
from app.models.user import AccessLevel

router = APIRouter(
    prefix="/cloth-purchases",
    tags=["Cloth Operations"]
)

@router.post("/operate", response_model=Any, status_code=status.HTTP_200_OK)
def operate_cloth_purchase(request: ClothOperationRequest, current_user: dict = Depends(get_current_user_with_access(AccessLevel.LEVEL_1))):
    """
    A single endpoint to handle all CRUD operations for cloth purchases.
    - **CREATE**: Provide `action: "CREATE"` and a valid `payload`.
    - **READ**: Provide `action: "READ"` and the `purchase_id`.
    - **READ_ALL**: Provide `action: "READ_ALL"`.
    - **UPDATE**: Provide `action: "UPDATE"`, `purchase_id`, and a `payload` with fields to update.
    - **DELETE**: Provide `action: "DELETE"` and the `purchase_id`.
    """
    action = request.action
    purchase_id = request.purchase_id
    payload = request.payload

    # --- CREATE Operation ---
    if action == CrudAction.CREATE:
        if not payload:
            raise HTTPException(status_code=400, detail="Payload required for CREATE action.")
        try:
            purchase_data = ClothPurchaseCreate(**payload).model_dump()
            purchase_data['created_at'] = datetime.utcnow()
            _, doc_ref = db.collection(CLOTH_COLLECTION).add(purchase_data)
            created_purchase = purchase_data
            created_purchase['id'] = doc_ref.id
            return created_purchase
        except ValidationError as e:
            raise HTTPException(status_code=422, detail=f"Invalid payload for creating purchase: {e}")

    # --- READ_ALL Operation ---
    if action == CrudAction.READ_ALL:
        purchases = []
        docs = db.collection(CLOTH_COLLECTION).stream()
        for doc in docs:
            purchase_data = doc.to_dict()
            purchase_data['id'] = doc.id
            purchases.append(purchase_data)
        return purchases

    # The following actions require a purchase_id
    if not purchase_id:
        raise HTTPException(status_code=400, detail=f"purchase_id is required for {action} action.")

    doc_ref = db.collection(CLOTH_COLLECTION).document(purchase_id)
    doc = doc_ref.get()
    if not doc.exists and action in [CrudAction.READ, CrudAction.UPDATE, CrudAction.DELETE]:
        raise HTTPException(status_code=404, detail="Purchase not found")

    # --- READ (Single) Operation ---
    if action == CrudAction.READ:
        purchase_data = doc.to_dict()
        purchase_data['id'] = doc.id
        return purchase_data

    # --- UPDATE Operation ---
    if action == CrudAction.UPDATE:
        if current_user["access_level"] != AccessLevel.LEVEL_2.value:
            raise HTTPException(status_code=403, detail="You do not have permission to perform this action")
        if not payload:
            raise HTTPException(status_code=400, detail="Payload required for UPDATE action.")
        try:
            update_data = ClothPurchaseUpdate(**payload).model_dump(exclude_unset=True)
            if not update_data:
                raise HTTPException(status_code=400, detail="No valid fields to update in payload.")
            doc_ref.update(update_data)
            updated_doc = doc_ref.get()
            response_data = updated_doc.to_dict()
            response_data['id'] = updated_doc.id
            return response_data
        except ValidationError as e:
            raise HTTPException(status_code=422, detail=f"Invalid payload for updating purchase: {e}")


    # --- DELETE Operation ---
    if action == CrudAction.DELETE:
        if current_user["access_level"] != AccessLevel.LEVEL_2.value:
            raise HTTPException(status_code=403, detail="You do not have permission to perform this action")
        doc_ref.delete()
        return {"status": "success", "message": f"Purchase {purchase_id} deleted."}

    raise HTTPException(status_code=400, detail="Invalid action specified.")