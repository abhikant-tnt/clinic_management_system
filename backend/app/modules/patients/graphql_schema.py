"""
GraphQL schema for Patient module using Strawberry
"""
import strawberry
from typing import Optional, List
from datetime import datetime


@strawberry.type
class PatientType:
    """GraphQL Patient type"""
    id: Optional[int] = None
    name: str
    age: int
    phone: str
    email: Optional[str] = None
    date_of_birth: Optional[str] = None
    address: Optional[str] = None
    registration_date: str
    billed_amount: float
    outstanding_amount: float


@strawberry.input
class PatientInput:
    """GraphQL Patient input for creating/updating"""
    name: str
    age: int
    phone: str
    email: Optional[str] = None
    date_of_birth: Optional[str] = None
    address: Optional[str] = None
    registration_date: str
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
    def patient(self, id: int) -> Optional[PatientType]:
        """Get a single patient by ID"""
        from app.modules.patients.routes import get_patient
        from fastapi import HTTPException
        
        try:
            result = get_patient(id)
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
        except HTTPException as e:
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
        from app.modules.patients.routes import create_patient
        from app.modules.patients.schemas import Patient as PatientSchema
        from fastapi import HTTPException
        
        # Convert GraphQL input to Pydantic model
        patient_data = PatientSchema(
            name=patient.name,
            age=patient.age,
            phone=patient.phone,
            email=patient.email,
            date_of_birth=patient.date_of_birth,
            address=patient.address,
            registration_date=patient.registration_date,
            billed_amount=patient.billed_amount,
            outstanding_amount=patient.outstanding_amount
        )
        
        try:
            create_patient(patient_data)
            # Fetch the created patient to return it
            # We'll need to get the ID from the response or fetch by phone
            from app.modules.patients.routes import get_patients
            all_patients = get_patients(page=1, limit=1000)
            # Find the patient by phone (assuming phone is unique)
            created_patient = next(
                (p for p in all_patients["patients"] if p["phone"] == patient.phone),
                None
            )
            if created_patient:
                return PatientType(**created_patient)
            raise Exception("Patient created but could not be retrieved")
        except HTTPException as e:
            raise Exception(f"Failed to create patient: {e.detail}")
    
    @strawberry.mutation
    def update_patient(
        self, 
        id: int, 
        patient: PatientInput
    ) -> Optional[PatientType]:
        """Update an existing patient"""
        from app.modules.patients.routes import update_patient
        from app.modules.patients.schemas import Patient as PatientSchema
        from fastapi import HTTPException
        
        # Convert GraphQL input to Pydantic model
        patient_data = PatientSchema(
            name=patient.name,
            age=patient.age,
            phone=patient.phone,
            email=patient.email,
            date_of_birth=patient.date_of_birth,
            address=patient.address,
            registration_date=patient.registration_date,
            billed_amount=patient.billed_amount,
            outstanding_amount=patient.outstanding_amount
        )
        
        try:
            update_patient(patient_id=id, patient=patient_data)
            # Fetch the updated patient
            from app.modules.patients.routes import get_patient
            result = get_patient(id)
            if "patient" in result:
                return PatientType(**result["patient"])
            return None
        except HTTPException as e:
            raise Exception(f"Failed to update patient: {e.detail}")
    
    @strawberry.mutation
    def delete_patient(self, id: int) -> bool:
        """Delete a patient by ID"""
        from app.modules.patients.routes import delete_patient
        from fastapi import HTTPException
        
        try:
            delete_patient(id)
            return True
        except HTTPException:
            return False


# Create the GraphQL schema
schema = strawberry.Schema(query=Query, mutation=Mutation)

