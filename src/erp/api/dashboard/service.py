from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import Date, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from src.erp.api.dashboard.schemas import (
    DashboardKPIs,
    DashboardResponse,
    IncomingPurchaseOrderSummary,
    LowStockAlert,
    RecentSellOrderSummary,
    RevenueChartDataPoint,
)
from src.erp.api.modules.inventory.models import Inventory
from src.erp.api.modules.purchase_order.models import PurchaseOrder
from src.erp.api.modules.sell_order.models import SellOrder


class DashboardService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_kpis(self, workspace_id: UUID, low_stock_threshold: int = 10) -> DashboardKPIs:
        """Calculates top-level Key Performance Indicators for the dashboard."""

        # Total Revenue (Excluding cancelled orders)
        revenue_stmt = select(func.coalesce(func.sum(SellOrder.total_amount), 0)).where(
            SellOrder.workspace_id == workspace_id,
            SellOrder.is_deleted.is_(False),
            SellOrder.status.in_(["CONFIRMED", "FULLFILLED"]),
        )
        total_revenue = (await self.db.execute(revenue_stmt)).scalar_one()

        # Total Sell Orders
        so_count_stmt = select(func.count(SellOrder.id)).where(
            SellOrder.workspace_id == workspace_id,
            SellOrder.is_deleted.is_(False),
        )
        total_sell_orders = (await self.db.execute(so_count_stmt)).scalar_one()

        # Total Purchase Orders
        po_count_stmt = select(func.count(PurchaseOrder.id)).where(
            PurchaseOrder.workspace_id == workspace_id,
            PurchaseOrder.is_deleted.is_(False),
            PurchaseOrder.status.in_(["SENT", "RECEIVED"]),
        )
        total_pos = (await self.db.execute(po_count_stmt)).scalar_one()

        # Low Stock Items count (Quantity on hand - allocated <= threshold)
        low_stock_count_stmt = select(func.count(Inventory.id)).where(
            Inventory.workspace_id == workspace_id,
            Inventory.is_deleted.is_(False),
            (Inventory.quantity_on_hand - Inventory.quantity_allocated) <= low_stock_threshold,
        )
        items_low_stock = (await self.db.execute(low_stock_count_stmt)).scalar_one()

        return DashboardKPIs(
            total_revenue=total_revenue,
            total_sell_orders=total_sell_orders,
            total_purchase_orders=total_pos,
            items_low_stock=items_low_stock,
        )

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
        """Fetches inventory items whose actual available stock is running low, sliced via SQL .limit()"""
        stmt = (
            select(Inventory)
            .options(selectinload(Inventory.item))
            .where(
                Inventory.workspace_id == workspace_id,
                Inventory.is_deleted.is_(False),
                (Inventory.quantity_on_hand - Inventory.quantity_allocated) <= threshold,
            )
            .order_by((Inventory.quantity_on_hand - Inventory.quantity_allocated).asc())
            .limit(limit)
        )

        result = await self.db.execute(stmt)
        inventories = result.scalars().all()

        alerts = []
        for inv in inventories:
            if not inv.item or inv.item.is_deleted:
                continue

            alerts.append(
                LowStockAlert(
                    item_id=inv.item.id,
                    sku=inv.item.sku,
                    title=inv.item.title,
                    quantity_on_hand=inv.quantity_on_hand,
                    quantity_allocated=inv.quantity_allocated,
                    quantity_available=inv.quantity_available,
                    quantity_on_order=inv.quantity_on_order,
                )
            )
        return alerts

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
