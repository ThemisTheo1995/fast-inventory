from uuid import UUID

from pydantic import TypeAdapter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.erp.api.search.models import GlobalSearchIndex
from src.erp.api.search.schemas import SearchResult
from src.erp.services.embedding import generate_embedding


class GlobalSearchService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def search(self, workspace_id: UUID, query_text: str, limit: int = 10) -> list[SearchResult]:
        """Search the global search index for a given workspace and query text."""
        query_vector = generate_embedding(query_text)

        stmt = (
            select(GlobalSearchIndex)
            .where(
                GlobalSearchIndex.workspace_id == workspace_id,
                GlobalSearchIndex.embedding.is_not(None),
            )
            .order_by(GlobalSearchIndex.embedding.cosine_distance(query_vector))
            .limit(limit)
        )

        # Properly await the database execution
        result = await self.db.execute(stmt)
        records = result.scalars().all()

        search_adapter = TypeAdapter(list[SearchResult])
        return search_adapter.validate_python(records)
