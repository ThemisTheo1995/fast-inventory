from sqlalchemy.orm import Session


class EbayOrderRepository:
    def __init__(self, db: Session) -> None:
        self.db = db
