from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import ValidationError

from app.auth import get_current_user_with_access
from app.models.expense import (
    ExpenseCreate,
    ExpenseCrudAction,
    ExpenseOperationRequest,
    ExpenseResponse,
    ExpenseUpdate,
)
from app.models.user import AccessLevel
from app.services.firebase_service import EXPENSES_COLLECTION, db


router = APIRouter(
    prefix="/expenses",
    tags=["Expense Operations"],
)


@router.post("/operate", response_model=Any, status_code=status.HTTP_200_OK)
def operate_expense(
    request: ExpenseOperationRequest,
    current_user: dict = Depends(get_current_user_with_access(AccessLevel.LEVEL_1)),
):
    """
    Unified endpoint handling CRUD operations for expenses.
    """
    action = request.action
    expense_id = request.expense_id
    payload = request.payload

    # --- CREATE Operation ---
    if action == ExpenseCrudAction.CREATE:
        if not payload:
            raise HTTPException(status_code=400, detail="Payload required for CREATE action.")
        try:
            create_payload = ExpenseCreate(**payload).model_dump()
            expense_data = {
                **create_payload,
                "created_at": datetime.utcnow(),
                "updated_at": None,
            }
            _, doc_ref = db.collection(EXPENSES_COLLECTION).add(expense_data)
            created_expense: ExpenseResponse = ExpenseResponse(id=doc_ref.id, **expense_data)
            return created_expense.model_dump()
        except ValidationError as e:
            raise HTTPException(status_code=422, detail=f"Invalid payload for creating expense: {e}")

    # --- READ_ALL Operation ---
    if action == ExpenseCrudAction.READ_ALL:
        expenses = []
        docs = db.collection(EXPENSES_COLLECTION).stream()
        for doc in docs:
            expense_data = doc.to_dict()
            expense_data["id"] = doc.id
            expenses.append(expense_data)
        return expenses

    # --- Common ID Validation ---
    if action in {ExpenseCrudAction.READ, ExpenseCrudAction.UPDATE, ExpenseCrudAction.DELETE}:
        if not expense_id:
            raise HTTPException(status_code=400, detail=f"expense_id is required for {action.value} action.")
        doc_ref = db.collection(EXPENSES_COLLECTION).document(expense_id)
        doc = doc_ref.get()
        if not doc.exists:
            raise HTTPException(status_code=404, detail="Expense not found.")
    else:
        doc_ref = doc = None  # type: ignore

    # --- READ (Single) Operation ---
    if action == ExpenseCrudAction.READ:
        expense_data = doc.to_dict()
        expense_data["id"] = doc.id
        return expense_data

    # --- UPDATE Operation ---
    if action == ExpenseCrudAction.UPDATE:
        if current_user["access_level"] != AccessLevel.LEVEL_2.value:
            raise HTTPException(status_code=403, detail="You do not have permission to perform this action.")
        if not payload:
            raise HTTPException(status_code=400, detail="Payload required for UPDATE action.")
        try:
            update_payload = ExpenseUpdate(**payload).model_dump(exclude_unset=True)
            if not update_payload:
                raise HTTPException(status_code=400, detail="No valid fields to update in payload.")
            update_payload["updated_at"] = datetime.utcnow()
            doc_ref.update(update_payload)
            updated_doc = doc_ref.get()
            response_data = updated_doc.to_dict()
            response_data["id"] = updated_doc.id
            return response_data
        except ValidationError as e:
            raise HTTPException(status_code=422, detail=f"Invalid payload for updating expense: {e}")

    # --- DELETE Operation ---
    if action == ExpenseCrudAction.DELETE:
        if current_user["access_level"] != AccessLevel.LEVEL_2.value:
            raise HTTPException(status_code=403, detail="You do not have permission to perform this action.")
        doc_ref.delete()
        return {"status": "success", "message": f"Expense {expense_id} deleted."}

    raise HTTPException(status_code=400, detail="Invalid action specified.")
