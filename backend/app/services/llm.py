"""Model construction and structured telemetry for LLM invocations."""
import json
import logging
import time
import uuid
from dataclasses import dataclass
from functools import lru_cache

from langchain_openai import ChatOpenAI

from app.config import settings
from app.llm_versions import current_version

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LLMUsage:
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    estimated_cost_usd: float | None = None


@dataclass(frozen=True)
class LLMInvocation:
    response: object
    usage: LLMUsage

    def __getattr__(self, name: str):
        return getattr(self.response, name)

@lru_cache
def get_chat_model() -> ChatOpenAI:
    return ChatOpenAI(
        model=settings.openai_model,
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
        temperature=1,
    )


def invoke(model, messages):
    """Invoke a model and emit redacted operational metadata as one JSON log event."""
    version = current_version()
    request_id = str(uuid.uuid4())
    started = time.perf_counter()
    try:
        response = model.invoke(messages)
    except Exception as exc:
        logger.exception(json.dumps({
            "event": "llm_invocation",
            "request_id": request_id,
            "provider": version.provider,
            "model": version.model,
            "prompt_name": version.prompt_name,
            "prompt_version": version.prompt_version,
            "prompt_hash": version.prompt_hash,
            "latency_ms": round((time.perf_counter() - started) * 1000, 2),
            "success": False,
            "error_type": type(exc).__name__,
        }))
        raise

    usage = getattr(response, "response_metadata", {}).get("token_usage", {})
    input_tokens = usage.get("prompt_tokens")
    output_tokens = usage.get("completion_tokens")
    estimated_cost = None
    if isinstance(input_tokens, int) and isinstance(output_tokens, int):
        estimated_cost = round(
            (input_tokens / 1_000_000) * settings.llm_input_cost_per_million
            + (output_tokens / 1_000_000) * settings.llm_output_cost_per_million,
            8,
        )
    logger.info(json.dumps({
        "event": "llm_invocation",
        "request_id": request_id,
        "provider": version.provider,
        "model": version.model,
        "prompt_name": version.prompt_name,
        "prompt_version": version.prompt_version,
        "prompt_hash": version.prompt_hash,
        "latency_ms": round((time.perf_counter() - started) * 1000, 2),
        "success": True,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": usage.get("total_tokens"),
        "estimated_cost_usd": estimated_cost,
    }))
    return LLMInvocation(
        response=response,
        usage=LLMUsage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=usage.get("total_tokens"),
            estimated_cost_usd=estimated_cost,
        ),
    )
