"""GraphQL schema for Billing module (Strawberry)"""
import strawberry
from typing import Optional, List
from decimal import Decimal
from app.common.graphql_types import PaginationInfo

@strawberry.type
class BillingItemType:
    """GraphQL Billing Item type"""
    id: Optional[str] = None
    tenant_id: Optional[str] = None
    invoice_id: Optional[int] = None
    item_type: str
    description: str
    quantity: int
    unit_price: float
    line_total: float
    inventory_item_id: Optional[int] = None
    created_at: Optional[str] = None  # Keep for billing_items (items have created_at)

@strawberry.input
class BillingItemInput:
    """GraphQL Billing Item input for creating"""
    item_type: str  # service, product
    description: str
    quantity: int
    unit_price: float
    line_total: float
    inventory_item_id: Optional[str] = None

@strawberry.type
class BillingInvoiceType:
    """GraphQL Billing Invoice type"""
    id: Optional[str] = None
    tenant_id: Optional[str] = None
    invoice_number: str
    patient_id: int
    appointment_id: int
    doctor_id: int
    issue_date: Optional[str] = None
    purpose: str
    total_amount: float
    tax_amount: float
    gst_percentage: float
    discount_amount: float
    coupon_code: Optional[str] = None
    adjustments: float
    amount_paid: float
    payment_mode: Optional[str] = None
    outstanding_amount: float
    status: str
    visit_charge: Optional[float] = 0.0
    medication_charge: Optional[float] = 0.0
    items: Optional[List[BillingItemType]] = None

@strawberry.input
class BillingInvoiceInput:
    """GraphQL Billing Invoice input for creating"""
    invoice_number: str
    patient_id: int
    appointment_id: int
    doctor_id: int
    issue_date: str
    purpose: str
    total_amount: float
    tax_amount: float
    gst_percentage: float
    discount_amount: float
    coupon_code: Optional[str] = None
    adjustments: float
    amount_paid: float
    payment_mode: Optional[str] = None
    status: str  # paid, partial, pending, refunded
    visit_charge: Optional[float] = 0.0
    medication_charge: Optional[float] = 0.0
    items: List[BillingItemInput]

@strawberry.input
class BillingInvoiceUpdateInput:
    """GraphQL Billing Invoice input for updating"""
    tax_amount: Optional[float] = None
    gst_percentage: Optional[float] = None
    discount_amount: Optional[float] = None
    coupon_code: Optional[str] = None
    adjustments: Optional[float] = None
    amount_paid: Optional[float] = None
    payment_mode: Optional[str] = None
    status: Optional[str] = None
    visit_charge: Optional[float] = None
    medication_charge: Optional[float] = None


@strawberry.type
class BillingInvoicesResponse:
    """Response type for paginated billing invoices"""
    invoices: List[BillingInvoiceType]
    pagination: PaginationInfo

@strawberry.type
class Query:
    """GraphQL Query type for Billing"""
    
    @strawberry.field
    async def invoice(self, invoice_id: str) -> Optional[BillingInvoiceType]:
        """Get a single invoice by ID"""
        from app.modules.billing.routes import get_invoice
        from fastapi import HTTPException
        
        try:
            # Note: GraphQL calls route directly, auth should be handled via GraphQL context
            # Route returns dict directly (not wrapped)
            invoice_data = await get_invoice(invoice_id, {})  # Pass empty dict for current_user
            if invoice_data:
                # Convert Decimal to float
                for key in ["total_amount", "tax_amount", "gst_percentage", "discount_amount", 
                           "adjustments", "amount_paid", "payment_mode", "outstanding_amount", "visit_charge", "medication_charge"]:
                    if key in invoice_data and invoice_data[key] is not None:
                        if isinstance(invoice_data[key], Decimal):
                            invoice_data[key] = float(invoice_data[key])
                
                # Convert date to string if needed
                if invoice_data.get("issue_date") and not isinstance(invoice_data["issue_date"], str):
                    invoice_data["issue_date"] = invoice_data["issue_date"].isoformat() if invoice_data["issue_date"] else None
                # Handle items
                items_list = []
                if invoice_data.get("items"):
                    for item in invoice_data["items"]:
                        item_data = item.copy()
                        # Convert Decimal to float
                        for key in ["unit_price", "line_total"]:
                            if key in item_data and item_data[key] is not None:
                                if isinstance(item_data[key], Decimal):
                                    item_data[key] = float(item_data[key])
                        if item_data.get("created_at") and not isinstance(item_data["created_at"], str):
                            item_data["created_at"] = item_data["created_at"].isoformat() if item_data["created_at"] else None
                        items_list.append(BillingItemType(**item_data))
                invoice_data["items"] = items_list
                
                return BillingInvoiceType(**invoice_data)
            return None
        except (HTTPException, Exception):
            return None
    
    @strawberry.field
    async def invoices(
        self,
        page: int = 1,
        limit: int = 10,
        patient_id: Optional[int] = None,
        status: Optional[str] = None
    ) -> BillingInvoicesResponse:
        """Get all invoices with optional filters"""
        from app.modules.billing.routes import get_invoices
        from fastapi import HTTPException
        
        try:
            # Note: GraphQL calls route directly, auth should be handled via GraphQL context
            result = await get_invoices(
                page=page,
                limit=limit,
                patient_id=patient_id,
                status=status,
                current_user={}
            )
            invoices_list = []
            for inv in result.get("invoices", []):
                inv_data = inv.copy()
                # Convert Decimal to float
                for key in ["total_amount", "tax_amount", "gst_percentage", "discount_amount",
                           "adjustments", "amount_paid", "payment_mode", "outstanding_amount", "visit_charge", "medication_charge"]:
                    if key in inv_data and inv_data[key] is not None:
                        if isinstance(inv_data[key], Decimal):
                            inv_data[key] = float(inv_data[key])
                
                # Convert date to string if needed
                if inv_data.get("issue_date") and not isinstance(inv_data["issue_date"], str):
                    inv_data["issue_date"] = inv_data["issue_date"].isoformat() if inv_data["issue_date"] else None
                invoices_list.append(BillingInvoiceType(**inv_data))
            
            pagination = PaginationInfo(**result.get("pagination", {}))
            return BillingInvoicesResponse(
                invoices=invoices_list,
                pagination=pagination
            )
        except HTTPException:
            return BillingInvoicesResponse(
                invoices=[],
                pagination=PaginationInfo(
                    total=0,
                    page=page,
                    limit=limit,
                    total_pages=0,
                    has_next=False,
                    has_prev=False
                )
            )

@strawberry.type
class Mutation:
    """GraphQL Mutation type for Billing"""
    
    @strawberry.mutation
    async def create_invoice(self, invoice: BillingInvoiceInput) -> BillingInvoiceType:
        """Create a new billing invoice"""
        from app.modules.billing.routes import create_invoice, get_invoice
        from app.modules.billing.schemas import BillingInvoiceCreate, BillingItemCreate
        from fastapi import HTTPException
        
        # Convert GraphQL input to Pydantic models
        items_data = [
            BillingItemCreate(
                item_type=item.item_type,
                description=item.description,
                quantity=item.quantity,
                unit_price=Decimal(str(item.unit_price)),
                line_total=Decimal(str(item.line_total)),
                inventory_item_id=item.inventory_item_id
            )
            for item in invoice.items
        ]
        
        invoice_data = BillingInvoiceCreate(
            invoice_number=invoice.invoice_number,
            patient_id=invoice.patient_id,
            appointment_id=invoice.appointment_id,
            doctor_id=invoice.doctor_id,
            issue_date=invoice.issue_date,
            purpose=invoice.purpose,
            total_amount=Decimal(str(invoice.total_amount)),
            tax_amount=Decimal(str(invoice.tax_amount)),
            gst_percentage=Decimal(str(invoice.gst_percentage)),
            discount_amount=Decimal(str(invoice.discount_amount)),
            coupon_code=invoice.coupon_code,
            adjustments=Decimal(str(invoice.adjustments)),
            amount_paid=Decimal(str(invoice.amount_paid)),
            payment_mode=invoice.payment_mode,
            status=invoice.status,
            visit_charge=Decimal(str(invoice.visit_charge)) if invoice.visit_charge else Decimal('0.0'),
            medication_charge=Decimal(str(invoice.medication_charge)) if invoice.medication_charge else Decimal('0.0'),
            items=items_data
        )
        
        try:
            # Note: GraphQL calls route directly, auth should be handled via GraphQL context
            result = await create_invoice(invoice_data, {})  # Pass empty dict for current_user
            # Route returns {"message": "...", "invoice_id": ...}
            invoice_id = result.get("invoice_id")
            if not invoice_id:
                raise ValueError("Invoice created but could not retrieve ID from response")
            
            # Fetch the created invoice
            invoice_data_result = await get_invoice(str(invoice_id), {})
            # Route returns dict directly (not wrapped) with items already included
            if invoice_data_result:
                # Convert Decimal to float
                for key in ["total_amount", "tax_amount", "gst_percentage", "discount_amount",
                           "adjustments", "amount_paid", "payment_mode", "outstanding_amount", "visit_charge", "medication_charge"]:
                    if key in invoice_data_result and invoice_data_result[key] is not None:
                        if isinstance(invoice_data_result[key], Decimal):
                            invoice_data_result[key] = float(invoice_data_result[key])
                
                # Convert date to string if needed (already converted in route)
                # Handle items - already converted in route
                items_list = []
                if invoice_data_result.get("items"):
                    for item in invoice_data_result["items"]:
                        items_list.append(BillingItemType(**item))
                invoice_data_result["items"] = items_list
                
                return BillingInvoiceType(**invoice_data_result)
            raise ValueError("Invoice created but could not retrieve from response")
        except HTTPException as e:
            raise ValueError(f"Failed to create invoice: {e.detail}") from e
    
    @strawberry.mutation
    async def update_invoice(
        self,
        invoice_id: str,
        invoice: BillingInvoiceUpdateInput
    ) -> Optional[BillingInvoiceType]:
        """Update an existing invoice"""
        from app.modules.billing.routes import update_invoice, get_invoice
        from app.modules.billing.schemas import BillingInvoiceUpdate
        from fastapi import HTTPException
        
        # Convert GraphQL input to Pydantic model
        invoice_data = BillingInvoiceUpdate(
            tax_amount=Decimal(str(invoice.tax_amount)) if invoice.tax_amount is not None else None,
            gst_percentage=Decimal(str(invoice.gst_percentage)) if invoice.gst_percentage is not None else None,
            discount_amount=Decimal(str(invoice.discount_amount)) if invoice.discount_amount is not None else None,
            coupon_code=invoice.coupon_code,
            adjustments=Decimal(str(invoice.adjustments)) if invoice.adjustments is not None else None,
            amount_paid=Decimal(str(invoice.amount_paid)) if invoice.amount_paid is not None else None,
            payment_mode=invoice.payment_mode,
            status=invoice.status,
            visit_charge=Decimal(str(invoice.visit_charge)) if invoice.visit_charge is not None else None,
            medication_charge=Decimal(str(invoice.medication_charge)) if invoice.medication_charge is not None else None
        )
        
        try:
            update_invoice(invoice_id, invoice_data, {})  # Pass empty dict for current_user
            # Fetch the updated invoice
            # Note: GraphQL calls route directly, auth should be handled via GraphQL context
            invoice_result = await get_invoice(invoice_id, {})
            # Route returns dict directly (not wrapped) with items already included
            if invoice_result:
                # Convert Decimal to float (already converted in route, but check anyway)
                for key in ["total_amount", "tax_amount", "gst_percentage", "discount_amount",
                           "adjustments", "amount_paid", "outstanding_amount", "visit_charge", "medication_charge"]:
                    if key in invoice_result and invoice_result[key] is not None:
                        if isinstance(invoice_result[key], Decimal):
                            invoice_result[key] = float(invoice_result[key])
                
                # Handle items - already converted in route
                items_list = []
                if invoice_result.get("items"):
                    for item in invoice_result["items"]:
                        items_list.append(BillingItemType(**item))
                invoice_result["items"] = items_list
                
                return BillingInvoiceType(**invoice_result)
            return None
        except HTTPException as e:
            raise ValueError(f"Failed to update invoice: {e.detail}") from e
    
    @strawberry.mutation
    async def delete_invoice(self, invoice_id: str) -> bool:
        """Delete an invoice by ID"""
        from app.modules.billing.routes import delete_invoice
        from fastapi import HTTPException
        
        try:
            # Note: GraphQL calls route directly, auth should be handled via GraphQL context
            await delete_invoice(invoice_id, {})  # Pass empty dict for current_user
            return True
        except HTTPException:
            return False

# Create the GraphQL schema
schema = strawberry.Schema(query=Query, mutation=Mutation)

