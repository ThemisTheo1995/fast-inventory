from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from erp.integrations.ebay.items.models import EbayItem
from erp.integrations.ebay.items.schemas import EbayCreateItem


class EbayItemRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, item_data: EbayCreateItem) -> EbayItem:
        db_item = EbayItem(**item_data.model_dump())

        try:
            self.db.add(db_item)
            self.db.commit()
            self.db.refresh(db_item)
        except IntegrityError:
            self.db.rollback()
            return None

        return db_item
