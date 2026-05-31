from datetime import datetime


class StandardClient:
    def get_orders(self, _since: datetime) -> list[dict]:
        return []

    def create_order(self, order_data: dict) -> dict:
        return {
            **order_data,
            "external_id": "STND-123",
            "marketplace": "standard"
        }

    def cancel_order(self, _order_id: str) -> None:
        pass
