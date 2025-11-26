"""
GraphQL schema for Patient module using Strawberry
"""
import re
import strawberry
from typing import Optional, List



@strawberry.type
class PatientType:
    """GraphQL Patient type"""
    id: Optional[int] = None
    tenant_id: Optional[str] = None
    name: str
    age: int
    gender: str
    phone: str
    email: Optional[str] = None
    date_of_birth: Optional[str] = None
    address: Optional[str] = None
    registration_date: str
    referral_source: str
    referral_subcategory: Optional[str] = None
    patient_status: str
    important_notes: Optional[str] = None
    billed_amount: float
    outstanding_amount: float


@strawberry.input
class PatientInput:
    """GraphQL Patient input for creating/updating"""
    name: str
    age: int
    gender: str
    phone: str
    email: Optional[str] = None
    date_of_birth: Optional[str] = None
    address: Optional[str] = None
    registration_date: str
    referral_source: str
    referral_subcategory: Optional[str] = None
    patient_status: str
    important_notes: Optional[str] = None
    billed_amount: float
    outstanding_amount: float


@strawberry.type
class PaginationInfo:
    """Pagination information"""
    total: int
    page: int
    limit: int
    total_pages: int
    has_next: bool
    has_prev: bool


@strawberry.type
class PatientsResponse:
    """Response type for paginated patients"""
    patients: List[PatientType]
    pagination: PaginationInfo


@strawberry.type
class Query:
    """GraphQL Query type""" 
    @strawberry.field
    def patient(self, patient_id: int) -> Optional[PatientType]:
        """Get a single patient by ID"""
        from app.modules.patients.routes import get_patient
        from fastapi import HTTPException
        
        try:
            result = get_patient(patient_id)
            if "patient" in result:
                patient_data = result["patient"]
                return PatientType(**patient_data)
            return None
        except HTTPException:
            return None
    
    @strawberry.field
    def patients(
        self, 
        page: int = 1, 
        limit: int = 10
    ) -> PatientsResponse:
        """Get all patients with pagination"""
        from app.modules.patients.routes import get_patients
        
        result = get_patients(page=page, limit=limit)
        
        patients_list = [PatientType(**p) for p in result["patients"]]
        pagination = PaginationInfo(**result["pagination"])
        
        return PatientsResponse(
            patients=patients_list,
            pagination=pagination
        )
    
    @strawberry.field
    def search_patients(
        self,
        q: str,
        page: int = 1,
        limit: int = 10
    ) -> PatientsResponse:
        """Search patients by name, id, phone, or email"""
        from app.modules.patients.routes import search_patients
        from fastapi import HTTPException
        
        try:
            result = search_patients(q=q, page=page, limit=limit)
            patients_list = [PatientType(**p) for p in result["patients"]]
            pagination = PaginationInfo(**result["pagination"])
            
            return PatientsResponse(
                patients=patients_list,
                pagination=pagination
            )
        except HTTPException:
            # Return empty result if not found
            return PatientsResponse(
                patients=[],
                pagination=PaginationInfo(
                    total=0,
                    page=page,
                    limit=limit,
                    total_pages=0,
                    has_next=False,
                    has_prev=False
                )
            )


@strawberry.type
class Mutation:
    """GraphQL Mutation type"""
    
    @strawberry.mutation
    def create_patient(self, patient: PatientInput) -> PatientType:
        """Create a new patient"""
        from app.modules.patients.routes import create_patient, get_patient
        from app.modules.patients.schemas import Patient as PatientSchema
        from fastapi import HTTPException
        # Convert GraphQL input to Pydantic model
        patient_data = PatientSchema(
            name=patient.name,
            age=patient.age,
            gender=patient.gender,
            phone=patient.phone,
            email=patient.email,
            date_of_birth=patient.date_of_birth,
            address=patient.address,
            registration_date=patient.registration_date,
            referral_source=patient.referral_source,
            referral_subcategory=patient.referral_subcategory,
            patient_status=patient.patient_status,
            important_notes=patient.important_notes,
            billed_amount=patient.billed_amount,
            outstanding_amount=patient.outstanding_amount
        )
        
        try:
            result = create_patient(patient_data)
            # Extract patient ID from the response message
            # Format: "Patient created successfully with ID {id}."
            message = result.get("message", "")
            match = re.search(r"ID (\d+)", message)
            if match:
                patient_id = int(match.group(1))
                # Fetch the created patient
                patient_result = get_patient(patient_id)
                if "patient" in patient_result:
                    return PatientType(**patient_result["patient"])
            raise ValueError("Patient created but could not retrieve ID from response")
        except HTTPException as e:
            raise ValueError(f"Failed to create patient: {e.detail}") from e
    
    @strawberry.mutation
    def update_patient(
        self, 
        patient_id: int, 
        patient: PatientInput
    ) -> Optional[PatientType]:
        """Update an existing patient"""
        from app.modules.patients.routes import update_patient, get_patient
        from app.modules.patients.schemas import Patient as PatientSchema
        from fastapi import HTTPException
        
        # Convert GraphQL input to Pydantic model
        patient_data = PatientSchema(
            name=patient.name,
            age=patient.age,
            gender=patient.gender,
            phone=patient.phone,
            email=patient.email,
            date_of_birth=patient.date_of_birth,
            address=patient.address,
            registration_date=patient.registration_date,
            referral_source=patient.referral_source,
            referral_subcategory=patient.referral_subcategory,
            patient_status=patient.patient_status,
            important_notes=patient.important_notes,
            billed_amount=patient.billed_amount,
            outstanding_amount=patient.outstanding_amount
        )
        
        try:
            update_patient(patient_id=patient_id, patient=patient_data)
            # Fetch the updated patient
            result = get_patient(patient_id)
            if "patient" in result:
                return PatientType(**result["patient"])
            return None
        except HTTPException as e:
            raise ValueError(f"Failed to update patient: {e.detail}") from e
    
    @strawberry.mutation
    def delete_patient(self, patient_id: int) -> bool:
        """Delete a patient by ID"""
        from app.modules.patients.routes import delete_patient
        from fastapi import HTTPException
        
        try:
            delete_patient(patient_id)
            return True
        except HTTPException:
            return False


# Create the GraphQL schema
schema = strawberry.Schema(query=Query, mutation=Mutation)

