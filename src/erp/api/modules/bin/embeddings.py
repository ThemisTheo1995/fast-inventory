import uuid

from sqlalchemy import select

from erp.api.modules.bin.models import Bin
from erp.api.search.enums import EntityTypeEnum
from erp.api.search.models import GlobalSearchIndex
from erp.database.base import AsyncSessionLocal
from erp.services.ai.embedding import generate_embedding


async def process_bin_search_index(bin_id: uuid.UUID) -> None:
    async with AsyncSessionLocal() as db:
        bin = await db.get(Bin, bin_id)

        if not bin or bin.is_deleted:
            return

        title = f"Bin: {bin.code} {bin.zone or ''}".strip()
        snippet = f"Zone: {bin.zone or 'N/A'}"
        url = f"/bins/{bin.id}"

        text_to_embed = f"Bin: {title} {snippet}"
        vector = generate_embedding(text_to_embed)

        result = await db.execute(
            select(GlobalSearchIndex).where(
                GlobalSearchIndex.workspace_id == bin.workspace_id,
                GlobalSearchIndex.entity_type == EntityTypeEnum.BIN,
                GlobalSearchIndex.entity_id == bin.id,
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
                    workspace_id=bin.workspace_id,
                    entity_type=EntityTypeEnum.BIN,
                    entity_id=bin.id,
                    title=title,
                    snippet=snippet,
                    url=url,
                    embedding=vector,
                )
            )

        await db.commit()
