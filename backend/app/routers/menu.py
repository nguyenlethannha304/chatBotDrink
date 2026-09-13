from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models import MenuItem
from app.schemas import MenuItemCreate, MenuItemOut, MenuItemUpdate

router = APIRouter(prefix="/menu", tags=["menu"])


def require_admin(x_admin_key: str | None = Header(default=None)):
    """If ADMIN_API_KEY is configured, write endpoints require the X-Admin-Key header."""
    if settings.admin_api_key and x_admin_key != settings.admin_api_key:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Invalid admin key")


@router.get("", response_model=list[MenuItemOut])
async def list_menu(db: AsyncSession = Depends(get_db)):
    items = await db.scalars(select(MenuItem).order_by(MenuItem.category, MenuItem.name))
    return list(items)


@router.post("", response_model=MenuItemOut, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(require_admin)])
async def create_item(payload: MenuItemCreate, db: AsyncSession = Depends(get_db)):
    if await db.scalar(select(MenuItem).where(MenuItem.name == payload.name)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Menu item with this name already exists")
    item = MenuItem(**payload.model_dump())
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item


@router.put("/{item_id}", response_model=MenuItemOut, dependencies=[Depends(require_admin)])
async def update_item(item_id: int, payload: MenuItemUpdate, db: AsyncSession = Depends(get_db)):
    item = await db.get(MenuItem, item_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Menu item not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    await db.commit()
    await db.refresh(item)
    return item


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT,
               dependencies=[Depends(require_admin)])
async def delete_item(item_id: int, db: AsyncSession = Depends(get_db)):
    item = await db.get(MenuItem, item_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Menu item not found")
    await db.delete(item)
    await db.commit()
