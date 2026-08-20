from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# --- KPIs ---
class DashboardKPIs(BaseModel):
    total_revenue: int = Field(
        default=0, description="Total amount from confirmed/completed sell orders (in cents/base unit)"
    )
    total_sell_orders: int = Field(default=0, description="Count of all active sell orders")
    total_purchase_orders: int = Field(default=0, description="Count of all purchase orders")
    items_low_stock: int = Field(default=0, description="Count of items where available stock is below threshold")


# --- Chart Data ---
class RevenueChartDataPoint(BaseModel):
    date: date
    revenue: int = Field(default=0, description="Revenue for the specific date")

    model_config = ConfigDict(from_attributes=True)


# --- Recent Sell Orders ---
class RecentSellOrderSummary(BaseModel):
    id: UUID
    so_number: str
    total_amount: int
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# --- Incoming Purchase Orders ---
class IncomingPurchaseOrderSummary(BaseModel):
    id: UUID
    po_number: str
    total_amount: int
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# --- Low Stock Alerts ---
class LowStockAlert(BaseModel):
    item_id: UUID
    sku: str
    title: str
    quantity_on_hand: int
    quantity_allocated: int
    quantity_available: int
    quantity_on_order: int

    model_config = ConfigDict(from_attributes=True)


# --- Aggregate Dashboard Response ---
class DashboardResponse(BaseModel):
    kpis: DashboardKPIs
    revenue_chart: list[RevenueChartDataPoint]
    recent_sell_orders: list[RecentSellOrderSummary]
    incoming_purchase_orders: list[IncomingPurchaseOrderSummary]
    low_stock_alerts: list[LowStockAlert]
