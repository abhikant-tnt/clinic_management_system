# Billing module table definitions - Billing Invoices Table
# Using INTEGER for all IDs and VARCHAR for tenant_id to match other tables
BILLING_INVOICES_TABLE = """
    CREATE TABLE IF NOT EXISTS billing_invoices (
        id SERIAL PRIMARY KEY,
        tenant_id VARCHAR(100) NOT NULL,
        invoice_number TEXT NOT NULL UNIQUE,
        patient_id INTEGER NOT NULL,
        appointment_id INTEGER NOT NULL,
        doctor_id INTEGER NOT NULL,
        issue_date DATE NOT NULL,
        purpose TEXT NOT NULL,
        total_amount NUMERIC(12,2) NOT NULL,
        tax_amount NUMERIC(12,2) NOT NULL,
        gst_percentage NUMERIC(5,2) NOT NULL,
        discount_amount NUMERIC(12,2) NOT NULL,
        coupon_code TEXT,
        adjustments NUMERIC(12,2) NOT NULL,
        amount_paid NUMERIC(12,2) NOT NULL,
        outstanding_amount NUMERIC(12,2) GENERATED ALWAYS AS ((total_amount + tax_amount + adjustments) - discount_amount - amount_paid) STORED,
        status TEXT NOT NULL,
        created_by INTEGER NOT NULL,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (patient_id) REFERENCES patients_table(id) ON DELETE CASCADE,
        FOREIGN KEY (appointment_id) REFERENCES appointments(id) ON DELETE CASCADE,
        FOREIGN KEY (doctor_id) REFERENCES staff(id) ON DELETE SET NULL
    )
"""

# Billing Items Table - Links to invoice via invoice_id (can access patient_id, doctor_id, purpose through invoice)
BILLING_ITEMS_TABLE = """
    CREATE TABLE IF NOT EXISTS billing_items (
        id SERIAL PRIMARY KEY,
        tenant_id VARCHAR(100) NOT NULL,
        invoice_id INTEGER NOT NULL,
        item_type TEXT NOT NULL,
        description TEXT NOT NULL,
        quantity INT NOT NULL,
        unit_price NUMERIC(12,2) NOT NULL,
        line_total NUMERIC(12,2) NOT NULL,
        inventory_item_id INTEGER,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (invoice_id) REFERENCES billing_invoices(id) ON DELETE CASCADE,
        FOREIGN KEY (inventory_item_id) REFERENCES inventory_items(id) ON DELETE SET NULL
    )
"""

# Indexes for billing_invoices
BILLING_INVOICES_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_billing_invoices_tenant_id ON billing_invoices(tenant_id)",
    "CREATE INDEX IF NOT EXISTS idx_billing_invoices_patient_id ON billing_invoices(patient_id)",
    "CREATE INDEX IF NOT EXISTS idx_billing_invoices_appointment_id ON billing_invoices(appointment_id)",
    "CREATE INDEX IF NOT EXISTS idx_billing_invoices_doctor_id ON billing_invoices(doctor_id)",
    "CREATE INDEX IF NOT EXISTS idx_billing_invoices_invoice_number ON billing_invoices(invoice_number)"
]

# Indexes for billing_items
BILLING_ITEMS_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_billing_items_tenant_id ON billing_items(tenant_id)",
    "CREATE INDEX IF NOT EXISTS idx_billing_items_invoice_id ON billing_items(invoice_id)",
    "CREATE INDEX IF NOT EXISTS idx_billing_items_inventory_item_id ON billing_items(inventory_item_id)"
]