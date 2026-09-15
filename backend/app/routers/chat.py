from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import ChatMessage, User, UserPreference
from app.schemas import ChatMessageOut, ChatRequest, ChatResponse, OrderOut, Recommendation
from app.services import agent
from app.services.auth import get_current_user

router = APIRouter(prefix="/chat", tags=["chat"])


async def _get_prefs(db: AsyncSession, user: User) -> UserPreference:
    prefs = await db.scalar(select(UserPreference).where(UserPreference.user_id == user.id))
    if prefs is None:
        prefs = UserPreference(user_id=user.id, tastes=[], drink_types=[],
                               allergies=[], dietary_restrictions=[])
        db.add(prefs)
        await db.flush()
    return prefs


async def _recent_history(db: AsyncSession, user_id: int, limit: int = 20) -> list[tuple[str, str]]:
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
    history = await _recent_history(db, user.id)
    db.add(ChatMessage(user_id=user.id, role="user", content=payload.message))

    result = await agent.run_chat_turn(db, user, prefs, history, payload.message)

    db.add(ChatMessage(
        user_id=user.id,
        role="assistant",
        content=result.reply,
        model_name=result.model_name,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        total_tokens=result.total_tokens,
        estimated_cost_usd=result.estimated_cost_usd,
    ))
    await db.commit()
    return ChatResponse(
        reply=result.reply,
        recommendations=[Recommendation(**r) for r in result.recommendations],
        order=OrderOut(**result.order) if result.order else None,
    )


@router.get("/history", response_model=list[ChatMessageOut])
async def history(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    messages = await db.scalars(
        select(ChatMessage)
        .where(ChatMessage.user_id == user.id)
        .order_by(ChatMessage.created_at, ChatMessage.id)
    )
    return list(messages)

