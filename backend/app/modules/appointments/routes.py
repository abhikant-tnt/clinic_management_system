from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from typing import Optional, Literal
from datetime import date
from decimal import Decimal
from app.modules.appointments.schemas import AppointmentCreate, AppointmentUpdate
from app.common.schemas import ErrorResponse
from app.core.database import (
    local_postgres_conn, 
    local_postgres_cursor, 
    sync_local_to_main,
    db_session
)
from app.core.models import AppointmentsModel, PatientModel
from sqlalchemy import and_
from app.core.config import settings

router = APIRouter()

def get_tenant_id() -> str:
    """Get tenant ID from settings"""
    return settings.TENANT_ID

def appointment_to_dict(appointment_data) -> dict:
    """Convert appointment object to dictionary"""
    if isinstance(appointment_data, dict):
        return appointment_data
    return {
        "id": appointment_data.id,
        "tenant_id": appointment_data.tenant_id,
        "patient_id": appointment_data.patient_id,
        "appointment_date": appointment_data.appointment_date,
        "appointment_time": appointment_data.appointment_time,
        "status": appointment_data.status,
        "doctor_name": appointment_data.doctor_name,
        "appointment_type": appointment_data.appointment_type,
        "notes": appointment_data.notes,
        "payment_pending": appointment_data.payment_pending if appointment_data.payment_pending else False,
        "follow_up_date": appointment_data.follow_up_date,
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
    """Check if patient exists"""
    if db_session:
        try:
            return db_session.query(PatientModel).filter(
                and_(PatientModel.id == patient_id, PatientModel.tenant_id == tenant_id)
            ).first() is not None
        except Exception:  # pylint: disable=broad-except
            return False
    elif local_postgres_cursor:
        try:
            local_postgres_cursor.execute("SELECT id FROM patients_table WHERE id = %s AND tenant_id = %s", (patient_id, tenant_id))
            return local_postgres_cursor.fetchone() is not None
        except Exception:  # pylint: disable=broad-except
            return False
    return False

def check_appointment_exists(appointment_id: int, tenant_id: str) -> bool:
    """Check if appointment exists"""
    if db_session:
        try:
            return db_session.query(AppointmentsModel).filter(
                and_(AppointmentsModel.id == appointment_id, AppointmentsModel.tenant_id == tenant_id)
            ).first() is not None
        except Exception:  # pylint: disable=broad-except
            return False
    elif local_postgres_cursor:
        try:
            local_postgres_cursor.execute("SELECT id FROM appointments WHERE id = %s AND tenant_id = %s", (appointment_id, tenant_id))
            return local_postgres_cursor.fetchone() is not None
        except Exception:  # pylint: disable=broad-except
            return False
    return False

def get_appointment_by_id(appointment_id: int, tenant_id: str):
    """Get appointment by ID, returns appointment object or dict"""
    if db_session:
        try:
            return db_session.query(AppointmentsModel).filter(
                and_(AppointmentsModel.id == appointment_id, AppointmentsModel.tenant_id == tenant_id)
            ).first()
        except Exception:  # pylint: disable=broad-except
            return None
    elif local_postgres_cursor:
        try:
            local_postgres_cursor.execute("""
                SELECT id, patient_id, tenant_id, appointment_date, appointment_time, status,
                       doctor_name, appointment_type, notes, payment_pending, follow_up_date,
                       diagnosis, treatment, visit_charge, medication_charge, total_charge, is_waived,
                       created_at, updated_at
                FROM appointments WHERE id = %s AND tenant_id = %s
            """, (appointment_id, tenant_id))
            record = local_postgres_cursor.fetchone()
            if record:
                columns = ["id", "patient_id", "tenant_id", "appointment_date", "appointment_time", "status",
                          "doctor_name", "appointment_type", "notes", "payment_pending", "follow_up_date",
                          "diagnosis", "treatment", "visit_charge", "medication_charge", "total_charge", "is_waived",
                          "created_at", "updated_at"]
                return dict(zip(columns, record))
        except Exception:  # pylint: disable=broad-except
            return None
    return None

def error_response(message: str, status_code: int = 400) -> JSONResponse:
    """Create standardized error response"""
    return JSONResponse(status_code=status_code, content=ErrorResponse(message=message).model_dump())

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
def get_appointments(
    today: Optional[bool] = Query(None, description="Filter appointments for today"),
    tomorrow: Optional[bool] = Query(None, description="Filter appointments for tomorrow"),
    status: Optional[Literal["Active", "Completed", "Cancelled", "DNA"]] = Query(None, description="Filter by status"),
    doctor_name: Optional[str] = Query(None, description="Filter by doctor name"),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100)
):
    """Get all appointments with optional filters (today, tomorrow, status, doctor)"""
    tenant_id = get_tenant_id()
    sync_local_to_main()
    
    appointments_list = []
    if db_session:
        try:
            query = db_session.query(AppointmentsModel).filter(AppointmentsModel.tenant_id == tenant_id)
            
            if today:
                query = query.filter(AppointmentsModel.appointment_date == get_today_date())
            elif tomorrow:
                query = query.filter(AppointmentsModel.appointment_date == get_tomorrow_date())
            
            if status:
                query = query.filter(AppointmentsModel.status == status)
            
            if doctor_name:
                query = query.filter(AppointmentsModel.doctor_name == doctor_name)
            
            appointments = query.order_by(AppointmentsModel.appointment_date, AppointmentsModel.appointment_time).all()
            appointments_list = [appointment_to_dict(apt) for apt in appointments]
        except Exception as e:  # pylint: disable=broad-except
            print(f"Error fetching appointments (SQLAlchemy): {e}")
    elif local_postgres_cursor:
        try:
            conditions = ["tenant_id = %s"]
            params = [tenant_id]
            
            if today:
                conditions.append("appointment_date = %s")
                params.append(get_today_date())
            elif tomorrow:
                conditions.append("appointment_date = %s")
                params.append(get_tomorrow_date())
            
            if status:
                conditions.append("status = %s")
                params.append(status)
            
            if doctor_name:
                conditions.append("doctor_name = %s")
                params.append(doctor_name)
            
            query = f"SELECT id, patient_id, tenant_id, appointment_date, appointment_time, status, doctor_name, appointment_type, notes, payment_pending, follow_up_date, diagnosis, treatment, visit_charge, medication_charge, total_charge, is_waived, created_at, updated_at FROM appointments WHERE {' AND '.join(conditions)} ORDER BY appointment_date, appointment_time"
            local_postgres_cursor.execute(query, params)
            columns = ["id", "patient_id", "tenant_id", "appointment_date", "appointment_time", "status",
                      "doctor_name", "appointment_type", "notes", "payment_pending", "follow_up_date",
                      "diagnosis", "treatment", "visit_charge", "medication_charge", "total_charge", "is_waived",
                      "created_at", "updated_at"]
            appointments_list = [dict(zip(columns, r)) for r in local_postgres_cursor.fetchall()]
        except Exception as e:  # pylint: disable=broad-except
            print(f"Error fetching appointments: {e}")
    
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
def get_queue():
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
                    AppointmentsModel.status == "Active"
                )
            ).order_by(AppointmentsModel.appointment_time.asc()).all()
            appointments_list = [appointment_to_dict(apt) for apt in appointments]
        except Exception as e:  # pylint: disable=broad-except
            print(f"Error fetching queue (SQLAlchemy): {e}")
    elif local_postgres_cursor:
        try:
            local_postgres_cursor.execute("""
                SELECT id, patient_id, tenant_id, appointment_date, appointment_time, status,
                       doctor_name, appointment_type, notes, payment_pending, follow_up_date,
                       diagnosis, treatment, visit_charge, medication_charge, total_charge, is_waived,
                       created_at, updated_at
                FROM appointments 
                WHERE tenant_id = %s AND appointment_date = %s AND status = 'Active'
                ORDER BY appointment_time ASC
            """, (tenant_id, today))
            columns = ["id", "patient_id", "tenant_id", "appointment_date", "appointment_time", "status",
                      "doctor_name", "appointment_type", "notes", "payment_pending", "follow_up_date",
                      "diagnosis", "treatment", "visit_charge", "medication_charge", "total_charge", "is_waived",
                      "created_at", "updated_at"]
            appointments_list = [dict(zip(columns, r)) for r in local_postgres_cursor.fetchall()]
        except Exception as e:  # pylint: disable=broad-except
            print(f"Error fetching queue: {e}")
    
    return {"queue": appointments_list, "date": today, "total": len(appointments_list)}

@router.post("/")
def create_appointment(appointment: AppointmentCreate):
    """Create a new appointment"""
    tenant_id = get_tenant_id()
    
    # Check if patient exists
    if not check_patient_exists(appointment.patient_id, tenant_id):
        raise HTTPException(status_code=404, detail=f"Patient with ID {appointment.patient_id} not found.")
    
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
                tenant_id=appointment_data["tenant_id"],
                appointment_date=appointment_data["appointment_date"],
                appointment_time=appointment_data["appointment_time"],
                status=appointment_data["status"],
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
                synced_to_main=False
            )
            db_session.add(new_appointment)
            db_session.commit()
            db_session.refresh(new_appointment)
            sync_local_to_main()  # Sync after creating appointment
            return {"database": "Local PostgreSQL", "appointment": appointment_to_dict(new_appointment)}
        except Exception as e:  # pylint: disable=broad-except
            db_session.rollback()
            raise HTTPException(status_code=500, detail=f"Error creating appointment: {str(e)}")
    # Fallback to raw SQL
    elif local_postgres_cursor:
        try:
            local_postgres_cursor.execute("""
                INSERT INTO appointments (patient_id, tenant_id, appointment_date, appointment_time, status,
                                        doctor_name, appointment_type, notes, payment_pending, follow_up_date,
                                        diagnosis, treatment, visit_charge, medication_charge, total_charge, is_waived)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id, patient_id, tenant_id, appointment_date, appointment_time, status,
                         doctor_name, appointment_type, notes, payment_pending, follow_up_date,
                         diagnosis, treatment, visit_charge, medication_charge, total_charge, is_waived,
                         created_at, updated_at
            """, (
                appointment_data["patient_id"], appointment_data["tenant_id"],
                appointment_data["appointment_date"], appointment_data["appointment_time"],
                appointment_data["status"], appointment_data.get("doctor_name"),
                appointment_data.get("appointment_type"), appointment_data.get("notes"),
                appointment_data.get("payment_pending", False), appointment_data.get("follow_up_date"),
                appointment_data.get("diagnosis"), appointment_data.get("treatment"),
                appointment_data["visit_charge"], appointment_data["medication_charge"],
                appointment_data["total_charge"], appointment_data.get("is_waived", False)
            ))
            record = local_postgres_cursor.fetchone()
            local_postgres_conn.commit()
            
            if record:
                columns = ["id", "patient_id", "tenant_id", "appointment_date", "appointment_time", "status",
                          "doctor_name", "appointment_type", "notes", "payment_pending", "follow_up_date",
                          "diagnosis", "treatment", "visit_charge", "medication_charge", "total_charge", "is_waived",
                          "created_at", "updated_at"]
                appointment_dict = dict(zip(columns, record))
                sync_local_to_main()  # Sync after creating appointment
                return {"database": "Local PostgreSQL", "appointment": appointment_dict}
        except Exception as e:  # pylint: disable=broad-except
            local_postgres_conn.rollback()
            raise HTTPException(status_code=500, detail=f"Error creating appointment: {str(e)}")
    
    raise HTTPException(status_code=500, detail="Database connection not available")

@router.get("/{appointment_id}")
def get_appointment(appointment_id: int):
    """Get a single appointment by ID"""
    tenant_id = get_tenant_id()
    appointment_data = get_appointment_by_id(appointment_id, tenant_id)
    if appointment_data:
        if isinstance(appointment_data, dict):
            return {"database": "Local PostgreSQL", "appointment": appointment_data}
        return {"database": "Local PostgreSQL", "appointment": appointment_to_dict(appointment_data)}
    raise HTTPException(status_code=404, detail=f"Appointment with ID {appointment_id} not found.")

@router.put("/{appointment_id}")
def update_appointment(appointment_id: int, appointment: AppointmentUpdate):
    """Update an appointment"""
    tenant_id = get_tenant_id()
    
    if not check_appointment_exists(appointment_id, tenant_id):
        raise HTTPException(status_code=404, detail=f"Appointment with ID {appointment_id} not found.")
    update_data = appointment.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")
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
                raise HTTPException(status_code=404, detail=f"Appointment with ID {appointment_id} not found.")
            
            # Update fields
            for key, value in update_data.items():
                setattr(appointment, key, value)
            
            from datetime import datetime
            appointment.updated_at = datetime.now()
            appointment.synced_to_main = False
            
            db_session.commit()
            db_session.refresh(appointment)
            sync_local_to_main()  # Sync after updating appointment
            return {"database": "Local PostgreSQL", "appointment": appointment_to_dict(appointment)}
        except HTTPException:
            raise
        except Exception as e:  # pylint: disable=broad-except
            db_session.rollback()
            raise HTTPException(status_code=500, detail=f"Error updating appointment: {str(e)}")
    # Fallback to raw SQL
    elif local_postgres_cursor:
        try:
            set_clauses = []
            params = []
            for key, value in update_data.items():
                set_clauses.append(f"{key} = %s")
                params.append(value)
            
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
            local_postgres_cursor.execute(query, params)
            record = local_postgres_cursor.fetchone()
            local_postgres_conn.commit()
            
            if record:
                columns = ["id", "patient_id", "tenant_id", "appointment_date", "appointment_time", "status",
                          "doctor_name", "appointment_type", "notes", "payment_pending", "follow_up_date",
                          "diagnosis", "treatment", "visit_charge", "medication_charge", "total_charge", "is_waived",
                          "created_at", "updated_at"]
                appointment_dict = dict(zip(columns, record))
                sync_local_to_main()  # Sync after updating appointment
                return {"database": "Local PostgreSQL", "appointment": appointment_dict}
        except Exception as e:  # pylint: disable=broad-except
            local_postgres_conn.rollback()
            raise HTTPException(status_code=500, detail=f"Error updating appointment: {str(e)}")
    
    raise HTTPException(status_code=500, detail="Database connection not available")

@router.delete("/{appointment_id}")
def delete_appointment(appointment_id: int):
    """Delete an appointment"""
    tenant_id = get_tenant_id()
    
    if not check_appointment_exists(appointment_id, tenant_id):
        raise HTTPException(status_code=404, detail=f"Appointment with ID {appointment_id} not found.")
    
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
                raise HTTPException(status_code=404, detail=f"Appointment with ID {appointment_id} not found.")
        except HTTPException:
            raise
        except Exception as e:  # pylint: disable=broad-except
            db_session.rollback()
            raise HTTPException(status_code=500, detail=f"Error deleting appointment: {str(e)}")
    # Fallback to raw SQL
    elif local_postgres_cursor:
        try:
            local_postgres_cursor.execute("DELETE FROM appointments WHERE id = %s AND tenant_id = %s", (appointment_id, tenant_id))
            local_postgres_conn.commit()
            return {"message": f"Appointment with ID {appointment_id} deleted successfully"}
        except Exception as e:  # pylint: disable=broad-except
            local_postgres_conn.rollback()
            raise HTTPException(status_code=500, detail=f"Error deleting appointment: {str(e)}")
    
    raise HTTPException(status_code=500, detail="Database connection not available")

@router.post("/{appointment_id}/complete")
def complete_appointment(appointment_id: int):
    """Mark an appointment as completed"""
    tenant_id = get_tenant_id()
    
    appointment_data = get_appointment_by_id(appointment_id, tenant_id)
    if not appointment_data:
        raise HTTPException(status_code=404, detail=f"Appointment with ID {appointment_id} not found.")
    
    if local_postgres_cursor:
        try:
            local_postgres_cursor.execute("""
                UPDATE appointments 
                SET status = 'Completed', updated_at = CURRENT_TIMESTAMP
                WHERE id = %s AND tenant_id = %s
                RETURNING id, patient_id, tenant_id, appointment_date, appointment_time, status,
                         doctor_name, appointment_type, notes, payment_pending, follow_up_date,
                         diagnosis, treatment, visit_charge, medication_charge, total_charge, is_waived,
                         created_at, updated_at
            """, (appointment_id, tenant_id))
            record = local_postgres_cursor.fetchone()
            local_postgres_conn.commit()
            
            if record:
                columns = ["id", "patient_id", "tenant_id", "appointment_date", "appointment_time", "status",
                          "doctor_name", "appointment_type", "notes", "payment_pending", "follow_up_date",
                          "diagnosis", "treatment", "visit_charge", "medication_charge", "total_charge", "is_waived",
                          "created_at", "updated_at"]
                appointment_dict = dict(zip(columns, record))
                return {"database": "Local PostgreSQL", "appointment": appointment_dict, "message": "Appointment marked as completed"}
        except Exception as e:  # pylint: disable=broad-except
            local_postgres_conn.rollback()
            raise HTTPException(status_code=500, detail=f"Error completing appointment: {str(e)}")
    
    raise HTTPException(status_code=500, detail="Database connection not available")
