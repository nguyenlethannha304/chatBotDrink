from tests.conftest import auth_headers, complete_onboarding, register_user


async def test_registration_seeds_first_onboarding_question(client):
    token = await register_user(client)
    resp = await client.get("/api/chat/history", headers=auth_headers(token))
    history = resp.json()
    assert len(history) == 1
    assert history[0]["role"] == "assistant"
    assert "flavors" in history[0]["content"]


async def test_onboarding_flow_saves_preferences(client, seeded_menu):
    token = await register_user(client)
    resp = await complete_onboarding(client, token, allergies="dairy and nuts")
    assert resp.json()["onboarding"] is False  # completed on the last answer

    prefs = (await client.get("/api/users/me/preferences", headers=auth_headers(token))).json()
    assert prefs["tastes"] == ["sweet", "creamy"]
    assert prefs["drink_types"] == ["coffee", "juice"]
    assert prefs["temperature"] == "iced"
    assert prefs["caffeine"] == "any"
    assert prefs["allergies"] == ["dairy", "nuts"]

    me = (await client.get("/api/users/me", headers=auth_headers(token))).json()
    assert me["onboarding_completed"] is True


async def test_onboarding_intermediate_replies_are_questions(client):
    token = await register_user(client)
    resp = await client.post("/api/chat", json={"message": "sweet"}, headers=auth_headers(token))
    body = resp.json()
    assert body["onboarding"] is True
    assert "kinds of drinks" in body["reply"]


async def test_recommendations_exclude_allergens(client, seeded_menu):
    token = await register_user(client)
    await complete_onboarding(client, token, allergies="dairy")

    resp = await client.post("/api/chat", json={"message": "something refreshing please"},
                             headers=auth_headers(token))
    assert resp.status_code == 200
    recs = resp.json()["recommendations"]
    assert recs, "expected fallback recommendations"
    names = {r["name"] for r in recs}
    # Caramel Latte (milk) and Mango Smoothie (yogurt) must never appear
    assert "Caramel Latte" not in names
    assert "Mango Smoothie" not in names
    assert "Sold Out Soda" not in names


async def test_recommendation_includes_price_and_reason(client, seeded_menu):
    token = await register_user(client)
    await complete_onboarding(client, token, allergies="none")
    resp = await client.post("/api/chat", json={"message": "recommend me a drink"},
                             headers=auth_headers(token))
    rec = resp.json()["recommendations"][0]
    assert rec["price"] > 0
    assert rec["reason"]
    assert rec["description"]


async def test_chat_history_persisted(client, seeded_menu):
    token = await register_user(client)
    await complete_onboarding(client, token)
    await client.post("/api/chat", json={"message": "hello"}, headers=auth_headers(token))
    history = (await client.get("/api/chat/history", headers=auth_headers(token))).json()
    # greeting + 5 answers + 5 replies + 1 message + 1 reply = 13
    assert len(history) == 13
    assert history[-2]["role"] == "user"
    assert history[-2]["content"] == "hello"


async def test_profile_update_via_chat(client, seeded_menu, monkeypatch):
    from app.services import llm as llm_module

    token = await register_user(client)
    await complete_onboarding(client, token, allergies="none")

    # simulate the LLM detecting a new allergy from the message
    monkeypatch.setattr(llm_module, "extract_profile_updates",
                        lambda message, profile: {"allergies": ["dairy"]})
    resp = await client.post("/api/chat", json={"message": "I'm allergic to dairy now"},
                             headers=auth_headers(token))
    assert resp.status_code == 200
    names = {r["name"] for r in resp.json()["recommendations"]}
    assert "Caramel Latte" not in names and "Mango Smoothie" not in names

    prefs = (await client.get("/api/users/me/preferences", headers=auth_headers(token))).json()
    assert prefs["allergies"] == ["dairy"]


async def test_favorites_flow(client, seeded_menu):
    token = await register_user(client)
    item_id = seeded_menu[0].id
    resp = await client.post(f"/api/users/me/favorites/{item_id}", headers=auth_headers(token))
    assert resp.status_code == 201
    favs = (await client.get("/api/users/me/favorites", headers=auth_headers(token))).json()
    assert favs[0]["menu_item"]["name"] == "Caramel Latte"
    resp = await client.delete(f"/api/users/me/favorites/{item_id}", headers=auth_headers(token))
    assert resp.status_code == 204
