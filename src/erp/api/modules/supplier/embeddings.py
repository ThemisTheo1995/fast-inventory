import uuid

from sqlalchemy import select

from erp.services.ai.embedding import generate_embedding
from src.erp.api.modules.supplier.models import Supplier
from src.erp.api.search.enums import EntityTypeEnum
from src.erp.api.search.models import GlobalSearchIndex
from src.erp.database.base import AsyncSessionLocal


async def process_supplier_search_index(supplier_id: uuid.UUID) -> None:
    async with AsyncSessionLocal() as db:
        supplier = await db.get(Supplier, supplier_id)

        if not supplier or supplier.is_deleted:
            return

        title = f"{supplier.name}".strip()
        snippet = f"Email: {supplier.email or ''}"
        url = f"/suppliers/{supplier.id}"

        text_to_embed = f"Supplier: {title} {snippet}"
        vector = generate_embedding(text_to_embed)

        result = await db.execute(
            select(GlobalSearchIndex).where(
                GlobalSearchIndex.workspace_id == supplier.workspace_id,
                GlobalSearchIndex.entity_type == EntityTypeEnum.SUPPLIER,
                GlobalSearchIndex.entity_id == supplier.id,
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
                    workspace_id=supplier.workspace_id,
                    entity_type=EntityTypeEnum.SUPPLIER,
                    entity_id=supplier.id,
                    title=title,
                    snippet=snippet,
                    url=url,
                    embedding=vector,
                )
            )

        await db.commit()
