"""Chat agent: a tool-calling loop that lets the LLM invoke backend functions
(update_profile, recommend_drink, order) instead of following a fixed script.

Business-rule safety (allergen exclusion, exact-name validation) is enforced in
the tool executors below, in code — never trusted to the model's own judgment.
"""
import json
from dataclasses import dataclass, field

from anyio import to_thread
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import MenuItem, Order, OrderItem, User, UserPreference
from app.llm_versions import SYSTEM_PROMPT_TEMPLATE
from app.services import llm, recommendation

MAX_TOOL_ITERATIONS = 4

TOOL_UPDATE_PROFILE = "update_profile"
TOOL_RECOMMEND_DRINK = "recommend_drink"
TOOL_ORDER = "order"

FALLBACK_ERROR_REPLY = "Sorry, I'm having trouble connecting right now — please try again shortly."
FALLBACK_LOOP_REPLY = "Sorry, I got a bit stuck there — could you rephrase what you'd like?"
FALLBACK_EMPTY_REPLY = "Could you tell me a bit more about what you're looking for?"

WELCOME_MESSAGE = (
    "Welcome, {name}! I'm your drink assistant \u2014 tell me what flavors, drink types, "
    "temperature and caffeine level you enjoy (and any allergies), or just ask me for a "
    "recommendation whenever you're ready."
)

_TEMPERATURE_VALUES = {"hot", "iced", "either"}
_CAFFEINE_VALUES = {"none", "low", "any"}
_LIST_FIELDS = ("tastes", "drink_types", "allergies", "dietary_restrictions")

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": TOOL_UPDATE_PROFILE,
            "description": (
                "Save a new or changed customer preference: taste, drink type, temperature, "
                "caffeine tolerance, allergy, or dietary restriction. Call this whenever the "
                "customer states such information, including the first time they mention it."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "tastes": {"type": "array", "items": {"type": "string"}},
                    "drink_types": {"type": "array", "items": {"type": "string"}},
                    "temperature": {"type": "string", "enum": sorted(_TEMPERATURE_VALUES)},
                    "caffeine": {"type": "string", "enum": sorted(_CAFFEINE_VALUES)},
                    "allergies": {"type": "array", "items": {"type": "string"}},
                    "dietary_restrictions": {"type": "array", "items": {"type": "string"}},
                },
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": TOOL_RECOMMEND_DRINK,
            "description": (
                "Fetch the shop's current menu, already filtered to drinks that are available "
                "and free of the customer's declared allergens. Call this before recommending "
                "any specific drink \u2014 never invent a drink name, price, or ingredient."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "What the customer is looking for (taste, mood, occasion, etc.)",
                    },
                },
                "required": ["query"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": TOOL_ORDER,
            "description": (
                "Create a pending order preview for one or more drinks. Never claim the order "
                "is placed: the customer must explicitly confirm it in the chat UI first."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "items": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string", "description": "Exact menu item name"},
                                "quantity": {"type": "integer", "minimum": 1},
                            },
                            "required": ["name", "quantity"],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": ["items"],
                "additionalProperties": False,
            },
        },
    },
]

@dataclass
class AgentResult:
    reply: str
    recommendations: list[dict] = field(default_factory=list)
    pending_order: dict | None = None
    model_name: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    estimated_cost_usd: float | None = None


def _build_messages(user: User, prefs: UserPreference, history: list[tuple[str, str]], message: str) -> list:
    system = SystemMessage(
        content=SYSTEM_PROMPT_TEMPLATE.format(
            name=user.name, profile_json=json.dumps(recommendation.profile_dict(prefs))
        )
    )
    messages: list = [system]
    for role, content in history:
        messages.append(HumanMessage(content=content) if role == "user" else AIMessage(content=content))
    messages.append(HumanMessage(content=message))
    return messages


def _exec_update_profile(prefs: UserPreference, args: dict) -> dict:
    applied = {}
    for field_name in _LIST_FIELDS:
        value = args.get(field_name)
        if isinstance(value, list) and all(isinstance(v, str) for v in value):
            cleaned = [v.strip().lower() for v in value if v.strip()]
            setattr(prefs, field_name, cleaned)
            applied[field_name] = cleaned
    temperature = args.get("temperature")
    if temperature in _TEMPERATURE_VALUES:
        prefs.temperature = temperature
        applied["temperature"] = temperature
    caffeine = args.get("caffeine")
    if caffeine in _CAFFEINE_VALUES:
        prefs.caffeine = caffeine
        applied["caffeine"] = caffeine
    return {"updated": applied}


async def _exec_recommend_drink(db: AsyncSession, prefs: UserPreference) -> tuple[dict, list[dict]]:
    items = list(await db.scalars(select(MenuItem)))
    candidates = recommendation.filter_candidates(items, prefs.allergies or [])
    if not candidates:
        return (
            {"candidates": [], "note": "No drinks on the current menu are safe for this customer's allergies."},
            [],
        )
    tool_result = {
        "candidates": [
            {
                "name": c.name,
                "description": c.description,
                "ingredients": c.ingredients or [],
                "price": float(c.price),
                "category": c.category,
            }
            for c in candidates
        ]
    }
    recommendations = recommendation.fallback_recommend(candidates, prefs, limit=3)
    return tool_result, recommendations


async def _exec_order(db: AsyncSession, user: User, prefs: UserPreference, args: dict) -> tuple[dict, dict | None]:
    requested = args.get("items")
    if not isinstance(requested, list) or not requested:
        return {"success": False, "message": "No items specified."}, None

    items = list(await db.scalars(select(MenuItem).where(MenuItem.available.is_(True))))
    by_name = {item.name.lower(): item for item in items}
    allergies = prefs.allergies or []

    accepted: list[tuple[MenuItem, int]] = []
    rejected: list[dict] = []
    for entry in requested:
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("name", "")).strip()
        quantity = entry.get("quantity")
        if not isinstance(quantity, int) or quantity < 1:
            rejected.append({"name": name, "reason": "invalid quantity"})
            continue
        item = by_name.get(name.lower())
        if item is None:
            rejected.append({"name": name, "reason": "not found on the available menu"})
            continue
        if recommendation.contains_allergen(item.ingredients or [], allergies):
            rejected.append({"name": item.name, "reason": "contains a declared allergen"})
            continue
        accepted.append((item, quantity))

    if not accepted:
        return {"success": False, "rejected": rejected, "message": "No valid items could be ordered."}, None

    total_price = sum(float(item.price) * qty for item, qty in accepted)
    order = Order(user_id=user.id, status="pending", total_price=total_price)
    db.add(order)
    await db.flush()
    for item, qty in accepted:
        db.add(OrderItem(order_id=order.id, menu_item_id=item.id, quantity=qty, unit_price=item.price))
    await db.flush()

    order_dict = {
        "id": order.id,
        "status": order.status,
        "total_price": float(order.total_price),
        "items": [{"name": item.name, "quantity": qty, "unit_price": float(item.price)} for item, qty in accepted],
    }
    tool_result = {"success": True, "pending_order": order_dict, "rejected": rejected}
    return tool_result, order_dict


async def _dispatch(db: AsyncSession, user: User, prefs: UserPreference, call: dict) -> tuple[dict, list[dict] | dict | None]:
    name = call.get("name")
    args = call.get("args") or {}
    if name == TOOL_UPDATE_PROFILE:
        return _exec_update_profile(prefs, args), None
    if name == TOOL_RECOMMEND_DRINK:
        result, recommendations = await _exec_recommend_drink(db, prefs)
        return result, recommendations
    if name == TOOL_ORDER:
        result, order = await _exec_order(db, user, prefs, args)
        return result, order
    return {"error": f"unknown tool '{name}'"}, None


async def run_chat_turn(
    db: AsyncSession,
    user: User,
    prefs: UserPreference,
    history: list[tuple[str, str]],
    message: str,
) -> AgentResult:
    """Run one turn of the tool-calling agent loop and return the final reply plus any
    structured recommendations/pending order produced along the way."""
    model = llm.get_chat_model().bind_tools(TOOL_SCHEMAS)
    messages = _build_messages(user, prefs, history, message)
    recommendations: list[dict] = []
    pending_order: dict | None = None
    usage = llm.LLMUsage()

    def result_with_usage(reply: str) -> AgentResult:
        return AgentResult(
            reply,
            recommendations,
            pending_order,
            settings.openai_model if any(value is not None for value in (
                usage.input_tokens,
                usage.output_tokens,
                usage.total_tokens,
                usage.estimated_cost_usd,
            )) else None,
            usage.input_tokens,
            usage.output_tokens,
            usage.total_tokens,
            usage.estimated_cost_usd,
        )

    def add_usage(current: int | float | None, added: int | float | None):
        if current is None:
            return added
        if added is None:
            return current
        return current + added

    for _ in range(MAX_TOOL_ITERATIONS):
        try:
            invocation = await to_thread.run_sync(llm.invoke, model, messages)
        except Exception as exc:
            print("Error invoking model:", exc)
            return result_with_usage(FALLBACK_ERROR_REPLY)

        ai_msg = invocation.response
        usage = llm.LLMUsage(
            input_tokens=add_usage(usage.input_tokens, invocation.usage.input_tokens),
            output_tokens=add_usage(usage.output_tokens, invocation.usage.output_tokens),
            total_tokens=add_usage(usage.total_tokens, invocation.usage.total_tokens),
            estimated_cost_usd=add_usage(usage.estimated_cost_usd, invocation.usage.estimated_cost_usd),
        )

        messages.append(ai_msg)
        tool_calls = getattr(ai_msg, "tool_calls", None) or []
        if not tool_calls:
            reply = ai_msg.content if isinstance(ai_msg.content, str) else str(ai_msg.content)
            return result_with_usage(reply or FALLBACK_EMPTY_REPLY)

        for call in tool_calls:
            result, extra = await _dispatch(db, user, prefs, call)
            if call.get("name") == TOOL_RECOMMEND_DRINK and isinstance(extra, list):
                recommendations = extra
            elif call.get("name") == TOOL_ORDER and extra is not None:
                pending_order = extra
            messages.append(ToolMessage(content=json.dumps(result, default=str), tool_call_id=call.get("id")))

    return result_with_usage(FALLBACK_LOOP_REPLY)
