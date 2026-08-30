import pytest

from src.erp.database import base


def test_get_db_yields_and_closes():
    """Verifies get_db yields a session and closes it afterwards."""
    db_gen = base.get_db()

    session = next(db_gen)
    assert session is not None

    with pytest.raises(StopIteration):
        next(db_gen)
