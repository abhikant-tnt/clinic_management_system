"""Inventory module table definitions"""

# Inventory Items Table
# Note: Inventory is not patient-specific, so no patient_id, doctor_id, or purpose needed
# Using INTEGER id and VARCHAR tenant_id to match other tables
INVENTORY_ITEMS_TABLE = """
    CREATE TABLE IF NOT EXISTS inventory_items (
        id SERIAL PRIMARY KEY,
        tenant_id VARCHAR(100) NOT NULL,
        -- Basic Information (from Create SKU form)
        name TEXT NOT NULL,
        product_type TEXT,
        category TEXT NOT NULL,
        sku_code TEXT,
        brand_name TEXT,
        manufacturer TEXT,
        description TEXT,
        -- Stock Configuration
        unit TEXT NOT NULL,
        pack_size INT,
        current_stock INT NOT NULL,
        min_stock_level INT NOT NULL,
        storage_location TEXT,
        unit_price NUMERIC(12,2) NOT NULL,
        -- Batch and Expiry
        batch_number TEXT,
        expiry_date DATE,
        status TEXT,
        -- Supplier Information
        supplier_name TEXT NOT NULL,
        supplier_phone TEXT NOT NULL,
        is_in_stock BOOLEAN NOT NULL DEFAULT TRUE,
        -- Consumable-Specific Fields
        is_sterile BOOLEAN,
        is_single_use BOOLEAN,
        is_reusable BOOLEAN,
        expiry_tracking_required BOOLEAN,
        -- Pharmaceutical-Specific Fields
        dosage_strength TEXT,
        dosage_form TEXT,
        route TEXT,
        schedule_type TEXT,
        prescription_required BOOLEAN,
        -- Timestamps
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
"""

# Indexes for inventory_items
INVENTORY_ITEMS_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_inventory_items_tenant_id ON inventory_items(tenant_id)",
    "CREATE INDEX IF NOT EXISTS idx_inventory_items_name ON inventory_items(name)",
    "CREATE INDEX IF NOT EXISTS idx_inventory_items_category ON inventory_items(category)",
    "CREATE INDEX IF NOT EXISTS idx_inventory_items_product_type ON inventory_items(product_type)",
    "CREATE INDEX IF NOT EXISTS idx_inventory_items_sku_code ON inventory_items(sku_code)",
    "CREATE INDEX IF NOT EXISTS idx_inventory_items_batch_number ON inventory_items(batch_number)",
    "CREATE INDEX IF NOT EXISTS idx_inventory_items_expiry_date ON inventory_items(expiry_date)",
    "CREATE INDEX IF NOT EXISTS idx_inventory_items_status ON inventory_items(status)",
    "CREATE INDEX IF NOT EXISTS idx_inventory_items_is_in_stock ON inventory_items(is_in_stock)"
]

