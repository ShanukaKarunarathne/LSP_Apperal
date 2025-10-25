from datetime import datetime
from typing import Dict

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import ValidationError

from app.auth import get_current_user_with_access
from app.models.quotation import (
    QuotationAction,
    QuotationCreatePayload,
    QuotationLine,
    QuotationOperationRequest,
    QuotationResponse,
)
from app.models.user import AccessLevel
from app.services.firebase_service import db, INVENTORY_COLLECTION

router = APIRouter(
    prefix="/quotations",
    tags=["Quotations"]
)


def _normalize_sizes(items) -> Dict[str, int]:
    """Aggregate requested quantities per size for quick lookups."""
    totals: Dict[str, int] = {}
    for item in items:
        size = item.size
        quantity = int(item.quantity)
        totals[size] = totals.get(size, 0) + quantity
    return totals


@router.post(
    "/operate",
    response_model=QuotationResponse,
    status_code=status.HTTP_200_OK,
)
def operate_quotation(
    request: QuotationOperationRequest,
    current_user: dict = Depends(get_current_user_with_access(AccessLevel.LEVEL_1)),
):
    if request.action != QuotationAction.GENERATE:
        raise HTTPException(status_code=400, detail="Invalid quotation action provided.")

    payload_data = request.payload or {}
    try:
        payload = QuotationCreatePayload(**payload_data)
    except ValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid payload for generating quotation: {exc}",
        )

    inventory_ref = db.collection(INVENTORY_COLLECTION).document(payload.design_id)
    inventory_doc = inventory_ref.get()
    if not inventory_doc.exists:
        raise HTTPException(status_code=404, detail="Inventory record not found for the design.")

    inventory_data = inventory_doc.to_dict() or {}
    inventory_sizes = {size: int(qty) for size, qty in (inventory_data.get("sizes") or {}).items()}

    size_totals = _normalize_sizes(payload.items)
    insufficient_sizes = []
    for size, qty in size_totals.items():
        available = inventory_sizes.get(size, 0)
        if available < qty:
            insufficient_sizes.append(f"{size} (requested {qty}, available {available})")

    if insufficient_sizes:
        raise HTTPException(
            status_code=400,
            detail="Not enough stock for: " + ", ".join(insufficient_sizes),
        )

    unit_price = float(payload.selling_price_per_piece)
    total_quantity = sum(size_totals.values())
    total_amount = unit_price * total_quantity

    quotation_items = [
        QuotationLine(
            size=item.size,
            requested_quantity=item.quantity,
            available_quantity=inventory_sizes.get(item.size, 0),
            selling_price=unit_price,
            line_total=unit_price * item.quantity,
        )
        for item in payload.items
    ]

    response = QuotationResponse(
        design_id=payload.design_id,
        total_requested_quantity=total_quantity,
        total_amount=total_amount,
        unit_price=unit_price,
        items=quotation_items,
        available_inventory=inventory_sizes,
        generated_at=datetime.utcnow(),
    )
    return response
