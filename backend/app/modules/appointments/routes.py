from fastapi import APIRouter, HTTPException, Query, Depends
from typing import Optional, Literal, Any, Union
from datetime import date, time
from app.modules.appointments.schemas import (
    AppointmentCreate, AppointmentUpdate, parse_time_string,
    PrescriptionCreate, PrescriptionUpdate, PrescriptionResponse, PrescriptionItemResponse,
    BillPaymentCreate
)
from app.common.utils import raise_not_found_error, raise_bad_request_error, raise_internal_server_error
from app.core.db_helper import check_exists, get_by_id
from app.core.date_helpers import date_to_string, string_to_date
from app.core.db_utils import get_db_session
from app.modules.patients.models import PatientModel
from app.modules.appointments.models import AppointmentsModel, PrescriptionModel, PrescriptionItemModel
from app.modules.users.models import UserModel
from app.modules.billing.models import BillingInvoiceModel, BillingItemModel
from sqlalchemy import and_, case
from app.core.config import settings
from app.core.dependencies import get_current_active_user

router = APIRouter()

def get_tenant_id() -> str:
    """Get tenant ID from settings"""
    return settings.TENANT_ID

# Endpoints for booking appointment flow
@router.get("/patients/list")
async def get_patients_for_booking(
    search: Optional[str] = Query(None, description="Search patient by name"),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=10),  # Max 10 per page as per requirements
    current_user: dict = Depends(get_current_active_user)
):
    """Get list of patients (names only) for booking appointment selection"""
    tenant_id = get_tenant_id()
    
    try:
        with get_db_session() as session:
            query = session.query(PatientModel).filter(PatientModel.tenant_id == tenant_id)
            
            if search and search.strip():
                search_term = search.strip().lower()
                query = query.filter(
                    (PatientModel.firstname.ilike(f"%{search_term}%")) |
                    (PatientModel.lastname.ilike(f"%{search_term}%"))
                )
            
            # Get total count for pagination
            total = query.count()
            
            # Apply pagination
            patients = query.order_by(PatientModel.firstname, PatientModel.lastname).offset((page - 1) * limit).limit(limit).all()
            patients_list = [
                {
                    "id": p.id,
                    "name": f"{p.firstname} {p.lastname}".strip(),
                    "firstname": p.firstname,
                    "lastname": p.lastname
                }
                for p in patients
            ]
            
            total_pages = (total + limit - 1) // limit if total > 0 else 1
            
            return {
                "patients": patients_list,
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
        raise_internal_server_error(f"Error fetching patients: {e}")

@router.get("/patients/{patient_id}/details")
async def get_patient_details_for_booking(
    patient_id: int,
    current_user: dict = Depends(get_current_active_user)
):
    """Get patient details (name, number, email) when patient is selected for booking"""
    tenant_id = get_tenant_id()
    
    try:
        with get_db_session() as session:
            patient = session.query(PatientModel).filter(
                and_(PatientModel.id == patient_id, PatientModel.tenant_id == tenant_id)
            ).first()
            
            if not patient:
                raise_not_found_error("Patient", patient_id)
            
            return {
                "id": patient.id,
                "name": f"{patient.firstname} {patient.lastname}".strip(),
                "firstname": patient.firstname,
                "lastname": patient.lastname,
                "number": patient.phone,
                "email": patient.email
            }
    except HTTPException:
        raise
    except Exception as e:
        raise_internal_server_error(f"Error fetching patient details: {e}")

def format_time_for_table(appointment_date, appointment_time) -> Optional[str]:
    """Format date and time as '01 Feb 2025 - 04:00 PM'"""
    if not appointment_date:
        return None
    
    # Convert date to date object if string
    if isinstance(appointment_date, str):
        from app.core.date_helpers import string_to_date
        date_obj = string_to_date(appointment_date)
    else:
        date_obj = appointment_date
    
    if not date_obj:
        return None
    
    # Format date as "01 Feb 2025"
    date_str = date_obj.strftime("%d %b %Y")
    
    # Format time if available
    if appointment_time:
        if isinstance(appointment_time, str):
            # Parse time string (HH:MM format)
            try:
                hour, minute = map(int, appointment_time.split(':'))
                from datetime import time as time_class
                time_obj = time_class(hour, minute)
            except (ValueError, AttributeError):
                return date_str
        else:
            time_obj = appointment_time
        
        # Format as 12-hour with AM/PM
        hour_12 = time_obj.hour % 12
        if hour_12 == 0:
            hour_12 = 12
        am_pm = "AM" if time_obj.hour < 12 else "PM"
        time_str = f"{hour_12:02d}:{time_obj.minute:02d} {am_pm}"
        return f"{date_str} - {time_str}"
    
    return date_str

def appointment_to_dict(appointment_data: Any, patient=None, doctor=None) -> dict:
    """Convert appointment object to dictionary, handling DATE to string conversion and joins"""
    # Handle dict input
    if isinstance(appointment_data, dict):
        result = appointment_data.copy()
        if "appointment_date" in result and result["appointment_date"] and not isinstance(result["appointment_date"], str):
            result["appointment_date"] = date_to_string(result["appointment_date"])
        if "follow_up_date" in result and result["follow_up_date"] and not isinstance(result["follow_up_date"], str):
            result["follow_up_date"] = date_to_string(result["follow_up_date"])
        if "appointment_time" in result and result["appointment_time"] and not isinstance(result["appointment_time"], str):
            result["appointment_time"] = str(result["appointment_time"]) if result["appointment_time"] else None
        
        # Add formatted appointment_time (date + time combined)
        result["appointment_time"] = format_time_for_table(result.get("appointment_date"), result.get("appointment_time"))
        
        # Add patient info if available
        if patient:
            result["patient"] = f"{patient.get('firstname', '')} {patient.get('lastname', '')}".strip()
            result["number"] = patient.get('phone', '')
        if doctor:
            result["doctor_name"] = f"Dr. {doctor.get('firstname', '').title()} {doctor.get('lastname', '').title()}".strip()
        
        return result
    
    # Convert from model object
    appt_date_str = date_to_string(appointment_data.appointment_date) if hasattr(appointment_data, 'appointment_date') and appointment_data.appointment_date else None
    follow_up_str = date_to_string(appointment_data.follow_up_date) if hasattr(appointment_data, 'follow_up_date') and appointment_data.follow_up_date else None
    
    # Get patient name and phone
    patient_name = None
    patient_phone = None
    if hasattr(appointment_data, 'patient') and appointment_data.patient:
        patient_name = f"{appointment_data.patient.firstname} {appointment_data.patient.lastname}".strip()
        patient_phone = appointment_data.patient.phone
    elif patient:
        patient_name = f"{patient.get('firstname', '')} {patient.get('lastname', '')}".strip()
        patient_phone = patient.get('phone', '')
    
    # Get doctor name
    doctor_name = None
    if hasattr(appointment_data, 'doctor') and appointment_data.doctor:
        doctor_name = f"Dr. {appointment_data.doctor.firstname.title()} {appointment_data.doctor.lastname.title()}".strip()
    elif hasattr(appointment_data, 'doctor_name') and appointment_data.doctor_name:
        doctor_name = appointment_data.doctor_name
    elif doctor:
        doctor_name = f"Dr. {doctor.get('firstname', '').title()} {doctor.get('lastname', '').title()}".strip()
    
    # Format appointment_time as date + time combined for display
    formatted_appointment_time = format_time_for_table(appointment_data.appointment_date, appointment_data.appointment_time)
    
    return {
        "id": appointment_data.id,
        "tenant_id": appointment_data.tenant_id,
        "patient": patient_name,
        "number": patient_phone,
        "appointment_date": appt_date_str or (appointment_data.appointment_date if hasattr(appointment_data, 'appointment_date') else None),
        "appointment_time": formatted_appointment_time,  # Formatted date + time for table view
        "status": getattr(appointment_data, 'status', None) or (getattr(appointment_data, 'appointment_status', None) if hasattr(appointment_data, 'appointment_status') else "In Progress"),
        "doctor_name": doctor_name,
        "purpose": getattr(appointment_data, 'purpose', None) or (getattr(appointment_data, 'appointment_type', None) if hasattr(appointment_data, 'appointment_type') else None),
        "interval": getattr(appointment_data, 'interval', None) or getattr(appointment_data, 'duration', None),
        "payment": getattr(appointment_data, 'payment', None) or ("Pending" if getattr(appointment_data, 'payment_pending', False) else "Paid"),
        "follow_up_date": follow_up_str or (appointment_data.follow_up_date if hasattr(appointment_data, 'follow_up_date') else None)
    }

def check_patient_exists(patient_id: int, tenant_id: str) -> bool:
    """Check if patient exists using database helper"""
    return check_exists(PatientModel, "patients_table", "id", patient_id, tenant_id)

def check_appointment_exists(appointment_id: int, tenant_id: str) -> bool:
    """Check if appointment exists using database helper"""
    return check_exists(AppointmentsModel, "appointments", "id", appointment_id, tenant_id)

def get_appointment_by_id(appointment_id: int, tenant_id: str) -> Union[dict, Any, None]:
    """Get appointment by ID using database helper"""
    columns = ["id", "patient_id", "doctor_id", "tenant_id", "appointment_date", "appointment_time", "status",
              "doctor_name", "purpose", "payment", "interval", "follow_up_date"]
    result = get_by_id(AppointmentsModel, "appointments", "id", appointment_id, tenant_id, columns)
    # If result is a model object, convert it
    if result and not isinstance(result, dict):
        return appointment_to_dict(result)
    return result

# Use create_error_response from utils instead

def get_today_date() -> str:
    """Get today's date in dd/mm/yyyy format"""
    today = date.today()
    return today.strftime("%d/%m/%Y")

def get_tomorrow_date() -> str:
    """Get tomorrow's date in dd/mm/yyyy format"""
    from datetime import timedelta
    tomorrow = date.today() + timedelta(days=1)
    return tomorrow.strftime("%d/%m/%Y")

@router.get("/")
async def get_appointments(
    today: Optional[bool] = Query(True, description="Filter appointments for today (default: True)"),
    status: Optional[Literal["In Progress", "Checked In", "No Show", "Checked Out", "Reschedule", "Scheduled", "Cancelled"]] = Query(None, description="Filter by appointment status"),
    doctor_id: Optional[int] = Query(None, description="Filter by doctor ID"),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=10),  # Max 10 per page as per requirements
    current_user: dict = Depends(get_current_active_user)
):
    """Get appointments for table view - defaults to today's appointments, max 10 per page"""
    tenant_id = get_tenant_id()
    
    appointments_list = []
    try:
        with get_db_session() as session:
            # Join with patient and users tables
            query = session.query(
                AppointmentsModel,
                PatientModel,
                UserModel
            ).join(
                PatientModel, AppointmentsModel.patient_id == PatientModel.id
            ).join(
                UserModel, AppointmentsModel.doctor_id == UserModel.id
            ).filter(
                AppointmentsModel.tenant_id == tenant_id
            )
            
            # Default to today's appointments
            if today:
                today_date_obj = date.today()
                query = query.filter(AppointmentsModel.appointment_date == today_date_obj)
            
            if status:
                query = query.filter(AppointmentsModel.status == status)
            
            if doctor_id:
                query = query.filter(AppointmentsModel.doctor_id == doctor_id)
            
            # Custom sorting: In Progress (1) > Checked In (2) > Checked Out (3) > Others (4)
            # Within Checked Out, sort by date/time ascending (older first, so checked_out patient 1 appears above checked_out patient 2)
            # Within other groups, sort by date/time ascending
            status_priority = case(
                (AppointmentsModel.status == "In Progress", 1),
                (AppointmentsModel.status == "Checked In", 2),
                (AppointmentsModel.status == "Checked Out", 3),
                else_=4
            )
            
            # Order by priority first, then by date/time (ascending for all groups)
            query = query.order_by(
                status_priority,
                AppointmentsModel.appointment_date.asc(),
                AppointmentsModel.appointment_time.asc()
            )
            
            # Get all results first for pagination
            results = query.all()
            
            # Convert to dict with patient and doctor info
            for apt, patient, doctor in results:
                patient_dict = {
                    "firstname": patient.firstname,
                    "lastname": patient.lastname,
                    "phone": patient.phone
                }
                doctor_dict = {
                    "firstname": doctor.firstname,
                    "lastname": doctor.lastname
                }
                appointments_list.append(appointment_to_dict(apt, patient=patient_dict, doctor=doctor_dict))
            
    except Exception as e:
        raise_internal_server_error(f"Error fetching appointments: {e}")
    
    # Format for table view: Patient, Purpose, appointment_time, Status, Number, Doctor Name, Payment, Action
    table_appointments = []
    for apt in appointments_list:
        table_appointments.append({
            "id": apt.get("id"),
            "patient": apt.get("patient", ""),  # Patient name
            "purpose": apt.get("purpose", ""),  # Purpose
            "appointment_time": apt.get("appointment_time", ""),  # Formatted date + time (e.g., "01 Feb 2025 - 04:00 PM")
            "status": apt.get("status", ""),  # Status
            "number": apt.get("number", ""),  # Patient phone number
            "doctor_name": apt.get("doctor_name", ""),  # Doctor name
            "payment": apt.get("payment", "Pending"),  # Payment status
            # Extra fields kept at the end
            "appointment_date": apt.get("appointment_date"),
            "interval": apt.get("interval", ""),
            "follow_up_date": apt.get("follow_up_date")
        })
    
    # Calculate pagination
    total = len(table_appointments)
    total_pages = (total + limit - 1) // limit if total > 0 else 1
    
    # Apply pagination
    paginated_appointments = table_appointments[(page - 1) * limit:page * limit]
    
    return {
        "appointments": paginated_appointments,
        "pagination": {
            "total": total, "page": page, "limit": limit, "total_pages": total_pages,
            "has_next": page < total_pages, "has_prev": page > 1
        }
    }

@router.get("/queue")
async def get_queue(current_user: dict = Depends(get_current_active_user)):
    """Get queue management - Active appointments for today, sorted by time"""
    tenant_id = get_tenant_id()
    today_date_obj = date.today()
    
    appointments_list = []
    try:
        with get_db_session() as session:
            appointments = session.query(AppointmentsModel).filter(
                and_(
                    AppointmentsModel.tenant_id == tenant_id,
                    AppointmentsModel.appointment_date == today_date_obj,
                    AppointmentsModel.status == "In Progress"
                )
            ).order_by(AppointmentsModel.appointment_time.asc()).all()
            appointments_list = [appointment_to_dict(apt) for apt in appointments]
    except Exception as e:
        raise_internal_server_error(f"Error fetching appointment queue: {e}")
    
    return {"queue": appointments_list, "date": get_today_date(), "total": len(appointments_list)}

@router.post("/")
async def create_appointment(appointment: AppointmentCreate, current_user: dict = Depends(get_current_active_user)):
    """Create a new appointment"""
    tenant_id = get_tenant_id()
    
    # Check if patient exists
    if not check_patient_exists(appointment.patient_id, tenant_id):
        raise_not_found_error("Patient", appointment.patient_id)
    
    # Check if doctor/user exists
    from app.modules.users.routes import check_user_exists, get_user_by_id
    if not check_user_exists(appointment.doctor_id, tenant_id):
        raise_not_found_error("Doctor/User", appointment.doctor_id)
    
    # Get doctor name from users table
    doctor_data = get_user_by_id(appointment.doctor_id, tenant_id)
    doctor_name = None
    if doctor_data:
        if isinstance(doctor_data, dict):
            doctor_name = f"Dr. {doctor_data.get('firstname', '').title()} {doctor_data.get('lastname', '').title()}".strip()
        else:
            doctor_name = f"Dr. {doctor_data.firstname.title()} {doctor_data.lastname.title()}".strip()
    
    # Convert date string to date object - required field
    from app.core.date_helpers import string_to_date
    appointment_date_obj = string_to_date(appointment.appointment_date)
    if not appointment_date_obj:
        raise_bad_request_error("Invalid appointment date format")
    
    # Validate date is not in past
    if appointment_date_obj < date.today():
        raise_bad_request_error("Appointment date cannot be in the past")
    
    # Convert time string to time object - required field
    try:
        hour, minute = parse_time_string(appointment.appointment_time)
        appointment_time_obj = time(hour, minute)
    except (ValueError, AttributeError) as e:
        raise_bad_request_error(f"Invalid appointment time format: {str(e)}")
    
    # Create using SQLAlchemy ORM with transaction
    try:
        with get_db_session() as session:
            new_appointment = AppointmentsModel(
                patient_id=appointment.patient_id,
                doctor_id=appointment.doctor_id,
                tenant_id=tenant_id,
                appointment_date=appointment_date_obj,
                appointment_time=appointment_time_obj,
                status=appointment.status,
                doctor_name=doctor_name,
                purpose=appointment.purpose,
                interval=appointment.interval,
                payment=appointment.payment or "Pending",  # Default to Pending
                follow_up_date=string_to_date(appointment.follow_up_date) if appointment.follow_up_date else None,
            )
            session.add(new_appointment)
            session.commit()
            session.refresh(new_appointment)
            return {
                "message": "Appointment booked successfully",
                "database": "PostgreSQL", 
                "appointment": appointment_to_dict(new_appointment)
            }
    except Exception as e:
        raise_internal_server_error(f"Error creating appointment: {e}")

@router.get("/{appointment_id}")
async def get_appointment(appointment_id: int, current_user: dict = Depends(get_current_active_user)):
    """Get a single appointment by ID"""
    tenant_id = get_tenant_id()
    appointment_data = get_appointment_by_id(appointment_id, tenant_id)
    if appointment_data:
        if isinstance(appointment_data, dict):
            return {"database": "PostgreSQL", "appointment": appointment_data}
        return {"database": "PostgreSQL", "appointment": appointment_to_dict(appointment_data)}
    raise_not_found_error("Appointment", appointment_id)

@router.put("/{appointment_id}")
async def update_appointment(appointment_id: int, appointment: AppointmentUpdate, current_user: dict = Depends(get_current_active_user)):
    """Update an appointment"""
    tenant_id = get_tenant_id()
    
    if not check_appointment_exists(appointment_id, tenant_id):
        raise_not_found_error("Appointment", appointment_id)
    
    update_data = appointment.model_dump(exclude_unset=True)
    if not update_data:
        raise_bad_request_error("No fields to update")
    
    # Convert date string to date object if provided
    from app.core.date_helpers import string_to_date
    if "appointment_date" in update_data:
        date_obj = string_to_date(update_data["appointment_date"])
        if not date_obj:
            raise_bad_request_error("Invalid appointment date format")
        update_data["appointment_date"] = date_obj
    
    # Convert time string to time object if provided - handle formats like "2.00 pm" or "9.00 am"
    if "appointment_time" in update_data and update_data["appointment_time"]:
        try:
            hour, minute = parse_time_string(update_data["appointment_time"])
            update_data["appointment_time"] = time(hour, minute)
        except (ValueError, AttributeError) as e:
            raise_bad_request_error(f"Invalid appointment time format: {str(e)}")
    
    # Update doctor_name if doctor_id is updated
    if "doctor_id" in update_data:
        from app.modules.users.routes import get_user_by_id
        doctor_data = get_user_by_id(update_data["doctor_id"], tenant_id)
        if doctor_data:
            if isinstance(doctor_data, dict):
                update_data["doctor_name"] = f"Dr. {doctor_data.get('firstname', '').title()} {doctor_data.get('lastname', '').title()}".strip()
            else:
                update_data["doctor_name"] = f"Dr. {doctor_data.firstname.title()} {doctor_data.lastname.title()}".strip()
    
    # Convert follow_up_date if provided
    if "follow_up_date" in update_data and update_data["follow_up_date"]:
        follow_up_date_obj = string_to_date(update_data["follow_up_date"])
        update_data["follow_up_date"] = follow_up_date_obj
    
    # Update using SQLAlchemy ORM with transaction
    try:
        with get_db_session() as session:
            appointment_obj = session.query(AppointmentsModel).filter(
                and_(AppointmentsModel.id == appointment_id, AppointmentsModel.tenant_id == tenant_id)
            ).first()
            if not appointment_obj:
                raise_not_found_error("Appointment", appointment_id)
            
            # Update fields
            for key, value in update_data.items():
                if hasattr(appointment_obj, key):
                    setattr(appointment_obj, key, value)
            
            session.commit()
            session.refresh(appointment_obj)
            return {"database": "PostgreSQL", "appointment": appointment_to_dict(appointment_obj)}
    except HTTPException:
        raise
    except Exception as e:
        raise_internal_server_error(f"Error updating appointment: {e}")

@router.delete("/{appointment_id}")
async def delete_appointment(appointment_id: int, current_user: dict = Depends(get_current_active_user)):
    """Delete an appointment"""
    tenant_id = get_tenant_id()
    
    if not check_appointment_exists(appointment_id, tenant_id):
        raise_not_found_error("Appointment", appointment_id)
    
    # Delete using SQLAlchemy ORM with transaction
    try:
        with get_db_session() as session:
            appointment = session.query(AppointmentsModel).filter(
                and_(AppointmentsModel.id == appointment_id, AppointmentsModel.tenant_id == tenant_id)
            ).first()
            if not appointment:
                raise_not_found_error("Appointment", appointment_id)
            
            session.delete(appointment)
            session.commit()
            return {"message": f"Appointment with ID {appointment_id} deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise_internal_server_error(f"Error deleting appointment: {e}")

@router.post("/{appointment_id}/complete")
async def complete_appointment(appointment_id: int, current_user: dict = Depends(get_current_active_user)):
    """Mark an appointment as completed"""
    tenant_id = get_tenant_id()
    
    appointment_data = get_appointment_by_id(appointment_id, tenant_id)
    if not appointment_data:
        raise_not_found_error("Appointment", appointment_id)
    
    # Update appointment status using ORM with transaction
    try:
        with get_db_session() as session:
            appointment = session.query(AppointmentsModel).filter(
                and_(AppointmentsModel.id == appointment_id, AppointmentsModel.tenant_id == tenant_id)
            ).first()
            if not appointment:
                raise_not_found_error("Appointment", appointment_id)
            
            appointment.status = "Checked Out"
            from datetime import datetime
            appointment.updated_at = datetime.now()
            
            session.commit()
            session.refresh(appointment)
            return {"database": "PostgreSQL", "appointment": appointment_to_dict(appointment), "message": "Appointment marked as completed"}
    except HTTPException:
        raise
    except Exception as e:
        raise_internal_server_error(f"Error completing appointment: {e}")

# Prescription Endpoints
@router.get("/{appointment_id}/prescription")
async def get_prescription(
    appointment_id: int,
    current_user: dict = Depends(get_current_active_user)
):
    """Get prescription for an appointment"""
    tenant_id = get_tenant_id()
    
    # Check if appointment exists
    if not check_appointment_exists(appointment_id, tenant_id):
        raise_not_found_error("Appointment", appointment_id)
    
    try:
        with get_db_session() as session:
            prescription = session.query(PrescriptionModel).filter(
                and_(PrescriptionModel.appointment_id == appointment_id, PrescriptionModel.tenant_id == tenant_id)
            ).first()
            
            if not prescription:
                return {"prescription": None, "message": "No prescription found for this appointment"}
            
            # Get prescription items
            items = session.query(PrescriptionItemModel).filter(
                PrescriptionItemModel.prescription_id == prescription.id
            ).all()
            
            items_list = [
                PrescriptionItemResponse(
                    id=item.id,
                    item_type=item.item_type,
                    source=item.source,
                    item_name=item.item_name,
                    quantity=item.quantity,
                    inventory_item_id=item.inventory_item_id
                )
                for item in items
            ]
            
            return {
                "prescription": PrescriptionResponse(
                    id=prescription.id,
                    appointment_id=prescription.appointment_id,
                    bill_date=date_to_string(prescription.bill_date),
                    description=prescription.description,
                    items=items_list,
                    created_at=prescription.created_at.isoformat() if prescription.created_at else None
                )
            }
    except Exception as e:
        raise_internal_server_error(f"Error fetching prescription: {e}")

@router.post("/{appointment_id}/prescription")
async def create_prescription(
    appointment_id: int,
    prescription: PrescriptionCreate,
    current_user: dict = Depends(get_current_active_user)
):
    """Create a new prescription for an appointment"""
    tenant_id = get_tenant_id()
    
    # Validate appointment_id matches
    if prescription.appointment_id != appointment_id:
        raise_bad_request_error("Appointment ID in URL must match appointment_id in request body")
    
    # Check if appointment exists
    if not check_appointment_exists(appointment_id, tenant_id):
        raise_not_found_error("Appointment", appointment_id)
    
    # Check if prescription already exists
    try:
        with get_db_session() as session:
            existing = session.query(PrescriptionModel).filter(
                and_(PrescriptionModel.appointment_id == appointment_id, PrescriptionModel.tenant_id == tenant_id)
            ).first()
            if existing:
                raise_bad_request_error("Prescription already exists for this appointment. Use PUT to update.")
            
            # Set bill_date to today if not provided
            bill_date_obj = string_to_date(prescription.bill_date) if prescription.bill_date else date.today()
            if not bill_date_obj:
                raise_bad_request_error("Invalid bill_date format. Use dd/mm/yyyy")
            
            # Create prescription
            new_prescription = PrescriptionModel(
                tenant_id=tenant_id,
                appointment_id=appointment_id,
                bill_date=bill_date_obj,
                description=prescription.description
            )
            session.add(new_prescription)
            session.flush()  # Get prescription ID
            
            # Create prescription items
            for item in prescription.items:
                new_item = PrescriptionItemModel(
                    tenant_id=tenant_id,
                    prescription_id=new_prescription.id,
                    item_type=item.item_type,
                    source=item.source,
                    item_name=item.item_name,
                    quantity=item.quantity,
                    inventory_item_id=item.inventory_item_id if item.source == "Inventory" else None
                )
                session.add(new_item)
            
            session.commit()
            session.refresh(new_prescription)
            
            # Return prescription with items
            items = session.query(PrescriptionItemModel).filter(
                PrescriptionItemModel.prescription_id == new_prescription.id
            ).all()
            
            items_list = [
                PrescriptionItemResponse(
                    id=item.id,
                    item_type=item.item_type,
                    source=item.source,
                    item_name=item.item_name,
                    quantity=item.quantity,
                    inventory_item_id=item.inventory_item_id
                )
                for item in items
            ]
            
            return {
                "message": "Prescription created successfully",
                "prescription": PrescriptionResponse(
                    id=new_prescription.id,
                    appointment_id=new_prescription.appointment_id,
                    bill_date=date_to_string(new_prescription.bill_date),
                    description=new_prescription.description,
                    items=items_list,
                    created_at=new_prescription.created_at.isoformat() if new_prescription.created_at else None
                )
            }
    except HTTPException:
        raise
    except Exception as e:
        raise_internal_server_error(f"Error creating prescription: {e}")

@router.put("/{appointment_id}/prescription")
async def update_prescription(
    appointment_id: int,
    prescription: PrescriptionUpdate,
    current_user: dict = Depends(get_current_active_user)
):
    """Update an existing prescription"""
    tenant_id = get_tenant_id()
    
    # Check if appointment exists
    if not check_appointment_exists(appointment_id, tenant_id):
        raise_not_found_error("Appointment", appointment_id)
    
    try:
        with get_db_session() as session:
            prescription_obj = session.query(PrescriptionModel).filter(
                and_(PrescriptionModel.appointment_id == appointment_id, PrescriptionModel.tenant_id == tenant_id)
            ).first()
            
            if not prescription_obj:
                raise_not_found_error("Prescription", appointment_id)
            
            # Update prescription fields
            if prescription.bill_date is not None:
                bill_date_obj = string_to_date(prescription.bill_date)
                if not bill_date_obj:
                    raise_bad_request_error("Invalid bill_date format. Use dd/mm/yyyy")
                prescription_obj.bill_date = bill_date_obj
            
            if prescription.description is not None:
                prescription_obj.description = prescription.description
            
            # Update items if provided
            if prescription.items is not None:
                # Delete existing items
                session.query(PrescriptionItemModel).filter(
                    PrescriptionItemModel.prescription_id == prescription_obj.id
                ).delete()
                
                # Create new items
                for item in prescription.items:
                    new_item = PrescriptionItemModel(
                        tenant_id=tenant_id,
                        prescription_id=prescription_obj.id,
                        item_type=item.item_type,
                        source=item.source,
                        item_name=item.item_name,
                        quantity=item.quantity,
                        inventory_item_id=item.inventory_item_id if item.source == "Inventory" else None
                    )
                    session.add(new_item)
            
            session.commit()
            session.refresh(prescription_obj)
            
            # Return updated prescription with items
            items = session.query(PrescriptionItemModel).filter(
                PrescriptionItemModel.prescription_id == prescription_obj.id
            ).all()
            
            items_list = [
                PrescriptionItemResponse(
                    id=item.id,
                    item_type=item.item_type,
                    source=item.source,
                    item_name=item.item_name,
                    quantity=item.quantity,
                    inventory_item_id=item.inventory_item_id
                )
                for item in items
            ]
            
            return {
                "message": "Prescription updated successfully",
                "prescription": PrescriptionResponse(
                    id=prescription_obj.id,
                    appointment_id=prescription_obj.appointment_id,
                    bill_date=date_to_string(prescription_obj.bill_date),
                    description=prescription_obj.description,
                    items=items_list,
                    created_at=prescription_obj.created_at.isoformat() if prescription_obj.created_at else None
                )
            }
    except HTTPException:
        raise
    except Exception as e:
        raise_internal_server_error(f"Error updating prescription: {e}")

@router.post("/{appointment_id}/prescription/save")
async def save_prescription(
    appointment_id: int,
    prescription: PrescriptionCreate,
    current_user: dict = Depends(get_current_active_user)
):
    """Save prescription to appointment (create or update)"""
    tenant_id = get_tenant_id()
    
    # Validate appointment_id matches
    if prescription.appointment_id != appointment_id:
        raise_bad_request_error("Appointment ID in URL must match appointment_id in request body")
    
    # Check if appointment exists
    if not check_appointment_exists(appointment_id, tenant_id):
        raise_not_found_error("Appointment", appointment_id)
    
    try:
        with get_db_session() as session:
            # Check if prescription exists
            existing = session.query(PrescriptionModel).filter(
                and_(PrescriptionModel.appointment_id == appointment_id, PrescriptionModel.tenant_id == tenant_id)
            ).first()
            
            if existing:
                # Update existing prescription
                prescription_update = PrescriptionUpdate(
                    bill_date=prescription.bill_date,
                    description=prescription.description,
                    items=prescription.items
                )
                # Call update logic
                if prescription.bill_date is not None:
                    bill_date_obj = string_to_date(prescription.bill_date)
                    if bill_date_obj:
                        existing.bill_date = bill_date_obj
                
                if prescription.description is not None:
                    existing.description = prescription.description
                
                # Replace items
                session.query(PrescriptionItemModel).filter(
                    PrescriptionItemModel.prescription_id == existing.id
                ).delete()
                
                for item in prescription.items:
                    new_item = PrescriptionItemModel(
                        tenant_id=tenant_id,
                        prescription_id=existing.id,
                        item_type=item.item_type,
                        source=item.source,
                        item_name=item.item_name,
                        quantity=item.quantity,
                        inventory_item_id=item.inventory_item_id if item.source == "Inventory" else None
                    )
                    session.add(new_item)
                
                session.commit()
                session.refresh(existing)
                prescription_obj = existing
                message = "Prescription updated successfully"
            else:
                # Create new prescription
                bill_date_obj = string_to_date(prescription.bill_date) if prescription.bill_date else date.today()
                if not bill_date_obj:
                    bill_date_obj = date.today()
                
                new_prescription = PrescriptionModel(
                    tenant_id=tenant_id,
                    appointment_id=appointment_id,
                    bill_date=bill_date_obj,
                    description=prescription.description
                )
                session.add(new_prescription)
                session.flush()
                
                for item in prescription.items:
                    new_item = PrescriptionItemModel(
                        tenant_id=tenant_id,
                        prescription_id=new_prescription.id,
                        item_type=item.item_type,
                        source=item.source,
                        item_name=item.item_name,
                        quantity=item.quantity,
                        inventory_item_id=item.inventory_item_id if item.source == "Inventory" else None
                    )
                    session.add(new_item)
                
                session.commit()
                session.refresh(new_prescription)
                prescription_obj = new_prescription
                message = "Prescription saved successfully"
            
            # Return prescription with items
            items = session.query(PrescriptionItemModel).filter(
                PrescriptionItemModel.prescription_id == prescription_obj.id
            ).all()
            
            items_list = [
                PrescriptionItemResponse(
                    id=item.id,
                    item_type=item.item_type,
                    source=item.source,
                    item_name=item.item_name,
                    quantity=item.quantity,
                    inventory_item_id=item.inventory_item_id
                )
                for item in items
            ]
            
            return {
                "message": message,
                "prescription": PrescriptionResponse(
                    id=prescription_obj.id,
                    appointment_id=prescription_obj.appointment_id,
                    bill_date=date_to_string(prescription_obj.bill_date),
                    description=prescription_obj.description,
                    items=items_list,
                    created_at=prescription_obj.created_at.isoformat() if prescription_obj.created_at else None
                )
            }
    except HTTPException:
        raise
    except Exception as e:
        raise_internal_server_error(f"Error saving prescription: {e}")

@router.get("/{appointment_id}/prescription/generate-bill")
async def generate_bill_from_prescription(
    appointment_id: int,
    for_print: Optional[bool] = Query(False, description="Set to true to exclude 'source' column for printing"),
    current_user: dict = Depends(get_current_active_user)
):
    """Get bill-ready data from prescription for Bill Payment UI"""
    tenant_id = get_tenant_id()
    
    # Check if appointment exists
    if not check_appointment_exists(appointment_id, tenant_id):
        raise_not_found_error("Appointment", appointment_id)
    
    try:
        with get_db_session() as session:
            # Get appointment with patient and doctor details
            appointment = session.query(AppointmentsModel).filter(
                and_(AppointmentsModel.id == appointment_id, AppointmentsModel.tenant_id == tenant_id)
            ).first()
            
            if not appointment:
                raise_not_found_error("Appointment", appointment_id)
            
            # Get patient details
            patient = session.query(PatientModel).filter(PatientModel.id == appointment.patient_id).first()
            patient_name = f"{patient.firstname} {patient.lastname}".strip() if patient else "Unknown"
            
            # Get doctor details
            doctor = session.query(UserModel).filter(UserModel.id == appointment.doctor_id).first()
            doctor_name = f"Dr. {doctor.firstname.title()} {doctor.lastname.title()}".strip() if doctor else "Unknown"
            
            # Get prescription
            prescription = session.query(PrescriptionModel).filter(
                and_(PrescriptionModel.appointment_id == appointment_id, PrescriptionModel.tenant_id == tenant_id)
            ).first()
            
            if not prescription:
                raise_not_found_error("Prescription", appointment_id)
            
            # Get prescription items
            prescription_items = session.query(PrescriptionItemModel).filter(
                PrescriptionItemModel.prescription_id == prescription.id
            ).all()
            
            if not prescription_items:
                raise_bad_request_error("Prescription has no items to bill")
            
            # Convert prescription items to bill items format
            from app.modules.inventory.models import InventoryItemModel
            from decimal import Decimal
            
            bill_items = []
            for item in prescription_items:
                # Get unit price from inventory if source is Inventory
                unit_price = Decimal('0.0')
                if item.source == "Inventory" and item.inventory_item_id:
                    inventory_item = session.query(InventoryItemModel).filter(
                        InventoryItemModel.id == item.inventory_item_id
                    ).first()
                    if inventory_item:
                        unit_price = inventory_item.unit_price
                
                # Parse quantity from text (e.g., "10 tablets" -> 10)
                quantity = 1
                if item.quantity:
                    try:
                        # Extract first number from quantity string
                        import re
                        match = re.search(r'\d+', item.quantity)
                        if match:
                            quantity = int(match.group())
                    except (ValueError, AttributeError):
                        quantity = 1
                
                # Calculate total (will be updated by user in UI)
                total = unit_price * Decimal(str(quantity))
                
                # Get expiry date from inventory if source is Inventory
                expiry_date = None
                if item.source == "Inventory" and item.inventory_item_id:
                    inventory_item = session.query(InventoryItemModel).filter(
                        InventoryItemModel.id == item.inventory_item_id
                    ).first()
                    if inventory_item and inventory_item.expiry_date:
                        expiry_date = date_to_string(inventory_item.expiry_date)
                
                bill_item = {
                    "item_type": item.item_type,
                    "item_name": item.item_name,
                    "quantity": quantity,
                    "unit_price": float(unit_price),
                    "total": float(total),
                    "inventory_item_id": item.inventory_item_id,
                    "prescription_item_id": item.id,  # Keep reference to prescription item
                    "expiry_date": expiry_date  # Add expiry date for print
                }
                
                # Only include "source" field if not for print
                if not for_print:
                    bill_item["source"] = item.source
                
                bill_items.append(bill_item)
            
            # Calculate subtotal
            subtotal = sum(item["total"] for item in bill_items)
            
            # Return bill-ready data
            return {
                "appointment_id": appointment_id,
                "appointment_details": {
                    "appointment_id": f"#{appointment_id}",
                    "patient": patient_name,
                    "purpose": appointment.purpose or "Schedule",
                    "doctor_name": doctor_name
                },
                "bill_date": date_to_string(date.today()),  # Auto-generated (today)
                "appointment_id_display": f"#{appointment_id}",  # Auto-generated
                "bill_items": bill_items,
                "summary": {
                    "subtotal": float(subtotal),
                    "promo_discount": 0.0,  # Default, will be set by user
                    "grand_total": float(subtotal)  # Will be recalculated after promo discount
                },
                "prescription_id": prescription.id
            }
    except HTTPException:
        raise
    except Exception as e:
        raise_internal_server_error(f"Error generating bill: {e}")

# Inventory search endpoint for prescription items
@router.get("/inventory/items/search")
async def search_inventory_items(
    q: Optional[str] = Query(None, description="Search term for inventory items"),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=10),  # Max 10 per page as per requirements
    current_user: dict = Depends(get_current_active_user)
):
    """Search inventory items for prescription item selection"""
    tenant_id = get_tenant_id()
    
    from app.modules.inventory.models import InventoryItemModel
    
    try:
        with get_db_session() as session:
            query = session.query(InventoryItemModel).filter(InventoryItemModel.tenant_id == tenant_id)
            
            if q and q.strip():
                search_term = q.strip().lower()
                query = query.filter(InventoryItemModel.name.ilike(f"%{search_term}%"))
            
            # Filter out zero-stock items (only show items with stock available)
            query = query.filter(
                InventoryItemModel.current_stock > 0,
                InventoryItemModel.is_in_stock == True
            )
            
            # Get total count for pagination
            total = query.count()
            
            # Apply pagination
            items = query.order_by(InventoryItemModel.name).offset((page - 1) * limit).limit(limit).all()
            
            items_list = [
                {
                    "id": item.id,
                    "name": item.name,
                    "category": item.category,
                    "unit": item.unit,
                    "unit_price": float(item.unit_price) if item.unit_price else 0.0,
                    "current_stock": item.current_stock,
                    "is_in_stock": item.is_in_stock if hasattr(item, 'is_in_stock') else (item.current_stock > 0)
                }
                for item in items
            ]
            
            total_pages = (total + limit - 1) // limit if total > 0 else 1
            
            return {
                "items": items_list,
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
        raise_internal_server_error(f"Error searching inventory items: {e}")

@router.post("/{appointment_id}/prescription/save-to-billings")
async def save_to_billings(
    appointment_id: int,
    bill_payment: BillPaymentCreate,
    current_user: dict = Depends(get_current_active_user)
):
    """Save bill payment to billing_invoices table - automatically splits into doctor and pharmacy bills"""
    tenant_id = get_tenant_id()
    
    # Validate appointment_id matches
    if bill_payment.appointment_id != appointment_id:
        raise_bad_request_error("Appointment ID in URL must match appointment_id in request body")
    
    # Check if appointment exists
    if not check_appointment_exists(appointment_id, tenant_id):
        raise_not_found_error("Appointment", appointment_id)
    
    try:
        with get_db_session() as session:
            # Get appointment details
            appointment = session.query(AppointmentsModel).filter(
                and_(AppointmentsModel.id == appointment_id, AppointmentsModel.tenant_id == tenant_id)
            ).first()
            
            if not appointment:
                raise_not_found_error("Appointment", appointment_id)
            
            from decimal import Decimal
            from datetime import datetime
            from app.modules.inventory.models import InventoryItemModel
            
            # Separate items into services and products
            service_items = [item for item in bill_payment.items if item.item_type.lower() == "service"]
            product_items = [item for item in bill_payment.items if item.item_type.lower() == "product" and item.source == "Inventory"]
            
            # Convert bill_date to date object
            bill_date_obj = string_to_date(bill_payment.bill_date) if bill_payment.bill_date else date.today()
            if not bill_date_obj:
                bill_date_obj = date.today()
            
            amount_paid = Decimal('0.0')
            status = "pending"
            created_invoices = []
            doctor_invoice = None  # Initialize for linking
            
            # Generate invoice numbers with prefixes
            timestamp = int(datetime.now().timestamp())
            
            # Create Doctor Bill (if services exist)
            if service_items:
                service_subtotal = sum(Decimal(str(item.total)) for item in service_items)
                service_discount = bill_payment.promo_discount if len(product_items) == 0 else Decimal('0.0')  # Apply discount only if no pharmacy bill
                service_grand_total = service_subtotal - service_discount
                if service_grand_total < 0:
                    service_grand_total = Decimal('0.0')
                
                doc_invoice_number = f"DOC-{appointment_id}-{timestamp}"
                # Check for collision
                existing_doc = session.query(BillingInvoiceModel).filter(
                    BillingInvoiceModel.invoice_number == doc_invoice_number
                ).first()
                if existing_doc:
                    import random
                    doc_invoice_number = f"DOC-{appointment_id}-{timestamp}{random.randint(100, 999)}"
                
                doctor_invoice = BillingInvoiceModel(
                    tenant_id=tenant_id,
                    invoice_number=doc_invoice_number,
                    patient_id=appointment.patient_id,
                    appointment_id=appointment_id,
                    doctor_id=appointment.doctor_id,
                    issue_date=bill_date_obj,
                    purpose=appointment.purpose or "Schedule",
                    total_amount=service_subtotal,
                    tax_amount=Decimal('0.0'),
                    gst_percentage=Decimal('0.0'),
                    discount_amount=service_discount,
                    coupon_code=bill_payment.promo_type if len(product_items) == 0 else None,
                    adjustments=Decimal('0.0'),
                    amount_paid=amount_paid,
                    status=status,
                    visit_charge=Decimal('0.0'),
                    medication_charge=Decimal('0.0'),
                    bill_type="doctor"
                )
                session.add(doctor_invoice)
                session.flush()
                
                # Add service items to doctor bill
                for item in service_items:
                    billing_item = BillingItemModel(
                        tenant_id=tenant_id,
                        invoice_id=doctor_invoice.id,
                        item_type="service",
                        description=item.item_name,
                        quantity=item.quantity,
                        unit_price=item.unit_price,
                        line_total=item.total,
                        inventory_item_id=item.inventory_item_id,
                        expiry_date=None
                    )
                    session.add(billing_item)
                
                created_invoices.append({
                    "invoice_id": doctor_invoice.id,
                    "invoice_number": doc_invoice_number,
                    "bill_type": "doctor",
                    "subtotal": float(service_subtotal),
                    "discount": float(service_discount),
                    "grand_total": float(service_grand_total)
                })
            
            # Create Pharmacy Bill (if products exist)
            if product_items:
                pharm_subtotal = sum(Decimal(str(item.total)) for item in product_items)
                pharm_discount = bill_payment.promo_discount if len(service_items) == 0 else Decimal('0.0')  # Apply discount only if no doctor bill
                pharm_grand_total = pharm_subtotal - pharm_discount
                if pharm_grand_total < 0:
                    pharm_grand_total = Decimal('0.0')
                
                pharm_invoice_number = f"PHARM-{appointment_id}-{timestamp}"
                # Check for collision
                existing_pharm = session.query(BillingInvoiceModel).filter(
                    BillingInvoiceModel.invoice_number == pharm_invoice_number
                ).first()
                if existing_pharm:
                    import random
                    pharm_invoice_number = f"PHARM-{appointment_id}-{timestamp}{random.randint(100, 999)}"
                
                pharmacy_invoice = BillingInvoiceModel(
                    tenant_id=tenant_id,
                    invoice_number=pharm_invoice_number,
                    patient_id=appointment.patient_id,
                    appointment_id=appointment_id,
                    doctor_id=appointment.doctor_id,
                    issue_date=bill_date_obj,
                    purpose=appointment.purpose or "Schedule",
                    total_amount=pharm_subtotal,
                    tax_amount=Decimal('0.0'),
                    gst_percentage=Decimal('0.0'),
                    discount_amount=pharm_discount,
                    coupon_code=bill_payment.promo_type if len(service_items) == 0 else None,
                    adjustments=Decimal('0.0'),
                    amount_paid=amount_paid,
                    status=status,
                    visit_charge=Decimal('0.0'),
                    medication_charge=Decimal('0.0'),
                    bill_type="pharmacy"
                )
                session.add(pharmacy_invoice)
                session.flush()
                
                # Link pharmacy bill to doctor bill if both exist
                if doctor_invoice:
                    pharmacy_invoice.related_invoice_id = doctor_invoice.id
                    doctor_invoice.related_invoice_id = pharmacy_invoice.id
                
                # Add product items to pharmacy bill with expiry dates
                for item in product_items:
                    expiry_date = None
                    if item.inventory_item_id:
                        inventory_item = session.query(InventoryItemModel).filter(
                            InventoryItemModel.id == item.inventory_item_id
                        ).first()
                        if inventory_item and inventory_item.expiry_date:
                            expiry_date = inventory_item.expiry_date
                    
                    billing_item = BillingItemModel(
                        tenant_id=tenant_id,
                        invoice_id=pharmacy_invoice.id,
                        item_type="product",
                        description=item.item_name,
                        quantity=item.quantity,
                        unit_price=item.unit_price,
                        line_total=item.total,
                        inventory_item_id=item.inventory_item_id,
                        expiry_date=expiry_date
                    )
                    session.add(billing_item)
                
                created_invoices.append({
                    "invoice_id": pharmacy_invoice.id,
                    "invoice_number": pharm_invoice_number,
                    "bill_type": "pharmacy",
                    "subtotal": float(pharm_subtotal),
                    "discount": float(pharm_discount),
                    "grand_total": float(pharm_grand_total)
                })
            
            if not created_invoices:
                raise_bad_request_error("No valid items to bill")
            
            session.commit()
            
            # Update appointment status if all bills are paid
            all_paid = True
            for inv_info in created_invoices:
                invoice = session.query(BillingInvoiceModel).filter(
                    BillingInvoiceModel.id == inv_info["invoice_id"]
                ).first()
                if invoice:
                    outstanding = float(invoice.outstanding_amount) if invoice.outstanding_amount else float(inv_info["grand_total"])
                    if outstanding > 0:
                        all_paid = False
                        break
            
            if all_paid:
                appointment.status = "Checked Out"
                session.commit()
            
            return {
                "message": "Bill(s) saved to billings successfully",
                "invoices": created_invoices,
                "total_grand_total": sum(inv["grand_total"] for inv in created_invoices)
            }
    except HTTPException:
        raise
    except Exception as e:
        raise_internal_server_error(f"Error saving bill to billings: {e}")
