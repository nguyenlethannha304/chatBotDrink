from app.models import MenuItem
from app.services.recommendation import (
    contains_allergen,
    expand_allergens,
    fallback_recommend,
    filter_candidates,
)


def item(name, ingredients, available=True, category="cafe", price=4.0):
    return MenuItem(name=name, description=name, ingredients=ingredients,
                    price=price, category=category, available=available)


def test_expand_allergens_includes_synonyms():
    keywords = expand_allergens(["dairy"])
    assert "milk" in keywords and "cream" in keywords and "yogurt" in keywords


def test_contains_allergen_direct_match():
    assert contains_allergen(["espresso", "milk"], ["milk"])


def test_contains_allergen_via_synonym():
    assert contains_allergen(["mango", "yogurt"], ["dairy"])
    assert contains_allergen(["almond milk"], ["nuts"])
    assert contains_allergen(["wheat", "water"], ["gluten"])


def test_contains_allergen_case_insensitive():
    assert contains_allergen(["Whole MILK"], ["Dairy"])


def test_non_dairy_milk_not_flagged_as_dairy():
    assert not contains_allergen(["oat milk", "espresso"], ["dairy"])
    assert not contains_allergen(["soy milk"], ["dairy"])


def test_no_allergen_no_match():
    assert not contains_allergen(["orange", "ice"], ["dairy", "nuts"])
    assert not contains_allergen(["milk"], [])


def test_filter_candidates_removes_allergens_and_unavailable():
    items = [
        item("Latte", ["espresso", "milk"]),
        item("Americano", ["espresso", "water"]),
        item("Gone", ["water"], available=False),
    ]
    names = [i.name for i in filter_candidates(items, ["dairy"])]
    assert names == ["Americano"]


def test_fallback_recommend_never_includes_allergen_items():
    items = [
        item("Latte", ["espresso", "milk"]),
        item("Americano", ["espresso", "water"]),
        item("Smoothie", ["mango", "yogurt"], category="fruit juice"),
    ]
    safe = filter_candidates(items, ["dairy"])
    recs = fallback_recommend(safe, prefs=None)
    assert [r["name"] for r in recs] == ["Americano"]
    assert all("milk" not in r["name"].lower() for r in recs)
