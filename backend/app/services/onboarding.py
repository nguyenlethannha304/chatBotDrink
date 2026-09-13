"""Conversational onboarding questionnaire.

Each question maps to a preference field. Answers are extracted with the LLM
when available, with deterministic keyword parsers as fallback, so onboarding
works even if Ollama is down.
"""
import re

from app.models import User, UserPreference
from app.services import llm

WELCOME = (
    "Welcome, {name}! Before I can recommend drinks, I'd like to know your taste. "
)

# (field, question) — asked in order; step index is stored on the user.
QUESTIONS: list[tuple[str, str]] = [
    ("tastes", "What flavors do you enjoy? (e.g., sweet, bitter, sour, creamy)"),
    ("drink_types", "What kinds of drinks do you like? (e.g., coffee, tea, smoothies, juice)"),
    ("temperature", "Do you prefer your drinks hot, iced, or either?"),
    ("caffeine", "How do you feel about caffeine? (none, low, or any amount is fine)"),
    ("allergies", "Do you have any allergies or dietary restrictions? (e.g., dairy, nuts, gluten — or none)"),
]

COMPLETION_MESSAGE = (
    "You're all set! Your preferences are saved. "
    "Ask me anything, like \"I want something refreshing and not too sweet\" \u2014 "
    "I'll find the perfect drink for you."
)

_NONE_RE = re.compile(r"^\s*(no|none|nope|nothing|n/?a|no thanks?)\b", re.IGNORECASE)


def parse_list(answer: str) -> list[str]:
    """Fallback parser: split a free-text answer into lowercase keywords."""
    if _NONE_RE.match(answer):
        return []
    parts = re.split(r"[,;/]|\band\b|\bor\b", answer, flags=re.IGNORECASE)
    cleaned = []
    for part in parts:
        word = re.sub(r"[^a-zA-Z\s-]", "", part).strip().lower()
        # drop filler like "i like", "maybe some"
        word = re.sub(r"^(i (really )?(like|love|prefer|enjoy|want)|maybe|some|mostly)\s+", "", word).strip()
        if word and len(word) <= 30:
            cleaned.append(word)
    return cleaned


def parse_temperature(answer: str) -> str:
    text = answer.lower()
    hot = "hot" in text or "warm" in text
    iced = any(w in text for w in ("iced", "ice", "cold", "chilled"))
    if "either" in text or "both" in text or (hot and iced):
        return "either"
    if hot:
        return "hot"
    if iced:
        return "iced"
    return "either"


def parse_caffeine(answer: str) -> str:
    text = answer.lower()
    if any(w in text for w in ("no caffeine", "none", "decaf", "caffeine-free", "avoid", "can't have", "cannot")):
        return "none"
    if any(w in text for w in ("low", "little", "small", "not much", "light")):
        return "low"
    return "any"


def extract_answer(field: str, question: str, answer: str) -> object:
    """Extract a structured value for the given onboarding field."""
    if field == "temperature":
        return parse_temperature(answer)
    if field == "caffeine":
        return parse_caffeine(answer)
    # list fields: try LLM first, fall back to keyword parsing
    extracted = llm.extract_list(question, answer)
    return extracted if extracted is not None else parse_list(answer)


def handle_turn(user: User, prefs: UserPreference, message: str) -> str:
    """Process one onboarding answer, mutate user/prefs in place, return the assistant reply."""
    step = user.onboarding_step
    if step >= len(QUESTIONS):  # defensive: shouldn't happen
        user.onboarding_completed = True
        return COMPLETION_MESSAGE

    field, question = QUESTIONS[step]
    value = extract_answer(field, question, message)
    setattr(prefs, field, value)

    user.onboarding_step = step + 1
    if user.onboarding_step >= len(QUESTIONS):
        user.onboarding_completed = True
        return COMPLETION_MESSAGE
    return QUESTIONS[user.onboarding_step][1]


def first_message(name: str) -> str:
    """Greeting + first question, stored as the assistant's opening chat message."""
    return WELCOME.format(name=name) + QUESTIONS[0][1]
