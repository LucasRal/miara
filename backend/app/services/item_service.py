"""Business logic for the `items` example resource.

Services own the logic and (later) persistence. They never import routers or
FastAPI request objects — they take/return plain data and schemas so they stay
testable in isolation. This example uses an in-memory store; swap it for a real
DB layer without touching the router.
"""

from datetime import datetime, timezone

from app.schemas.item import ItemCreate, ItemRead

# In-memory stand-in for a database. Replace with a real repository/DB session.
_ITEMS: list[ItemRead] = []
_NEXT_ID = 1


def list_items(limit: int, offset: int) -> list[ItemRead]:
    return _ITEMS[offset : offset + limit]


def get_item(item_id: int) -> ItemRead | None:
    return next((i for i in _ITEMS if i.id == item_id), None)


def create_item(payload: ItemCreate) -> ItemRead:
    global _NEXT_ID
    item = ItemRead(
        id=_NEXT_ID,
        name=payload.name,
        description=payload.description,
        created_at=datetime.now(timezone.utc),
    )
    _ITEMS.append(item)
    _NEXT_ID += 1
    return item
