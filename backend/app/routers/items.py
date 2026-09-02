"""HTTP layer for the `items` example resource.

Routers translate between HTTP and the service layer: parse/validate input,
call a service, map results to status codes. No business logic here.

This whole module is an illustrative example — delete it (and its schema/
service) once you add real resources, and drop its include in app/main.py.
"""

from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies import Pagination, pagination
from app.schemas.item import ItemCreate, ItemRead
from app.services import item_service

router = APIRouter(prefix="/items", tags=["items"])


@router.get("", response_model=list[ItemRead])
async def list_items(page: Pagination = Depends(pagination)) -> list[ItemRead]:
    return item_service.list_items(limit=page.limit, offset=page.offset)


@router.get("/{item_id}", response_model=ItemRead)
async def get_item(item_id: int) -> ItemRead:
    item = item_service.get_item(item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    return item


@router.post("", response_model=ItemRead, status_code=status.HTTP_201_CREATED)
async def create_item(payload: ItemCreate) -> ItemRead:
    return item_service.create_item(payload)
