from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from erp.api.base.service import BaseService
from erp.api.modules.bin.exceptions import BinHasInventoryItemsError, BinNotFoundError
from erp.api.modules.bin.filters.bin import BinFilter
from erp.api.modules.bin.models import Bin
from erp.api.modules.bin.schemas.bin import BinCreate, BinListResponse, BinPaginatedResponse, BinResponse, BinUpdate
from erp.api.modules.bin.schemas.bin_expanded import BinExpandedResponse
from erp.api.modules.inventory.models import Inventory


class BinService(BaseService[Bin]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db, Bin)

    async def _get_active_bin(self, workspace_id: UUID, bin_id: UUID, expand: list[str] | None = None) -> Bin:
        """Helper method to securely fetch a bin enforcing tenant isolation."""
        stmt = select(Bin).where(
            Bin.workspace_id == workspace_id,
            Bin.id == bin_id,
            Bin.is_deleted.is_(False),
        )

        if expand:
            loader_options = self.build_loader_options(expand)
            stmt = stmt.options(*loader_options).execution_options(populate_existing=True)

        result = await self.db.execute(stmt)
        bin = result.unique().scalar_one_or_none()

        if not bin:
            raise BinNotFoundError()

        return bin

    async def create_bin(self, workspace_id: UUID, data: BinCreate) -> Bin:
        """Create a bin."""
        bin = Bin(
            workspace_id=workspace_id,
            **data.model_dump(),
        )

        self.db.add(bin)
        await self.db.commit()
        await self.db.refresh(bin)

        return bin

    async def get_bins(
        self,
        workspace_id: UUID,
        search: str | None = None,
        page: int = 1,
        limit: int = 20,
        expand: list[str] | None = None,
        filters: BinFilter | None = None,
    ) -> BinPaginatedResponse:
        """Fetch paginated bins with their total quantity on hand."""

        bin_filter = filters or BinFilter(is_deleted=False)

        query = select(Bin).where(Bin.workspace_id == workspace_id)

        query = bin_filter.apply(query, Bin)
        query = bin_filter.apply_search(query, search)

        # Count matching bins.
        count_result = await self.db.execute(select(func.count()).select_from(query.subquery()))
        total = count_result.scalar_one()

        # Aggregate active inventory quantities per bin.
        inventory_totals = (
            select(
                Inventory.bin_id,
                func.sum(Inventory.quantity_on_hand).label("quantity_on_hand"),
            )
            .where(
                Inventory.workspace_id == workspace_id,
                Inventory.is_deleted.is_(False),
            )
            .group_by(Inventory.bin_id)
            .subquery()
        )

        # Fetch bins and their stock totals.
        items_query = (
            select(
                Bin,
                func.coalesce(inventory_totals.c.quantity_on_hand, 0),
            )
            .outerjoin(inventory_totals, inventory_totals.c.bin_id == Bin.id)
            .where(Bin.id.in_(query.with_only_columns(Bin.id)))
            .order_by(Bin.created_at.desc(), Bin.id.desc())
            .offset((page - 1) * limit)
            .limit(limit)
        )

        if expand:
            items_query = items_query.options(*self.build_loader_options(expand)).execution_options(
                populate_existing=True
            )

        result = await self.db.execute(items_query)

        items = [
            BinListResponse.model_validate(bin).model_copy(update={"quantity_on_hand": int(quantity or 0)})
            for bin, quantity in result.all()
        ]

        return BinPaginatedResponse(items=items, total=total)

    async def get_bin(
        self, workspace_id: UUID, bin_id: UUID, expand: list[str] | None = None
    ) -> BinResponse | BinExpandedResponse:
        """Fetches a single active bin."""
        bin = await self._get_active_bin(workspace_id, bin_id, expand=expand)

        return BinExpandedResponse.model_validate(bin) if expand else BinResponse.model_validate(bin)

    async def update_bin(self, workspace_id: UUID, bin_id: UUID, data: BinUpdate) -> Bin:
        """Applies partial updates."""
        bin = await self._get_active_bin(workspace_id, bin_id)
        update_data = data.model_dump(exclude_unset=True)

        for key, value in update_data.items():
            setattr(bin, key, value)

        self.db.add(bin)
        await self.db.commit()
        await self.db.refresh(bin)
        return bin

    async def delete_bin(self, workspace_id: UUID, bin_id: UUID) -> None:
        """Soft-deletes a bin if it contains no active physical stock."""
        bin = await self._get_active_bin(
            workspace_id,
            bin_id,
            expand=["inventory_items"],
        )

        has_active_stock = any(inv.quantity_on_hand > 0 and not inv.is_deleted for inv in bin.inventory_items)

        if has_active_stock:
            raise BinHasInventoryItemsError()

        bin.soft_delete()
        await self.db.commit()
