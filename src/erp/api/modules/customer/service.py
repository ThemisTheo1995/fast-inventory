from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from erp.api.modules.customer.exceptions import CustomerEmailExistsError, CustomerNotFoundError
from erp.api.modules.customer.models import Customer
from erp.api.modules.customer.schemas import CustomerCreate, CustomerPaginatedResponse, CustomerUpdate


class CustomerService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def _get_active_customer(self, workspace_id: UUID, customer_id: UUID) -> Customer:
        """Helper method to securely fetch a customer enforcing tenant isolation."""
        stmt = select(Customer).where(
            Customer.workspace_id == workspace_id,
            Customer.id == customer_id,
            Customer.is_deleted.is_(False),
        )
        result = await self.db.execute(stmt)
        customer = result.scalar_one_or_none()

        if not customer:
            raise CustomerNotFoundError()
        return customer

    async def _check_email_unique(
        self, workspace_id: UUID, email: str, exclude_customer_id: UUID | None = None
    ) -> None:
        """Helper method to ensure email is unique within the workspace."""
        stmt = select(Customer).where(
            Customer.workspace_id == workspace_id, Customer.email == email, Customer.is_deleted.is_(False)
        )

        if exclude_customer_id:
            stmt = stmt.where(Customer.id != exclude_customer_id)

        result = await self.db.execute(stmt)
        if result.scalar_one_or_none():
            raise CustomerEmailExistsError()

    async def create_customer(self, workspace_id: UUID, data: CustomerCreate) -> Customer:
        """
        Create a customer.

        If a soft-deleted customer with the same email exists in the workspace,
        restore that customer instead of creating a new record.
        """
        await self._check_email_unique(workspace_id, data.email)

        stmt = select(Customer).where(
            Customer.workspace_id == workspace_id,
            Customer.email == data.email,
            Customer.is_deleted.is_(True),
        )

        result = await self.db.execute(stmt)
        deleted_customer = result.scalar_one_or_none()

        if deleted_customer:
            deleted_customer.is_deleted = False

            for field, value in data.model_dump().items():
                setattr(deleted_customer, field, value)

            await self.db.commit()
            await self.db.refresh(deleted_customer)
            return deleted_customer

        customer = Customer(
            workspace_id=workspace_id,
            **data.model_dump(),
        )

        self.db.add(customer)
        await self.db.commit()
        await self.db.refresh(customer)

        return customer

    async def get_customers(
        self, workspace_id: UUID, search: str | None = None, page: int = 1, limit: int = 20
    ) -> dict:
        """Fetches paginated customers and the total count."""

        # Build the base query
        base_query = select(Customer).where(
            Customer.workspace_id == workspace_id,
            Customer.is_deleted.is_(False),
        )

        if search:
            search_term = f"%{search}%"
            base_query = base_query.where(
                or_(
                    Customer.first_name.ilike(search_term),
                    Customer.last_name.ilike(search_term),
                    Customer.email.ilike(search_term),
                )
            )

        # Get the total count
        count_query = select(func.count()).select_from(base_query.subquery())
        count_result = await self.db.execute(count_query)
        total = count_result.scalar_one()

        # Apply pagination
        skip = (page - 1) * limit
        items_query = base_query.offset(skip).limit(limit)
        items_result = await self.db.execute(items_query)
        items = list(items_result.scalars().all())

        return CustomerPaginatedResponse(items=items, total=total)

    async def get_customer(self, workspace_id: UUID, customer_id: UUID) -> Customer:
        """Fetches a single active customer."""
        return await self._get_active_customer(workspace_id, customer_id)

    async def update_customer(self, workspace_id: UUID, customer_id: UUID, data: CustomerUpdate) -> Customer:
        """Applies partial updates, validating uniqueness if the email changes."""
        customer = await self._get_active_customer(workspace_id, customer_id)
        update_data = data.model_dump(exclude_unset=True)

        if "email" in update_data and update_data["email"] != customer.email:
            await self._check_email_unique(workspace_id, update_data["email"], exclude_customer_id=customer_id)

        for key, value in update_data.items():
            setattr(customer, key, value)

        self.db.add(customer)
        await self.db.commit()
        await self.db.refresh(customer)
        return customer

    async def delete_customer(self, workspace_id: UUID, customer_id: UUID) -> None:
        """Soft-deletes a customer."""
        customer = await self._get_active_customer(workspace_id, customer_id)
        customer.soft_delete()
        await self.db.commit()
