from fastapi import HTTPException
from sqlalchemy.orm import Session

from erp.api.supplier.models import Supplier
from erp.api.user.models import SupplierUser, User


class OnboardingService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def onboard_supplier(
        self,
        name: str,
        email: str,
        first_name: str,
        last_name: str
    ) -> SupplierUser:
        """
        Creates a new Supplier and User, linking them via SupplierUser.
        Uses a single transaction to ensure atomicity.
        """
        try:
            # 1. Create the Supplier (Workspace)
            supplier = Supplier(name=name, email=email)
            self.db.add(supplier)
            self.db.flush()

            # 2. Get or Create the User
            user = self.db.query(User).filter(User.email == email).first()
            if not user:
                user = User(
                    email=email,
                    first_name=first_name,
                    last_name=last_name
                )
                self.db.add(user)
                self.db.flush()

            # 3. Link them via SupplierUser
            supplier_user = SupplierUser(
                user_id=user.id,
                supplier_id=supplier.id
            )
            self.db.add(supplier_user)

            self.db.commit()

            return supplier_user

        except Exception as e:
            self.db.rollback()
            raise HTTPException(
                status_code=400,
                detail=f"Onboarding failed: {e!s}"
            ) from e
