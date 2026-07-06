from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.erp.api.modules.customer.exceptions import CustomerEmailExistsError, CustomerNotFoundError
from src.erp.api.modules.customer.models import Customer
from src.erp.api.modules.customer.schemas import CustomerCreate, CustomerUpdate


class CustomerService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _get_active_customer(self, workspace_id: UUID, customer_id: UUID) -> Customer:
        """Helper method to securely fetch a customer enforcing tenant isolation."""
        stmt = select(Customer).where(
            Customer.workspace_id == workspace_id,
            Customer.id == customer_id,
            Customer.is_deleted.is_(False),
        )
        customer = self.db.execute(stmt).scalar_one_or_none()

        if not customer:
            raise CustomerNotFoundError()
        return customer

    def _check_email_unique(self, workspace_id: UUID, email: str, exclude_customer_id: UUID | None = None) -> None:
        """Helper method to ensure email is unique within the workspace."""
        stmt = select(Customer).where(
            Customer.workspace_id == workspace_id, Customer.email == email, Customer.is_deleted.is_(False)
        )

        if exclude_customer_id:
            stmt = stmt.where(Customer.id != exclude_customer_id)

        if self.db.execute(stmt).scalar_one_or_none():
            raise CustomerEmailExistsError()

    def create_customer(self, workspace_id: UUID, data: CustomerCreate) -> Customer:
        """
        Create a customer.

        If a soft-deleted customer with the same email exists in the workspace,
        restore that customer instead of creating a new record.
        """

        self._check_email_unique(workspace_id, data.email)

        stmt = select(Customer).where(
            Customer.workspace_id == workspace_id,
            Customer.email == data.email,
            Customer.is_deleted.is_(True),
        )

        deleted_customer = self.db.execute(stmt).scalar_one_or_none()

        if deleted_customer:
            deleted_customer.is_deleted = False

            for field, value in data.model_dump().items():
                setattr(deleted_customer, field, value)

            self.db.commit()
            self.db.refresh(deleted_customer)
            return deleted_customer

        customer = Customer(
            workspace_id=workspace_id,
            **data.model_dump(),
        )

        self.db.add(customer)
        self.db.commit()
        self.db.refresh(customer)

        return customer

    def get_customers(self, workspace_id: UUID, skip: int = 0, limit: int = 100) -> list[Customer]:
        """Fetches all non-deleted customers for a workspace."""
        stmt = (
            select(Customer)
            .where(
                Customer.workspace_id == workspace_id,
                Customer.is_deleted.is_(False),
            )
            .offset(skip)
            .limit(limit)
        )

        return list(self.db.execute(stmt).scalars().all())

    def get_customer(self, workspace_id: UUID, customer_id: UUID) -> Customer:
        """Fetches a single active customer."""
        return self._get_active_customer(workspace_id, customer_id)

    def update_customer(self, workspace_id: UUID, customer_id: UUID, data: CustomerUpdate) -> Customer:
        """Applies partial updates, validating uniqueness if the email changes."""
        customer = self._get_active_customer(workspace_id, customer_id)
        update_data = data.model_dump(exclude_unset=True)

        if "email" in update_data and update_data["email"] != customer.email:
            self._check_email_unique(workspace_id, update_data["email"], exclude_customer_id=customer_id)

        for key, value in update_data.items():
            setattr(customer, key, value)

        self.db.add(customer)
        self.db.commit()
        self.db.refresh(customer)
        return customer

    def delete_customer(self, workspace_id: UUID, customer_id: UUID) -> None:
        """Soft-deletes a customer."""
        customer = self._get_active_customer(workspace_id, customer_id)
        customer.soft_delete()
        self.db.commit()
