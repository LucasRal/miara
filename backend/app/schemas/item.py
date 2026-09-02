"""Pydantic request/response models for the `items` example resource.

Schemas are the API contract: what the client sends and receives. They are
separate from any persistence model. `*Create` = input, `*Read` = output.
"""

from datetime import datetime

from pydantic import BaseModel, Field


class ItemCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None


class ItemRead(BaseModel):
    id: int
    name: str
    description: str | None
    created_at: datetime
