"""Inventory module table definitions"""

# Inventory Items Table
# Note: Inventory is not patient-specific, so no patient_id, doctor_id, or purpose needed
# Using INTEGER id and VARCHAR tenant_id to match other tables
INVENTORY_ITEMS_TABLE = """
    CREATE TABLE IF NOT EXISTS inventory_items (
        id SERIAL PRIMARY KEY,
        tenant_id VARCHAR(100) NOT NULL,
        name TEXT NOT NULL,
        category TEXT NOT NULL,
        unit TEXT NOT NULL,
        current_stock INT NOT NULL,
        min_stock_level INT NOT NULL,
        unit_price NUMERIC(12,2) NOT NULL,
        expiry_date DATE NOT NULL,
        supplier_name TEXT NOT NULL,
        supplier_phone TEXT NOT NULL,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        synced_to_main BOOLEAN DEFAULT {},
        last_synced_at TIMESTAMP
    )
"""

# Indexes for inventory_items
INVENTORY_ITEMS_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_inventory_items_tenant_id ON inventory_items(tenant_id)",
    "CREATE INDEX IF NOT EXISTS idx_inventory_items_name ON inventory_items(name)",
    "CREATE INDEX IF NOT EXISTS idx_inventory_items_category ON inventory_items(category)",
    "CREATE INDEX IF NOT EXISTS idx_inventory_items_expiry_date ON inventory_items(expiry_date)"
]

