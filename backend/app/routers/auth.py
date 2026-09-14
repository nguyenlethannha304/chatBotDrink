from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import ChatMessage, User, UserPreference
from app.schemas import LoginRequest, RegisterRequest, TokenResponse
from app.services.agent import WELCOME_MESSAGE
from app.services.auth import create_access_token

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, db: AsyncSession = Depends(get_db)):
    existing = await db.scalar(select(User).where(User.phone == payload.phone))
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "Phone number already registered")

    user = User(phone=payload.phone, name=payload.name, address=payload.address)
    user.preferences = UserPreference(
        tastes=[], drink_types=[], allergies=[], dietary_restrictions=[]
    )
    db.add(user)
    await db.flush()
    # Seed the chat with a greeting so the assistant's first message is in history
    db.add(ChatMessage(user_id=user.id, role="assistant", content=WELCOME_MESSAGE.format(name=user.name)))
    await db.commit()

    return TokenResponse(access_token=create_access_token(user.id, user.phone))


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)):
    user = await db.scalar(select(User).where(User.phone == payload.phone))
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Phone number not registered")
    return TokenResponse(access_token=create_access_token(user.id, user.phone))
