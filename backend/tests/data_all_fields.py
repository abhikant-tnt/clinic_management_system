from decimal import Decimal

def jsonify(data):
    """Deep convert Decimals to floats for TestClient JSON serialization."""
    if isinstance(data, list):
        return [jsonify(v) for v in data]
    if isinstance(data, dict):
        return {k: jsonify(v) for k, v in data.items()}
    if isinstance(data, Decimal):
        return float(data)
    return data

# ALL possible fields for creating records
USER_DATA = {
    "firstname": "AllFields",
    "lastname": "User",
    "phone": "9999999999",
    "username": "all_fields_user",
    "password": "Password123",
    "user_type": "doctor",
    "speciality": "Cardiology",
    "tenant_id": "test_tenant_xyz"
}

PATIENT_DATA = {
    "firstname": "AllFields",
    "lastname": "Patient",
    "phone": "8888888888",
    "email": "allfields@example.com",
    "dob": "15/05/1985",
    "gender": "female",
    "blood_group": "B+ve",
    "status": "checked_in",
    "vip": True,
    "address1": "789 Rich Ave",
    "address2": "Suite 500",
    "country": "India",
    "state": "Maharashtra",
    "city": "Mumbai",
    "pincode": "400001",
    "image": "image_data_string",
    "past_medical_record": "None",
    "allergies": "Peanuts",
    "dermatological_history": "Dry skin",
    "medications": "Vitamin D",
    "surgeries": "None",
    "hormonal_issues": "None",
    "lifestyle_assessment": "Active",
    "billing_firstname": "Bill",
    "billing_lastname": "Fields",
    "billing_phone": "7777777777",
    "billing_email": "billing@example.com",
    "billing_gstin": "27AAAAA0000A1Z5",
    "billing_address1": "456 Billing St",
    "billing_city": "Pune",
    "billing_state": "Maharashtra",
    "billing_country": "India",
    "billing_pincode": "411001",
    "emergency_contact_name": "Emergency Contact",
    "emergency_contact_phone": "6666666666",
    "referral_source": "friend",
    "referral_subcategory": "College Friend"
}

APPOINTMENT_DATA = {
    "appointment_date": "10/10/2026",
    "appointment_time": "02:30 pm",
    "status": "Scheduled",
    "purpose": "procedure",
    "interval": "30 min",
    "payment": "Paid",
    "follow_up_date": "17/10/2026"
}

INVENTORY_DATA = jsonify({
    "name": "Full Field Item",
    "product_type": "Pharmaceutical",
    "category": "Tablets",
    "sku_code": "SKU-999",
    "brand_name": "AlphaBrand",
    "manufacturer": "AlphaPharma",
    "description": "Powerful painkiller",
    "unit": "box",
    "pack_size": 10,
    "current_stock": 500,
    "min_stock_level": 50,
    "storage_location": "Shelf B4",
    "unit_price": Decimal("150.00"),
    "batch_number": "BATCH-XYZ",
    "expiry_date": "31/12/2029",
    "status": "Normal",
    "supplier_name": "Premium Supplier",
    "supplier_phone": "5555555555",
    "is_in_stock": True,
    "dosage_strength": "500mg",
    "dosage_form": "Tablet",
    "route": "oral",
    "schedule_type": "H1",
    "prescription_required": True
})

BILLING_ITEM_DATA = jsonify({
    "item_type": "product",
    "description": "Medication X",
    "quantity": 2,
    "unit_price": Decimal("100.00"),
    "line_total": Decimal("200.00")
})

BILLING_INVOICE_DATA = jsonify({
    "invoice_number": "INV-FULL-999",
    "issue_date": "01/01/2025",
    "purpose": "Treatment",
    "total_amount": Decimal("200.00"),
    "tax_amount": Decimal("36.00"),
    "gst_percentage": Decimal("18"),
    "discount_amount": Decimal("10.00"),
    "coupon_code": "SAVE10",
    "adjustments": Decimal("5.00"),
    "amount_paid": Decimal("231.00"),
    "payment_mode": "Card",
    "status": "paid",
    "visit_charge": Decimal("50.00"),
    "medication_charge": Decimal("150.00"),
    "items": [BILLING_ITEM_DATA]
})

ROOM_DATA = {
    "room_number": "R999",
    "room_type": "Specialized Treatment"
}

MACHINE_DATA = {
    "name": "Full Field Machine",
    "status": "Maintenance",
    "room_id": 0 # Replace in test
}
