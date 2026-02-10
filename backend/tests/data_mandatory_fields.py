from decimal import Decimal
import json

class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Decimal):
            return float(o)
        return super().default(o)

def jsonify(data):
    """Deep convert Decimals to floats/strings for TestClient JSON serialization."""
    if isinstance(data, list):
        return [jsonify(v) for v in data]
    if isinstance(data, dict):
        return {k: jsonify(v) for k, v in data.items()}
    if isinstance(data, Decimal):
        return float(data)
    return data

# Mandatory fields ONLY for creating records
USER_DATA = {
    "firstname": "Mandatory",
    "lastname": "User",
    "phone": "1111111111",
    "username": "mandatory_user",
    "password": "Password123",
    "user_type": "staff"
}

PATIENT_DATA = {
    "firstname": "Mandatory",
    "lastname": "Patient",
    "phone": "2222222222",
    "email": "mandatory@example.com",
    "dob": "01/01/1990",
    "gender": "male",
    "status": "scheduled",
    "address1": "123 Main St"
}

APPOINTMENT_DATA = {
    "appointment_date": "01/01/2026", # Future date
    "appointment_time": "10:00 am",
    "purpose": "Schedule",
    "interval": "15 min"
}

INVENTORY_DATA = jsonify({
    "name": "Mandatory Item",
    "category": "Medical",
    "unit": "pcs",
    "current_stock": 100,
    "min_stock_level": 10,
    "unit_price": Decimal("50.00"),
    "supplier_name": "Mandatory Supplier",
    "supplier_phone": "3333333333"
})

BILLING_ITEM_DATA = jsonify({
    "item_type": "service",
    "description": "Consultation",
    "quantity": 1,
    "unit_price": Decimal("500.00"),
    "line_total": Decimal("500.00")
})

BILLING_INVOICE_DATA = jsonify({
    "invoice_number": "INV-MANDATORY-001",
    "issue_date": "01/01/2025",
    "purpose": "Consultation",
    "total_amount": Decimal("500.00"),
    "tax_amount": Decimal("60.00"),
    "gst_percentage": Decimal("12"),
    "discount_amount": Decimal("0.00"),
    "adjustments": Decimal("0.00"),
    "amount_paid": Decimal("560.00"),
    "status": "paid",
    "items": [BILLING_ITEM_DATA]
})

ROOM_DATA = {
    "room_number": "R101",
    "room_type": "Consultation"
}

MACHINE_DATA = {
    "name": "Mandatory Machine",
    "status": "Active"
}
