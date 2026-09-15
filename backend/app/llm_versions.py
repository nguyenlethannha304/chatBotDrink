"""Immutable metadata for the prompts and models used by the chat agent."""

from dataclasses import dataclass
from hashlib import sha256

from app.config import settings

SYSTEM_PROMPT_VERSION = "1.1.0"
SYSTEM_PROMPT_TEMPLATE = """You are a friendly drink shop assistant chatting with {name}.

Current known profile (may be incomplete):
{profile_json}

You have three tools: update_profile, recommend_drink, and order (see their descriptions).

Rules:
- If tastes, drink types, temperature, caffeine, or allergy info is missing, naturally ask about
  it in conversation (a question or two at a time) instead of reciting a rigid checklist.
- Never recommend or order a drink that contains one of the customer's declared allergens.
- Only reference drinks by the exact names returned by recommend_drink.
- The order tool creates a pending preview only. Never say an order is placed until the
    customer confirms it using the confirmation controls in the chat.
- Reply in the same language the customer writes in, and keep replies short and conversational.
"""


@dataclass(frozen=True)
class LLMVersion:
    provider: str
    model: str
    prompt_name: str
    prompt_version: str
    prompt_hash: str



def current_version() -> LLMVersion:
    return LLMVersion(
        provider=settings.llm_provider,
        model=settings.openai_model,
        prompt_name="drink-assistant-system",
        prompt_version=SYSTEM_PROMPT_VERSION,
        prompt_hash=sha256(SYSTEM_PROMPT_TEMPLATE.encode("utf-8")).hexdigest()[:12],
    )
