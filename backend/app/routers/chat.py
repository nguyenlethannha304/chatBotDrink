from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import ChatMessage, MenuItem, Order, OrderItem, User, UserPreference
from app.schemas import (
    ChatMessageOut,
    ChatRequest,
    ChatResponse,
    OrderConfirmationRequest,
    OrderOut,
    Recommendation,
)
from app.services import agent
from app.services import recommendation
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
        pending_order=OrderOut(**result.pending_order) if result.pending_order else None,
    )


def _order_out(order: Order) -> OrderOut:
    return OrderOut(
        id=order.id,
        status=order.status,
        total_price=float(order.total_price),
        items=[
            {
                "name": item.menu_item.name,
                "quantity": item.quantity,
                "unit_price": float(item.unit_price),
            }
            for item in order.items
        ],
    )


@router.get("/orders/pending", response_model=list[OrderOut])
async def pending_orders(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    orders = await db.scalars(
        select(Order)
        .where(Order.user_id == user.id, Order.status == "pending")
        .options(selectinload(Order.items).selectinload(OrderItem.menu_item))
        .order_by(Order.id)
    )
    return [_order_out(order) for order in orders]


@router.post("/orders/{order_id}/confirm", response_model=OrderOut)
async def confirm_order(
    order_id: int,
    payload: OrderConfirmationRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    order = await db.scalar(
        select(Order)
        .where(Order.id == order_id, Order.user_id == user.id)
        .options(selectinload(Order.items).selectinload(OrderItem.menu_item))
    )
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.status != "pending":
        raise HTTPException(status_code=409, detail=f"Order is already {order.status}")
    if not payload.confirmed:
        order.status = "cancelled"
        await db.commit()
        return _order_out(order)

    prefs = await _get_prefs(db, user)
    for item in order.items:
        current = await db.scalar(select(MenuItem).where(MenuItem.id == item.menu_item_id))
        if current is None or not current.available:
            raise HTTPException(status_code=409, detail=f"{item.menu_item.name} is no longer available")
        if recommendation.contains_allergen(current.ingredients or [], prefs.allergies or []):
            raise HTTPException(status_code=409, detail=f"{current.name} contains a declared allergen")
        if float(current.price) != float(item.unit_price):
            raise HTTPException(status_code=409, detail=f"The price of {current.name} has changed")

    order.status = "placed"
    await db.commit()
    return _order_out(order)


@router.get("/history", response_model=list[ChatMessageOut])
async def history(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    messages = await db.scalars(
        select(ChatMessage)
        .where(ChatMessage.user_id == user.id)
        .order_by(ChatMessage.created_at, ChatMessage.id)
    )
    return list(messages)

