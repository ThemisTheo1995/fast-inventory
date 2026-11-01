from uuid import uuid4

import pytest
from pydantic import ValidationError

from erp.api.search.schemas import SearchResult


def test_search_result_valid():
    entity_id = uuid4()

    result = SearchResult(
        entity_type="item",
        entity_id=entity_id,
        title="Test Item",
        url="/items/test-item",
    )

    assert result.entity_type == "item"
    assert result.entity_id == entity_id
    assert result.title == "Test Item"
    assert result.url == "/items/test-item"


def test_search_result_accepts_uuid_string():
    entity_id = uuid4()

    result = SearchResult(
        entity_type="item",
        entity_id=str(entity_id),
        title="Test Item",
        url="/items/test-item",
    )

    assert result.entity_id == entity_id


@pytest.mark.parametrize(
    "missing_field",
    ["entity_type", "entity_id", "title", "url"],
)
def test_search_result_requires_all_fields(missing_field):
    data = {
        "entity_type": "item",
        "entity_id": uuid4(),
        "title": "Test Item",
        "url": "/items/test-item",
    }

    del data[missing_field]

    with pytest.raises(ValidationError):
        SearchResult(**data)


def test_search_result_rejects_invalid_uuid():
    with pytest.raises(ValidationError):
        SearchResult(
            entity_type="item",
            entity_id="invalid-uuid",
            title="Test Item",
            url="/items/test-item",
        )


def test_search_result_rejects_none_entity_type():
    with pytest.raises(ValidationError):
        SearchResult(
            entity_type=None,
            entity_id=uuid4(),
            title="Test Item",
            url="/items/test-item",
        )


def test_search_result_supports_from_attributes():
    entity_id = uuid4()

    record = type(
        "SearchRecord",
        (),
        {
            "entity_type": "customer",
            "entity_id": entity_id,
            "title": "John Smith",
            "url": "/customers/john-smith",
        },
    )()

    result = SearchResult.model_validate(record)

    assert result.entity_type == "customer"
    assert result.entity_id == entity_id
    assert result.title == "John Smith"
    assert result.url == "/customers/john-smith"
