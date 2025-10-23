from datetime import datetime
from fastapi import APIRouter, HTTPException, status, Depends
from google.cloud.firestore_v1.base_query import FieldFilter

from app.auth import get_current_user_with_access
from app.models.sale import SaleAction, SaleOperationRequest
from app.models.user import AccessLevel
from app.services.firebase_service import (
    db,
    INVENTORY_COLLECTION,
    SALES_COLLECTION,
)

router = APIRouter(
    prefix="/sales",
    tags=["Sales"]
)


def _normalize_sizes(items):
    size_totals = {}
    for item in items:
        if isinstance(item, dict):
            size = item.get("size")
            quantity = int(item.get("quantity", 0))
        else:
            size = item.size
            quantity = item.quantity
        if not size:
            continue
        size_totals[size] = size_totals.get(size, 0) + quantity
    return size_totals


@router.post("/operate", status_code=status.HTTP_200_OK)
def operate_sales(
    request: SaleOperationRequest,
    current_user: dict = Depends(get_current_user_with_access(AccessLevel.LEVEL_1))
):
    action = request.action

    if action == SaleAction.CREATE:
        payload = request.payload
        design_id = payload.design_id
        inventory_ref = db.collection(INVENTORY_COLLECTION).document(design_id)
        inventory_doc = inventory_ref.get()
        if not inventory_doc.exists:
            raise HTTPException(status_code=400, detail="No inventory available for the selected design.")

        inventory_data = inventory_doc.to_dict()
        inventory_sizes = {size: int(qty) for size, qty in (inventory_data.get("sizes") or {}).items()}
        size_totals = _normalize_sizes(payload.items)
        total_sold = 0

        for size, qty in size_totals.items():
            available = int(inventory_sizes.get(size, 0))
            if available < qty:
                raise HTTPException(status_code=400, detail=f"Not enough stock for size {size}. Available: {available}")
            inventory_sizes[size] = available - qty
            total_sold += qty

        remaining_total = int(inventory_data.get("total_available", 0)) - total_sold
        if remaining_total < 0:
            raise HTTPException(status_code=400, detail="Inventory would become negative.")

        now = datetime.utcnow()
        inventory_ref.update({
            "sizes": inventory_sizes,
            "total_available": remaining_total,
            "updated_at": now,
        })

        sale_record = {
            "customer_name": payload.customer_name,
            "customer_phone": payload.customer_phone,
            "design_id": design_id,
            "items": [item.model_dump() for item in payload.items],
            "total_quantity": total_sold,
            "created_at": now,
            "updated_at": now,
        }
        doc_ref = db.collection(SALES_COLLECTION).document()
        doc_ref.set(sale_record)
        sale_record["id"] = doc_ref.id
        return sale_record

    if action == SaleAction.READ_ALL:
        docs = db.collection(SALES_COLLECTION).stream()
        sales = []
        for doc in docs:
            record = doc.to_dict()
            record["id"] = doc.id
            sales.append(record)
        return sales

    if action == SaleAction.GET_BY_ID:
        doc_ref = db.collection(SALES_COLLECTION).document(request.sale_id)
        doc = doc_ref.get()
        if not doc.exists:
            raise HTTPException(status_code=404, detail="Sale not found.")
        record = doc.to_dict()
        record["id"] = doc.id
        return record

    if action == SaleAction.GET_BY_DESIGN:
        docs = db.collection(SALES_COLLECTION).where(
            filter=FieldFilter("design_id", "==", request.design_id)
        ).stream()
        sales = []
        for doc in docs:
            record = doc.to_dict()
            record["id"] = doc.id
            sales.append(record)
        return sales

    if action == SaleAction.UPDATE:
        sale_ref = db.collection(SALES_COLLECTION).document(request.sale_id)
        sale_doc = sale_ref.get()
        if not sale_doc.exists:
            raise HTTPException(status_code=404, detail="Sale not found.")

        existing_sale = sale_doc.to_dict()
        payload = request.payload
        if payload.design_id != existing_sale.get("design_id"):
            raise HTTPException(status_code=400, detail="Cannot change design for an existing sale.")

        design_id = payload.design_id
        inventory_ref = db.collection(INVENTORY_COLLECTION).document(design_id)
        inventory_doc = inventory_ref.get()
        if not inventory_doc.exists:
            raise HTTPException(status_code=400, detail="Inventory record missing for the design.")

        inventory_data = inventory_doc.to_dict()
        inventory_sizes = {size: int(qty) for size, qty in (inventory_data.get("sizes") or {}).items()}

        old_totals = _normalize_sizes(existing_sale.get("items", []))
        new_totals = _normalize_sizes(payload.items)

        for size, qty in old_totals.items():
            inventory_sizes[size] = int(inventory_sizes.get(size, 0)) + qty

        for size, qty in new_totals.items():
            available = int(inventory_sizes.get(size, 0))
            if available < qty:
                raise HTTPException(status_code=400, detail=f"Not enough stock for size {size}. Available: {available}")
            inventory_sizes[size] = available - qty

        total_old = sum(old_totals.values())
        total_new = sum(new_totals.values())
        remaining_total = int(inventory_data.get("total_available", 0)) + total_old - total_new
        if remaining_total < 0:
            raise HTTPException(status_code=400, detail="Inventory would become negative.")

        now = datetime.utcnow()
        inventory_ref.update({
            "sizes": inventory_sizes,
            "total_available": remaining_total,
            "updated_at": now,
        })

        sale_update = {
            "customer_name": payload.customer_name,
            "customer_phone": payload.customer_phone,
            "design_id": design_id,
            "items": [item.model_dump() for item in payload.items],
            "total_quantity": total_new,
            "updated_at": now,
        }
        sale_ref.update(sale_update)

        updated_doc = sale_ref.get()
        data = updated_doc.to_dict()
        data["id"] = sale_ref.id
        return data

    if action == SaleAction.DELETE:
        sale_ref = db.collection(SALES_COLLECTION).document(request.sale_id)
        sale_doc = sale_ref.get()
        if not sale_doc.exists:
            raise HTTPException(status_code=404, detail="Sale not found.")

        sale_data = sale_doc.to_dict()
        design_id = sale_data.get("design_id")
        if not design_id:
            sale_ref.delete()
            return {"status": "success", "message": f"Sale {request.sale_id} deleted."}

        inventory_ref = db.collection(INVENTORY_COLLECTION).document(design_id)
        inventory_doc = inventory_ref.get()
        if not inventory_doc.exists:
            raise HTTPException(status_code=400, detail="Inventory record missing for the design.")

        inventory_data = inventory_doc.to_dict()
        inventory_sizes = {size: int(qty) for size, qty in (inventory_data.get("sizes") or {}).items()}

        sale_totals = _normalize_sizes(sale_data.get("items", []))
        total_return = sum(sale_totals.values())

        for size, qty in sale_totals.items():
            inventory_sizes[size] = int(inventory_sizes.get(size, 0)) + qty

        remaining_total = int(inventory_data.get("total_available", 0)) + total_return

        now = datetime.utcnow()
        inventory_ref.update({
            "sizes": inventory_sizes,
            "total_available": remaining_total,
            "updated_at": now,
        })

        sale_ref.delete()
        return {
            "status": "success",
            "message": f"Sale {request.sale_id} deleted.",
            "restored_quantity": total_return
        }

    raise HTTPException(status_code=400, detail="Invalid sales action provided.")
