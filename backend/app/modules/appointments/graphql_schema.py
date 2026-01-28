"""GraphQL schema for Appointments module (Strawberry)"""
import strawberry
from typing import Optional, List
from app.common.graphql_types import PaginationInfo

@strawberry.type
class AppointmentType:
    """GraphQL Appointment type"""
    id: Optional[int] = None
    tenant_id: Optional[str] = None
    patient_id: int
    patient: Optional[str] = None  # Patient name
    number: Optional[str] = None  # Patient phone number
    appointment_date: str
    appointment_time: Optional[str] = None  # Formatted date + time for table view
    status: str
    doctor_name: Optional[str] = None
    purpose: Optional[str] = None
    interval: Optional[str] = None
    payment: str
    follow_up_date: Optional[str] = None

@strawberry.input
class AppointmentInput:
    """GraphQL Appointment input for creating"""
    patient_id: int
    doctor_id: int
    appointment_date: Optional[str] = None  # Optional, defaults to today
    appointment_time: Optional[str] = None  # Formats like "2.00 pm", "9.00 am", or "14:30"
    status: Optional[str] = "Scheduled"
    purpose: str  # Schedule, follow_up, procedure
    interval: str  # Appointment interval - stores text value from UI dropdown
    payment: Optional[str] = "Pending"
    follow_up_date: Optional[str] = None

@strawberry.input
class AppointmentUpdateInput:
    """GraphQL Appointment input for updating"""
    appointment_date: Optional[str] = None
    appointment_time: Optional[str] = None
    status: Optional[str] = None
    doctor_id: Optional[int] = None
    purpose: Optional[str] = None
    interval: Optional[str] = None
    payment: Optional[str] = None
    follow_up_date: Optional[str] = None

@strawberry.type
class AppointmentsResponse:
    """Response type for paginated appointments"""
    appointments: List[AppointmentType]
    pagination: PaginationInfo

@strawberry.type
class Query:
    """GraphQL Query type for Appointments"""
    
    @strawberry.field
    async def appointment(self, appointment_id: int) -> Optional[AppointmentType]:
        """Get a single appointment by ID"""
        from app.modules.appointments.routes import get_appointment
        from fastapi import HTTPException
        
        try:
            # Note: GraphQL calls route directly, auth should be handled via GraphQL context
            result = await get_appointment(appointment_id, {})  # Pass empty dict for current_user
            # Route returns {"database": "PostgreSQL", "appointment": {...}}
            appointment_data = result.get("appointment") if isinstance(result, dict) else None
            if appointment_data:
                return AppointmentType(**appointment_data)
            return None
        except HTTPException:
            return None
    
    @strawberry.field
    async def appointments(
        self,
        today: Optional[bool] = True,
        status: Optional[str] = None,
        doctor_id: Optional[int] = None,
        page: int = 1,
        limit: int = 10
    ) -> AppointmentsResponse:
        """Get all appointments with optional filters"""
        from app.modules.appointments.routes import get_appointments
        from fastapi import HTTPException
        
        try:
            # Note: GraphQL calls route directly, auth should be handled via GraphQL context
            result = await get_appointments(
                today=today,
                status=status,
                doctor_id=doctor_id,
                page=page,
                limit=limit,
                current_user={}
            )
            appointments_list = []
            for apt in result.get("appointments", []):
                apt_data = apt.copy()
                appointments_list.append(AppointmentType(**apt_data))
            
            pagination = PaginationInfo(**result.get("pagination", {}))
            return AppointmentsResponse(
                appointments=appointments_list,
                pagination=pagination
            )
        except HTTPException:
            return AppointmentsResponse(
                appointments=[],
                pagination=PaginationInfo(
                    total=0,
                    page=page,
                    limit=limit,
                    total_pages=0,
                    has_next=False,
                    has_prev=False
                )
            )
    
    @strawberry.field
    async def appointment_queue(self) -> List[AppointmentType]:
        """Get appointment queue for today"""
        from app.modules.appointments.routes import get_queue
        from fastapi import HTTPException
        
        try:
            # Note: GraphQL calls route directly, auth should be handled via GraphQL context
            result = await get_queue({})  # Pass empty dict for current_user
            appointments_list = []
            for apt in result.get("queue", []):
                apt_data = apt.copy()
                appointments_list.append(AppointmentType(**apt_data))
            return appointments_list
        except HTTPException:
            return []

@strawberry.type
class Mutation:
    """GraphQL Mutation type for Appointments"""
    
    @strawberry.mutation
    async def create_appointment(self, appointment: AppointmentInput) -> AppointmentType:
        """Create a new appointment"""
        from app.modules.appointments.routes import create_appointment
        from app.modules.appointments.schemas import AppointmentCreate
        from fastapi import HTTPException
        
        # Convert GraphQL input to Pydantic model
        appointment_data = AppointmentCreate(
            patient_id=appointment.patient_id,
            doctor_id=appointment.doctor_id,
            appointment_date=appointment.appointment_date,
            appointment_time=appointment.appointment_time,
            status=appointment.status or "Scheduled",
            purpose=appointment.purpose,
            interval=appointment.interval,
            payment=appointment.payment or "Pending",
            follow_up_date=appointment.follow_up_date
        )
        
        try:
            # Note: GraphQL calls route directly, auth should be handled via GraphQL context
            result = await create_appointment(appointment_data, {})  # Pass empty dict for current_user
            # Route returns {"database": "PostgreSQL", "appointment": {...}}
            appointment_result = result.get("appointment") if isinstance(result, dict) else None
            if appointment_result:
                return AppointmentType(**appointment_result)
            raise ValueError("Appointment created but could not retrieve from response")
        except HTTPException as e:
            raise ValueError(f"Failed to create appointment: {e.detail}") from e
    
    @strawberry.mutation
    async def update_appointment(
        self,
        appointment_id: int,
        appointment: AppointmentUpdateInput
    ) -> Optional[AppointmentType]:
        """Update an existing appointment"""
        from app.modules.appointments.routes import update_appointment, get_appointment
        from app.modules.appointments.schemas import AppointmentUpdate
        from fastapi import HTTPException
        
        # Convert GraphQL input to Pydantic model
        appointment_data = AppointmentUpdate(
            appointment_date=appointment.appointment_date,
            appointment_time=appointment.appointment_time,
            status=appointment.status,
            doctor_id=appointment.doctor_id,
            purpose=appointment.purpose,
            interval=appointment.interval,
            payment=appointment.payment,
            follow_up_date=appointment.follow_up_date
        )
        
        try:
            # Note: GraphQL calls route directly, auth should be handled via GraphQL context
            await update_appointment(appointment_id, appointment_data, {})  # Pass empty dict for current_user
            # Fetch the updated appointment
            result = await get_appointment(appointment_id, {})
            # Route returns {"database": "PostgreSQL", "appointment": {...}}
            appointment_result = result.get("appointment") if isinstance(result, dict) else None
            if appointment_result:
                return AppointmentType(**appointment_result)
            return None
        except HTTPException as e:
            raise ValueError(f"Failed to update appointment: {e.detail}") from e
    
    @strawberry.mutation
    async def delete_appointment(self, appointment_id: int) -> bool:
        """Delete an appointment by ID"""
        from app.modules.appointments.routes import delete_appointment
        from fastapi import HTTPException
        
        try:
            # Note: GraphQL calls route directly, auth should be handled via GraphQL context
            await delete_appointment(appointment_id, {})  # Pass empty dict for current_user
            return True
        except HTTPException:
            return False
    
    @strawberry.mutation
    async def complete_appointment(self, appointment_id: int) -> Optional[AppointmentType]:
        """Mark an appointment as completed"""
        from app.modules.appointments.routes import complete_appointment
        from fastapi import HTTPException
        
        try:
            # Note: GraphQL calls route directly, auth should be handled via GraphQL context
            result = await complete_appointment(appointment_id, {})  # Pass empty dict for current_user
            # Route returns {"database": "PostgreSQL", "appointment": {...}}
            appointment_result = result.get("appointment") if isinstance(result, dict) else None
            if appointment_result:
                return AppointmentType(**appointment_result)
            return None
        except HTTPException as e:
            raise ValueError(f"Failed to complete appointment: {e.detail}") from e

# Create the GraphQL schema
schema = strawberry.Schema(query=Query, mutation=Mutation)

