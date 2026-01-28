"""GraphQL schema for Patient module (Strawberry)"""
import re
import strawberry
from typing import Optional, List
from app.common.graphql_types import PaginationInfo

@strawberry.type
class PatientType:
    """GraphQL Patient type - updated to match new schema"""
    id: Optional[int] = None
    tenant_id: Optional[str] = None
    firstname: str
    lastname: str
    dob: str
    age: int
    gender: str
    phone: str
    email: Optional[str] = None
    primary_doctor: Optional[int] = None  # Staff ID
    blood_group: Optional[str] = None
    status: str
    vip: bool = False  # VIP status
    address1: str
    address2: Optional[str] = None
    country: Optional[str] = None
    country2: Optional[str] = None
    city: Optional[str] = None
    city2: Optional[str] = None
    state: Optional[str] = None
    state2: Optional[str] = None
    pincode: Optional[str] = None
    pincode2: Optional[str] = None
    image: Optional[str] = "None"
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    registration_date: str
    referral_source: Optional[str] = None
    referral_subcategory: Optional[str] = None
    patient_status: Optional[str] = None  # Legacy field for backward compatibility
    past_medical_record: Optional[str] = None
    allergies: Optional[str] = None
    dermatological_history: Optional[str] = None
    medications: Optional[str] = None
    surgeries: Optional[str] = None
    hormonal_issues: Optional[str] = None
    lifestyle_assessment: Optional[str] = None
    billing_firstname: Optional[str] = None
    billing_lastname: Optional[str] = None
    billing_email: Optional[str] = None
    billing_gstin: Optional[str] = None
    billing_phone: Optional[str] = None
    billing_address1: Optional[str] = None
    billing_address2: Optional[str] = None
    billing_country: Optional[str] = None
    billing_country2: Optional[str] = None
    billing_state: Optional[str] = None
    billing_state2: Optional[str] = None
    billing_city: Optional[str] = None
    billing_city2: Optional[str] = None
    billing_pincode: Optional[str] = None
    billing_pincode2: Optional[str] = None

@strawberry.input
class PatientInput:
    """GraphQL Patient input for creating/updating - updated to match new schema"""
    firstname: str
    lastname: str
    dob: str
    gender: str
    phone: str
    email: Optional[str] = None
    primary_doctor: Optional[int] = None  # Staff ID
    blood_group: Optional[str] = None
    status: str
    vip: bool = False  # VIP status
    address1: str
    address2: Optional[str] = None
    country: Optional[str] = None
    country2: Optional[str] = None
    city: Optional[str] = None
    city2: Optional[str] = None
    state: Optional[str] = None
    state2: Optional[str] = None
    pincode: Optional[str] = None
    pincode2: Optional[str] = None
    image: Optional[str] = "None"
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    registration_date: Optional[str] = None  # Auto-filled if not provided
    referral_source: Optional[str] = None
    referral_subcategory: Optional[str] = None
    past_medical_record: Optional[str] = "None"
    allergies: Optional[str] = "None"
    dermatological_history: Optional[str] = "None"
    medications: Optional[str] = "None"
    surgeries: Optional[str] = "None"
    hormonal_issues: Optional[str] = "None"
    lifestyle_assessment: Optional[str] = "None"
    billing_firstname: Optional[str] = None
    billing_lastname: Optional[str] = None
    billing_email: Optional[str] = None
    billing_gstin: Optional[str] = None
    billing_phone: Optional[str] = None
    billing_address1: Optional[str] = None
    billing_address2: Optional[str] = None
    billing_country: Optional[str] = None
    billing_country2: Optional[str] = None
    billing_state: Optional[str] = None
    billing_state2: Optional[str] = None
    billing_city: Optional[str] = None
    billing_city2: Optional[str] = None
    billing_pincode: Optional[str] = None
    billing_pincode2: Optional[str] = None

@strawberry.type
class PatientsResponse:
    """Response type for paginated patients"""
    patients: List[PatientType]
    pagination: PaginationInfo

@strawberry.type
class Query:
    """GraphQL Query type""" 
    @strawberry.field
    async def patient(self, patient_id: int) -> Optional[PatientType]:
        """Get a single patient by ID"""
        from app.modules.patients.routes import get_patient
        from fastapi import HTTPException
        
        try:
            result = await get_patient(patient_id, {})  # Pass empty dict for current_user
            if "patient" in result:
                patient_data = result["patient"]
                return PatientType(**patient_data)
            return None
        except HTTPException:
            return None

    @strawberry.field
    async def patients(
        self, 
        page: int = 1, 
        limit: int = 10
    ) -> PatientsResponse:
        """Get all patients with pagination"""
        from app.modules.patients.routes import get_patients
        result = await get_patients(page=page, limit=limit, current_user={})
        patients_list = [PatientType(**p) for p in result["patients"]]
        pagination = PaginationInfo(**result["pagination"])
        return PatientsResponse(
            patients=patients_list,
            pagination=pagination
        )
    
    @strawberry.field
    async def search_patients(
        self,
        q: str,
        page: int = 1,
        limit: int = 10
    ) -> PatientsResponse:
        """Search patients by name, id, phone, or email"""
        from app.modules.patients.routes import advanced_search_patients
        from fastapi import HTTPException
        
        try:
            result = await advanced_search_patients(q=q, page=page, limit=limit, current_user={})
            patients_list = [PatientType(**p) for p in result.get("patients", [])]
            pagination = PaginationInfo(**result.get("pagination", {
                "total": 0,
                "page": page,
                "limit": limit,
                "total_pages": 0,
                "has_next": False,
                "has_prev": False
            }))
            
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
    async def create_patient(self, patient: PatientInput) -> PatientType:
        """Create a new patient"""
        from app.modules.patients.routes import create_patient, get_patient
        from app.modules.patients.schemas import PatientCreate
        from fastapi import HTTPException
        # Convert GraphQL input to Pydantic model
        patient_data = PatientCreate(
            firstname=patient.firstname,
            lastname=patient.lastname,
            dob=patient.dob,
            gender=patient.gender,
            phone=patient.phone,
            email=patient.email or "",
            primary_doctor=patient.primary_doctor,
            blood_group=patient.blood_group,
            status=patient.status,
            address1=patient.address1,
            address2=patient.address2,
            country=patient.country,
            country2=patient.country2,
            city=patient.city,
            city2=patient.city2,
            state=patient.state,
            state2=patient.state2,
            pincode=patient.pincode,
            pincode2=patient.pincode2,
            image=patient.image,
            emergency_contact_name=patient.emergency_contact_name,
            emergency_contact_phone=patient.emergency_contact_phone,
            registration_date=patient.registration_date,
            referral_source=patient.referral_source,
            referral_subcategory=patient.referral_subcategory,
            past_medical_record=patient.past_medical_record,
            allergies=patient.allergies,
            dermatological_history=patient.dermatological_history,
            medications=patient.medications,
            surgeries=patient.surgeries,
            hormonal_issues=patient.hormonal_issues,
            lifestyle_assessment=patient.lifestyle_assessment,
            billing_firstname=patient.billing_firstname,
            billing_lastname=patient.billing_lastname,
            billing_email=patient.billing_email,
            billing_gstin=patient.billing_gstin,
            billing_phone=patient.billing_phone,
            billing_address1=patient.billing_address1,
            billing_address2=patient.billing_address2,
            billing_country=patient.billing_country,
            billing_country2=patient.billing_country2,
            billing_state=patient.billing_state,
            billing_state2=patient.billing_state2,
            billing_city=patient.billing_city,
            billing_city2=patient.billing_city2,
            billing_pincode=patient.billing_pincode,
            billing_pincode2=patient.billing_pincode2
        )
        
        try:
            result = await create_patient(patient_data, {})  # Pass empty dict for current_user
            # Extract patient ID from the response message
            # Format: "Patient created successfully with ID {id}."
            message = result.get("message", "")
            match = re.search(r"ID (\d+)", message)
            if match:
                patient_id = int(match.group(1))
                # Fetch the created patient
                patient_result = await get_patient(patient_id, {})
                if "patient" in patient_result:
                    return PatientType(**patient_result["patient"])
            raise ValueError("Patient created but could not retrieve ID from response")
        except HTTPException as e:
            raise ValueError(f"Failed to create patient: {e.detail}") from e

    @strawberry.mutation
    async def update_patient(
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
            firstname=patient.firstname,
            lastname=patient.lastname,
            dob=patient.dob,
            gender=patient.gender,
            phone=patient.phone,
            email=patient.email,
            primary_doctor=patient.primary_doctor,
            blood_group=patient.blood_group,
            status=patient.status,
            address1=patient.address1,
            address2=patient.address2,
            country=patient.country,
            country2=patient.country2,
            city=patient.city,
            city2=patient.city2,
            state=patient.state,
            state2=patient.state2,
            pincode=patient.pincode,
            pincode2=patient.pincode2,
            image=patient.image,
            emergency_contact_name=patient.emergency_contact_name,
            emergency_contact_phone=patient.emergency_contact_phone,
            registration_date=patient.registration_date,
            referral_source=patient.referral_source,
            referral_subcategory=patient.referral_subcategory,
            past_medical_record=patient.past_medical_record,
            allergies=patient.allergies,
            dermatological_history=patient.dermatological_history,
            medications=patient.medications,
            surgeries=patient.surgeries,
            hormonal_issues=patient.hormonal_issues,
            lifestyle_assessment=patient.lifestyle_assessment,
            billing_firstname=patient.billing_firstname,
            billing_lastname=patient.billing_lastname,
            billing_email=patient.billing_email,
            billing_gstin=patient.billing_gstin,
            billing_phone=patient.billing_phone,
            billing_address1=patient.billing_address1,
            billing_address2=patient.billing_address2,
            billing_country=patient.billing_country,
            billing_country2=patient.billing_country2,
            billing_state=patient.billing_state,
            billing_state2=patient.billing_state2,
            billing_city=patient.billing_city,
            billing_city2=patient.billing_city2,
            billing_pincode=patient.billing_pincode,
            billing_pincode2=patient.billing_pincode2
        )
        
        try:
            await update_patient(patient_id, patient_data, {})  # Pass empty dict for current_user
            # Fetch the updated patient
            result = await get_patient(patient_id, {})
            if "patient" in result:
                return PatientType(**result["patient"])
            return None
        except HTTPException as e:
            raise ValueError(f"Failed to update patient: {e.detail}") from e

    @strawberry.mutation
    async def delete_patient(self, patient_id: int) -> bool:
        """Delete a patient by ID"""
        from app.modules.patients.routes import delete_patient
        from fastapi import HTTPException
        
        try:
            await delete_patient(patient_id, {})  # Pass empty dict for current_user
            return True
        except HTTPException:
            return False

# Create the GraphQL schema
schema = strawberry.Schema(query=Query, mutation=Mutation)