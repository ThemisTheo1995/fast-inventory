from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from erp.api.search.service import GlobalSearchService
from erp.database.base import get_db

router = APIRouter()


@router.get("/search")
async def global_search(
    workspace_id: UUID, db: Annotated[AsyncSession, Depends(get_db)], q: str, limit: int = 10
) -> list:
    service = GlobalSearchService(db)
    return await service.search(workspace_id=workspace_id, query_text=q, limit=limit)
