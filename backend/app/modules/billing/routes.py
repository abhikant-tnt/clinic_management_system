from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from datetime import datetime
import uuid
from app.core.config import settings
from app.core.database import postgres_conn, postgres_cursor
from app.modules.billing.schemas import (
    BillingInvoiceCreate, BillingInvoiceUpdate
)

def get_tenant_uuid() -> uuid.UUID:
    """Convert string tenant_id to UUID using deterministic UUID5 generation"""
    namespace = uuid.UUID('6ba7b810-9dad-11d1-80b4-00c04fd430c8')  # DNS namespace
    return uuid.uuid5(namespace, settings.TENANT_ID)
def check_patient_exists(patient_id: int, tenant_id: str) -> bool:
    """Check if patient exists"""
    if postgres_cursor:
        try:
            postgres_cursor.execute("SELECT id FROM patients_table WHERE id = %s AND tenant_id = %s", (patient_id, tenant_id))
            return postgres_cursor.fetchone() is not None
        except Exception:
            return False
    return False

def check_appointment_exists(appointment_id: int, tenant_id: str) -> bool:
    """Check if appointment exists"""
    if postgres_cursor:
        try:
            postgres_cursor.execute("SELECT id FROM appointments WHERE id = %s AND tenant_id = %s", (appointment_id, tenant_id))
            return postgres_cursor.fetchone() is not None
        except Exception:
            return False
    return False

def check_staff_exists(staff_id: int, tenant_id: str) -> bool:
    """Check if staff exists"""
    if postgres_cursor:
        try:
            postgres_cursor.execute("SELECT id FROM staff WHERE id = %s AND tenant_id = %s", (staff_id, tenant_id))
            return postgres_cursor.fetchone() is not None
        except Exception:
            return False
    return False

router = APIRouter()

def get_tenant_id() -> str:
    return settings.TENANT_ID

def convert_date_format(date_str: str) -> str:
    """Convert dd/mm/yyyy to yyyy-mm-dd for PostgreSQL DATE"""
    if not date_str:
        return None
    day, month, year = map(int, date_str.split('/'))
    return f"{year}-{month:02d}-{day:02d}"

@router.get("/invoices")
def get_invoices(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    patient_id: Optional[int] = None,
    status: Optional[str] = None
):
    tenant_id_string = settings.TENANT_ID
    
    invoices_list = []
    if postgres_cursor:
        try:
            conditions = ["tenant_id = %s"]
            params = [tenant_id_string]
            
            if patient_id:
                conditions.append("patient_id = %s")
                params.append(patient_id)
            
            if status:
                conditions.append("status = %s")
                params.append(status)
            
            query = f"""
                SELECT id, tenant_id, invoice_number, patient_id, appointment_id, doctor_id,
                       issue_date, purpose, total_amount, tax_amount, gst_percentage,
                       discount_amount, coupon_code, adjustments, amount_paid, outstanding_amount,
                       status, created_by, created_at, updated_at
                FROM billing_invoices
                WHERE {' AND '.join(conditions)}
                ORDER BY created_at DESC
            """
            postgres_cursor.execute(query, params)
            columns = [desc[0] for desc in postgres_cursor.description]
            invoices_list = [dict(zip(columns, r)) for r in postgres_cursor.fetchall()]
        except Exception as e:
            pass
    
    total = len(invoices_list)
    total_pages = (total + limit - 1) // limit if total > 0 else 1
    
    return {
        "invoices": invoices_list[(page - 1) * limit:page * limit],
        "pagination": {"total": total, "page": page, "limit": limit, "total_pages": total_pages, "has_next": page < total_pages, "has_prev": page > 1}
    }

@router.get("/invoices/{invoice_id}")
def get_invoice(invoice_id: str):
    tenant_id_string = settings.TENANT_ID
    
    if postgres_cursor:
        try:
            # Convert invoice_id to integer (was UUID, now INTEGER)
            invoice_id_int = int(invoice_id)
            postgres_cursor.execute("""
                SELECT id, tenant_id, invoice_number, patient_id, appointment_id, doctor_id,
                       issue_date, purpose, total_amount, tax_amount, gst_percentage,
                       discount_amount, coupon_code, adjustments, amount_paid, outstanding_amount,
                       status, created_by, created_at, updated_at
                FROM billing_invoices
                WHERE id = %s AND tenant_id = %s
            """, (invoice_id_int, tenant_id_string))
            record = postgres_cursor.fetchone()
            if record:
                columns = [desc[0] for desc in postgres_cursor.description]
                invoice_dict = dict(zip(columns, record))
                
                # Get items for this invoice
                postgres_cursor.execute("""
                    SELECT id, tenant_id, invoice_id, item_type, description, quantity,
                           unit_price, line_total, inventory_item_id, created_at
                    FROM billing_items
                    WHERE invoice_id = %s
                    ORDER BY created_at
                """, (invoice_id_int,))
                items_columns = [desc[0] for desc in postgres_cursor.description]
                items = [dict(zip(items_columns, r)) for r in postgres_cursor.fetchall()]
                invoice_dict["items"] = items
                
                return invoice_dict
            else:
                raise HTTPException(status_code=404, detail=f"Invoice with ID {invoice_id} not found")
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error fetching invoice: {str(e)}")
    
    raise HTTPException(status_code=500, detail="Database connection not available")

@router.post("/invoices")
def create_invoice(invoice_data: BillingInvoiceCreate):
    # Use string tenant_id (VARCHAR) instead of UUID
    tenant_id_to_use = invoice_data.tenant_id if invoice_data.tenant_id else settings.TENANT_ID
    
    # Validate foreign keys (these tables use VARCHAR for tenant_id)
    if not check_patient_exists(invoice_data.patient_id, tenant_id_to_use):
        raise HTTPException(status_code=404, detail=f"Patient with ID {invoice_data.patient_id} not found")
    
    if not check_appointment_exists(invoice_data.appointment_id, tenant_id_to_use):
        raise HTTPException(status_code=404, detail=f"Appointment with ID {invoice_data.appointment_id} not found")
    
    if not check_staff_exists(invoice_data.doctor_id, tenant_id_to_use):
        raise HTTPException(status_code=404, detail=f"Staff/Doctor with ID {invoice_data.doctor_id} not found")
    
    if postgres_cursor and postgres_conn:
        try:
            # Check if invoice_number already exists
            postgres_cursor.execute(
                "SELECT id FROM billing_invoices WHERE invoice_number = %s",
                (invoice_data.invoice_number,)
            )
            if postgres_cursor.fetchone():
                raise HTTPException(status_code=400, detail="Invoice number already exists")
            
            issue_date_pg = convert_date_format(invoice_data.issue_date)
            
            # Insert invoice
            postgres_cursor.execute("""
                INSERT INTO billing_invoices (
                    tenant_id, invoice_number, patient_id, appointment_id, doctor_id,
                    issue_date, purpose, total_amount, tax_amount, gst_percentage,
                    discount_amount, coupon_code, adjustments, amount_paid, status,
                    created_by
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                tenant_id_to_use, invoice_data.invoice_number, invoice_data.patient_id,
                invoice_data.appointment_id, invoice_data.doctor_id, issue_date_pg,
                invoice_data.purpose, invoice_data.total_amount, invoice_data.tax_amount,
                invoice_data.gst_percentage, invoice_data.discount_amount,
                invoice_data.coupon_code, invoice_data.adjustments, invoice_data.amount_paid,
                invoice_data.status, invoice_data.created_by
            ))
            
            invoice_result = postgres_cursor.fetchone()
            invoice_id = invoice_result[0] if invoice_result else None
            
            if not invoice_id:
                raise HTTPException(status_code=500, detail="Failed to create invoice")
            
            # Insert billing items
            for item in invoice_data.items:
                # Convert inventory_item_id to integer if provided (was UUID, now INTEGER)
                inventory_item_id = int(item.inventory_item_id) if item.inventory_item_id else None
                postgres_cursor.execute("""
                    INSERT INTO billing_items (
                        tenant_id, invoice_id, item_type, description, quantity,
                        unit_price, line_total, inventory_item_id
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    tenant_id_to_use, invoice_id, item.item_type, item.description,
                    item.quantity, item.unit_price, item.line_total, inventory_item_id
                ))
            
            postgres_conn.commit()
            
            return {"message": f"Invoice created successfully", "invoice_id": invoice_id}
            
        except HTTPException:
            raise
        except Exception as e:
            postgres_conn.rollback()
            raise HTTPException(status_code=500, detail=f"Error creating invoice: {str(e)}")
    
    raise HTTPException(status_code=500, detail="Database connection not available")

@router.put("/invoices/{invoice_id}")
def update_invoice(invoice_id: str, invoice_data: BillingInvoiceUpdate):
    tenant_id_string = settings.TENANT_ID
    
    # Check if invoice exists
    if postgres_cursor:
        try:
            # Convert invoice_id to integer (was UUID, now INTEGER)
            invoice_id_int = int(invoice_id)
            postgres_cursor.execute(
                "SELECT id FROM billing_invoices WHERE id = %s AND tenant_id = %s",
                (invoice_id_int, tenant_id_string)
            )
            if not postgres_cursor.fetchone():
                raise HTTPException(status_code=404, detail=f"Invoice with ID {invoice_id} not found")
            
            update_data = {}
            if invoice_data.tax_amount is not None:
                update_data["tax_amount"] = invoice_data.tax_amount
            if invoice_data.gst_percentage is not None:
                update_data["gst_percentage"] = invoice_data.gst_percentage
            if invoice_data.discount_amount is not None:
                update_data["discount_amount"] = invoice_data.discount_amount
            if invoice_data.coupon_code is not None:
                update_data["coupon_code"] = invoice_data.coupon_code
            if invoice_data.adjustments is not None:
                update_data["adjustments"] = invoice_data.adjustments
            if invoice_data.amount_paid is not None:
                update_data["amount_paid"] = invoice_data.amount_paid
            if invoice_data.status is not None:
                update_data["status"] = invoice_data.status
            
            update_data["updated_at"] = datetime.now()
            
            if not update_data:
                raise HTTPException(status_code=400, detail="No fields provided for update")
            
            set_clauses = [f"{key} = %s" for key in update_data.keys()]
            values = [update_data[key] for key in update_data.keys()]
            values.append(invoice_id_int)
            values.append(tenant_id_string)
            
            query = f"UPDATE billing_invoices SET {', '.join(set_clauses)} WHERE id = %s AND tenant_id = %s"
            postgres_cursor.execute(query, values)
            postgres_conn.commit()
            return {"message": f"Invoice with ID {invoice_id} updated successfully"}
            
        except HTTPException:
            raise
        except Exception as e:
            postgres_conn.rollback()
            raise HTTPException(status_code=500, detail=f"Error updating invoice: {str(e)}")
    
    raise HTTPException(status_code=500, detail="Database connection not available")

@router.delete("/invoices/{invoice_id}")
def delete_invoice(invoice_id: str):
    tenant_id_string = settings.TENANT_ID
    
    if postgres_cursor and postgres_conn:
        try:
            # Convert invoice_id to integer (was UUID, now INTEGER)
            invoice_id_int = int(invoice_id)
            postgres_cursor.execute(
                "DELETE FROM billing_invoices WHERE id = %s AND tenant_id = %s",
                (invoice_id_int, tenant_id_string)
            )
            postgres_conn.commit()
            
            if postgres_cursor.rowcount > 0:
                return {"message": f"Invoice with ID {invoice_id} deleted successfully"}
            else:
                raise HTTPException(status_code=404, detail=f"Invoice with ID {invoice_id} not found")
        except HTTPException:
            raise
        except Exception as e:
            postgres_conn.rollback()
            raise HTTPException(status_code=500, detail=f"Error deleting invoice: {str(e)}")
    
    raise HTTPException(status_code=500, detail="Database connection not available")

@router.get("/items/{item_id}")
def get_billing_item(item_id: str):
    tenant_id_string = settings.TENANT_ID
    
    if postgres_cursor:
        try:
            # Convert item_id to integer (was UUID, now INTEGER)
            item_id_int = int(item_id)
            postgres_cursor.execute("""
                SELECT id, tenant_id, invoice_id, item_type, description, quantity,
                       unit_price, line_total, inventory_item_id, created_at
                FROM billing_items
                WHERE id = %s AND tenant_id = %s
            """, (item_id_int, tenant_id_string))
            record = postgres_cursor.fetchone()
            if record:
                columns = [desc[0] for desc in postgres_cursor.description]
                return dict(zip(columns, record))
            else:
                raise HTTPException(status_code=404, detail=f"Billing item with ID {item_id} not found")
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error fetching billing item: {str(e)}")
    
    raise HTTPException(status_code=500, detail="Database connection not available")
