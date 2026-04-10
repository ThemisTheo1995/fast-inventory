import random
from datetime import datetime


class EbayItemClient:
    """Client for interacting with eBay's Inventory API."""

    def get_items(self, _since: datetime) -> list[dict]:
        """
        Generates 400+ mock eBay items to test frontend performance and filtering.
        """
        items = []

        # Categories and images for variety
        categories = ["Watch", "Camera", "Lens", "Keyboard", "Headphones", "Monitor"]
        brands = ["Seiko", "Canon", "Sony", "Logitech", "Bose", "Dell"]
        images = [
            "https://images.unsplash.com/photo-1524592093825-f537c3098ec0",
            "https://images.unsplash.com/photo-1617005082133-548c4dd27f35",
            "https://images.unsplash.com/photo-1511467687858-23d96c32e4ae",
            "https://images.unsplash.com/photo-1505740420928-5e560c06d30e",
            "https://images.unsplash.com/photo-1531346878377-a5be20888e57"
        ]

        for i in range(1, 421):
            category = random.choice(categories)
            brand = random.choice(brands)
            quantity = random.randint(0, 50)
            status = "ACTIVE" if quantity > 0 else "OUT_OF_STOCK"

            # Pad ID for consistent sorting (e.g., 001, 002)
            item_index = str(i).zfill(3)

            items.append({
                "sku": f"SKU-{category.upper()}-{item_index}",
                "availability": {
                    "shipToLocationAvailability": {
                        "quantity": quantity
                    }
                },
                "product": {
                    "title": f"{brand} Professional {category} Model {item_index}",
                    "description": f"High-quality {category} from {brand}. Perfect for professional use.",
                    "imageUrls": [random.choice(images) + f"?w=100&h=100&fit=crop&sig={i}"],
                    "aspects": {
                        "Brand": [brand],
                        "Condition": ["New"]
                    }
                },
                "price": {
                    "value": f"{random.uniform(10.0, 999.0):.2f}",
                    "currency": "GBP"
                },
                "listingId": f"294810{1000 + i}",
                "status": status
            })

        return items
