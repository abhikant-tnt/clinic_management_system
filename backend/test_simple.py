"""Simple test to create a patient and appointment"""
import requests
import json
from datetime import date

BASE_URL = "http://localhost:8000/api"

print("=" * 60)
print("Creating Test Records")
print("=" * 60)

# 1. Create Patient
print("\n1. Creating patient...")
patient_data = {
    "name": "abhikant bhave",
    "gender": "male",
    "phone": "9876543220",  # Changed to avoid duplicate
    "email": "abhikant.bhave@yahoo.com",
    "date_of_birth": "15/01/1990",
    "address": "123 Main Street",
    "registration_date": date.today().strftime("%d/%m/%Y"),
    "referral_source": "self",
    "patient_status": "Active"
}

try:
    response = requests.post(f"{BASE_URL}/patients", json=patient_data, timeout=10)
    if response.status_code == 200:
        result = response.json()
        # Response format: {"message": "Patient created successfully with ID X."}
        message = result.get("message", "")
        if "ID" in message:
            import re
            patient_id = int(re.search(r'ID (\d+)', message).group(1))
            print(f"   ✅ Patient created! ID: {patient_id}")
            
            # Get the full patient details
            get_response = requests.get(f"{BASE_URL}/patients/{patient_id}", timeout=10)
            if get_response.status_code == 200:
                patient = get_response.json().get("patient", {})
                print(f"      Name: {patient.get('name')}, Age: {patient.get('age')}")
        else:
            print(f"   ⚠️  Created but couldn't extract ID: {message}")
            patient_id = None
        
        # 2. Create Appointment
        print("\n2. Creating appointment...")
        if not patient_id:
            print("   ❌ Cannot create appointment without patient ID")
            exit(1)
            
        appointment_data = {
            "patient_id": patient_id,
            "appointment_date": date.today().strftime("%d/%m/%Y"),
            "appointment_time": "10:30",
            "status": "Active",
            "doctor_name": "Dr. Smith",
            "appointment_type": "Consultation"
        }
        
        response = requests.post(f"{BASE_URL}/appointments", json=appointment_data, timeout=10)
        if response.status_code == 200:
            result = response.json()
            appointment = result.get("appointment", {})
            appointment_id = appointment.get("id")
            print(f"   ✅ Appointment created! ID: {appointment_id}")
            print(f"      Date: {appointment.get('appointment_date')}, Time: {appointment.get('appointment_time')}")
            
            # 3. Complete appointment with clinical data
            print("\n3. Completing appointment (adding clinical data)...")
            complete_response = requests.post(f"{BASE_URL}/appointments/{appointment_id}/complete", timeout=10)
            if complete_response.status_code == 200:
                clinical_update = {
                    "diagnosis": "Acne vulgaris",
                    "treatment": "Topical retinoid cream",
                    "visit_charge": 500.0,
                    "medication_charge": 300.0
                }
                update_response = requests.put(f"{BASE_URL}/appointments/{appointment_id}", json=clinical_update, timeout=10)
                if update_response.status_code == 200:
                    result = update_response.json()
                    appt = result.get("appointment", {})
                    print(f"   ✅ Clinical data added!")
                    print(f"      Diagnosis: {appt.get('diagnosis')}")
                    print(f"      Total Charge: ₹{appt.get('total_charge')}")
        else:
            print(f"   ❌ Error: {response.text}")
    else:
        print(f"   ❌ Error: {response.text}")
except Exception as e:
    print(f"   ❌ Error: {e}")

print("\n" + "=" * 60)
print("✅ Test completed! Check http://localhost:8000/docs for API documentation")
print("=" * 60)

