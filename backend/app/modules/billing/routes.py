from fastapi import APIRouter, HTTPException, Query, Depends
from typing import Optional, List
import uuid
from app.core.config import settings
from app.core.db_utils import get_db_session
from app.core.models import BillingInvoiceModel, BillingItemModel, PatientModel, AppointmentsModel, UserModel, InventoryItemModel, PharmacyWalkInBillModel, PharmacyWalkInItemModel
from app.core.dependencies import get_current_active_user
from app.core.db_helper import check_exists
from app.common.utils import raise_not_found_error, raise_internal_server_error
from sqlalchemy import and_
from app.core.date_helpers import string_to_date, date_to_string
from app.modules.billing.schemas import (
    BillingInvoiceCreate, BillingInvoiceUpdate,
    PharmacyWalkInBillCreate, PharmacyWalkInBillUpdate
)

def get_tenant_uuid() -> uuid.UUID:
    """Convert string tenant_id to UUID using deterministic UUID5 generation"""
    namespace = uuid.UUID('6ba7b810-9dad-11d1-80b4-00c04fd430c8')  # DNS namespace
    return uuid.uuid5(namespace, settings.TENANT_ID)
def check_patient_exists(patient_id: int, tenant_id: str) -> bool:
    """Check if patient exists using database helper"""
    return check_exists(PatientModel, "patients_table", "id", patient_id, tenant_id)

def check_appointment_exists(appointment_id: int, tenant_id: str) -> bool:
    """Check if appointment exists using database helper"""
    return check_exists(AppointmentsModel, "appointments", "id", appointment_id, tenant_id)

def check_user_exists(user_id: int, tenant_id: str) -> bool:
    """Check if user exists using database helper"""
    return check_exists(UserModel, "users", "id", user_id, tenant_id)

def reduce_inventory_stock(session, items, tenant_id: str):
    """
    Reduce inventory stock for pharmacy items when bill is paid.
    Items can be BillingItemModel or PharmacyWalkInItemModel.
    """
    from app.core.models import InventoryItemModel
    
    for item in items:
        # Handle both BillingItemModel and PharmacyWalkInItemModel
        inventory_item_id = item.inventory_item_id if hasattr(item, 'inventory_item_id') else None
        item_type = item.item_type.lower() if hasattr(item, 'item_type') else "product"
        quantity = item.quantity if hasattr(item, 'quantity') else 0
        
        if inventory_item_id and item_type == "product":
            inventory_item = session.query(InventoryItemModel).filter(
                and_(
                    InventoryItemModel.id == inventory_item_id,
                    InventoryItemModel.tenant_id == tenant_id
                )
            ).first()
            
            if inventory_item:
                # Check if sufficient stock available
                if inventory_item.current_stock < quantity:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Insufficient stock for {inventory_item.name}. Available: {inventory_item.current_stock}, Required: {quantity}"
                    )
                
                # Reduce stock
                inventory_item.current_stock -= quantity
                
                # Update is_in_stock flag
                inventory_item.is_in_stock = inventory_item.current_stock > 0
                
                session.add(inventory_item)

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
async def get_invoices(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=10),  # Max 10 per page as per requirements
    patient_id: Optional[int] = None,
    status: Optional[str] = None,
    search: Optional[str] = Query(None, description="Search by invoice number, patient name, or appointment ID"),
    start_date: Optional[str] = Query(None, description="Start date filter (dd/mm/yyyy)"),
    end_date: Optional[str] = Query(None, description="End date filter (dd/mm/yyyy)"),
    current_user: dict = Depends(get_current_active_user)
):
    """Get invoices for billing panel table view"""
    tenant_id_string = settings.TENANT_ID
    
    try:
        with get_db_session() as session:
            # Join with Patient and Users tables
            query = session.query(
                BillingInvoiceModel,
                PatientModel,
                UserModel
            ).join(
                PatientModel, BillingInvoiceModel.patient_id == PatientModel.id
            ).join(
                UserModel, BillingInvoiceModel.doctor_id == UserModel.id
            ).filter(
                BillingInvoiceModel.tenant_id == tenant_id_string
            )
            
            if patient_id:
                query = query.filter(BillingInvoiceModel.patient_id == patient_id)
            
            if status:
                query = query.filter(BillingInvoiceModel.status == status)
            
            # Date range filter
            if start_date:
                start_date_obj = string_to_date(start_date)
                if start_date_obj:
                    query = query.filter(BillingInvoiceModel.issue_date >= start_date_obj)
            
            if end_date:
                end_date_obj = string_to_date(end_date)
                if end_date_obj:
                    query = query.filter(BillingInvoiceModel.issue_date <= end_date_obj)
            
            # Search filter
            if search and search.strip():
                search_term = search.strip()
                query = query.filter(
                    (BillingInvoiceModel.invoice_number.ilike(f"%{search_term}%")) |
                    (PatientModel.firstname.ilike(f"%{search_term}%")) |
                    (PatientModel.lastname.ilike(f"%{search_term}%")) |
                    (BillingInvoiceModel.appointment_id.cast(str).ilike(f"%{search_term}%"))
                )
            
            results = query.order_by(BillingInvoiceModel.id.desc()).all()
            
            # Format for table view
            table_invoices = []
            for inv, patient, doctor in results:
                # Calculate status: if total_amount > 0 and balance_due == 0, then "Paid"
                total_amount = float(inv.total_amount) if inv.total_amount else 0.0
                balance_due = float(inv.outstanding_amount) if inv.outstanding_amount else 0.0
                
                # Auto-calculate status
                calculated_status = inv.status
                if total_amount > 0 and balance_due == 0:
                    calculated_status = "Paid"
                
                # Format invoice date as dd/mm/yy
                invoice_date_formatted = None
                if inv.issue_date:
                    invoice_date_formatted = inv.issue_date.strftime("%d/%m/%y")
                
                # Format amounts with commas
                def format_amount(amount):
                    return f"{amount:,.0f}" if amount == int(amount) else f"{amount:,.2f}"
                
                # Get patient name
                patient_name = f"{patient.firstname} {patient.lastname}".strip() if patient else "Unknown"
                
                # Get doctor name
                doctor_name = f"Dr. {doctor.firstname.title()} {doctor.lastname.title()}".strip() if doctor else "Unknown"
                
                # Table view response ordered as per UI: Invoice No, Patient, Appointment ID, Doctor Name, Invoice Date, Total Amount, Balance Due, Status
                table_invoices.append({
                    "invoice_no": f"#{inv.invoice_number}",  # 1. Invoice No
                    "patient": patient_name,  # 2. Patient
                    "appointment_id": f"#{inv.appointment_id}",  # 3. Appointment ID
                    "doctor_name": doctor_name,  # 4. Doctor Name
                    "invoice_date": invoice_date_formatted,  # 5. Invoice Date (dd/mm/yy)
                    "total_amount": format_amount(total_amount),  # 6. Total Amount (formatted)
                    "balance_due": format_amount(balance_due),  # 7. Balance Due (formatted)
                    "status": calculated_status,  # 8. Status (auto-calculated)
                    # Extra fields kept at the end for edit/delete operations
                    "id": inv.id,
                    "patient_id": inv.patient_id,
                    "appointment_id_raw": inv.appointment_id,
                    "doctor_id": inv.doctor_id,
                    "total_amount_raw": total_amount,
                    "balance_due_raw": balance_due,
                    "status_raw": inv.status,
                    "issue_date": date_to_string(inv.issue_date),
                    "purpose": inv.purpose,
                    "coupon_code": inv.coupon_code,
                    "discount_amount": float(inv.discount_amount) if inv.discount_amount else 0.0,
                    "tax_amount": float(inv.tax_amount) if inv.tax_amount else 0.0,
                    "amount_paid": float(inv.amount_paid) if inv.amount_paid else 0.0,
                    "payment_mode": inv.payment_mode,
                    "gst_percentage": float(inv.gst_percentage) if inv.gst_percentage else 0.0,
                    "adjustments": float(inv.adjustments) if inv.adjustments else 0.0,
                    "visit_charge": float(inv.visit_charge) if inv.visit_charge else 0.0,
                    "medication_charge": float(inv.medication_charge) if inv.medication_charge else 0.0,
                })
            
            total = len(table_invoices)
            total_pages = (total + limit - 1) // limit if total > 0 else 1
            
            # Apply pagination
            paginated_invoices = table_invoices[(page - 1) * limit:page * limit]
            
            return {
                "invoices": paginated_invoices,
                "pagination": {
                    "total": total,
                    "page": page,
                    "limit": limit,
                    "total_pages": total_pages,
                    "has_next": page < total_pages,
                    "has_prev": page > 1
                }
            }
    except Exception as e:
        raise_internal_server_error(f"Error fetching invoices: {e}")

@router.get("/invoices/{invoice_id}")
async def get_invoice(invoice_id: str, current_user: dict = Depends(get_current_active_user)):
    tenant_id_string = settings.TENANT_ID
    
    try:
        invoice_id_int = int(invoice_id)
        with get_db_session() as session:
            invoice = session.query(BillingInvoiceModel).filter(
                and_(
                    BillingInvoiceModel.id == invoice_id_int,
                    BillingInvoiceModel.tenant_id == tenant_id_string
                )
            ).first()
            
            if not invoice:
                raise_not_found_error("Invoice", invoice_id)
            
            invoice_dict = {
                "id": invoice.id,
                "tenant_id": invoice.tenant_id,
                "invoice_number": invoice.invoice_number,
                "patient_id": invoice.patient_id,
                "appointment_id": invoice.appointment_id,
                "doctor_id": invoice.doctor_id,
                "issue_date": invoice.issue_date.isoformat() if invoice.issue_date else None,
                "purpose": invoice.purpose,
                "total_amount": float(invoice.total_amount) if invoice.total_amount else 0.0,
                "tax_amount": float(invoice.tax_amount) if invoice.tax_amount else 0.0,
                "gst_percentage": float(invoice.gst_percentage) if invoice.gst_percentage else 0.0,
                "discount_amount": float(invoice.discount_amount) if invoice.discount_amount else 0.0,
                "coupon_code": invoice.coupon_code,
                "adjustments": float(invoice.adjustments) if invoice.adjustments else 0.0,
                "amount_paid": float(invoice.amount_paid) if invoice.amount_paid else 0.0,
                "payment_mode": invoice.payment_mode,
                "outstanding_amount": float(invoice.outstanding_amount) if invoice.outstanding_amount else 0.0,
                "status": invoice.status,
                "visit_charge": float(invoice.visit_charge) if invoice.visit_charge else 0.0,
                "medication_charge": float(invoice.medication_charge) if invoice.medication_charge else 0.0
            }
            
            # Get items for this invoice
            items = session.query(BillingItemModel).filter(
                BillingItemModel.invoice_id == invoice_id_int
            ).order_by(BillingItemModel.created_at).all()
            
            invoice_dict["items"] = [
                {
                    "id": item.id,
                    "tenant_id": item.tenant_id,
                    "invoice_id": item.invoice_id,
                    "item_type": item.item_type,
                    "description": item.description,
                    "quantity": item.quantity,
                    "unit_price": float(item.unit_price) if item.unit_price else 0.0,
                    "line_total": float(item.line_total) if item.line_total else 0.0,
                    "inventory_item_id": item.inventory_item_id,
                    "created_at": item.created_at.isoformat() if item.created_at else None
                }
                for item in items
            ]
            
            return invoice_dict
    except HTTPException:
        raise
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid invoice ID format")
    except Exception as e:
        raise_internal_server_error(f"Error fetching invoice: {e}")

@router.post("/invoices")
async def create_invoice(invoice_data: BillingInvoiceCreate, current_user: dict = Depends(get_current_active_user)):
    # Use string tenant_id (VARCHAR) instead of UUID
    tenant_id_to_use = invoice_data.tenant_id if invoice_data.tenant_id else settings.TENANT_ID
    
    # Validate foreign keys (these tables use VARCHAR for tenant_id)
    if not check_patient_exists(invoice_data.patient_id, tenant_id_to_use):
        raise HTTPException(status_code=404, detail=f"Patient with ID {invoice_data.patient_id} not found")
    
    if not check_appointment_exists(invoice_data.appointment_id, tenant_id_to_use):
        raise HTTPException(status_code=404, detail=f"Appointment with ID {invoice_data.appointment_id} not found")
    
    if not check_user_exists(invoice_data.doctor_id, tenant_id_to_use):
        raise HTTPException(status_code=404, detail=f"User/Doctor with ID {invoice_data.doctor_id} not found")
    
    issue_date_pg = string_to_date(invoice_data.issue_date) if invoice_data.issue_date else None
    if not issue_date_pg:
        raise HTTPException(status_code=400, detail="Invalid issue_date format. Use dd/mm/yyyy")
    
    try:
        with get_db_session() as session:
            # Check if invoice_number already exists
            existing = session.query(BillingInvoiceModel).filter(
                BillingInvoiceModel.invoice_number == invoice_data.invoice_number
            ).first()
            if existing:
                raise HTTPException(status_code=400, detail="Invoice number already exists")
            
            # Create invoice
            new_invoice = BillingInvoiceModel(
                tenant_id=tenant_id_to_use,
                invoice_number=invoice_data.invoice_number,
                patient_id=invoice_data.patient_id,
                appointment_id=invoice_data.appointment_id,
                doctor_id=invoice_data.doctor_id,
                issue_date=issue_date_pg,
                purpose=invoice_data.purpose,
                total_amount=invoice_data.total_amount,
                tax_amount=invoice_data.tax_amount,
                gst_percentage=invoice_data.gst_percentage,
                discount_amount=invoice_data.discount_amount,
                coupon_code=invoice_data.coupon_code,
                adjustments=invoice_data.adjustments,
                amount_paid=invoice_data.amount_paid,
                payment_mode=invoice_data.payment_mode,
                status=invoice_data.status,
                visit_charge=invoice_data.visit_charge if invoice_data.visit_charge else 0,
                medication_charge=invoice_data.medication_charge if invoice_data.medication_charge else 0
            )
            session.add(new_invoice)
            session.flush()  # Get the invoice ID
            
            # Create billing items
            for item in invoice_data.items:
                inventory_item_id = int(item.inventory_item_id) if item.inventory_item_id else None
                new_item = BillingItemModel(
                    tenant_id=tenant_id_to_use,
                    invoice_id=new_invoice.id,
                    item_type=item.item_type,
                    description=item.description,
                    quantity=item.quantity,
                    unit_price=item.unit_price,
                    line_total=item.line_total,
                    inventory_item_id=inventory_item_id
                )
                session.add(new_item)
            
            session.commit()
            session.refresh(new_invoice)
            
            # Reduce inventory stock if pharmacy bill is paid
            if (invoice_data.status == "paid" or (new_invoice.outstanding_amount and float(new_invoice.outstanding_amount) == 0)):
                # Check if this is a pharmacy bill
                if new_invoice.bill_type == "pharmacy":
                    # Get billing items
                    billing_items = session.query(BillingItemModel).filter(
                        BillingItemModel.invoice_id == new_invoice.id
                    ).all()
                    if billing_items:
                        reduce_inventory_stock(session, billing_items, tenant_id_to_use)
                        session.commit()
                
                # Update appointment status to "Checked Out" if payment is paid
                appointment = session.query(AppointmentsModel).filter(
                    and_(
                        AppointmentsModel.id == invoice_data.appointment_id,
                        AppointmentsModel.tenant_id == tenant_id_to_use
                    )
                ).first()
                if appointment:
                    appointment.status = "Checked Out"
                    session.commit()
            
            return {"message": f"Invoice created successfully", "invoice_id": new_invoice.id}
    except HTTPException:
        raise
    except Exception as e:
        raise_internal_server_error(f"Error creating invoice: {e}")

@router.put("/invoices/{invoice_id}")
async def update_invoice(invoice_id: str, invoice_data: BillingInvoiceUpdate, current_user: dict = Depends(get_current_active_user)):
    tenant_id_string = settings.TENANT_ID
    
    try:
        invoice_id_int = int(invoice_id)
        with get_db_session() as session:
            invoice = session.query(BillingInvoiceModel).filter(
                and_(
                    BillingInvoiceModel.id == invoice_id_int,
                    BillingInvoiceModel.tenant_id == tenant_id_string
                )
            ).first()
            
            if not invoice:
                raise_not_found_error("Invoice", invoice_id)
            
            # Update fields
            if invoice_data.tax_amount is not None:
                invoice.tax_amount = invoice_data.tax_amount
            if invoice_data.gst_percentage is not None:
                invoice.gst_percentage = invoice_data.gst_percentage
            if invoice_data.discount_amount is not None:
                invoice.discount_amount = invoice_data.discount_amount
            if invoice_data.coupon_code is not None:
                invoice.coupon_code = invoice_data.coupon_code
            if invoice_data.adjustments is not None:
                invoice.adjustments = invoice_data.adjustments
            if invoice_data.amount_paid is not None:
                invoice.amount_paid = invoice_data.amount_paid
            if invoice_data.payment_mode is not None:
                invoice.payment_mode = invoice_data.payment_mode
            if invoice_data.status is not None:
                invoice.status = invoice_data.status
            if invoice_data.visit_charge is not None:
                invoice.visit_charge = invoice_data.visit_charge
            if invoice_data.medication_charge is not None:
                invoice.medication_charge = invoice_data.medication_charge
            
            # Check previous status to avoid reducing inventory multiple times
            previous_status = invoice.status
            previous_outstanding = float(invoice.outstanding_amount) if invoice.outstanding_amount else 0.0
            was_paid_before = previous_status == "paid" or previous_outstanding == 0
            
            session.commit()
            session.refresh(invoice)
            
            # Check if status is "paid" or if outstanding_amount is 0 (fully paid)
            outstanding = float(invoice.outstanding_amount) if invoice.outstanding_amount else 0.0
            is_paid = invoice.status == "paid" or outstanding == 0
            
            # Reduce inventory stock if pharmacy bill is newly paid (not already paid)
            if is_paid and not was_paid_before and invoice.bill_type == "pharmacy":
                # Get billing items
                billing_items = session.query(BillingItemModel).filter(
                    BillingItemModel.invoice_id == invoice.id
                ).all()
                if billing_items:
                    reduce_inventory_stock(session, billing_items, tenant_id_string)
                    session.commit()
            
            if is_paid:
                appointment = session.query(AppointmentsModel).filter(
                    and_(
                        AppointmentsModel.id == invoice.appointment_id,
                        AppointmentsModel.tenant_id == tenant_id_string
                    )
                ).first()
                if appointment:
                    appointment.status = "Checked Out"
                    session.commit()
            
            return {"message": f"Invoice with ID {invoice_id} updated successfully"}
    except HTTPException:
        raise
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid invoice ID format")
    except Exception as e:
        raise_internal_server_error(f"Error updating invoice: {e}")

@router.delete("/invoices/{invoice_id}")
async def delete_invoice(invoice_id: str, current_user: dict = Depends(get_current_active_user)):
    tenant_id_string = settings.TENANT_ID
    
    try:
        invoice_id_int = int(invoice_id)
        with get_db_session() as session:
            invoice = session.query(BillingInvoiceModel).filter(
                and_(
                    BillingInvoiceModel.id == invoice_id_int,
                    BillingInvoiceModel.tenant_id == tenant_id_string
                )
            ).first()
            
            if not invoice:
                raise_not_found_error("Invoice", invoice_id)
            
            session.delete(invoice)
            session.commit()
            
            return {"message": f"Invoice with ID {invoice_id} deleted successfully"}
    except HTTPException:
        raise
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid invoice ID format")
    except Exception as e:
        raise_internal_server_error(f"Error deleting invoice: {e}")

@router.get("/items/{item_id}")
async def get_billing_item(item_id: str, current_user: dict = Depends(get_current_active_user)):
    tenant_id_string = settings.TENANT_ID
    
    try:
        item_id_int = int(item_id)
        with get_db_session() as session:
            item = session.query(BillingItemModel).filter(
                and_(
                    BillingItemModel.id == item_id_int,
                    BillingItemModel.tenant_id == tenant_id_string
                )
            ).first()
            
            if not item:
                raise_not_found_error("Billing item", item_id)
            
            return {
                "id": item.id,
                "tenant_id": item.tenant_id,
                "invoice_id": item.invoice_id,
                "item_type": item.item_type,
                "description": item.description,
                "quantity": item.quantity,
                "unit_price": float(item.unit_price) if item.unit_price else 0.0,
                "line_total": float(item.line_total) if item.line_total else 0.0,
                "inventory_item_id": item.inventory_item_id,
                "created_at": item.created_at.isoformat() if item.created_at else None
            }
    except HTTPException:
        raise
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid item ID format")
    except Exception as e:
        raise_internal_server_error(f"Error fetching billing item: {e}")

# Walk-in Pharmacy Bills Routes
@router.get("/pharmacy/walk-in")
async def get_walk_in_bills(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=10),
    status: Optional[str] = None,
    search: Optional[str] = Query(None, description="Search by invoice number or customer name"),
    start_date: Optional[str] = Query(None, description="Start date filter (dd/mm/yyyy)"),
    end_date: Optional[str] = Query(None, description="End date filter (dd/mm/yyyy)"),
    current_user: dict = Depends(get_current_active_user)
):
    """Get walk-in pharmacy bills"""
    tenant_id_string = settings.TENANT_ID
    
    try:
        with get_db_session() as session:
            query = session.query(
                PharmacyWalkInBillModel,
                UserModel
            ).join(
                UserModel, PharmacyWalkInBillModel.created_by == UserModel.id
            ).filter(
                PharmacyWalkInBillModel.tenant_id == tenant_id_string
            )
            
            if status:
                query = query.filter(PharmacyWalkInBillModel.status == status)
            
            # Date range filter
            if start_date:
                start_date_obj = string_to_date(start_date)
                if start_date_obj:
                    query = query.filter(PharmacyWalkInBillModel.issue_date >= start_date_obj)
            
            if end_date:
                end_date_obj = string_to_date(end_date)
                if end_date_obj:
                    query = query.filter(PharmacyWalkInBillModel.issue_date <= end_date_obj)
            
            # Search filter
            if search and search.strip():
                search_term = search.strip()
                query = query.filter(
                    (PharmacyWalkInBillModel.invoice_number.ilike(f"%{search_term}%")) |
                    (PharmacyWalkInBillModel.customer_name.ilike(f"%{search_term}%"))
                )
            
            results = query.order_by(PharmacyWalkInBillModel.id.desc()).all()
            
            # Format for table view
            table_bills = []
            for bill, user in results:
                total_amount = float(bill.total_amount) if bill.total_amount else 0.0
                balance_due = float(bill.outstanding_amount) if bill.outstanding_amount else 0.0
                
                calculated_status = bill.status
                if total_amount > 0 and balance_due == 0:
                    calculated_status = "Paid"
                
                invoice_date_formatted = None
                if bill.issue_date:
                    invoice_date_formatted = bill.issue_date.strftime("%d/%m/%y")
                
                def format_amount(amount):
                    return f"{amount:,.0f}" if amount == int(amount) else f"{amount:,.2f}"
                
                pharmacist_name = f"{user.firstname.title()} {user.lastname.title()}".strip() if user else "Unknown"
                
                table_bills.append({
                    "invoice_no": f"#{bill.invoice_number}",
                    "customer_name": bill.customer_name or "Walk-in Customer",
                    "pharmacist": pharmacist_name,
                    "invoice_date": invoice_date_formatted,
                    "total_amount": format_amount(total_amount),
                    "balance_due": format_amount(balance_due),
                    "status": calculated_status,
                    "id": bill.id,
                    "total_amount_raw": total_amount,
                    "balance_due_raw": balance_due,
                    "status_raw": bill.status,
                    "issue_date": date_to_string(bill.issue_date),
                    "coupon_code": bill.coupon_code,
                    "discount_amount": float(bill.discount_amount) if bill.discount_amount else 0.0,
                    "tax_amount": float(bill.tax_amount) if bill.tax_amount else 0.0,
                    "amount_paid": float(bill.amount_paid) if bill.amount_paid else 0.0,
                    "payment_mode": bill.payment_mode,
                    "gst_percentage": float(bill.gst_percentage) if bill.gst_percentage else 0.0,
                    "adjustments": float(bill.adjustments) if bill.adjustments else 0.0,
                    "created_by": bill.created_by,
                })
            
            total = len(table_bills)
            total_pages = (total + limit - 1) // limit if total > 0 else 1
            
            paginated_bills = table_bills[(page - 1) * limit:page * limit]
            
            return {
                "bills": paginated_bills,
                "pagination": {
                    "total": total,
                    "page": page,
                    "limit": limit,
                    "total_pages": total_pages,
                    "has_next": page < total_pages,
                    "has_prev": page > 1
                }
            }
    except Exception as e:
        raise_internal_server_error(f"Error fetching walk-in bills: {e}")

@router.get("/pharmacy/walk-in/{bill_id}")
async def get_walk_in_bill(bill_id: str, current_user: dict = Depends(get_current_active_user)):
    """Get a specific walk-in pharmacy bill"""
    tenant_id_string = settings.TENANT_ID
    
    try:
        bill_id_int = int(bill_id)
        with get_db_session() as session:
            bill = session.query(PharmacyWalkInBillModel).filter(
                and_(
                    PharmacyWalkInBillModel.id == bill_id_int,
                    PharmacyWalkInBillModel.tenant_id == tenant_id_string
                )
            ).first()
            
            if not bill:
                raise_not_found_error("Walk-in bill", bill_id)
            
            bill_dict = {
                "id": bill.id,
                "tenant_id": bill.tenant_id,
                "invoice_number": bill.invoice_number,
                "customer_name": bill.customer_name,
                "created_by": bill.created_by,
                "issue_date": bill.issue_date.isoformat() if bill.issue_date else None,
                "total_amount": float(bill.total_amount) if bill.total_amount else 0.0,
                "tax_amount": float(bill.tax_amount) if bill.tax_amount else 0.0,
                "gst_percentage": float(bill.gst_percentage) if bill.gst_percentage else 0.0,
                "discount_amount": float(bill.discount_amount) if bill.discount_amount else 0.0,
                "coupon_code": bill.coupon_code,
                "adjustments": float(bill.adjustments) if bill.adjustments else 0.0,
                "amount_paid": float(bill.amount_paid) if bill.amount_paid else 0.0,
                "payment_mode": bill.payment_mode,
                "outstanding_amount": float(bill.outstanding_amount) if bill.outstanding_amount else 0.0,
                "status": bill.status,
                "created_at": bill.created_at.isoformat() if bill.created_at else None,
                "updated_at": bill.updated_at.isoformat() if bill.updated_at else None
            }
            
            # Get items for this bill
            items = session.query(PharmacyWalkInItemModel).filter(
                PharmacyWalkInItemModel.bill_id == bill_id_int
            ).order_by(PharmacyWalkInItemModel.created_at).all()
            
            bill_dict["items"] = [
                {
                    "id": item.id,
                    "tenant_id": item.tenant_id,
                    "bill_id": item.bill_id,
                    "item_type": item.item_type,
                    "description": item.description,
                    "quantity": item.quantity,
                    "unit_price": float(item.unit_price) if item.unit_price else 0.0,
                    "line_total": float(item.line_total) if item.line_total else 0.0,
                    "inventory_item_id": item.inventory_item_id,
                    "expiry_date": item.expiry_date.isoformat() if item.expiry_date else None,
                    "created_at": item.created_at.isoformat() if item.created_at else None
                }
                for item in items
            ]
            
            return bill_dict
    except HTTPException:
        raise
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid bill ID format")
    except Exception as e:
        raise_internal_server_error(f"Error fetching walk-in bill: {e}")

@router.post("/pharmacy/walk-in")
async def create_walk_in_bill(bill_data: PharmacyWalkInBillCreate, current_user: dict = Depends(get_current_active_user)):
    """Create a walk-in pharmacy bill"""
    tenant_id_to_use = bill_data.tenant_id if bill_data.tenant_id else settings.TENANT_ID
    
    # Validate created_by user exists
    if not check_user_exists(current_user.get("id"), tenant_id_to_use):
        raise HTTPException(status_code=404, detail="User not found")
    
    issue_date_pg = string_to_date(bill_data.issue_date) if bill_data.issue_date else None
    if not issue_date_pg:
        raise HTTPException(status_code=400, detail="Invalid issue_date format. Use dd/mm/yyyy")
    
    try:
        with get_db_session() as session:
            # Check if invoice_number already exists
            existing = session.query(PharmacyWalkInBillModel).filter(
                PharmacyWalkInBillModel.invoice_number == bill_data.invoice_number
            ).first()
            if existing:
                raise HTTPException(status_code=400, detail="Invoice number already exists")
            
            # Create bill
            new_bill = PharmacyWalkInBillModel(
                tenant_id=tenant_id_to_use,
                invoice_number=bill_data.invoice_number,
                customer_name=bill_data.customer_name,
                created_by=current_user.get("id"),
                issue_date=issue_date_pg,
                total_amount=bill_data.total_amount,
                tax_amount=bill_data.tax_amount,
                gst_percentage=bill_data.gst_percentage,
                discount_amount=bill_data.discount_amount,
                coupon_code=bill_data.coupon_code,
                adjustments=bill_data.adjustments,
                amount_paid=bill_data.amount_paid,
                payment_mode=bill_data.payment_mode,
                status=bill_data.status
            )
            session.add(new_bill)
            session.flush()  # Get the bill ID
            
            # Create bill items
            from app.core.models import InventoryItemModel
            for item in bill_data.items:
                inventory_item_id = int(item.inventory_item_id) if item.inventory_item_id else None
                expiry_date = None
                
                # Get expiry date from inventory if available
                if inventory_item_id:
                    inventory_item = session.query(InventoryItemModel).filter(
                        InventoryItemModel.id == inventory_item_id
                    ).first()
                    if inventory_item and inventory_item.expiry_date:
                        expiry_date = inventory_item.expiry_date
                
                new_item = PharmacyWalkInItemModel(
                    tenant_id=tenant_id_to_use,
                    bill_id=new_bill.id,
                    item_type=item.item_type,
                    description=item.description,
                    quantity=item.quantity,
                    unit_price=item.unit_price,
                    line_total=item.line_total,
                    inventory_item_id=inventory_item_id,
                    expiry_date=expiry_date
                )
                session.add(new_item)
            
            session.commit()
            session.refresh(new_bill)
            
            # Reduce inventory stock if bill is paid
            if bill_data.status == "paid" or (new_bill.outstanding_amount and float(new_bill.outstanding_amount) == 0):
                bill_items = session.query(PharmacyWalkInItemModel).filter(
                    PharmacyWalkInItemModel.bill_id == new_bill.id
                ).all()
                if bill_items:
                    reduce_inventory_stock(session, bill_items, tenant_id_to_use)
                    session.commit()
            
            return {"message": f"Walk-in bill created successfully", "bill_id": new_bill.id}
    except HTTPException:
        raise
    except Exception as e:
        raise_internal_server_error(f"Error creating walk-in bill: {e}")

@router.put("/pharmacy/walk-in/{bill_id}")
async def update_walk_in_bill(bill_id: str, bill_data: PharmacyWalkInBillUpdate, current_user: dict = Depends(get_current_active_user)):
    """Update a walk-in pharmacy bill"""
    tenant_id_string = settings.TENANT_ID
    
    try:
        bill_id_int = int(bill_id)
        with get_db_session() as session:
            bill = session.query(PharmacyWalkInBillModel).filter(
                and_(
                    PharmacyWalkInBillModel.id == bill_id_int,
                    PharmacyWalkInBillModel.tenant_id == tenant_id_string
                )
            ).first()
            
            if not bill:
                raise_not_found_error("Walk-in bill", bill_id)
            
            # Check previous status to avoid reducing inventory multiple times
            previous_status = bill.status
            previous_outstanding = float(bill.outstanding_amount) if bill.outstanding_amount else 0.0
            was_paid_before = previous_status == "paid" or previous_outstanding == 0
            
            # Update fields
            if bill_data.tax_amount is not None:
                bill.tax_amount = bill_data.tax_amount
            if bill_data.gst_percentage is not None:
                bill.gst_percentage = bill_data.gst_percentage
            if bill_data.discount_amount is not None:
                bill.discount_amount = bill_data.discount_amount
            if bill_data.coupon_code is not None:
                bill.coupon_code = bill_data.coupon_code
            if bill_data.adjustments is not None:
                bill.adjustments = bill_data.adjustments
            if bill_data.amount_paid is not None:
                bill.amount_paid = bill_data.amount_paid
            if bill_data.payment_mode is not None:
                bill.payment_mode = bill_data.payment_mode
            if bill_data.status is not None:
                bill.status = bill_data.status
            
            session.commit()
            session.refresh(bill)
            
            # Check if status is "paid" or if outstanding_amount is 0 (fully paid)
            outstanding = float(bill.outstanding_amount) if bill.outstanding_amount else 0.0
            is_paid = bill.status == "paid" or outstanding == 0
            
            # Reduce inventory stock if bill is newly paid (not already paid)
            if is_paid and not was_paid_before:
                bill_items = session.query(PharmacyWalkInItemModel).filter(
                    PharmacyWalkInItemModel.bill_id == bill.id
                ).all()
                if bill_items:
                    reduce_inventory_stock(session, bill_items, tenant_id_string)
                    session.commit()
            
            return {"message": f"Walk-in bill with ID {bill_id} updated successfully"}
    except HTTPException:
        raise
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid bill ID format")
    except Exception as e:
        raise_internal_server_error(f"Error updating walk-in bill: {e}")

@router.delete("/pharmacy/walk-in/{bill_id}")
async def delete_walk_in_bill(bill_id: str, current_user: dict = Depends(get_current_active_user)):
    """Delete a walk-in pharmacy bill"""
    tenant_id_string = settings.TENANT_ID
    
    try:
        bill_id_int = int(bill_id)
        with get_db_session() as session:
            bill = session.query(PharmacyWalkInBillModel).filter(
                and_(
                    PharmacyWalkInBillModel.id == bill_id_int,
                    PharmacyWalkInBillModel.tenant_id == tenant_id_string
                )
            ).first()
            
            if not bill:
                raise_not_found_error("Walk-in bill", bill_id)
            
            session.delete(bill)
            session.commit()
            
            return {"message": f"Walk-in bill with ID {bill_id} deleted successfully"}
    except HTTPException:
        raise
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid bill ID format")
    except Exception as e:
        raise_internal_server_error(f"Error deleting walk-in bill: {e}")
