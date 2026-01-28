"""SQLAlchemy models for Inventory module"""
from sqlalchemy import Column, Integer, String, Text, Date, DECIMAL, DateTime, Boolean
from datetime import datetime
from app.core.models import Base

class InventoryItemModel(Base):
    """Inventory item model"""
    __tablename__ = "inventory_items"
    
    # Primary and tenant fields
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String(100), nullable=False, index=True)
    
    # Basic Information (from Create SKU form)
    name = Column(Text, nullable=False, index=True)  # Stock Name / Item Name
    product_type = Column(Text, nullable=True, index=True)  # Type (Consumable, Pharmaceutical, etc.)
    category = Column(Text, nullable=False, index=True)  # Category (Medical, Injectable, etc.)
    sku_code = Column(Text, nullable=True, index=True)  # Item Code / SKU
    brand_name = Column(Text, nullable=True)  # Brand Name
    manufacturer = Column(Text, nullable=True)  # Manufacturer
    description = Column(Text, nullable=True)  # Description
    
    # Stock Configuration
    unit = Column(Text, nullable=False)  # Unit of Measure
    pack_size = Column(Integer, nullable=True)  # Pack Size
    current_stock = Column(Integer, nullable=False)  # Stock Available
    min_stock_level = Column(Integer, nullable=False)  # Minimum low-stock alert
    storage_location = Column(Text, nullable=True)  # Storage Location (Shelf / Fridge / Room)
    unit_price = Column(DECIMAL(12, 2), nullable=False)
    
    # Batch and Expiry
    batch_number = Column(Text, nullable=True, index=True)  # Batch Number
    expiry_date = Column(Date, nullable=True, index=True)  # Expiry Date (nullable for items without expiry)
    
    # Status (can be calculated: "Out of Stock", "Expiring Soon", "Normal")
    status = Column(Text, nullable=True, index=True)
    
    # Supplier Information
    supplier_name = Column(Text, nullable=False)
    supplier_phone = Column(Text, nullable=False)
    
    # Stock Status
    is_in_stock = Column(Boolean, nullable=False, default=True, index=True)
    
    # Consumable-Specific Fields
    is_sterile = Column(Boolean, nullable=True)  # Is Sterile
    is_single_use = Column(Boolean, nullable=True)  # Single Use
    is_reusable = Column(Boolean, nullable=True)  # Reusable
    expiry_tracking_required = Column(Boolean, nullable=True)  # Expiry Tracking Required
    
    # Pharmaceutical-Specific Fields
    dosage_strength = Column(Text, nullable=True)  # Dosage Strength (e.g., 100U, 500mg)
    dosage_form = Column(Text, nullable=True)  # Dosage Form
    route = Column(Text, nullable=True)  # Route (oral, IM, IV)
    schedule_type = Column(Text, nullable=True)  # Schedule Type (OTC / H / H1)
    prescription_required = Column(Boolean, nullable=True)  # Prescription Required
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
