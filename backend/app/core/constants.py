"""Constants for the clinic management system"""

# User types
USER_TYPE_PLATFORM_ADMIN = "platform_admin"  # Platform team managing entire software
USER_TYPE_OWNER = "owner"  # Clinic owner/admin (main doctor)
USER_TYPE_DOCTOR = "doctor"
USER_TYPE_RECEPTIONIST = "receptionist"
USER_TYPE_STAFF = "staff"
USER_TYPE_PHARMACIST = "pharmacist"

def is_platform_admin(user_type: str) -> bool:
    """Check if user type is platform admin."""
    return user_type == USER_TYPE_PLATFORM_ADMIN
