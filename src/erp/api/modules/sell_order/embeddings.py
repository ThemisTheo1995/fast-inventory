import uuid

from sqlalchemy import select
from sqlalchemy.orm import selectinload, with_loader_criteria

from erp.services.ai.embedding import generate_embedding
from src.erp.api.modules.sell_order.models import SellOrder, SellOrderLine
from src.erp.api.search.enums import EntityTypeEnum
from src.erp.api.search.models import GlobalSearchIndex
from src.erp.database.base import AsyncSessionLocal


async def process_sell_order_search_index(sell_order_id: uuid.UUID) -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(SellOrder)
            .options(
                selectinload(SellOrder.customer),
                selectinload(SellOrder.sell_order_lines).selectinload(SellOrderLine.item),
                with_loader_criteria(SellOrderLine, SellOrderLine.is_deleted.is_(False), include_aliases=True),
            )
            .where(SellOrder.id == sell_order_id)
        )
        sell_order = result.scalar_one_or_none()

        if not sell_order or getattr(sell_order, "is_deleted", False):
            return

        customer_name = (
            f"{getattr(sell_order.customer, 'first_name', '')}\n"
            f"{getattr(sell_order.customer, 'last_name', '').strip()})"
        )

        line_items_text = []
        for line in sell_order.sell_order_lines:
            item_name = (
                getattr(line.item, "name", getattr(line.item, "title", "Unknown Item")) if line.item else "Unknown Item"
            )
            line_items_text.append(f"{line.quantity}x {item_name}")

        items_str = ", ".join(line_items_text) if line_items_text else "No active line items"

        title = f"SO #{sell_order.so_number}"
        snippet = f"Customer: {customer_name} | Status: {sell_order.status or ''} | Total: {sell_order.total_amount}"

        url = f"/sell-orders/{sell_order.id}"

        text_to_embed = (
            f"Document Type: Sell Order, Sales Order.\n"
            f"Sell Order Number (SO Number): {sell_order.so_number}\n"
            f"Customer Name: {customer_name}\n"
            f"Sell Order Status: {sell_order.status.label}\n"
            f"Total Amount: {sell_order.total_amount}\n"
            f"Line Items Ordered: {items_str}."
        )

        vector = generate_embedding(text_to_embed)

        index_result = await db.execute(
            select(GlobalSearchIndex).where(
                GlobalSearchIndex.workspace_id == sell_order.workspace_id,
                GlobalSearchIndex.entity_type == EntityTypeEnum.SELL_ORDER,
                GlobalSearchIndex.entity_id == sell_order.id,
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
                    workspace_id=sell_order.workspace_id,
                    entity_type=EntityTypeEnum.SELL_ORDER,
                    entity_id=sell_order.id,
                    title=title,
                    snippet=snippet,
                    url=url,
                    embedding=vector,
                )
            )

        await db.commit()
