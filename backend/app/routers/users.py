from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import Favorite, MenuItem, User, UserPreference
from app.schemas import FavoriteOut, PreferenceOut, PreferenceUpdate, UserOut
from app.services.auth import get_current_user

router = APIRouter(prefix="/users", tags=["users"])


async def _get_prefs(db: AsyncSession, user: User) -> UserPreference:
    prefs = await db.scalar(select(UserPreference).where(UserPreference.user_id == user.id))
    if prefs is None:
        prefs = UserPreference(user_id=user.id, tastes=[], drink_types=[],
                               allergies=[], dietary_restrictions=[])
        db.add(prefs)
        await db.flush()
    return prefs


@router.get("/me", response_model=UserOut)
async def get_me(user: User = Depends(get_current_user)):
    return user


@router.get("/me/preferences", response_model=PreferenceOut)
async def get_preferences(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await _get_prefs(db, user)


@router.put("/me/preferences", response_model=PreferenceOut)
async def update_preferences(
    payload: PreferenceUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    prefs = await _get_prefs(db, user)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(prefs, field, value)
    await db.commit()
    await db.refresh(prefs)
    return prefs


@router.get("/me/favorites", response_model=list[FavoriteOut])
async def list_favorites(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    favorites = await db.scalars(
        select(Favorite)
        .where(Favorite.user_id == user.id)
        .options(selectinload(Favorite.menu_item))
    )
    return list(favorites)


@router.post("/me/favorites/{menu_item_id}", response_model=FavoriteOut,
             status_code=status.HTTP_201_CREATED)
async def add_favorite(
    menu_item_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if await db.get(MenuItem, menu_item_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Menu item not found")
    existing = await db.scalar(
        select(Favorite).where(Favorite.user_id == user.id, Favorite.menu_item_id == menu_item_id)
    )
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "Already in favorites")
    favorite = Favorite(user_id=user.id, menu_item_id=menu_item_id)
    db.add(favorite)
    await db.commit()
    favorite = await db.scalar(
        select(Favorite).where(Favorite.id == favorite.id).options(selectinload(Favorite.menu_item))
    )
    return favorite


@router.delete("/me/favorites/{menu_item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_favorite(
    menu_item_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    favorite = await db.scalar(
        select(Favorite).where(Favorite.user_id == user.id, Favorite.menu_item_id == menu_item_id)
    )
    if favorite is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Favorite not found")
    await db.delete(favorite)
    await db.commit()
