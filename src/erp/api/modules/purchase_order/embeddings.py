import uuid

from sqlalchemy import select
from sqlalchemy.orm import selectinload, with_loader_criteria

from erp.services.ai.embedding import generate_embedding
from src.erp.api.modules.purchase_order.models import PurchaseOrder, PurchaseOrderLine
from src.erp.api.search.enums import EntityTypeEnum
from src.erp.api.search.models import GlobalSearchIndex
from src.erp.database.base import AsyncSessionLocal


async def process_purchase_order_search_index(purchase_order_id: uuid.UUID) -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(PurchaseOrder)
            .options(
                selectinload(PurchaseOrder.supplier),
                selectinload(PurchaseOrder.purchase_order_lines).selectinload(PurchaseOrderLine.item),
                with_loader_criteria(PurchaseOrderLine, PurchaseOrderLine.is_deleted.is_(False), include_aliases=True),
            )
            .where(PurchaseOrder.id == purchase_order_id)
        )
        purchase_order = result.scalar_one_or_none()

        if not purchase_order or getattr(purchase_order, "is_deleted", False):
            return

        supplier_name = f"{purchase_order.supplier.name}\n{getattr(purchase_order.supplier, 'email', '').strip()}"

        line_items_text = []
        for line in purchase_order.purchase_order_lines:
            item_name = (
                getattr(line.item, "name", getattr(line.item, "title", "Unknown Item")) if line.item else "Unknown Item"
            )
            line_items_text.append(f"{line.quantity}x {item_name}")

        items_str = ", ".join(line_items_text) if line_items_text else "No active line items"

        title = f"PO #{purchase_order.po_number}"
        snippet = f"Supplier: {supplier_name} | Status: {purchase_order.status} | Total: {purchase_order.total_amount}"

        url = f"/purchase-orders/{purchase_order.id}"

        text_to_embed = (
            f"Document Type: Purchase Order.\n"
            f"Purchase Order Number (PO Number): {purchase_order.po_number}\n"
            f"Supplier Name: {supplier_name}\n"
            f"Purchase Order Status: {purchase_order.status.label}\n"
            f"Total Amount: {purchase_order.total_amount}\n"
            f"Line Items Ordered: {items_str}."
        )

        vector = generate_embedding(text_to_embed)

        index_result = await db.execute(
            select(GlobalSearchIndex).where(
                GlobalSearchIndex.workspace_id == purchase_order.workspace_id,
                GlobalSearchIndex.entity_type == EntityTypeEnum.PURCHASE_ORDER,
                GlobalSearchIndex.entity_id == purchase_order.id,
            )
        )

        existing = index_result.scalar_one_or_none()

        if existing:
            existing.title = title
            existing.snippet = snippet
            existing.url = url
            existing.embedding = vector
        else:
            db.add(
                GlobalSearchIndex(
                    workspace_id=purchase_order.workspace_id,
                    entity_type=EntityTypeEnum.PURCHASE_ORDER,
                    entity_id=purchase_order.id,
                    title=title,
                    snippet=snippet,
                    url=url,
                    embedding=vector,
                )
            )

        await db.commit()
