import uuid

from sqlalchemy import select

from erp.api.modules.customer.models import Customer
from erp.api.search.models import GlobalSearchIndex
from erp.database.base import AsyncSessionLocal
from erp.services.embedding import generate_embedding


async def process_customer_search_index(customer_id: uuid.UUID) -> None:
    async with AsyncSessionLocal() as db:
        customer = await db.get(Customer, customer_id)

        if not customer or customer.is_deleted:
            return

        title = f"{customer.first_name} {customer.last_name or ''}".strip()
        snippet = f"Email: {customer.email}"
        url = f"/customers/{customer.id}"

        text_to_embed = f"Customer: {title} {snippet}"
        vector = generate_embedding(text_to_embed)

        result = await db.execute(
            select(GlobalSearchIndex).where(
                GlobalSearchIndex.workspace_id == customer.workspace_id,
                GlobalSearchIndex.entity_type == "customer",
                GlobalSearchIndex.entity_id == customer.id,
            )
        )

        existing = result.scalar_one_or_none()

        if existing:
            existing.title = title
            existing.snippet = snippet
            existing.url = url
            existing.embedding = vector
        else:
            db.add(
                GlobalSearchIndex(
                    workspace_id=customer.workspace_id,
                    entity_type="customer",
                    entity_id=customer.id,
                    title=title,
                    snippet=snippet,
                    url=url,
                    embedding=vector,
                )
            )

        await db.commit()
