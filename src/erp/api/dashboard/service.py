from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import Date, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from erp.api.dashboard.schemas import (
    DashboardKPIs,
    DashboardResponse,
    IncomingPurchaseOrderSummary,
    LowStockAlert,
    RecentSellOrderSummary,
    RevenueChartDataPoint,
)
from erp.api.modules.item.models import Item
from erp.api.modules.purchase_order.enums import POStatusEnum
from erp.api.modules.purchase_order.models import PurchaseOrder
from erp.api.modules.sell_order.enums import SOStatusEnum
from erp.api.modules.sell_order.models import SellOrder


class DashboardService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_kpis(self, workspace_id: UUID, low_stock_threshold: int = 10) -> DashboardKPIs:
        """Calculates top-level Key Performance Indicators and dynamic period-over-period trends."""
        now = datetime.now(UTC)
        thirty_days_ago = now - timedelta(days=30)
        sixty_days_ago = now - timedelta(days=60)

        # --- 1. Total Revenue & Trend ---
        revenue_stmt = select(func.coalesce(func.sum(SellOrder.total_amount), 0)).where(
            SellOrder.workspace_id == workspace_id,
            SellOrder.is_deleted.is_(False),
            SellOrder.status.in_([SOStatusEnum.CONFIRMED, SOStatusEnum.FULLFILLED]),
        )
        total_revenue = (await self.db.execute(revenue_stmt)).scalar_one()

        rev_current = (
            await self.db.execute(
                select(func.coalesce(func.sum(SellOrder.total_amount), 0)).where(
                    SellOrder.workspace_id == workspace_id,
                    SellOrder.is_deleted.is_(False),
                    SellOrder.status.in_([SOStatusEnum.CONFIRMED, SOStatusEnum.FULLFILLED]),
                    SellOrder.created_at >= thirty_days_ago,
                )
            )
        ).scalar_one()

        rev_prev = (
            await self.db.execute(
                select(func.coalesce(func.sum(SellOrder.total_amount), 0)).where(
                    SellOrder.workspace_id == workspace_id,
                    SellOrder.is_deleted.is_(False),
                    SellOrder.status.in_([SOStatusEnum.CONFIRMED, SOStatusEnum.FULLFILLED]),
                    SellOrder.created_at >= sixty_days_ago,
                    SellOrder.created_at < thirty_days_ago,
                )
            )
        ).scalar_one()
        revenue_trend, revenue_trend_up = self._calculate_trend(rev_current, rev_prev)

        # --- 2. Total Sell Orders & Trend ---
        so_count_stmt = select(func.count(SellOrder.id)).where(
            SellOrder.workspace_id == workspace_id,
            SellOrder.is_deleted.is_(False),
        )
        total_sell_orders = (await self.db.execute(so_count_stmt)).scalar_one()

        so_current = (
            await self.db.execute(
                select(func.count(SellOrder.id)).where(
                    SellOrder.workspace_id == workspace_id,
                    SellOrder.is_deleted.is_(False),
                    SellOrder.created_at >= thirty_days_ago,
                )
            )
        ).scalar_one()

        so_prev = (
            await self.db.execute(
                select(func.count(SellOrder.id)).where(
                    SellOrder.workspace_id == workspace_id,
                    SellOrder.is_deleted.is_(False),
                    SellOrder.created_at >= sixty_days_ago,
                    SellOrder.created_at < thirty_days_ago,
                )
            )
        ).scalar_one()
        sell_orders_trend, sell_orders_trend_up = self._calculate_trend(so_current, so_prev)

        # --- 3. Total Purchase Orders & Trend ---
        po_count_stmt = select(func.count(PurchaseOrder.id)).where(
            PurchaseOrder.workspace_id == workspace_id,
            PurchaseOrder.is_deleted.is_(False),
            PurchaseOrder.status.in_([POStatusEnum.SENT, POStatusEnum.RECEIVED]),
        )
        total_pos = (await self.db.execute(po_count_stmt)).scalar_one()

        po_current = (
            await self.db.execute(
                select(func.count(PurchaseOrder.id)).where(
                    PurchaseOrder.workspace_id == workspace_id,
                    PurchaseOrder.is_deleted.is_(False),
                    PurchaseOrder.status.in_([POStatusEnum.SENT, POStatusEnum.RECEIVED]),
                    PurchaseOrder.created_at >= thirty_days_ago,
                )
            )
        ).scalar_one()

        po_prev = (
            await self.db.execute(
                select(func.count(PurchaseOrder.id)).where(
                    PurchaseOrder.workspace_id == workspace_id,
                    PurchaseOrder.is_deleted.is_(False),
                    PurchaseOrder.status.in_([POStatusEnum.SENT, POStatusEnum.RECEIVED]),
                    PurchaseOrder.created_at >= sixty_days_ago,
                    PurchaseOrder.created_at < thirty_days_ago,
                )
            )
        ).scalar_one()
        purchase_orders_trend, purchase_orders_trend_up = self._calculate_trend(po_current, po_prev)

        # --- 4. Low Stock Items count ---
        items_stmt = (
            select(Item)
            .options(selectinload(Item.inventory_items))
            .where(
                Item.workspace_id == workspace_id,
                Item.is_deleted.is_(False),
            )
        )
        items = (await self.db.execute(items_stmt)).scalars().all()
        items_low_stock = sum(
            1 for item in items if (item.total_quantity_on_hand - item.quantity_allocated) <= low_stock_threshold
        )

        return DashboardKPIs(
            total_revenue=total_revenue,
            revenue_trend=revenue_trend,
            revenue_trend_up=revenue_trend_up,
            total_sell_orders=total_sell_orders,
            sell_orders_trend=sell_orders_trend,
            sell_orders_trend_up=sell_orders_trend_up,
            total_purchase_orders=total_pos,
            purchase_orders_trend=purchase_orders_trend,
            purchase_orders_trend_up=purchase_orders_trend_up,
            items_low_stock=items_low_stock,
        )

    @staticmethod
    def _calculate_trend(current: float, previous: float) -> tuple[str | None, bool]:
        """Helper to calculate percentage change between current and previous periods."""
        if previous == 0:
            if current > 0:
                return "No prior data", True
            return None, True

        change = ((current - previous) / previous) * 100
        is_up = change >= 0
        sign = "+" if is_up else ""
        return f"{sign}{round(change)}%", is_up

    async def get_revenue_chart_data(self, workspace_id: UUID, days: int = 30) -> list[RevenueChartDataPoint]:
        """Aggregates revenue grouped by date for the last X days."""
        target_date = datetime.now(UTC).today() - timedelta(days=days)

        stmt = (
            select(
                cast(SellOrder.created_at, Date).label("date"),
                func.coalesce(func.sum(SellOrder.total_amount), 0).label("revenue"),
            )
            .where(
                SellOrder.workspace_id == workspace_id,
                SellOrder.is_deleted.is_(False),
                SellOrder.status != "CANCELLED",
                cast(SellOrder.created_at, Date) >= target_date,
            )
            .group_by(cast(SellOrder.created_at, Date))
            .order_by(cast(SellOrder.created_at, Date).asc())
        )

        results = (await self.db.execute(stmt)).all()
        return [RevenueChartDataPoint(date=row.date, revenue=row.revenue) for row in results]

    async def get_recent_sell_orders(self, workspace_id: UUID, limit: int = 50) -> list[RecentSellOrderSummary]:
        """Fetches the most recently created sell orders, sliced via SQL .limit()"""
        stmt = (
            select(SellOrder)
            .where(
                SellOrder.workspace_id == workspace_id,
                SellOrder.is_deleted.is_(False),
            )
            .order_by(SellOrder.created_at.desc())
            .limit(limit)
        )

        result = await self.db.execute(stmt)
        orders = result.scalars().all()
        return [RecentSellOrderSummary.model_validate(order) for order in orders]

    async def get_incoming_purchase_orders(
        self, workspace_id: UUID, limit: int = 50
    ) -> list[IncomingPurchaseOrderSummary]:
        """Fetches recent purchase orders that are awaiting delivery, sliced via SQL .limit()"""
        stmt = (
            select(PurchaseOrder)
            .where(
                PurchaseOrder.workspace_id == workspace_id,
                PurchaseOrder.is_deleted.is_(False),
                PurchaseOrder.status == "SENT",
            )
            .order_by(PurchaseOrder.created_at.desc())
            .limit(limit)
        )

        result = await self.db.execute(stmt)
        orders = result.scalars().all()
        return [IncomingPurchaseOrderSummary.model_validate(order) for order in orders]

    async def get_low_stock_alerts(
        self, workspace_id: UUID, threshold: int = 10, limit: int = 50
    ) -> list[LowStockAlert]:
        """Fetches items whose actual available stock is running low."""
        stmt = (
            select(Item)
            .options(selectinload(Item.inventory_items))
            .where(
                Item.workspace_id == workspace_id,
                Item.is_deleted.is_(False),
            )
        )

        result = await self.db.execute(stmt)
        items = result.scalars().all()

        alerts = []
        for item in items:
            available = item.total_quantity_on_hand - item.quantity_allocated
            if available <= threshold:
                alerts.append(
                    LowStockAlert(
                        item_id=item.id,
                        sku=item.sku,
                        title=item.title,
                        quantity_on_hand=item.total_quantity_on_hand,
                        quantity_allocated=item.quantity_allocated,
                        quantity_available=available,
                        quantity_on_order=item.quantity_on_order,
                    )
                )

        # Sort by available quantity ascending and apply limit
        alerts.sort(key=lambda x: x.quantity_available)
        return alerts[:limit]

    async def get_full_dashboard(
        self, workspace_id: UUID, chart_days: int = 30, low_stock_threshold: int = 10, list_limit: int = 50
    ) -> DashboardResponse:
        """Orchestrates all queries to return the complete dashboard payload."""
        return DashboardResponse(
            kpis=await self.get_kpis(workspace_id, low_stock_threshold),
            revenue_chart=await self.get_revenue_chart_data(workspace_id, chart_days),
            recent_sell_orders=await self.get_recent_sell_orders(workspace_id, limit=list_limit),
            incoming_purchase_orders=await self.get_incoming_purchase_orders(workspace_id, limit=list_limit),
            low_stock_alerts=await self.get_low_stock_alerts(workspace_id, low_stock_threshold, limit=list_limit),
        )
