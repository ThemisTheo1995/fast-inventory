import uuid

from sqlalchemy import event, inspect
from sqlalchemy.orm import Session

from erp.api.base.models import AuditLog, BaseModel
from erp.api.base.utils import serialize_value


def should_audit(obj: object) -> bool:
    """Return True if object is a BaseModel instance and not opted out of auditing."""
    if not isinstance(obj, BaseModel):
        return False
    return getattr(obj, "__audited__", True)


@event.listens_for(Session, "before_flush")
def capture_model_changes(session: Session, *_args: object, **_kwargs: object) -> None:
    audit_records: list[AuditLog] = []

    current_user_id = session.info.get("user_id")
    current_workspace_id = session.info.get("workspace_id")

    # Handle New Instances (POST)
    for obj in session.new:
        if should_audit(obj):
            if obj.id is None:
                obj.id = uuid.uuid4()

            state = inspect(obj)
            new_data: dict[str, object] = {}

            for prop in state.mapper.column_attrs:
                val = getattr(obj, prop.key)
                if val is not None:
                    new_data[prop.key] = serialize_value(val)

            audit_records.append(
                AuditLog(
                    table_name=obj.__tablename__,
                    record_id=obj.id,
                    action="INSERT",
                    new_data=new_data,
                    user_id=current_user_id,
                    workspace_id=current_workspace_id,
                )
            )

    # Handle Updated Instances (PATCH/PUT/Soft Delete)
    for obj in session.dirty:
        if should_audit(obj) and session.is_modified(obj):
            state = inspect(obj)
            old_data: dict[str, object] = {}
            new_data: dict[str, object] = {}

            for prop in state.mapper.column_attrs:
                attr = state.attrs[prop.key]
                hist = attr.history
                if hist.has_changes():
                    old_val = hist.deleted[0] if hist.deleted else None
                    new_val = hist.added[0] if hist.added else None

                    old_data[prop.key] = serialize_value(old_val)
                    new_data[prop.key] = serialize_value(new_val)

            if old_data or new_data:
                action = "SOFT_DELETE" if new_data.get("is_deleted") is True else "UPDATE"

                audit_records.append(
                    AuditLog(
                        table_name=obj.__tablename__,
                        record_id=obj.id,
                        action=action,
                        old_data=old_data,
                        new_data=new_data,
                        user_id=current_user_id,
                        workspace_id=current_workspace_id,
                    )
                )

    # Handle Hard Deletes (DELETE)
    for obj in session.deleted:
        if should_audit(obj):
            state = inspect(obj)
            old_data: dict[str, object] = {}

            for prop in state.mapper.column_attrs:
                val = getattr(obj, prop.key)
                old_data[prop.key] = serialize_value(val)

            audit_records.append(
                AuditLog(
                    table_name=obj.__tablename__,
                    record_id=obj.id,
                    action="DELETE",
                    old_data=old_data,
                    user_id=current_user_id,
                    workspace_id=current_workspace_id,
                )
            )

    if audit_records:
        session.add_all(audit_records)
