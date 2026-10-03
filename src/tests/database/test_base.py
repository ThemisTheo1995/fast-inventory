import pytest

from erp.database import base


@pytest.mark.asyncio
async def test_get_db_yields_and_closes():
    """Verifies get_db yields a session and closes it afterwards."""
    db_gen = base.get_db()

    session = await anext(db_gen)
    assert session is not None

    with pytest.raises(StopAsyncIteration):
        await anext(db_gen)
