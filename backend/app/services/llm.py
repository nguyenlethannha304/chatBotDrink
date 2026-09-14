"""Thin wrapper providing the OpenAI chat model used for tool-calling (function-calling) chat."""
from functools import lru_cache

from langchain_openai import ChatOpenAI

from app.config import settings

@lru_cache
def get_chat_model() -> ChatOpenAI:
    return ChatOpenAI(
        model=settings.openai_model,
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
        temperature=1,
    )
