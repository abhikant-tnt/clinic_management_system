"""GraphQL schema for Patient module (Strawberry)"""
import re
import strawberry
from typing import Optional, List

@strawberry.type
class PatientType:
    """GraphQL Patient type"""
    id: Optional[int] = None
    tenant_id: Optional[str] = None
    title: str
    firstname: str
    lastname: str
    dob: str
    age: int
    gender: str
    phone: str
    email: Optional[str] = None
    primary_doctor: Optional[str] = None
    address1: str
    address2: Optional[str] = None
    country: Optional[str] = None
    city: str
    state: str
    pincode: str
    emergency_contact_name: str
    emergency_contact_phone: str
    registration_date: str
    referral_source: str
    referral_subcategory: Optional[str] = None
    patient_status: str
    important_notes: Optional[str] = None
    last_visit_date: Optional[str] = None
    purpose: Optional[str] = None
    past_medical_record: Optional[str] = None
    dermatological_history: Optional[str] = None
    medications: Optional[str] = None
    surgeries: Optional[str] = None
    hormonal_issues: Optional[str] = None

@strawberry.input
class PatientInput:
    """GraphQL Patient input for creating/updating"""
    title: str
    firstname: str
    lastname: str
    dob: str
    gender: str
    phone: str
    email: Optional[str] = None
    primary_doctor: Optional[str] = None
    address1: str
    address2: Optional[str] = None
    country: Optional[str] = None
    city: str
    state: str
    pincode: str
    emergency_contact_name: str
    emergency_contact_phone: str
    registration_date: str
    referral_source: str
    referral_subcategory: Optional[str] = None
    patient_status: str
    important_notes: Optional[str] = None
    last_visit_date: Optional[str] = None
    purpose: Optional[str] = None
    past_medical_record: Optional[str] = None
    dermatological_history: Optional[str] = None
    medications: Optional[str] = None
    surgeries: Optional[str] = None
    hormonal_issues: Optional[str] = None

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
        from app.modules.patients.schemas import PatientCreate
        from fastapi import HTTPException
        # Convert GraphQL input to Pydantic model
        patient_data = PatientCreate(
            title=patient.title,
            firstname=patient.firstname,
            lastname=patient.lastname,
            dob=patient.dob,
            gender=patient.gender,
            phone=patient.phone,
            email=patient.email,
            primary_doctor=patient.primary_doctor,
            address1=patient.address1,
            address2=patient.address2,
            country=patient.country,
            city=patient.city,
            state=patient.state,
            pincode=patient.pincode,
            emergency_contact_name=patient.emergency_contact_name,
            emergency_contact_phone=patient.emergency_contact_phone,
            registration_date=patient.registration_date,
            referral_source=patient.referral_source,
            referral_subcategory=patient.referral_subcategory,
            patient_status=patient.patient_status,
            important_notes=patient.important_notes,
            last_visit_date=patient.last_visit_date,
            purpose=patient.purpose,
            past_medical_record=patient.past_medical_record,
            dermatological_history=patient.dermatological_history,
            medications=patient.medications,
            surgeries=patient.surgeries,
            hormonal_issues=patient.hormonal_issues
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
        from app.modules.patients.schemas import PatientUpdate
        from fastapi import HTTPException
        
        # Convert GraphQL input to Pydantic model
        patient_data = PatientUpdate(
            title=patient.title,
            firstname=patient.firstname,
            lastname=patient.lastname,
            dob=patient.dob,
            gender=patient.gender,
            phone=patient.phone,
            email=patient.email,
            primary_doctor=patient.primary_doctor,
            address1=patient.address1,
            address2=patient.address2,
            country=patient.country,
            city=patient.city,
            state=patient.state,
            pincode=patient.pincode,
            emergency_contact_name=patient.emergency_contact_name,
            emergency_contact_phone=patient.emergency_contact_phone,
            registration_date=patient.registration_date,
            referral_source=patient.referral_source,
            referral_subcategory=patient.referral_subcategory,
            patient_status=patient.patient_status,
            important_notes=patient.important_notes,
            last_visit_date=patient.last_visit_date,
            purpose=patient.purpose,
            past_medical_record=patient.past_medical_record,
            dermatological_history=patient.dermatological_history,
            medications=patient.medications,
            surgeries=patient.surgeries,
            hormonal_issues=patient.hormonal_issues
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