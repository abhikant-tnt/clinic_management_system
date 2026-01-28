from fastapi import APIRouter, HTTPException, Query, Depends
from fastapi.responses import JSONResponse
from typing import Optional, Literal, Any, Union
from datetime import date
from decimal import Decimal
from app.modules.appointments.schemas import AppointmentCreate, AppointmentUpdate
from app.common.schemas import ErrorResponse
from app.common.utils import create_error_response, raise_not_found_error, raise_bad_request_error, raise_internal_server_error
from app.core.db_helper import check_exists, get_by_id
from app.core.date_helpers import date_to_string
from app.core.database import (
    postgres_conn, 
    postgres_cursor, 
    db_session
)
from app.core.models import AppointmentsModel, PatientModel
from sqlalchemy import and_
from app.core.config import settings
from app.core.dependencies import get_current_active_user
from app.common.utils import validate_column_names

router = APIRouter()

def get_tenant_id() -> str:
    """Get tenant ID from settings"""
    return settings.TENANT_ID

def appointment_to_dict(appointment_data: Any) -> dict:
    """Convert appointment object to dictionary, handling DATE to string conversion"""
    if isinstance(appointment_data, dict):
        # Convert DATE fields to string format for API response
        result = appointment_data.copy()
        if "appointment_date" in result and result["appointment_date"] and not isinstance(result["appointment_date"], str):
            result["appointment_date"] = date_to_string(result["appointment_date"])
        if "follow_up_date" in result and result["follow_up_date"] and not isinstance(result["follow_up_date"], str):
            result["follow_up_date"] = date_to_string(result["follow_up_date"])
        if "appointment_time" in result and result["appointment_time"] and not isinstance(result["appointment_time"], str):
            result["appointment_time"] = str(result["appointment_time"]) if result["appointment_time"] else None
        return result
    
    # Convert from model object
    appt_date_str = date_to_string(appointment_data.appointment_date) if hasattr(appointment_data, 'appointment_date') and appointment_data.appointment_date else None
    follow_up_str = date_to_string(appointment_data.follow_up_date) if hasattr(appointment_data, 'follow_up_date') and appointment_data.follow_up_date else None
    time_str = str(appointment_data.appointment_time) if hasattr(appointment_data, 'appointment_time') and appointment_data.appointment_time else None
    
    return {
        "id": appointment_data.id,
        "tenant_id": appointment_data.tenant_id,
        "patient_id": appointment_data.patient_id,
        "doctor_id": appointment_data.doctor_id if hasattr(appointment_data, 'doctor_id') else None,
        "appointment_date": appt_date_str or (appointment_data.appointment_date if hasattr(appointment_data, 'appointment_date') else None),
        "appointment_time": time_str or (appointment_data.appointment_time if hasattr(appointment_data, 'appointment_time') else None),
        "appointment_status": appointment_data.appointment_status,
        "doctor_name": appointment_data.doctor_name,
        "appointment_type": appointment_data.appointment_type,
        "notes": appointment_data.notes,
        "payment_pending": appointment_data.payment_pending if appointment_data.payment_pending else False,
        "follow_up_date": follow_up_str or (appointment_data.follow_up_date if hasattr(appointment_data, 'follow_up_date') else None),
        "diagnosis": appointment_data.diagnosis if hasattr(appointment_data, 'diagnosis') else None,
        "treatment": appointment_data.treatment if hasattr(appointment_data, 'treatment') else None,
        "visit_charge": float(appointment_data.visit_charge) if hasattr(appointment_data, 'visit_charge') and appointment_data.visit_charge else 0.0,
        "medication_charge": float(appointment_data.medication_charge) if hasattr(appointment_data, 'medication_charge') and appointment_data.medication_charge else 0.0,
        "total_charge": float(appointment_data.total_charge) if hasattr(appointment_data, 'total_charge') and appointment_data.total_charge else 0.0,
        "is_waived": appointment_data.is_waived if hasattr(appointment_data, 'is_waived') and appointment_data.is_waived else False,
        "created_at": appointment_data.created_at.isoformat() if appointment_data.created_at else None,
        "updated_at": appointment_data.updated_at.isoformat() if appointment_data.updated_at else None
    }

def check_patient_exists(patient_id: int, tenant_id: str) -> bool:
    """Check if patient exists using database helper"""
    return check_exists(PatientModel, "patients_table", "id", patient_id, tenant_id)

def check_appointment_exists(appointment_id: int, tenant_id: str) -> bool:
    """Check if appointment exists using database helper"""
    return check_exists(AppointmentsModel, "appointments", "id", appointment_id, tenant_id)

def get_appointment_by_id(appointment_id: int, tenant_id: str) -> Union[dict, Any, None]:
    """Get appointment by ID using database helper"""
    columns = ["id", "patient_id", "doctor_id", "tenant_id", "appointment_date", "appointment_time", "appointment_status",
              "doctor_name", "appointment_type", "notes", "payment_pending", "follow_up_date",
              "diagnosis", "treatment", "visit_charge", "medication_charge", "total_charge", "is_waived",
              "created_at", "updated_at"]
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
    today: Optional[bool] = Query(None, description="Filter appointments for today"),
    tomorrow: Optional[bool] = Query(None, description="Filter appointments for tomorrow"),
    appointment_status: Optional[Literal["first time appointment", "follow up", "vip"]] = Query(None, description="Filter by appointment status"),
    doctor_name: Optional[str] = Query(None, description="Filter by doctor name"),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    current_user: dict = Depends(get_current_active_user)
):
    """Get all appointments with optional filters (today, tomorrow, status, doctor)"""
    tenant_id = get_tenant_id()
    
    appointments_list = []
    if db_session:
        try:
            query = db_session.query(AppointmentsModel).filter(AppointmentsModel.tenant_id == tenant_id)
            
            if today:
                query = query.filter(AppointmentsModel.appointment_date == get_today_date())
            elif tomorrow:
                query = query.filter(AppointmentsModel.appointment_date == get_tomorrow_date())
            
            if appointment_status:
                query = query.filter(AppointmentsModel.appointment_status == appointment_status)
            
            if doctor_name:
                query = query.filter(AppointmentsModel.doctor_name == doctor_name)
            
            appointments = query.order_by(AppointmentsModel.appointment_date, AppointmentsModel.appointment_time).all()
            appointments_list = [appointment_to_dict(apt) for apt in appointments]
        except Exception as e:
            pass
    elif postgres_cursor:
        try:
            conditions = ["tenant_id = %s"]
            params = [tenant_id]
            
            if today:
                conditions.append("appointment_date = %s")
                params.append(get_today_date())
            elif tomorrow:
                conditions.append("appointment_date = %s")
                params.append(get_tomorrow_date())
            
                if appointment_status:
                    conditions.append("appointment_status = %s")
                    params.append(appointment_status)
            
            if doctor_name:
                conditions.append("doctor_name = %s")
                params.append(doctor_name)
            
            query = f"SELECT id, patient_id, tenant_id, appointment_date, appointment_time, appointment_status, doctor_name, appointment_type, notes, payment_pending, follow_up_date, diagnosis, treatment, visit_charge, medication_charge, total_charge, is_waived, created_at, updated_at FROM appointments WHERE {' AND '.join(conditions)} ORDER BY appointment_date, appointment_time"
            postgres_cursor.execute(query, params)
            columns = ["id", "patient_id", "tenant_id", "appointment_date", "appointment_time", "status",
                      "doctor_name", "appointment_type", "notes", "payment_pending", "follow_up_date",
                      "diagnosis", "treatment", "visit_charge", "medication_charge", "total_charge", "is_waived",
                      "created_at", "updated_at"]
            appointments_list = [dict(zip(columns, r)) for r in postgres_cursor.fetchall()]
        except Exception as e:
            pass
    
    # Sort by date and time
    appointments_list.sort(key=lambda x: (x.get("appointment_date", ""), x.get("appointment_time", "")))
    total = len(appointments_list)
    total_pages = (total + limit - 1) // limit if total > 0 else 1
    
    return {
        "appointments": appointments_list[(page - 1) * limit:page * limit],
        "pagination": {
            "total": total, "page": page, "limit": limit, "total_pages": total_pages,
            "has_next": page < total_pages, "has_prev": page > 1
        }
    }

@router.get("/queue")
async def get_queue(current_user: dict = Depends(get_current_active_user)):
    """Get queue management - Active appointments for today, sorted by time"""
    tenant_id = get_tenant_id()
    today = get_today_date()
    
    appointments_list = []
    if db_session:
        try:
            appointments = db_session.query(AppointmentsModel).filter(
                and_(
                    AppointmentsModel.tenant_id == tenant_id,
                    AppointmentsModel.appointment_date == today,
                    AppointmentsModel.appointment_status == "first time appointment"
                )
            ).order_by(AppointmentsModel.appointment_time.asc()).all()
            appointments_list = [appointment_to_dict(apt) for apt in appointments]
        except Exception as e:
            pass
    elif postgres_cursor:
        try:
            postgres_cursor.execute("""
                SELECT id, patient_id, tenant_id, appointment_date, appointment_time, status,
                       doctor_name, appointment_type, notes, payment_pending, follow_up_date,
                       diagnosis, treatment, visit_charge, medication_charge, total_charge, is_waived,
                       created_at, updated_at
                FROM appointments 
                WHERE tenant_id = %s AND appointment_date = %s AND appointment_status = %s
                ORDER BY appointment_time ASC
            """, (tenant_id, today, "first time appointment"))
            columns = ["id", "patient_id", "tenant_id", "appointment_date", "appointment_time", "status",
                      "doctor_name", "appointment_type", "notes", "payment_pending", "follow_up_date",
                      "diagnosis", "treatment", "visit_charge", "medication_charge", "total_charge", "is_waived",
                      "created_at", "updated_at"]
            appointments_list = [dict(zip(columns, r)) for r in postgres_cursor.fetchall()]
        except Exception as e:
            pass
    
    return {"queue": appointments_list, "date": today, "total": len(appointments_list)}

@router.post("/")
async def create_appointment(appointment: AppointmentCreate, current_user: dict = Depends(get_current_active_user)):
    """Create a new appointment"""
    tenant_id = get_tenant_id()
    
    # Check if patient exists
    if not check_patient_exists(appointment.patient_id, tenant_id):
        raise_not_found_error("Patient", appointment.patient_id)
    
    # Check if doctor/staff exists
    from app.modules.staff.routes import check_staff_exists
    if not check_staff_exists(appointment.doctor_id, tenant_id):
        raise_not_found_error("Staff/Doctor", appointment.doctor_id)
    
    # Calculate total charge
    visit_charge = appointment.visit_charge if appointment.visit_charge is not None else 0.0
    medication_charge = appointment.medication_charge if appointment.medication_charge is not None else 0.0
    total_charge = visit_charge + medication_charge
    
    appointment_data = appointment.model_dump(exclude={"tenant_id"})
    appointment_data["tenant_id"] = tenant_id
    appointment_data["visit_charge"] = Decimal(str(visit_charge))
    appointment_data["medication_charge"] = Decimal(str(medication_charge))
    appointment_data["total_charge"] = Decimal(str(total_charge))
    
    # Create using SQLAlchemy ORM
    if db_session:
        try:
            new_appointment = AppointmentsModel(
                patient_id=appointment_data["patient_id"],
                doctor_id=appointment_data["doctor_id"],
                tenant_id=appointment_data["tenant_id"],
                appointment_date=appointment_data["appointment_date"],
                appointment_time=appointment_data["appointment_time"],
                appointment_status=appointment_data["appointment_status"],
                doctor_name=appointment_data.get("doctor_name"),
                appointment_type=appointment_data.get("appointment_type"),
                notes=appointment_data.get("notes"),
                payment_pending=appointment_data.get("payment_pending", False),
                follow_up_date=appointment_data.get("follow_up_date"),
                diagnosis=appointment_data.get("diagnosis"),
                treatment=appointment_data.get("treatment"),
                visit_charge=appointment_data["visit_charge"],
                medication_charge=appointment_data["medication_charge"],
                total_charge=appointment_data["total_charge"],
                is_waived=appointment_data.get("is_waived", False),
            )
            db_session.add(new_appointment)
            db_session.commit()
            db_session.refresh(new_appointment)
            return {"database": "PostgreSQL", "appointment": appointment_to_dict(new_appointment)}
        except Exception as e:
            db_session.rollback()
            raise_internal_server_error("Error creating appointment. Please try again or contact support.")
    # Fallback to raw SQL
    elif postgres_cursor:
        try:
            postgres_cursor.execute("""
                INSERT INTO appointments (patient_id, doctor_id, tenant_id, appointment_date, appointment_time, status,
                                        doctor_name, appointment_type, notes, payment_pending, follow_up_date,
                                        diagnosis, treatment, visit_charge, medication_charge, total_charge, is_waived)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id, patient_id, doctor_id, tenant_id, appointment_date, appointment_time, status,
                         doctor_name, appointment_type, notes, payment_pending, follow_up_date,
                         diagnosis, treatment, visit_charge, medication_charge, total_charge, is_waived,
                         created_at, updated_at
            """, (
                appointment_data["patient_id"], appointment_data["doctor_id"], appointment_data["tenant_id"],
                appointment_data["appointment_date"], appointment_data["appointment_time"],
                appointment_data["appointment_status"], appointment_data.get("doctor_name"),
                appointment_data.get("appointment_type"), appointment_data.get("notes"),
                appointment_data.get("payment_pending", False), appointment_data.get("follow_up_date"),
                appointment_data.get("diagnosis"), appointment_data.get("treatment"),
                appointment_data["visit_charge"], appointment_data["medication_charge"],
                appointment_data["total_charge"], appointment_data.get("is_waived", False)
            ))
            record = postgres_cursor.fetchone()
            postgres_conn.commit()
            
            if record:
                columns = ["id", "patient_id", "doctor_id", "tenant_id", "appointment_date", "appointment_time", "status",
                          "doctor_name", "appointment_type", "notes", "payment_pending", "follow_up_date",
                          "diagnosis", "treatment", "visit_charge", "medication_charge", "total_charge", "is_waived",
                          "created_at", "updated_at"]
                appointment_dict = dict(zip(columns, record))
                return {"database": "PostgreSQL", "appointment": appointment_dict}
        except Exception as e:
            postgres_conn.rollback()
            raise_internal_server_error("Error creating appointment. Please try again or contact support.")
    
    raise HTTPException(status_code=500, detail="Database connection not available")

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
    # Recalculate total_charge if charges are updated
    if "visit_charge" in update_data or "medication_charge" in update_data:
        current_appointment = get_appointment_by_id(appointment_id, tenant_id)
        visit_charge = update_data.get("visit_charge")
        medication_charge = update_data.get("medication_charge")
        
        if visit_charge is None:
            visit_charge = float(current_appointment.get("visit_charge", 0)) if isinstance(current_appointment, dict) else (float(current_appointment.visit_charge) if current_appointment.visit_charge else 0.0)
        if medication_charge is None:
            medication_charge = float(current_appointment.get("medication_charge", 0)) if isinstance(current_appointment, dict) else (float(current_appointment.medication_charge) if current_appointment.medication_charge else 0.0)
        
        update_data["total_charge"] = Decimal(str(visit_charge + medication_charge))
        update_data["visit_charge"] = Decimal(str(visit_charge))
        update_data["medication_charge"] = Decimal(str(medication_charge))
    
    # Update using SQLAlchemy ORM
    if db_session:
        try:
            appointment = db_session.query(AppointmentsModel).filter(
                and_(AppointmentsModel.id == appointment_id, AppointmentsModel.tenant_id == tenant_id)
            ).first()
            if not appointment:
                raise_not_found_error("Appointment", appointment_id)
            
            # Update fields
            for key, value in update_data.items():
                setattr(appointment, key, value)
            
            from datetime import datetime
            appointment.updated_at = datetime.now()
            
            db_session.commit()
            db_session.refresh(appointment)
            return {"database": "PostgreSQL", "appointment": appointment_to_dict(appointment)}
        except HTTPException:
            raise
        except Exception as e:
            db_session.rollback()
            raise_internal_server_error("Error updating appointment. Please try again or contact support.")
    # Fallback to raw SQL
    elif postgres_cursor:
        try:
            # Validate column names to prevent SQL injection
            allowed_columns = {
                "appointment_date", "appointment_time", "appointment_status", "doctor_name",
                "appointment_type", "notes", "payment_pending", "follow_up_date",
                "diagnosis", "treatment", "visit_charge", "medication_charge",
                "total_charge", "is_waived", "patient_id", "doctor_id"
            }
            validated_keys = validate_column_names(set(update_data.keys()), allowed_columns)
            set_clauses = []
            params = []
            for key in validated_keys:
                set_clauses.append(f"{key} = %s")
                params.append(update_data[key])
            
            params.append(appointment_id)
            params.append(tenant_id)
            
            query = f"""
                UPDATE appointments 
                SET {', '.join(set_clauses)}, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s AND tenant_id = %s
                RETURNING id, patient_id, tenant_id, appointment_date, appointment_time, status,
                         doctor_name, appointment_type, notes, payment_pending, follow_up_date,
                         diagnosis, treatment, visit_charge, medication_charge, total_charge, is_waived,
                         created_at, updated_at
            """
            postgres_cursor.execute(query, params)
            record = postgres_cursor.fetchone()
            postgres_conn.commit()
            
            if record:
                columns = ["id", "patient_id", "doctor_id", "tenant_id", "appointment_date", "appointment_time", "status",
                          "doctor_name", "appointment_type", "notes", "payment_pending", "follow_up_date",
                          "diagnosis", "treatment", "visit_charge", "medication_charge", "total_charge", "is_waived",
                          "created_at", "updated_at"]
                appointment_dict = dict(zip(columns, record))
                return {"database": "PostgreSQL", "appointment": appointment_dict}
        except Exception as e:
            postgres_conn.rollback()
            raise_internal_server_error("Error updating appointment. Please try again or contact support.")
    
    raise HTTPException(status_code=500, detail="Database connection not available")

@router.delete("/{appointment_id}")
async def delete_appointment(appointment_id: int, current_user: dict = Depends(get_current_active_user)):
    """Delete an appointment"""
    tenant_id = get_tenant_id()
    
    if not check_appointment_exists(appointment_id, tenant_id):
        raise_not_found_error("Appointment", appointment_id)
    
    # Delete using SQLAlchemy ORM
    if db_session:
        try:
            appointment = db_session.query(AppointmentsModel).filter(
                and_(AppointmentsModel.id == appointment_id, AppointmentsModel.tenant_id == tenant_id)
            ).first()
            if appointment:
                db_session.delete(appointment)
                db_session.commit()
                return {"message": f"Appointment with ID {appointment_id} deleted successfully"}
            else:
                raise_not_found_error("Appointment", appointment_id)
        except HTTPException:
            raise
        except Exception as e:
            db_session.rollback()
            raise_internal_server_error("Error deleting appointment. Please try again or contact support.")
    # Fallback to raw SQL
    elif postgres_cursor:
        try:
            postgres_cursor.execute("DELETE FROM appointments WHERE id = %s AND tenant_id = %s", (appointment_id, tenant_id))
            postgres_conn.commit()
            return {"message": f"Appointment with ID {appointment_id} deleted successfully"}
        except Exception as e:
            postgres_conn.rollback()
            raise_internal_server_error("Error deleting appointment. Please try again or contact support.")
    
    raise HTTPException(status_code=500, detail="Database connection not available")

@router.post("/{appointment_id}/complete")
async def complete_appointment(appointment_id: int, current_user: dict = Depends(get_current_active_user)):
    """Mark an appointment as completed"""
    tenant_id = get_tenant_id()
    
    appointment_data = get_appointment_by_id(appointment_id, tenant_id)
    if not appointment_data:
        raise_not_found_error("Appointment", appointment_id)
    
    if postgres_cursor:
        try:
            postgres_cursor.execute("""
                UPDATE appointments 
                SET appointment_status = 'follow up', updated_at = CURRENT_TIMESTAMP
                WHERE id = %s AND tenant_id = %s
                RETURNING id, patient_id, tenant_id, appointment_date, appointment_time, appointment_status,
                         doctor_name, appointment_type, notes, payment_pending, follow_up_date,
                         diagnosis, treatment, visit_charge, medication_charge, total_charge, is_waived,
                         created_at, updated_at
            """, (appointment_id, tenant_id))
            record = postgres_cursor.fetchone()
            postgres_conn.commit()
            
            if record:
                columns = ["id", "patient_id", "tenant_id", "appointment_date", "appointment_time", "appointment_status",
                          "doctor_name", "appointment_type", "notes", "payment_pending", "follow_up_date",
                          "diagnosis", "treatment", "visit_charge", "medication_charge", "total_charge", "is_waived",
                          "created_at", "updated_at"]
                appointment_dict = dict(zip(columns, record))
                return {"database": "PostgreSQL", "appointment": appointment_dict, "message": "Appointment marked as completed"}
        except Exception as e:
            postgres_conn.rollback()
            raise_internal_server_error("Error completing appointment. Please try again or contact support.")
    
    raise HTTPException(status_code=500, detail="Database connection not available")
