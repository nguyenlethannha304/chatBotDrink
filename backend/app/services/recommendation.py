"""Drink recommendation logic.

Allergen safety is enforced HERE, in code: drinks containing a user's allergens
are removed from the candidate list before the LLM ever sees the menu, so the
model cannot recommend them. LLM output is additionally validated against the
candidate list to reject hallucinated drinks.
"""
import json

from app.models import MenuItem, UserPreference
from app.services import llm

# Maps a declared allergy/restriction to ingredient keywords it covers.
ALLERGEN_SYNONYMS: dict[str, list[str]] = {
    "dairy": ["milk", "cream", "yogurt", "cheese", "butter", "whey"],
    "lactose": ["milk", "cream", "yogurt", "cheese", "butter", "whey"],
    "nuts": ["almond", "peanut", "cashew", "hazelnut", "walnut", "pistachio", "macadamia", "pecan"],
    "nut": ["almond", "peanut", "cashew", "hazelnut", "walnut", "pistachio", "macadamia", "pecan"],
    "peanut": ["peanut"],
    "gluten": ["wheat", "barley", "malt", "rye"],
    "soy": ["soy", "soya"],
    "egg": ["egg"],
    "caffeine": ["espresso", "coffee", "black tea", "green tea", "oolong", "matcha", "cola"],
}

# Note: "oat milk" / "almond milk" are dairy-free; exclude them from dairy keyword hits.
NON_DAIRY_MILKS = ["oat milk", "almond milk", "soy milk", "coconut milk", "rice milk"]


def expand_allergens(allergies: list[str]) -> set[str]:
    """Expand declared allergies into the full set of ingredient keywords to avoid."""
    keywords: set[str] = set()
    for allergy in allergies:
        key = allergy.strip().lower()
        if not key:
            continue
        keywords.add(key)
        keywords.update(ALLERGEN_SYNONYMS.get(key, []))
    return keywords


def _ingredient_matches(ingredient: str, keyword: str) -> bool:
    ing = ingredient.strip().lower()
    if keyword in ("milk", "cream") and any(alt in ing for alt in NON_DAIRY_MILKS):
        return False
    return keyword in ing


def contains_allergen(ingredients: list[str], allergies: list[str]) -> bool:
    """True if any ingredient matches any declared allergen (or its synonyms)."""
    keywords = expand_allergens(allergies)
    return any(
        _ingredient_matches(ingredient, keyword)
        for ingredient in ingredients
        for keyword in keywords
    )


def filter_candidates(items: list[MenuItem], allergies: list[str]) -> list[MenuItem]:
    """Keep only available drinks free of the user's allergens."""
    return [
        item
        for item in items
        if item.available and not contains_allergen(item.ingredients or [], allergies)
    ]


def _score(item: MenuItem, prefs: UserPreference | None) -> int:
    """Simple preference match score used by the non-LLM fallback."""
    if prefs is None:
        return 0
    score = 0
    text = f"{item.name} {item.description} {' '.join(item.ingredients or [])}".lower()
    if item.category.lower() in [t.lower() for t in (prefs.drink_types or [])]:
        score += 3
    for taste in prefs.tastes or []:
        if taste.lower() in text:
            score += 2
    if prefs.temperature in ("hot", "iced") and prefs.temperature in text:
        score += 1
    if prefs.caffeine == "none" and not contains_allergen(item.ingredients or [], ["caffeine"]):
        score += 2
    return score


def fallback_recommend(candidates: list[MenuItem], prefs: UserPreference | None, limit: int = 3) -> list[dict]:
    """Deterministic recommendation used when the LLM is unavailable or returns garbage."""
    ranked = sorted(candidates, key=lambda i: _score(i, prefs), reverse=True)[:limit]
    return [
        {
            "name": item.name,
            "description": item.description,
            "price": float(item.price),
            "reason": "Matches your saved preferences and is free of your allergens.",
        }
        for item in ranked
    ]


RECOMMEND_PROMPT = """You are a friendly drink shop assistant. Recommend drinks ONLY from this menu
(it has already been filtered for the customer's allergies — every item below is safe):

{menu}

Customer profile: {profile}

Recent conversation:
{history}

Customer's latest message: "{message}"

Rules:
- Recommend 1-3 drinks, ONLY using exact "name" values from the menu above.
- Consider the customer's tastes, drink type, temperature and caffeine preferences,
  plus any mood/weather/occasion in the conversation.
- Reply in the same language the customer writes in.

Return ONLY a JSON object in this exact format:
{{"reply": "<short friendly reply text>", "recommendations": [{{"name": "<exact menu name>", "reason": "<why this fits>"}}]}}
"""


def _profile_dict(prefs: UserPreference | None) -> dict:
    if prefs is None:
        return {}
    return {
        "tastes": prefs.tastes or [],
        "drink_types": prefs.drink_types or [],
        "temperature": prefs.temperature,
        "caffeine": prefs.caffeine,
        "allergies": prefs.allergies or [],
        "dietary_restrictions": prefs.dietary_restrictions or [],
    }


def recommend(
    message: str,
    candidates: list[MenuItem],
    prefs: UserPreference | None,
    history: list[tuple[str, str]],
) -> tuple[str, list[dict]]:
    """Return (reply_text, recommendations). Falls back to deterministic ranking on LLM failure."""
    if not candidates:
        return (
            "I'm sorry — no drinks on our current menu are safe for your allergies. "
            "Please check back soon!",
            [],
        )

    menu_json = json.dumps(
        [
            {
                "name": c.name,
                "description": c.description,
                "ingredients": c.ingredients or [],
                "price": float(c.price),
                "category": c.category,
            }
            for c in candidates
        ]
    )
    history_text = "\n".join(f"{role}: {content}" for role, content in history[-10:]) or "(none)"

    try:
        raw = llm.invoke_llm(
            RECOMMEND_PROMPT.format(
                menu=menu_json,
                profile=json.dumps(_profile_dict(prefs)),
                history=history_text,
                message=message,
            )
        )
        parsed = llm.parse_json_block(raw)
    except Exception:
        parsed = None

    if not isinstance(parsed, dict) or "reply" not in parsed:
        recs = fallback_recommend(candidates, prefs)
        return ("Here are some drinks I think you'll enjoy:", recs)

    # Validate LLM picks against the safe candidate list; drop hallucinated names.
    by_name = {c.name.lower(): c for c in candidates}
    recs: list[dict] = []
    for pick in parsed.get("recommendations", []):
        if not isinstance(pick, dict):
            continue
        item = by_name.get(str(pick.get("name", "")).strip().lower())
        if item is None:
            continue
        recs.append(
            {
                "name": item.name,
                "description": item.description,
                "price": float(item.price),
                "reason": str(pick.get("reason", "A great match for you.")),
            }
        )

    if not recs:
        recs = fallback_recommend(candidates, prefs)
    return (str(parsed["reply"]), recs)
