import uuid

from pydantic import BaseModel, ConfigDict


class SearchResult(BaseModel):
    entity_type: str
    entity_id: uuid.UUID
    title: str
    url: str

    model_config = ConfigDict(from_attributes=True)
