import datetime
import enum
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from erp.api.auth.models import User
from erp.api.base.audit import should_audit
from erp.api.base.models import AuditLog, BaseModel
from erp.api.base.utils import serialize_value
from erp.api.workspace.models import Workspace

# ==============================================================================
# 1. TESTS FOR `serialize_value`
# ==============================================================================


class DummyEnum(enum.Enum):
    ACTIVE = "active"
    PENDING = "pending"


@pytest.mark.parametrize(
    "input_val, expected_type",
    [
        (uuid.uuid4(), str),
        (datetime.datetime.now(datetime.UTC), str),
        (datetime.datetime.now(datetime.UTC).date(), str),
        (DummyEnum.ACTIVE, str),
        ("standard string", str),
        (12345, int),
        (12.34, float),
        (True, bool),
        (None, type(None)),
        ({"key": "value"}, dict),
        (["item1", "item2"], list),
    ],
)
def test_serialize_value(input_val, expected_type):
    result = serialize_value(input_val)
    assert isinstance(result, expected_type)
    if isinstance(input_val, (uuid.UUID, datetime.datetime, datetime.date)):
        assert result == str(input_val)
    elif isinstance(input_val, enum.Enum):
        assert result == input_val.value


# ==============================================================================
# 2. TESTS FOR `should_audit`
# ==============================================================================


def test_should_audit_ignores_non_models():
    assert should_audit({"id": "123"}) is False
    assert should_audit(object()) is False
    assert should_audit(None) is False


def test_should_audit_identifies_audited_models():
    workspace = Workspace(id=uuid.uuid4())
    assert should_audit(workspace) is True


def test_should_audit_identifies_ignored_models():
    # AuditLog is ignored
    audit_log = AuditLog(id=uuid.uuid4(), table_name="test", record_id=uuid.uuid4(), action="INSERT")
    assert should_audit(audit_log) is False

    # User is now explicitly ignored
    user = User(id=uuid.uuid4(), email="test@test.com", first_name="A", last_name="B")
    assert should_audit(user) is False

    class DummyIgnoredModel(BaseModel):
        __tablename__ = "dummy_ignored"
        __audited__ = False

    assert should_audit(DummyIgnoredModel()) is False


# ==============================================================================
# 3. TESTS FOR `capture_model_changes` (Integration using Workspace)
# ==============================================================================


@pytest.mark.asyncio
async def test_audit_insert_creates_log_with_context(db_session: AsyncSession):
    user_id = uuid.uuid4()
    workspace_id = uuid.uuid4()

    db_session.info["user_id"] = user_id
    db_session.info["workspace_id"] = workspace_id

    ws_id = uuid.uuid4()
    workspace = Workspace(id=ws_id, name="Test Audit Workspace", email="audit-insert@test.com", is_deleted=False)
    db_session.add(workspace)
    await db_session.flush()

    result = await db_session.execute(select(AuditLog).where(AuditLog.record_id == ws_id))
    log: AuditLog = result.scalars().first()

    assert log is not None
    assert log.action == "INSERT"
    assert log.table_name == workspace.__tablename__
    assert log.user_id == user_id
    assert log.workspace_id == workspace_id
    assert log.new_data["name"] == "Test Audit Workspace"
    assert log.new_data["email"] == "audit-insert@test.com"


@pytest.mark.asyncio
async def test_audit_insert_generates_missing_uuid(db_session: AsyncSession):
    workspace = Workspace(name="No ID Workspace", email="noid@test.com", is_deleted=False)
    db_session.add(workspace)
    await db_session.flush()

    assert workspace.id is not None
    assert isinstance(workspace.id, uuid.UUID)

    result = await db_session.execute(select(AuditLog).where(AuditLog.record_id == workspace.id))
    log = result.scalars().first()
    assert log is not None
    assert log.action == "INSERT"


@pytest.mark.asyncio
async def test_audit_update_captures_diffs(db_session: AsyncSession):
    workspace = Workspace(
        id=uuid.uuid4(),
        name="Original Name",
        email="original@company.com",
        is_deleted=False,
    )
    db_session.add(workspace)
    await db_session.flush()

    workspace.name = "Updated Name"
    await db_session.flush()

    result = await db_session.execute(
        select(AuditLog).where(AuditLog.record_id == workspace.id, AuditLog.action == "UPDATE")
    )
    log = result.scalars().first()

    assert log is not None
    assert log.action == "UPDATE"
    assert log.old_data["name"] == "Original Name"
    assert log.new_data["name"] == "Updated Name"
    assert "email" not in log.new_data


@pytest.mark.asyncio
async def test_audit_update_ignores_unmodified_dirty_objects(db_session: AsyncSession):
    workspace = Workspace(
        id=uuid.uuid4(),
        name="Same Name",
        email="same@company.com",
        is_deleted=False,
    )
    db_session.add(workspace)
    await db_session.flush()

    workspace.name = workspace.name
    await db_session.flush()

    result = await db_session.execute(
        select(AuditLog).where(AuditLog.record_id == workspace.id, AuditLog.action == "UPDATE")
    )
    assert result.scalars().first() is None


@pytest.mark.asyncio
async def test_audit_soft_delete_action(db_session: AsyncSession):
    workspace = Workspace(
        id=uuid.uuid4(),
        name="Delete Me",
        email="softdelete@company.com",
        is_deleted=False,
    )
    db_session.add(workspace)
    await db_session.flush()

    workspace.is_deleted = True
    await db_session.flush()

    result = await db_session.execute(
        select(AuditLog).where(AuditLog.record_id == workspace.id, AuditLog.action == "SOFT_DELETE")
    )
    log = result.scalars().first()

    assert log is not None
    assert log.old_data["is_deleted"] is False
    assert log.new_data["is_deleted"] is True


@pytest.mark.asyncio
async def test_audit_hard_delete_captures_old_data(db_session: AsyncSession):
    workspace = Workspace(
        id=uuid.uuid4(),
        name="Hard Delete",
        email="delete@company.com",
        is_deleted=False,
    )
    db_session.add(workspace)
    await db_session.flush()

    await db_session.delete(workspace)
    await db_session.flush()

    result = await db_session.execute(
        select(AuditLog).where(AuditLog.record_id == workspace.id, AuditLog.action == "DELETE")
    )
    log = result.scalars().first()

    assert log is not None
    assert log.action == "DELETE"
    assert not log.new_data
    assert log.old_data["email"] == "delete@company.com"
    assert log.old_data["name"] == "Hard Delete"


@pytest.mark.asyncio
async def test_audit_prevents_infinite_recursion(db_session: AsyncSession):
    log_id = uuid.uuid4()
    audit_log = AuditLog(
        id=log_id, table_name="test_table", record_id=uuid.uuid4(), action="INSERT", new_data={"test": "data"}
    )

    db_session.add(audit_log)
    await db_session.flush()

    result = await db_session.execute(select(AuditLog).where(AuditLog.record_id == log_id))
    assert len(result.scalars().all()) == 0
