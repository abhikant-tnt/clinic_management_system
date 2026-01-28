from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional, Literal
from datetime import date
import re

# Type aliases for dropdown options
BloodGroup = Literal["O+ve", "O-ve", "A+ve", "A-ve", "B+ve", "B-ve", "AB+ve", "AB-ve"]
Purpose = Literal["consultation", "follow up", "treatment"]
PatientStatus = Literal["scheduled", "no_show", "cancelled", "In progress", "checked_in"]

def calculate_age(dob: str) -> int:
    """Calculate age from dob in dd/mm/yyyy format"""
    day, month, year = map(int, dob.split('/'))
    birth_date = date(year, month, day)
    today = date.today()
    return today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))

def validate_phone(v: str) -> str:
    """Validate phone number: exactly 10 digits, only digits allowed"""
    v = v.strip() if v else ""
    if not v or not v.isdigit() or len(v) != 10:
        raise ValueError("Phone number must contain exactly 10 digits (numbers only)")
    return v

def validate_pincode(v: str) -> str:
    """Validate pincode: numbers only, no alphabets allowed"""
    v = v.strip() if v else ""
    if not v or not v.isdigit():
        raise ValueError("Pincode must contain only numbers, no alphabets allowed")
    return v

def validate_date_format(v: str) -> str:
    """Validate date: must be in dd/mm/yyyy format"""
    v = v.strip()
    if not re.match(r'^\d{2}/\d{2}/\d{4}$', v):
        raise ValueError("Date must be in dd/mm/yyyy format (e.g., 15/01/1994)")
    try:
        day, month, year = map(int, v.split('/'))
        current_year = date.today().year
        if day < 1 or day > 31 or month < 1 or month > 12 or year < 1900 or year > current_year:
            raise ValueError(f"Invalid date: day (1-31), month (1-12), year (1900-{current_year})")
        date(year, month, day)
    except ValueError as e:
        raise ValueError(f"Invalid date: {str(e)}") from e
    return v

def validate_date_not_future(v: str, field_name: str = "Date") -> str:
    """Validate date is not in the future"""
    v = validate_date_format(v)
    day, month, year = map(int, v.split('/'))
    date_obj = date(year, month, day)
    if date_obj > date.today():
        raise ValueError(f"{field_name} cannot be in the future")
    return v

def validate_text_max_length(v: Optional[str], max_length: int, field_name: str) -> Optional[str]:
    """Validate text field max length"""
    if v is None:
        return v
    if len(v) > max_length:
        raise ValueError(f"{field_name} cannot exceed {max_length} characters")
    return v

def to_lowercase(v: Optional[str]) -> Optional[str]:
    """Convert string to lowercase for case-insensitive storage"""
    return v.lower().strip() if v else v

class PatientCreate(BaseModel):
    """Schema for creating a patient - matches UI order"""
    tenant_id: Optional[str] = None
    
    # Personal Information - Basic Information (all required with asterisk)
    firstname: str  # Required *
    lastname: str  # Required *
    phone: str  # Required *: exactly 10 digits
    email: EmailStr  # Required *
    primary_doctor: Optional[int] = None  # Dropdown from staff table (staff ID)
    dob: str  # Required * - used to calculate age automatically
    gender: Literal["male", "female", "other"]  # Required *
    blood_group: Optional[BloodGroup] = None  # Dropdown menu
    status: PatientStatus  # Required * - values: scheduled, no_show, cancelled, In progress, checked_in
    vip: Optional[bool] = False  # VIP status
    
    # Address Information - Address 1
    address1: str  # Required
    country: Optional[str] = None  # Dropdown
    state: Optional[str] = None  # Dropdown (cascading from country)
    city: Optional[str] = None  # Dropdown (cascading from state)
    pincode: Optional[str] = None  # Required: numbers only
    
    # Address Information - Address 2
    address2: Optional[str] = None  # Optional
    country2: Optional[str] = None  # Dropdown
    state2: Optional[str] = None  # Dropdown (cascading from country2)
    city2: Optional[str] = None  # Dropdown (cascading from state2)
    pincode2: Optional[str] = None  # Optional: numbers only
    
    # Upload Image
    image: Optional[str] = "None"  # Default "none", file upload up to 50MB
    
    # Medical History (all default "None", maintain order)
    past_medical_record: Optional[str] = "None"
    allergies: Optional[str] = "None"
    dermatological_history: Optional[str] = "None"
    medications: Optional[str] = "None"
    surgeries: Optional[str] = "None"
    hormonal_issues: Optional[str] = "None"
    lifestyle_assessment: Optional[str] = "None"
    
    # Billing Information
    billing_firstname: Optional[str] = None
    billing_lastname: Optional[str] = None
    billing_phone: Optional[str] = None
    billing_email: Optional[EmailStr] = None
    billing_gstin: Optional[str] = None
    billing_address1: Optional[str] = None
    billing_country: Optional[str] = None  # Dropdown
    billing_state: Optional[str] = None  # Dropdown (cascading from billing_country)
    billing_city: Optional[str] = None  # Dropdown (cascading from billing_state)
    billing_pincode: Optional[str] = None
    billing_address2: Optional[str] = None
    billing_country2: Optional[str] = None  # Dropdown
    billing_state2: Optional[str] = None  # Dropdown (cascading from billing_country2)
    billing_city2: Optional[str] = None  # Dropdown (cascading from billing_state2)
    billing_pincode2: Optional[str] = None
    
    # Legacy fields (kept for backward compatibility, will be removed later)
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    registration_date: Optional[str] = None  # Auto-filled with today's date if not provided
    referral_source: Optional[Literal["doctor", "self", "friend", "online"]] = None
    referral_subcategory: Optional[str] = None

    @field_validator('phone', 'emergency_contact_phone', 'billing_phone')
    @classmethod
    def validate_phone_fields(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        return validate_phone(v)

    @field_validator('pincode', 'pincode2', 'billing_pincode', 'billing_pincode2')
    @classmethod
    def validate_pincode_fields(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        return validate_pincode(v)

    @field_validator('dob', 'registration_date')
    @classmethod
    def validate_dates(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        return validate_date_format(v)
    
    @field_validator('firstname', 'lastname', 'city', 'city2', 'state', 'state2', 'country', 'country2', 
                     'emergency_contact_name', 'referral_subcategory', 'billing_firstname', 'billing_lastname',
                     'billing_state', 'billing_state2', 'billing_city', 'billing_city2', 'billing_country', 'billing_country2')
    @classmethod
    def to_lowercase_fields(cls, v: Optional[str]) -> Optional[str]:
        return to_lowercase(v)
    
    @field_validator('address1', 'address2', 'billing_address1', 'billing_address2')
    @classmethod
    def to_lowercase_address(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        return to_lowercase(v)

class PatientUpdate(BaseModel):
    """Schema for updating a patient"""
    firstname: Optional[str] = None
    lastname: Optional[str] = None
    dob: Optional[str] = None  # If provided, age will be recalculated
    gender: Optional[Literal["male", "female", "other"]] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    primary_doctor: Optional[int] = None  # Staff ID
    blood_group: Optional[BloodGroup] = None
    status: Optional[PatientStatus] = None
    vip: Optional[bool] = None  # VIP status
    address1: Optional[str] = None
    address2: Optional[str] = None
    country: Optional[str] = None
    country2: Optional[str] = None
    city: Optional[str] = None
    city2: Optional[str] = None
    state: Optional[str] = None
    state2: Optional[str] = None
    pincode: Optional[str] = None
    pincode2: Optional[str] = None
    image: Optional[str] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    registration_date: Optional[str] = None
    referral_source: Optional[Literal["doctor", "self", "friend", "online"]] = None
    referral_subcategory: Optional[str] = None
    past_medical_record: Optional[str] = None
    dermatological_history: Optional[str] = None
    medications: Optional[str] = None
    surgeries: Optional[str] = None
    hormonal_issues: Optional[str] = None
    allergies: Optional[str] = None
    lifestyle_assessment: Optional[str] = None
    billing_firstname: Optional[str] = None
    billing_lastname: Optional[str] = None
    billing_email: Optional[EmailStr] = None
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

    @field_validator('phone', 'emergency_contact_phone', 'billing_phone')
    @classmethod
    def validate_phone_fields(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        return validate_phone(v)

    @field_validator('pincode', 'pincode2', 'billing_pincode', 'billing_pincode2')
    @classmethod
    def validate_pincode_fields(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        return validate_pincode(v)

    @field_validator('dob')
    @classmethod
    def validate_dob(cls, v: Optional[str]) -> Optional[str]:
        """Validate DOB: not in future"""
        if v is None:
            return v
        return validate_date_not_future(v, "Date of birth")
    
    @field_validator('registration_date')
    @classmethod
    def validate_registration_date(cls, v: Optional[str]) -> Optional[str]:
        """Validate registration date: not in future"""
        if v is None:
            return v
        return validate_date_not_future(v, "Registration date")
    
    @field_validator('firstname', 'lastname')
    @classmethod
    def validate_name_fields(cls, v: Optional[str]) -> Optional[str]:
        """Validate name fields: not empty if provided, max length"""
        if v is None:
            return v
        if not v or not v.strip():
            raise ValueError("Name cannot be empty")
        v = v.strip()
        if len(v) > 255:
            raise ValueError("Name cannot exceed 255 characters")
        return v.lower()
    
    @field_validator('city', 'city2', 'state', 'state2', 'country', 'country2', 'emergency_contact_name', 
                     'referral_subcategory', 'billing_firstname', 'billing_lastname',
                     'billing_state', 'billing_state2', 'billing_city', 'billing_city2', 'billing_country', 'billing_country2')
    @classmethod
    def validate_text_fields(cls, v: Optional[str]) -> Optional[str]:
        """Validate text fields: max length"""
        if v is None:
            return v
        v = v.strip()
        if len(v) > 255:
            raise ValueError("Field cannot exceed 255 characters")
        return v.lower()
    
    @field_validator('address1', 'address2', 'billing_address1', 'billing_address2')
    @classmethod
    def validate_address_fields(cls, v: Optional[str]) -> Optional[str]:
        """Validate address fields: max length"""
        if v is None:
            return v
        v = v.strip()
        if len(v) > 1000:
            raise ValueError("Address cannot exceed 1000 characters")
        return v.lower()
    
    @field_validator('past_medical_record', 'dermatological_history', 'medications', 'surgeries', 'hormonal_issues', 'allergies', 'lifestyle_assessment')
    @classmethod
    def validate_medical_history_fields(cls, v: Optional[str]) -> Optional[str]:
        """Validate medical history fields: max length"""
        if v is None:
            return v
        if len(v) > 5000:
            raise ValueError("Medical history field cannot exceed 5000 characters")
        return v

class PatientModel(BaseModel):
    """Schema for patient output - includes calculated age"""
    id: Optional[int] = None
    tenant_id: Optional[str] = None
    firstname: str
    lastname: str
    dob: str
    age: int  # Calculated from dob
    gender: Literal["male", "female", "other"]
    phone: str
    email: Optional[EmailStr] = None
    primary_doctor: Optional[int] = None  # Staff ID
    blood_group: Optional[str] = None
    status: PatientStatus
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
    referral_source: Optional[Literal["doctor", "self", "friend", "online"]] = None
    referral_subcategory: Optional[str] = None
    registration_date: str
    past_medical_record: Optional[str] = None
    dermatological_history: Optional[str] = None
    medications: Optional[str] = None
    surgeries: Optional[str] = None
    hormonal_issues: Optional[str] = None
    allergies: Optional[str] = None
    lifestyle_assessment: Optional[str] = None
    billing_firstname: Optional[str] = None
    billing_lastname: Optional[str] = None
    billing_email: Optional[EmailStr] = None
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

    @field_validator('age')
    @classmethod
    def validate_age(cls, v: int) -> int:
        """Validate age: must be between 1 and 110"""
        if v < 1 or v > 110:
            raise ValueError("Age must be between 1 and 110")
        return v
