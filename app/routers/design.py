from fastapi import APIRouter, HTTPException, status
from typing import List, Any, Dict
from datetime import datetime
from pydantic import ValidationError

from app.models.design import DesignCreatePayload, DesignUpdate, DesignResponse, DesignOperationRequest, Design
from app.services.firebase_service import db, CLOTH_COLLECTION

router = APIRouter(
    prefix="/designs",
    tags=["Design Operations"]
)

DESIGN_COLLECTION = "designs"

@router.post("/operate", response_model=Any, status_code=status.HTTP_200_OK)
def operate_design(request: DesignOperationRequest):
    """
    A single endpoint to handle all CRUD operations for designs.
    - **CREATE**: Provide `action: "CREATE"` and a valid `payload`.
    - **READ**: Provide `action: "READ"` and the `design_id`.
    - **READ_ALL**: Provide `action: "READ_ALL"`.
    - **UPDATE**: Provide `action: "UPDATE"`, `design_id`, and a `payload` with fields to update.
    - **DELETE**: Provide `action: "DELETE"` and the `design_id`.
    - **GET_TOTALS**: Provide `action: "GET_TOTALS"` and a `payload` with the `design_code`.
    """
    action = request.action
    design_id = request.design_id
    payload = request.payload

    # --- CREATE Operation ---
    if action == "CREATE":
        if not payload:
            raise HTTPException(status_code=400, detail="Payload required for CREATE action.")
        try:
            create_payload = DesignCreatePayload(**payload)

            if not create_payload.cloth_purchase_id:
                raise HTTPException(status_code=400, detail="cloth_purchase_id is required.")
            
            # Check cloth purchase and available yards
            cloth_purchase_ref = db.collection(CLOTH_COLLECTION).document(create_payload.cloth_purchase_id)
            cloth_purchase_doc = cloth_purchase_ref.get()

            if not cloth_purchase_doc.exists:
                raise HTTPException(status_code=404, detail="Cloth purchase not found.")

            cloth_purchase_data = cloth_purchase_doc.to_dict()
            
            total_yards_for_design = create_payload.allocated_yards_per_piece * create_payload.number_of_pieces

            if cloth_purchase_data['total_yards'] < total_yards_for_design:
                raise HTTPException(status_code=400, detail="Not enough yards in the cloth purchase.")
            
            # Calculate new size distribution
            new_size_distribution = []
            for size_info in create_payload.size_distribution:
                new_size_distribution.append({
                    "size": size_info.size,
                    "quantity": size_info.quantity * create_payload.number_of_pieces
                })

            design_data = Design(
                design_code=create_payload.design_code,
                cloth_purchase_id=create_payload.cloth_purchase_id,
                allocated_yards=total_yards_for_design,
                size_distribution=new_size_distribution
            ).model_dump()
            
            design_data['created_at'] = datetime.utcnow()
            _, doc_ref = db.collection(DESIGN_COLLECTION).add(design_data)
            
            # Update cloth purchase with reduced yards
            new_total_yards = cloth_purchase_data['total_yards'] - total_yards_for_design
            cloth_purchase_ref.update({"total_yards": new_total_yards})
            
            created_design = design_data
            created_design['id'] = doc_ref.id
            return created_design

        except ValidationError as e:
            raise HTTPException(status_code=422, detail=f"Invalid payload for creating design: {e}")

    # --- READ_ALL Operation ---
    if action == "READ_ALL":
        designs = []
        docs = db.collection(DESIGN_COLLECTION).stream()
        for doc in docs:
            design_data = doc.to_dict()
            design_data['id'] = doc.id
            designs.append(design_data)
        return designs

    # The following actions require a design_id
    if not design_id and action in ["READ", "UPDATE", "DELETE"]:
        raise HTTPException(status_code=400, detail=f"design_id is required for {action} action.")

    if design_id:
        doc_ref = db.collection(DESIGN_COLLECTION).document(design_id)
        doc = doc_ref.get()
        if not doc.exists and action in ["READ", "UPDATE", "DELETE"]:
            raise HTTPException(status_code=404, detail="Design not found")

    # --- READ (Single) Operation ---
    if action == "READ":
        design_data = doc.to_dict()
        design_data['id'] = doc.id
        return design_data

    # --- UPDATE Operation ---
    if action == "UPDATE":
        if not payload:
            raise HTTPException(status_code=400, detail="Payload required for UPDATE action.")
        try:
            update_data = DesignUpdate(**payload).model_dump(exclude_unset=True)
            if not update_data:
                raise HTTPException(status_code=400, detail="No valid fields to update in payload.")

            design_data = doc.to_dict()
            original_allocated_yards = design_data.get('allocated_yards', 0)

            # Update design document
            doc_ref.update(update_data)
            
            if 'allocated_yards' in update_data:
                new_allocated_yards = update_data['allocated_yards']
                yardage_difference = new_allocated_yards - original_allocated_yards
                
                cloth_purchase_ref = db.collection(CLOTH_COLLECTION).document(design_data['cloth_purchase_id'])
                cloth_purchase_doc = cloth_purchase_ref.get()
                
                if not cloth_purchase_doc.exists:
                    # Revert the design update if the cloth purchase is not found
                    doc_ref.update({'allocated_yards': original_allocated_yards})
                    raise HTTPException(status_code=404, detail="Cloth purchase not found.")
                
                cloth_purchase_data = cloth_purchase_doc.to_dict()
                new_total_yards = cloth_purchase_data['total_yards'] - yardage_difference
                
                if new_total_yards < 0:
                    # Revert the design update if not enough yards
                    doc_ref.update({'allocated_yards': original_allocated_yards})
                    raise HTTPException(status_code=400, detail="Not enough yards in the cloth purchase.")

                cloth_purchase_ref.update({"total_yards": new_total_yards})

            updated_doc = doc_ref.get()
            response_data = updated_doc.to_dict()
            response_data['id'] = updated_doc.id
            return response_data
        except ValidationError as e:
            raise HTTPException(status_code=422, detail=f"Invalid payload for updating design: {e}")

    # --- DELETE Operation ---
    if action == "DELETE":
        design_data = doc.to_dict()
        original_allocated_yards = design_data.get('allocated_yards', 0)
        
        cloth_purchase_ref = db.collection(CLOTH_COLLECTION).document(design_data['cloth_purchase_id'])
        cloth_purchase_doc = cloth_purchase_ref.get()
        
        if cloth_purchase_doc.exists:
            cloth_purchase_data = cloth_purchase_doc.to_dict()
            new_total_yards = cloth_purchase_data['total_yards'] + original_allocated_yards
            cloth_purchase_ref.update({"total_yards": new_total_yards})

        doc_ref.delete()
        return {"status": "success", "message": f"Design {design_id} deleted and yards returned to cloth purchase."}
    
    # --- GET TOTALS ---
    if action == "GET_TOTALS":
        if not payload or 'design_code' not in payload:
            raise HTTPException(status_code=400, detail="design_code is required for GET_TOTALS action.")
        
        design_code = payload['design_code']
        docs = db.collection(DESIGN_COLLECTION).where('design_code', '==', design_code).stream()
        
        size_totals = {}
        for doc in docs:
            design_data = doc.to_dict()
            for size_info in design_data.get('size_distribution', []):
                size = size_info.get('size')
                quantity = size_info.get('quantity')
                if size and quantity:
                    size_totals[size] = size_totals.get(size, 0) + quantity
        
        return {"design_code": design_code, "size_totals": size_totals}


    raise HTTPException(status_code=400, detail="Invalid action specified.")