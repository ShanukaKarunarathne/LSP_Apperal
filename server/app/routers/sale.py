from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from google.cloud import firestore
from google.cloud.firestore_v1.base_query import FieldFilter
from pydantic import ValidationError

from app.auth import get_current_user_with_access
from app.models.sale import (
    CreditPaymentPayload,
    PaymentType,
    SaleAction,
    SaleCreatePayload,
    SaleOperationRequest,
    SaleRecord,
    SaleUpdatePayload,
)
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


def _normalize_sizes(items: Any) -> Dict[str, int]:
    """Aggregate quantities per size from payload or stored sale items."""
    size_totals: Dict[str, int] = {}
    if not items:
        return size_totals
    for item in items:
        if isinstance(item, dict):
            size = item.get("size")
            quantity = int(item.get("quantity", 0))
        else:
            size = getattr(item, "size", None)
            quantity = int(getattr(item, "quantity", 0))
        if not size:
            continue
        size_totals[size] = size_totals.get(size, 0) + quantity
    return size_totals


def _extract_unit_price(items: Any, *, default: Optional[float] = None) -> float:
    """
    Determine the selling price for a design ensuring all entries share the same unit price.
    Raises HTTPException if conflicting values are provided.
    """
    prices: List[float] = []
    if items:
        for item in items:
            if isinstance(item, dict):
                raw_price = item.get("selling_price")
            else:
                raw_price = getattr(item, "selling_price", None)
            if raw_price is None:
                continue
            prices.append(float(raw_price))

    if prices:
        base_price = prices[0]
        for price in prices[1:]:
            if abs(price - base_price) > 1e-6:
                raise HTTPException(
                    status_code=400,
                    detail="All selling prices must match for a design.",
                )
        return base_price

    if default is not None:
        return float(default)

    raise HTTPException(status_code=400, detail="Selling price is required for the sale.")


def _build_line_items(payload_items: List[Any], unit_price: float) -> Dict[str, Any]:
    """Build sale line items using the fixed unit selling price."""
    items: List[Dict[str, Any]] = []
    total_quantity = 0
    total_amount = 0.0

    for item in payload_items:
        if isinstance(item, dict):
            quantity = int(item.get("quantity", 0))
            size = item.get("size")
        else:
            quantity = int(getattr(item, "quantity", 0))
            size = getattr(item, "size", None)

        line_total = unit_price * quantity
        items.append({
            "size": size,
            "quantity": quantity,
            "selling_price": unit_price,
            "line_total": line_total,
        })
        total_quantity += quantity
        total_amount += line_total

    return {
        "items": items,
        "total_quantity": total_quantity,
        "total_amount": total_amount,
    }


def _format_sale_doc(doc) -> SaleRecord:
    data = doc.to_dict() or {}
    payment_history = data.get("payment_history") or []
    amount_paid = float(data.get("amount_paid", 0.0))
    total_amount = float(data.get("total_amount", 0.0))
    balance = float(data.get("balance", total_amount - amount_paid))
    payment_type = data.get("payment_type") or PaymentType.CASH.value

    formatted = SaleRecord(
        id=doc.id,
        customer_name=data.get("customer_name", ""),
        customer_phone=data.get("customer_phone", ""),
        design_id=data.get("design_id", ""),
        items=data.get("items", []),
        total_quantity=int(data.get("total_quantity", 0)),
        total_amount=total_amount,
        payment_type=payment_type,
        amount_paid=amount_paid,
        balance=balance,
        payment_history=payment_history,
        created_at=data.get("created_at"),
        updated_at=data.get("updated_at"),
    )
    return formatted


@router.post("/operate", status_code=status.HTTP_200_OK)
def operate_sales(
    request: SaleOperationRequest,
    current_user: dict = Depends(get_current_user_with_access(AccessLevel.LEVEL_1))
):
    action = request.action

    if action == SaleAction.CREATE:
        payload_data = request.payload or {}
        try:
            payload = SaleCreatePayload(**payload_data)
        except ValidationError as e:
            raise HTTPException(status_code=422, detail=f"Invalid payload for creating sale: {e}")

        design_id = payload.design_id
        inventory_ref = db.collection(INVENTORY_COLLECTION).document(design_id)
        inventory_doc = inventory_ref.get()
        if not inventory_doc.exists:
            raise HTTPException(status_code=400, detail="No inventory available for the selected design.")

        inventory_data = inventory_doc.to_dict()
        inventory_sizes = {size: int(qty) for size, qty in (inventory_data.get("sizes") or {}).items()}
        size_totals = _normalize_sizes(payload.items)
        unit_price = float(payload.selling_price_per_piece)

        for size, qty in size_totals.items():
            available = int(inventory_sizes.get(size, 0))
            if available < qty:
                raise HTTPException(status_code=400, detail=f"Not enough stock for size {size}. Available: {available}")
            inventory_sizes[size] = available - qty

        build_result = _build_line_items(payload.items, unit_price)
        total_quantity = build_result["total_quantity"]
        total_amount = build_result["total_amount"]

        amount_paid = float(payload.amount_paid)
        if payload.payment_type == PaymentType.CASH and abs(amount_paid - total_amount) > 1e-6:
            raise HTTPException(status_code=400, detail="Cash sales must be fully paid at the time of purchase.")
        if payload.payment_type == PaymentType.CREDIT and amount_paid - total_amount > 1e-6:
            raise HTTPException(status_code=400, detail="Initial payment cannot exceed the total sale amount.")

        balance = total_amount - amount_paid
        if balance < -1e-6:
            raise HTTPException(status_code=400, detail="Calculated balance cannot be negative.")

        remaining_total = int(inventory_data.get("total_available", 0)) - total_quantity
        if remaining_total < 0:
            raise HTTPException(status_code=400, detail="Inventory would become negative.")

        now = datetime.utcnow()
        payment_history: List[Dict[str, Any]] = []
        if amount_paid > 0:
            note = "Initial payment"
            payment_history.append({
                "payment_amount": amount_paid,
                "payment_date": now,
                "payment_note": note,
                "remaining_balance": max(balance, 0.0),
            })

        inventory_ref.update({
            "sizes": inventory_sizes,
            "total_available": remaining_total,
            "updated_at": now,
        })

        sale_record = {
            "customer_name": payload.customer_name,
            "customer_phone": payload.customer_phone,
            "design_id": design_id,
            "items": build_result["items"],
            "total_quantity": total_quantity,
            "total_amount": total_amount,
            "unit_selling_price": unit_price,
             "payment_type": payload.payment_type.value,
             "amount_paid": amount_paid,
             "balance": max(balance, 0.0),
             "payment_history": payment_history,
            "created_at": now,
            "updated_at": now,
        }
        doc_ref = db.collection(SALES_COLLECTION).document()
        doc_ref.set(sale_record)
        sale_doc = doc_ref.get()
        return _format_sale_doc(sale_doc).model_dump()

    if action == SaleAction.READ_ALL:
        docs = db.collection(SALES_COLLECTION).stream()
        sales = []
        for doc in docs:
            sales.append(_format_sale_doc(doc).model_dump())
        return sales

    if action == SaleAction.GET_BY_ID:
        doc_ref = db.collection(SALES_COLLECTION).document(request.sale_id)
        doc = doc_ref.get()
        if not doc.exists:
            raise HTTPException(status_code=404, detail="Sale not found.")
        return _format_sale_doc(doc).model_dump()

    if action == SaleAction.GET_BY_DESIGN:
        docs = db.collection(SALES_COLLECTION).where(
            filter=FieldFilter("design_id", "==", request.design_id)
        ).stream()
        sales = []
        for doc in docs:
            sales.append(_format_sale_doc(doc).model_dump())
        return sales

    if action == SaleAction.GET_CREDIT_SALES:
        query = db.collection(SALES_COLLECTION).where(
            filter=FieldFilter("balance", ">", 0)
        ).order_by("balance", direction=firestore.Query.DESCENDING)
        docs = query.stream()
        credit_sales = []
        for doc in docs:
            formatted = _format_sale_doc(doc)
            credit_sales.append(formatted.model_dump())
        return credit_sales

    if action == SaleAction.UPDATE:
        payload_data = request.payload or {}
        prohibited_fields = {"payment_type", "amount_paid", "balance"}
        if any(field in payload_data for field in prohibited_fields):
            raise HTTPException(status_code=400, detail="Use MAKE_PAYMENT to modify payment details.")

        try:
            payload = SaleUpdatePayload(**payload_data)
        except ValidationError as e:
            raise HTTPException(status_code=422, detail=f"Invalid payload for updating sale: {e}")

        sale_ref = db.collection(SALES_COLLECTION).document(request.sale_id)
        sale_doc = sale_ref.get()
        if not sale_doc.exists:
            raise HTTPException(status_code=404, detail="Sale not found.")

        existing_sale = sale_doc.to_dict()
        balance = float(existing_sale.get("balance", existing_sale.get("total_amount", 0.0) - existing_sale.get("amount_paid", 0.0)))
        if balance > 1e-6:
            raise HTTPException(status_code=400, detail="Cannot update sale details while balance remains outstanding.")

        design_id = existing_sale.get("design_id")
        if not design_id:
            raise HTTPException(status_code=400, detail="Sale is missing design information.")

        inventory_ref = db.collection(INVENTORY_COLLECTION).document(design_id)
        inventory_doc = inventory_ref.get()
        if not inventory_doc.exists:
            raise HTTPException(status_code=400, detail="Inventory record missing for the design.")

        inventory_data = inventory_doc.to_dict()
        inventory_sizes = {size: int(qty) for size, qty in (inventory_data.get("sizes") or {}).items()}

        old_items = existing_sale.get("items", [])
        old_totals = _normalize_sizes(old_items)
        new_totals = _normalize_sizes(payload.items) if payload.items is not None else old_totals

        update_fields: Dict[str, Any] = {}

        if payload.customer_name is not None:
            update_fields["customer_name"] = payload.customer_name
        if payload.customer_phone is not None:
            update_fields["customer_phone"] = payload.customer_phone

        unit_price = existing_sale.get("unit_selling_price")
        if unit_price is None:
            unit_price = _extract_unit_price(existing_sale.get("items", []))
        unit_price = float(unit_price)

        if payload.items is not None:
            for size, qty in old_totals.items():
                inventory_sizes[size] = int(inventory_sizes.get(size, 0)) + qty

            for size, qty in new_totals.items():
                available = int(inventory_sizes.get(size, 0))
                if available < qty:
                    raise HTTPException(status_code=400, detail=f"Not enough stock for size {size}. Available: {available}")
                inventory_sizes[size] = available - qty

            build_result = _build_line_items(payload.items, unit_price)
            total_new = build_result["total_quantity"]
            total_amount = build_result["total_amount"]
            total_old = sum(old_totals.values())
            existing_total_amount = float(existing_sale.get("total_amount", 0.0))
            if abs(total_amount - existing_total_amount) > 1e-6:
                raise HTTPException(
                    status_code=400,
                    detail="Updated items would change the total amount. Adjust payments using MAKE_PAYMENT first."
                )

            remaining_total = int(inventory_data.get("total_available", 0)) + total_old - total_new
            if remaining_total < 0:
                raise HTTPException(status_code=400, detail="Inventory would become negative.")

            now = datetime.utcnow()
            inventory_ref.update({
                "sizes": inventory_sizes,
                "total_available": remaining_total,
                "updated_at": now,
            })

            update_fields.update({
                "items": build_result["items"],
                "total_quantity": total_new,
                "total_amount": total_amount,
                "unit_selling_price": unit_price,
            })

        if not update_fields:
            raise HTTPException(status_code=400, detail="No valid fields provided for update.")

        now = datetime.utcnow()
        update_fields["updated_at"] = now
        sale_ref.update(update_fields)

        updated_doc = sale_ref.get()
        return _format_sale_doc(updated_doc).model_dump()

    if action == SaleAction.MAKE_PAYMENT:
        payload_data = request.payload or {}
        try:
            payment_payload = CreditPaymentPayload(**payload_data)
        except ValidationError as e:
            raise HTTPException(status_code=422, detail=f"Invalid payload for credit payment: {e}")

        sale_ref = db.collection(SALES_COLLECTION).document(request.sale_id)
        sale_doc = sale_ref.get()
        if not sale_doc.exists:
            raise HTTPException(status_code=404, detail="Sale not found.")

        sale_data = sale_doc.to_dict()
        if sale_data.get("payment_type") != PaymentType.CREDIT.value:
            raise HTTPException(status_code=400, detail="Payments can only be recorded for credit sales.")

        amount_paid = float(sale_data.get("amount_paid", 0.0))
        total_amount = float(sale_data.get("total_amount", 0.0))
        balance = float(sale_data.get("balance", total_amount - amount_paid))
        if balance <= 1e-6:
            raise HTTPException(status_code=400, detail="Sale is already fully paid.")

        payment_amount = float(payment_payload.payment_amount)
        if payment_amount > balance + 1e-6:
            raise HTTPException(status_code=400, detail="Payment amount cannot exceed the outstanding balance.")

        new_amount_paid = amount_paid + payment_amount
        new_balance = total_amount - new_amount_paid
        if new_balance < -1e-6:
            raise HTTPException(status_code=400, detail="Calculated balance cannot be negative.")

        payment_history = list(sale_data.get("payment_history") or [])
        now = datetime.utcnow()
        payment_history.append({
            "payment_amount": payment_amount,
            "payment_date": now,
            "payment_note": payment_payload.payment_note or "Credit payment",
            "remaining_balance": max(new_balance, 0.0),
        })

        sale_ref.update({
            "amount_paid": new_amount_paid,
            "balance": max(new_balance, 0.0),
            "payment_history": payment_history,
            "updated_at": now,
        })

        updated_doc = sale_ref.get()
        return {
            "status": "success",
            "message": "Payment recorded successfully.",
            "sale": _format_sale_doc(updated_doc).model_dump(),
        }

    if action == SaleAction.GET_PAYMENT_HISTORY:
        sale_ref = db.collection(SALES_COLLECTION).document(request.sale_id)
        sale_doc = sale_ref.get()
        if not sale_doc.exists:
            raise HTTPException(status_code=404, detail="Sale not found.")

        sale_data = _format_sale_doc(sale_doc).model_dump()
        return {
            "sale_id": sale_data["id"],
            "customer_name": sale_data["customer_name"],
            "total_amount": sale_data["total_amount"],
            "amount_paid": sale_data["amount_paid"],
            "balance": sale_data["balance"],
            "payment_history": sale_data["payment_history"],
        }

    if action == SaleAction.DELETE:
        sale_ref = db.collection(SALES_COLLECTION).document(request.sale_id)
        sale_doc = sale_ref.get()
        if not sale_doc.exists:
            raise HTTPException(status_code=404, detail="Sale not found.")

        sale_data = sale_doc.to_dict()
        balance = float(sale_data.get("balance", sale_data.get("total_amount", 0.0) - sale_data.get("amount_paid", 0.0)))
        warning_message: Optional[str] = None
        if balance > 1e-6:
            if current_user["access_level"] != AccessLevel.LEVEL_2.value:
                raise HTTPException(
                    status_code=403,
                    detail="Only Level 2 users can delete sales with outstanding balance."
                )
            warning_message = "Sale deleted with outstanding balance. Verify financial reconciliation."

        design_id = sale_data.get("design_id")
        if not design_id:
            sale_ref.delete()
            response = {"status": "success", "message": f"Sale {request.sale_id} deleted."}
            if warning_message:
                response["warning"] = warning_message
            return response

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
        response = {
            "status": "success",
            "message": f"Sale {request.sale_id} deleted.",
            "restored_quantity": total_return
        }
        if warning_message:
            response["warning"] = warning_message
        return response

    raise HTTPException(status_code=400, detail="Invalid sales action provided.")
