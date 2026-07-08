from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from src.erp.api.modules.supplier.exceptions import SupplierEmailExistsError, SupplierNotFoundError
from src.erp.api.modules.supplier.models import Supplier
from src.erp.api.modules.supplier.schemas import SupplierCreate, SupplierPaginatedResponse, SupplierUpdate


class SupplierService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _get_active_supplier(self, workspace_id: UUID, supplier_id: UUID) -> Supplier:
        """Helper method to securely fetch a supplier enforcing tenant isolation."""
        stmt = select(Supplier).where(
            Supplier.workspace_id == workspace_id,
            Supplier.id == supplier_id,
            Supplier.is_deleted.is_(False),
        )
        supplier = self.db.execute(stmt).scalar_one_or_none()

        if not supplier:
            raise SupplierNotFoundError()
        return supplier

    def _check_email_unique(
        self, workspace_id: UUID, email: str | None, exclude_supplier_id: UUID | None = None
    ) -> None:
        """Helper method to ensure email is unique within the workspace if provided."""
        if not email:
            return

        stmt = select(Supplier).where(
            Supplier.workspace_id == workspace_id, Supplier.email == email, Supplier.is_deleted.is_(False)
        )

        if exclude_supplier_id:
            stmt = stmt.where(Supplier.id != exclude_supplier_id)

        if self.db.execute(stmt).scalar_one_or_none():
            raise SupplierEmailExistsError()

    def create_supplier(self, workspace_id: UUID, data: SupplierCreate) -> Supplier:
        """
        Create a supplier.

        If a soft-deleted supplier with the same email exists in the workspace,
        restore that supplier instead of creating a new record.
        """
        if data.email:
            self._check_email_unique(workspace_id, data.email)

            stmt = select(Supplier).where(
                Supplier.workspace_id == workspace_id,
                Supplier.email == data.email,
                Supplier.is_deleted.is_(True),
            )
            deleted_supplier = self.db.execute(stmt).scalar_one_or_none()

            if deleted_supplier:
                deleted_supplier.is_deleted = False

                for field, value in data.model_dump().items():
                    setattr(deleted_supplier, field, value)

                self.db.commit()
                self.db.refresh(deleted_supplier)
                return deleted_supplier

        supplier = Supplier(
            workspace_id=workspace_id,
            **data.model_dump(),
        )

        self.db.add(supplier)
        self.db.commit()
        self.db.refresh(supplier)

        return supplier

    def get_suppliers(
        self, workspace_id: UUID, search: str | None = None, page: int = 1, limit: int = 20
    ) -> SupplierPaginatedResponse:
        """Fetches paginated suppliers and the total count."""

        # Build the base query (filters applied, but NO limit/offset yet)
        base_query = select(Supplier).where(
            Supplier.workspace_id == workspace_id,
            Supplier.is_deleted.is_(False),
        )

        if search:
            search_term = f"%{search}%"
            base_query = base_query.where(or_(Supplier.name.ilike(search_term), Supplier.email.ilike(search_term)))

        # Get the total count of matching records
        count_query = select(func.count()).select_from(base_query.subquery())
        total = self.db.execute(count_query).scalar_one()

        # Apply pagination and fetch the actual items
        skip = (page - 1) * limit
        items_query = base_query.offset(skip).limit(limit)
        items = list(self.db.execute(items_query).scalars().all())

        return SupplierPaginatedResponse(items=items, total=total)

    def get_supplier(self, workspace_id: UUID, supplier_id: UUID) -> Supplier:
        """Fetches a single active supplier."""
        return self._get_active_supplier(workspace_id, supplier_id)

    def update_supplier(self, workspace_id: UUID, supplier_id: UUID, data: SupplierUpdate) -> Supplier:
        """Applies partial updates, validating uniqueness if the email changes."""
        supplier = self._get_active_supplier(workspace_id, supplier_id)
        update_data = data.model_dump(exclude_unset=True)

        if "email" in update_data and update_data["email"] != supplier.email:
            self._check_email_unique(workspace_id, update_data["email"], exclude_supplier_id=supplier_id)

        for key, value in update_data.items():
            setattr(supplier, key, value)

        self.db.add(supplier)
        self.db.commit()
        self.db.refresh(supplier)
        return supplier

    def delete_supplier(self, workspace_id: UUID, supplier_id: UUID) -> None:
        """Soft-deletes a supplier."""
        supplier = self._get_active_supplier(workspace_id, supplier_id)
        supplier.soft_delete()
        self.db.commit()
