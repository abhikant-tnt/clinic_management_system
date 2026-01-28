# Platform Admin Module

## Overview
Platform Admin module provides system management capabilities **without access to PHI (Protected Health Information)**. This follows industry standards for healthcare data privacy (HIPAA/GDPR compliance).

## Access Restrictions

### ✅ Platform Admin CAN Access:
- **System Health** - Database status, API health, performance metrics
- **Tenant Metadata** - Clinic counts, activity status (NO patient data)
- **Aggregated Metrics** - System-wide counts (NO patient names/details)
- **System Logs** - Error logs (sanitized, NO PHI)
- **User Management** - Clinic staff accounts (metadata only, NO patient data)
- **Non-PHI Modules** - Inventory, Settings, Assets, Users (clinic staff)

### ❌ Platform Admin CANNOT Access:
- **Patient Module** - NO access to patient names, medical records, PHI
- **Patient Data** - Names, DOB, phone, email, addresses, medical history
- **Prescriptions** - Patient-specific prescription details
- **Patient Documents** - Medical documents/images

## Endpoints

All endpoints require `platform_admin` user type and are prefixed with `/api/v1/platform/`

### 1. System Health
```
GET /api/v1/platform/health
```
Returns database connectivity, response times, API version.

### 2. Tenants List
```
GET /api/v1/platform/tenants
```
Returns list of all clinics with metadata:
- Tenant ID
- User counts
- Patient counts (NO patient names/data)
- Appointment counts (NO details)
- Activity status

### 3. Aggregated Metrics
```
GET /api/v1/platform/metrics
```
Returns system-wide aggregated statistics:
- Total tenants, users, patients (counts only)
- Total appointments, bills (counts only)
- Active appointments today/tomorrow (counts only)

### 4. System Logs
```
GET /api/v1/platform/logs?limit=100
```
Returns sanitized system logs (PHI filtered out).

### 5. Users List
```
GET /api/v1/platform/users?tenant_id=clinic_001
```
Returns clinic staff metadata:
- User IDs, types, activity status
- NO names, phone numbers, emails

### 6. Audit Logs
```
GET /api/v1/platform/audit?limit=100
```
Returns audit trail of all platform admin actions.

## Audit Logging

All platform admin actions are automatically logged:
- Endpoint accessed
- Timestamp
- Success/failure
- Action details

## Security Notes

1. **PHI Protection**: Patient data is NEVER exposed in platform admin endpoints
2. **Counts Only**: Patient-related endpoints return counts, not actual data
3. **Audit Trail**: All platform admin access is logged for compliance
4. **Permission-Based**: Platform admin cannot access patient module routes

## Usage Example

```python
# Platform admin login
POST /api/v1/auth/login
{
  "username": "platform_admin",
  "password": "secure_password"
}

# Get system health
GET /api/v1/platform/health
Authorization: Bearer <token>

# Get tenant metadata (no PHI)
GET /api/v1/platform/tenants
Authorization: Bearer <token>
```

## Industry Standards Compliance

- ✅ **HIPAA Compliance**: No PHI access
- ✅ **GDPR Compliance**: Data minimization principle
- ✅ **Principle of Least Privilege**: Only necessary access
- ✅ **Audit Logging**: All actions tracked
- ✅ **Data Anonymization**: Counts only, no identifiers
