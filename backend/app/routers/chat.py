import re

from anyio import to_thread
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import ChatMessage, MenuItem, User, UserPreference
from app.schemas import ChatMessageOut, ChatRequest, ChatResponse, Recommendation
from app.services import llm, onboarding, recommendation
from app.services.auth import get_current_user

router = APIRouter(prefix="/chat", tags=["chat"])

# Cheap keyword gate so the profile-update LLM call only runs when likely relevant
PROFILE_HINT_RE = re.compile(
    r"allerg|intoleran|can't (drink|have)|cannot (drink|have)|no longer|"
    r"i('m| am) (now )?(vegan|vegetarian)|i (now )?(prefer|like|hate|dislike)",
    re.IGNORECASE,
)


async def _get_prefs(db: AsyncSession, user: User) -> UserPreference:
    prefs = await db.scalar(select(UserPreference).where(UserPreference.user_id == user.id))
    if prefs is None:
        prefs = UserPreference(user_id=user.id, tastes=[], drink_types=[],
                               allergies=[], dietary_restrictions=[])
        db.add(prefs)
        await db.flush()
    return prefs


async def _recent_history(db: AsyncSession, user_id: int, limit: int = 10) -> list[tuple[str, str]]:
    messages = await db.scalars(
        select(ChatMessage)
        .where(ChatMessage.user_id == user_id)
        .order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc())
        .limit(limit)
    )
    return [(m.role, m.content) for m in reversed(list(messages))]


@router.post("", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    prefs = await _get_prefs(db, user)
    db.add(ChatMessage(user_id=user.id, role="user", content=payload.message))

    # --- Onboarding flow ---
    if not user.onboarding_completed:
        reply = await to_thread.run_sync(onboarding.handle_turn, user, prefs, payload.message)
        db.add(ChatMessage(user_id=user.id, role="assistant", content=reply))
        await db.commit()
        return ChatResponse(reply=reply, onboarding=not user.onboarding_completed)

    # --- Profile update detection (e.g., "I'm allergic to peanuts now") ---
    if PROFILE_HINT_RE.search(payload.message):
        profile = {
            "tastes": prefs.tastes or [],
            "drink_types": prefs.drink_types or [],
            "temperature": prefs.temperature,
            "caffeine": prefs.caffeine,
            "allergies": prefs.allergies or [],
            "dietary_restrictions": prefs.dietary_restrictions or [],
        }
        updates = await to_thread.run_sync(llm.extract_profile_updates, payload.message, profile)
        for field, value in updates.items():
            setattr(prefs, field, value)

    # --- Recommendation flow: hard allergen filter happens before the LLM ---
    history = await _recent_history(db, user.id)
    items = list(await db.scalars(select(MenuItem)))
    candidates = recommendation.filter_candidates(items, prefs.allergies or [])
    reply, recs = await to_thread.run_sync(
        recommendation.recommend, payload.message, candidates, prefs, history
    )

    db.add(ChatMessage(user_id=user.id, role="assistant", content=reply))
    await db.commit()
    return ChatResponse(reply=reply, recommendations=[Recommendation(**r) for r in recs])


@router.get("/history", response_model=list[ChatMessageOut])
async def history(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    messages = await db.scalars(
        select(ChatMessage)
        .where(ChatMessage.user_id == user.id)
        .order_by(ChatMessage.created_at, ChatMessage.id)
    )
    return list(messages)
