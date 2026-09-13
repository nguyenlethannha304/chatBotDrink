"""Thin wrapper around Langchain chat models with safe JSON parsing helpers.

Provider is selected via LLM_PROVIDER: ollama (local dev), openai, or gemini.
"""
import json
import re
from functools import lru_cache

from app.config import settings


@lru_cache
def get_chat_model():
    # Provider imports are lazy so only the configured SDK needs to be installed
    if settings.llm_provider == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=settings.openai_model,
            api_key=settings.openai_api_key,
            temperature=0.3,
        )
    if settings.llm_provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(
            model=settings.gemini_model,
            google_api_key=settings.gemini_api_key,
            temperature=0.3,
        )
    from langchain_ollama import ChatOllama

    return ChatOllama(
        model=settings.ollama_model,
        base_url=settings.ollama_base_url,
        temperature=0.3,
    )


def invoke_llm(prompt: str) -> str:
    """Send a single prompt to the LLM and return the raw text response."""
    response = get_chat_model().invoke(prompt)
    return response.content if isinstance(response.content, str) else str(response.content)


def parse_json_block(text: str):
    """Extract the first JSON object or array from LLM output; None on failure."""
    match = re.search(r"\{.*\}|\[.*\]", text, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


EXTRACT_LIST_PROMPT = """You extract structured data from a customer's answer.
Question asked: "{question}"
Customer answer: "{answer}"

Return ONLY a JSON array of short lowercase keywords extracted from the answer
(e.g. ["sweet", "creamy"]). If the customer indicates none/nothing, return [].
"""


def extract_list(question: str, answer: str) -> list[str] | None:
    """LLM-based keyword extraction. Returns None if the LLM is unreachable or output is invalid."""
    try:
        raw = invoke_llm(EXTRACT_LIST_PROMPT.format(question=question, answer=answer))
    except Exception:
        return None
    parsed = parse_json_block(raw)
    if isinstance(parsed, list) and all(isinstance(x, str) for x in parsed):
        return [x.strip().lower() for x in parsed if x.strip()]
    return None


PROFILE_UPDATE_PROMPT = """A customer of a drink shop sent this chat message:
"{message}"

Their current profile: {profile}

If the message declares a CHANGE to their profile (new allergy, removed allergy,
new taste/drink preference), return ONLY a JSON object with the changed fields, e.g.:
{{"allergies": ["dairy", "peanut"]}} or {{"tastes": ["sweet"]}}
Allowed keys: tastes, drink_types, temperature, caffeine, allergies, dietary_restrictions.
For list fields return the FULL updated list. If nothing changed, return {{}}.
"""


def extract_profile_updates(message: str, profile: dict) -> dict:
    """Detect preference/allergy changes in a chat message. Empty dict when none or on failure."""
    try:
        raw = invoke_llm(PROFILE_UPDATE_PROMPT.format(message=message, profile=json.dumps(profile)))
    except Exception:
        return {}
    parsed = parse_json_block(raw)
    if not isinstance(parsed, dict):
        return {}
    allowed = {"tastes", "drink_types", "temperature", "caffeine", "allergies", "dietary_restrictions"}
    return {k: v for k, v in parsed.items() if k in allowed}
