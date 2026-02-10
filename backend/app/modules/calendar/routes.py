from fastapi import APIRouter, Depends, Query, HTTPException
from typing import Optional, Tuple
from datetime import date, timedelta, time
from app.core.dependencies import get_current_active_user
from app.core.config import settings
from app.core.db_utils import get_db_session
from app.modules.appointments.models import AppointmentsModel
from app.modules.patients.models import PatientModel
from app.modules.users.models import UserModel
from app.core.date_helpers import string_to_date, date_to_string
from sqlalchemy import and_, or_

router = APIRouter()

def get_tenant_id() -> str:
    """Get tenant ID from settings"""
    return settings.TENANT_ID

def get_week_start_end(week_start_str: Optional[str] = None) -> Tuple[date, date]:
    """Get start and end dates for a week. Defaults to current week."""
    today = date.today()
    
    if week_start_str:
        week_start_date = string_to_date(week_start_str)
        if not week_start_date:
            # Invalid date, default to current week
            days_since_monday = today.weekday()
            week_start_date = today - timedelta(days=days_since_monday)
    else:
        # Get start of current week (Monday)
        days_since_monday = today.weekday()
        week_start_date = today - timedelta(days=days_since_monday)
    
    week_end_date = week_start_date + timedelta(days=6)  # Sunday
    
    return week_start_date, week_end_date

def format_time_for_calendar(time_obj: Optional[time]) -> str:
    """Format time object for calendar display (e.g., '8:00 AM', '2:00 PM')"""
    if not time_obj:
        return ""
    
    hour = time_obj.hour
    minute = time_obj.minute
    
    if hour == 0:
        display_hour = 12
        period = "AM"
    elif hour < 12:
        display_hour = hour
        period = "AM"
    elif hour == 12:
        display_hour = 12
        period = "PM"
    else:
        display_hour = hour - 12
        period = "PM"
    
    return f"{display_hour}:{minute:02d} {period}"

@router.get("/")
async def get_calendar(
    week_start: Optional[str] = Query(None, description="Week start date (dd/mm/yyyy). Defaults to current week"),
    current_user: dict = Depends(get_current_active_user)
):
    """
    Get calendar data for appointments.
    Defaults to current week if week_start is not provided.
    Returns appointments grouped by date and time.
    """
    tenant_id = get_tenant_id()
    
    # Get week start and end dates
    week_start_date, week_end_date = get_week_start_end(week_start)
    
    try:
        with get_db_session() as session:
            # Get all appointments for the week with patient data
            appointments = session.query(
                AppointmentsModel,
                PatientModel.firstname,
                PatientModel.lastname
            ).join(
                PatientModel, AppointmentsModel.patient_id == PatientModel.id
            ).filter(
                and_(
                    AppointmentsModel.tenant_id == tenant_id,
                    AppointmentsModel.appointment_date >= week_start_date,
                    AppointmentsModel.appointment_date <= week_end_date
                )
            ).order_by(
                AppointmentsModel.appointment_date.asc(),
                AppointmentsModel.appointment_time.asc()
            ).all()
            
            # Group appointments by date and time
            calendar_data = {}
            
            for appointment_row in appointments:
                appointment = appointment_row[0]  # AppointmentsModel
                patient_firstname = appointment_row[1]  # PatientModel.firstname
                patient_lastname = appointment_row[2]  # PatientModel.lastname
                
                appt_date = appointment.appointment_date
                date_str = date_to_string(appt_date)
                
                if date_str not in calendar_data:
                    calendar_data[date_str] = []
                
                # Format patient name
                patient_name = f"{patient_firstname.title()} {patient_lastname.title()}".strip() if patient_firstname and patient_lastname else ""
                
                # Format time
                time_str = format_time_for_calendar(appointment.appointment_time)
                
                # Determine status color (based on status)
                status_color_map = {
                    "Scheduled": "green",
                    "In Progress": "blue",
                    "Checked In": "blue",
                    "No Show": "purple",
                    "Cancelled": "red",
                    "Checked Out": "gray",
                    "Reschedule": "orange"
                }
                status_color = status_color_map.get(appointment.status, "gray")
                
                calendar_data[date_str].append({
                    "id": appointment.id,
                    "patient_name": patient_name,
                    "patient_id": appointment.patient_id,
                    "time": time_str,
                    "status": appointment.status,
                    "status_color": status_color,
                    "purpose": appointment.purpose or "Schedule",
                    "doctor_name": appointment.doctor_name or "",
                    "doctor_id": appointment.doctor_id
                })
            
            # Ensure all days in the week are present (even if empty)
            week_days = {}
            current_date = week_start_date
            while current_date <= week_end_date:
                date_str = date_to_string(current_date)
                week_days[date_str] = {
                    "date": date_str,
                    "day_name": current_date.strftime("%A"),
                    "day_number": current_date.day,
                    "appointments": calendar_data.get(date_str, [])
                }
                current_date += timedelta(days=1)
            
            return {
                "week_start": date_to_string(week_start_date),
                "week_end": date_to_string(week_end_date),
                "days": list(week_days.values()),
                "total_appointments": len(appointments)
            }
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching calendar data: {str(e)}")
