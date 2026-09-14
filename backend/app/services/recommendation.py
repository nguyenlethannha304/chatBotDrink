"""Drink recommendation logic.

Allergen safety is enforced HERE, in code: drinks containing a user's allergens
are removed from the candidate list before the chat agent ever sees the menu, so
the model cannot recommend or order them.
"""
from app.models import MenuItem, UserPreference

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
    """Deterministic recommendation ranking used to populate structured recommendation cards."""
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


def profile_dict(prefs: UserPreference | None) -> dict:
    """Serialize a user's preferences for use in LLM prompts."""
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
