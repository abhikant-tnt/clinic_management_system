"""GraphQL schema for Inventory module (Strawberry)"""
import strawberry
from typing import Optional, List
from app.common.graphql_types import PaginationInfo

@strawberry.type
class InventoryItemType:
    """GraphQL Inventory Item type (table view)"""
    id: Optional[str] = None
    tenant_id: Optional[str] = None
    # Basic Information
    name: str  # Stock Name
    product_type: Optional[str] = None  # Type
    category: str  # Category
    sku_code: Optional[str] = None  # Item Code / SKU
    brand_name: Optional[str] = None  # Brand Name
    manufacturer: Optional[str] = None  # Manufacturer
    description: Optional[str] = None  # Description
    # Stock Configuration
    unit: str  # Unit
    pack_size: Optional[int] = None  # Pack Size
    current_stock: int  # Stock Available
    min_stock_level: int  # Minimum low-stock alert
    storage_location: Optional[str] = None  # Storage Location
    unit_price: float
    # Batch and Expiry
    batch_number: Optional[str] = None  # Batch Number
    expiry_date: Optional[str] = None  # Expiry Date
    status: Optional[str] = None  # Status
    # Supplier Information
    supplier_name: str
    supplier_phone: str
    is_in_stock: Optional[bool] = True
    # Consumable-Specific Fields
    is_sterile: Optional[bool] = None
    is_single_use: Optional[bool] = None
    is_reusable: Optional[bool] = None
    expiry_tracking_required: Optional[bool] = None
    # Pharmaceutical-Specific Fields
    dosage_strength: Optional[str] = None
    dosage_form: Optional[str] = None
    route: Optional[str] = None
    schedule_type: Optional[str] = None
    prescription_required: Optional[bool] = None
    # Timestamps
    created_at: Optional[str] = None
    updated_at: Optional[str] = None  # Last Updated

@strawberry.input
class InventoryItemInput:
    """GraphQL Inventory Item input for creating (CREATE SKU form)"""
    # Basic Information - Compulsory fields (marked with *)
    name: str  # Item Name *
    product_type: Optional[str] = None  # Product Type *
    category: str  # Category *
    sku_code: Optional[str] = None  # Item Code / SKU *
    brand_name: Optional[str] = None  # Brand Name *
    manufacturer: Optional[str] = None  # Manufacturer *
    description: Optional[str] = None  # Description (optional)
    # Stock Configuration - Compulsory fields
    unit: str  # Unit of Measure *
    pack_size: Optional[int] = None  # Pack Size *
    current_stock: int  # Stock Available
    min_stock_level: int  # Minimum low-stock alert *
    storage_location: Optional[str] = None  # Storage Location *
    unit_price: float
    # Batch and Expiry
    batch_number: Optional[str] = None  # Batch Number
    expiry_date: Optional[str] = None  # Expiry Date (dd/mm/yyyy format, optional)
    status: Optional[str] = None  # Status
    # Supplier Information - Compulsory
    supplier_name: str
    supplier_phone: str
    # Consumable-Specific Fields - Compulsory if product_type is Consumable
    is_sterile: Optional[bool] = None  # Is Sterile *
    is_single_use: Optional[bool] = None  # Single Use *
    is_reusable: Optional[bool] = None  # Reusable *
    expiry_tracking_required: Optional[bool] = None  # Expiry Tracking Required *
    # Pharmaceutical-Specific Fields - Compulsory if product_type is Pharmaceutical
    dosage_strength: Optional[str] = None  # Dosage Strength *
    dosage_form: Optional[str] = None  # Dosage Form *
    route: Optional[str] = None  # Route *
    schedule_type: Optional[str] = None  # Schedule Type *
    prescription_required: Optional[bool] = None  # Prescription Required *

@strawberry.input
class InventoryItemUpdateInput:
    """GraphQL Inventory Item input for updating"""
    # Basic Information
    name: Optional[str] = None
    product_type: Optional[str] = None
    category: Optional[str] = None
    sku_code: Optional[str] = None
    brand_name: Optional[str] = None
    manufacturer: Optional[str] = None
    description: Optional[str] = None
    # Stock Configuration
    unit: Optional[str] = None
    pack_size: Optional[int] = None
    current_stock: Optional[int] = None
    min_stock_level: Optional[int] = None
    storage_location: Optional[str] = None
    unit_price: Optional[float] = None
    # Batch and Expiry
    batch_number: Optional[str] = None
    expiry_date: Optional[str] = None
    status: Optional[str] = None
    # Supplier Information
    supplier_name: Optional[str] = None
    supplier_phone: Optional[str] = None
    # Consumable-Specific Fields
    is_sterile: Optional[bool] = None
    is_single_use: Optional[bool] = None
    is_reusable: Optional[bool] = None
    expiry_tracking_required: Optional[bool] = None
    # Pharmaceutical-Specific Fields
    dosage_strength: Optional[str] = None
    dosage_form: Optional[str] = None
    route: Optional[str] = None
    schedule_type: Optional[str] = None
    prescription_required: Optional[bool] = None

@strawberry.type
class InventoryItemsResponse:
    """Response type for paginated inventory items"""
    items: List[InventoryItemType]
    pagination: PaginationInfo

@strawberry.type
class LowStockAlertType:
    """GraphQL Low Stock Alert type"""
    id: str
    name: str
    category: str
    current_stock: int
    min_stock_level: int
    unit: str

@strawberry.type
class LowStockAlertsResponse:
    """Response type for paginated low stock alerts"""
    alerts: List[LowStockAlertType]
    count: int
    pagination: PaginationInfo

@strawberry.type
class ExpiringItemType:
    """GraphQL Expiring Item type"""
    id: str
    name: str
    category: str
    expiry_date: Optional[str] = None
    current_stock: int
    unit: str

@strawberry.type
class ExpiringItemsResponse:
    """Response type for paginated expiring items"""
    alerts: List[ExpiringItemType]
    count: int
    days_ahead: int
    pagination: PaginationInfo

@strawberry.type
class Query:
    """GraphQL Query type for Inventory"""
    
    @strawberry.field
    async def inventoryItem(self, item_id: str) -> Optional[InventoryItemType]:
        """Get a single inventory item by ID"""
        from app.modules.inventory.routes import get_inventory_item
        from fastapi import HTTPException
        
        try:
            # Note: GraphQL calls route directly, auth should be handled via GraphQL context
            item_data = await get_inventory_item(item_id, {})  # Pass empty dict for current_user
            if item_data:
                # Convert Decimal to float if needed
                if isinstance(item_data.get("unit_price"), (int, float)):
                    item_data["unit_price"] = float(item_data["unit_price"])
                return InventoryItemType(**item_data)
            return None
        except HTTPException:
            return None
    
    @strawberry.field
    async def inventoryItems(
        self,
        page: int = 1,
        limit: int = 10,
        category: Optional[str] = None,
        low_stock: Optional[bool] = None
    ) -> InventoryItemsResponse:
        """Get all inventory items with optional filters"""
        from app.modules.inventory.routes import get_inventory_items
        from fastapi import HTTPException
        
        try:
            # Note: GraphQL calls route directly, auth should be handled via GraphQL context
            result = await get_inventory_items(
                page=page,
                limit=limit,
                category=category,
                low_stock=low_stock,
                current_user={}
            )
            items_list = []
            for item in result.get("items", []):
                item_data = item.copy()
                # Convert Decimal to float if needed
                if isinstance(item_data.get("unit_price"), (int, float)):
                    item_data["unit_price"] = float(item_data["unit_price"])
                items_list.append(InventoryItemType(**item_data))
            
            pagination_data = result.get("pagination", {})
            pagination = PaginationInfo(
                total=pagination_data.get("total", 0),
                page=pagination_data.get("page", 1),
                limit=pagination_data.get("limit", 10),
                total_pages=pagination_data.get("total_pages", 1),
                has_next=pagination_data.get("has_next", False),
                has_prev=pagination_data.get("has_prev", False)
            )
            
            return InventoryItemsResponse(items=items_list, pagination=pagination)
        except HTTPException:
            return InventoryItemsResponse(items=[], pagination=PaginationInfo(total=0, page=1, limit=10, total_pages=1, has_next=False, has_prev=False))
    
    @strawberry.field
    async def lowStockAlerts(
        self,
        page: int = 1,
        limit: int = 10
    ) -> LowStockAlertsResponse:
        """Get low stock alerts"""
        from app.modules.inventory.routes import get_low_stock_alerts
        from fastapi import HTTPException
        
        try:
            # Note: GraphQL calls route directly, auth should be handled via GraphQL context
            result = await get_low_stock_alerts(
                page=page,
                limit=limit,
                current_user={}
            )
            alerts_list = []
            for alert in result.get("alerts", []):
                alerts_list.append(LowStockAlertType(**alert))
            
            pagination_data = result.get("pagination", {})
            pagination = PaginationInfo(
                total=pagination_data.get("total", 0),
                page=pagination_data.get("page", 1),
                limit=pagination_data.get("limit", 10),
                total_pages=pagination_data.get("total_pages", 1),
                has_next=pagination_data.get("has_next", False),
                has_prev=pagination_data.get("has_prev", False)
            )
            
            return LowStockAlertsResponse(
                alerts=alerts_list,
                count=result.get("count", 0),
                pagination=pagination
            )
        except HTTPException:
            return LowStockAlertsResponse(
                alerts=[],
                count=0,
                pagination=PaginationInfo(total=0, page=1, limit=10, total_pages=1, has_next=False, has_prev=False)
            )
    
    @strawberry.field
    async def expiringItems(
        self,
        days: int = 30,
        page: int = 1,
        limit: int = 10
    ) -> ExpiringItemsResponse:
        """Get expiring items within specified days"""
        from app.modules.inventory.routes import get_expiring_items
        from fastapi import HTTPException
        
        try:
            # Note: GraphQL calls route directly, auth should be handled via GraphQL context
            result = await get_expiring_items(
                days=days,
                page=page,
                limit=limit,
                current_user={}
            )
            alerts_list = []
            for alert in result.get("alerts", []):
                alerts_list.append(ExpiringItemType(**alert))
            
            pagination_data = result.get("pagination", {})
            pagination = PaginationInfo(
                total=pagination_data.get("total", 0),
                page=pagination_data.get("page", 1),
                limit=pagination_data.get("limit", 10),
                total_pages=pagination_data.get("total_pages", 1),
                has_next=pagination_data.get("has_next", False),
                has_prev=pagination_data.get("has_prev", False)
            )
            
            return ExpiringItemsResponse(
                alerts=alerts_list,
                count=result.get("count", 0),
                days_ahead=result.get("days_ahead", days),
                pagination=pagination
            )
        except HTTPException:
            return ExpiringItemsResponse(
                alerts=[],
                count=0,
                days_ahead=days,
                pagination=PaginationInfo(total=0, page=1, limit=10, total_pages=1, has_next=False, has_prev=False)
            )

@strawberry.type
class Mutation:
    """GraphQL Mutation type for Inventory"""
    
    @strawberry.mutation
    async def createInventoryItem(self, item: InventoryItemInput) -> InventoryItemType:
        """Create a new inventory item"""
        from app.modules.inventory.routes import create_inventory_item, get_inventory_item
        from app.modules.inventory.schemas import InventoryItemCreate
        from decimal import Decimal
        from fastapi import HTTPException
        
        # Convert GraphQL input to Pydantic model
        item_data = InventoryItemCreate(
            name=item.name,
            product_type=item.product_type,
            category=item.category,
            sku_code=item.sku_code,
            brand_name=item.brand_name,
            manufacturer=item.manufacturer,
            description=item.description,
            unit=item.unit,
            pack_size=item.pack_size,
            current_stock=item.current_stock,
            min_stock_level=item.min_stock_level,
            storage_location=item.storage_location,
            unit_price=Decimal(str(item.unit_price)),
            batch_number=item.batch_number,
            expiry_date=item.expiry_date,
            status=item.status,
            supplier_name=item.supplier_name,
            supplier_phone=item.supplier_phone,
            is_sterile=item.is_sterile,
            is_single_use=item.is_single_use,
            is_reusable=item.is_reusable,
            expiry_tracking_required=item.expiry_tracking_required,
            dosage_strength=item.dosage_strength,
            dosage_form=item.dosage_form,
            route=item.route,
            schedule_type=item.schedule_type,
            prescription_required=item.prescription_required
        )
        
        try:
            # Note: GraphQL calls route directly, auth should be handled via GraphQL context
            result = await create_inventory_item(item_data, {})  # Pass empty dict for current_user
            # Route returns {"message": "...", "item_id": ...}
            item_id = result.get("item_id")
            if not item_id:
                raise ValueError("Item created but could not retrieve ID from response")
            
            # Fetch the created item
            item_data_result = await get_inventory_item(str(item_id), {})
            if item_data_result:
                # Convert Decimal to float if needed
                if isinstance(item_data_result.get("unit_price"), (int, float)):
                    item_data_result["unit_price"] = float(item_data_result["unit_price"])
                return InventoryItemType(**item_data_result)
            raise ValueError("Item created but could not retrieve from response")
        except HTTPException as e:
            raise ValueError(f"Failed to create inventory item: {e.detail}") from e
    
    @strawberry.mutation
    async def updateInventoryItem(
        self,
        item_id: str,
        item: InventoryItemUpdateInput
    ) -> Optional[InventoryItemType]:
        """Update an existing inventory item"""
        from app.modules.inventory.routes import update_inventory_item, get_inventory_item
        from app.modules.inventory.schemas import InventoryItemUpdate
        from decimal import Decimal
        from fastapi import HTTPException
        
        # Convert GraphQL input to Pydantic model
        item_data = InventoryItemUpdate(
            name=item.name,
            product_type=item.product_type,
            category=item.category,
            sku_code=item.sku_code,
            brand_name=item.brand_name,
            manufacturer=item.manufacturer,
            description=item.description,
            unit=item.unit,
            pack_size=item.pack_size,
            current_stock=item.current_stock,
            min_stock_level=item.min_stock_level,
            storage_location=item.storage_location,
            unit_price=Decimal(str(item.unit_price)) if item.unit_price is not None else None,
            batch_number=item.batch_number,
            expiry_date=item.expiry_date,
            status=item.status,
            supplier_name=item.supplier_name,
            supplier_phone=item.supplier_phone,
            is_sterile=item.is_sterile,
            is_single_use=item.is_single_use,
            is_reusable=item.is_reusable,
            expiry_tracking_required=item.expiry_tracking_required,
            dosage_strength=item.dosage_strength,
            dosage_form=item.dosage_form,
            route=item.route,
            schedule_type=item.schedule_type,
            prescription_required=item.prescription_required
        )
        
        try:
            # Note: GraphQL calls route directly, auth should be handled via GraphQL context
            await update_inventory_item(item_id, item_data, {})  # Pass empty dict for current_user
            # Fetch the updated item
            item_result = await get_inventory_item(item_id, {})
            if item_result:
                # Convert Decimal to float if needed
                if isinstance(item_result.get("unit_price"), (int, float)):
                    item_result["unit_price"] = float(item_result["unit_price"])
                return InventoryItemType(**item_result)
            return None
        except HTTPException as e:
            raise ValueError(f"Failed to update inventory item: {e.detail}") from e
    
    @strawberry.mutation
    async def deleteInventoryItem(self, item_id: str) -> bool:
        """Delete an inventory item by ID"""
        from app.modules.inventory.routes import delete_inventory_item
        from fastapi import HTTPException
        
        try:
            # Note: GraphQL calls route directly, auth should be handled via GraphQL context
            await delete_inventory_item(item_id, {})  # Pass empty dict for current_user
            return True
        except HTTPException:
            return False

# Create the GraphQL schema
schema = strawberry.Schema(query=Query, mutation=Mutation)

