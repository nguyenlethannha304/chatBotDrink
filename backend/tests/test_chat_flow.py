from tests.conftest import ai_text, ai_tool_call, auth_headers, register_user, stub_agent_model


async def test_registration_seeds_welcome_message(client):
    token = await register_user(client)
    resp = await client.get("/api/chat/history", headers=auth_headers(token))
    history = resp.json()
    assert len(history) == 1
    assert history[0]["role"] == "assistant"
    assert "Alice" in history[0]["content"]


async def test_chat_reply_with_no_tool_calls(client, monkeypatch):
    token = await register_user(client)
    stub_agent_model(monkeypatch, [ai_text("Hi there! What flavors do you enjoy?")])

    resp = await client.post("/api/chat", json={"message": "hello"}, headers=auth_headers(token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["reply"] == "Hi there! What flavors do you enjoy?"
    assert body["recommendations"] == []
    assert body["order"] is None


async def test_update_profile_via_chat(client, monkeypatch):
    token = await register_user(client)
    stub_agent_model(monkeypatch, [
        ai_tool_call("update_profile", {"allergies": ["dairy", "nuts"], "temperature": "iced"}),
        ai_text("Got it, I've saved your preferences!"),
    ])

    resp = await client.post("/api/chat", json={"message": "I'm allergic to dairy and nuts, and I like iced drinks"},
                             headers=auth_headers(token))
    assert resp.status_code == 200
    assert resp.json()["reply"] == "Got it, I've saved your preferences!"

    prefs = (await client.get("/api/users/me/preferences", headers=auth_headers(token))).json()
    assert prefs["allergies"] == ["dairy", "nuts"]
    assert prefs["temperature"] == "iced"


async def test_recommend_drink_excludes_allergens(client, seeded_menu, monkeypatch):
    token = await register_user(client)
    await client.put("/api/users/me/preferences", json={"allergies": ["dairy"]}, headers=auth_headers(token))

    stub_agent_model(monkeypatch, [
        ai_tool_call("recommend_drink", {"query": "something refreshing"}),
        ai_text("How about an Iced Americano?"),
    ])

    resp = await client.post("/api/chat", json={"message": "something refreshing please"},
                             headers=auth_headers(token))
    assert resp.status_code == 200
    recs = resp.json()["recommendations"]
    assert recs, "expected fallback-ranked recommendations"
    names = {r["name"] for r in recs}
    assert "Caramel Latte" not in names
    assert "Mango Smoothie" not in names
    assert "Sold Out Soda" not in names
    assert recs[0]["price"] > 0
    assert recs[0]["reason"]


async def test_order_creates_order_and_confirms(client, seeded_menu, monkeypatch):
    token = await register_user(client)
    stub_agent_model(monkeypatch, [
        ai_tool_call("order", {"items": [{"name": "Iced Americano", "quantity": 2}]}),
        ai_text("Your order is placed!"),
    ])

    resp = await client.post("/api/chat", json={"message": "order me 2 iced americanos"},
                             headers=auth_headers(token))
    assert resp.status_code == 200
    order = resp.json()["order"]
    assert order is not None
    assert order["status"] == "placed"
    assert order["total_price"] == 6.0
    assert order["items"] == [{"name": "Iced Americano", "quantity": 2, "unit_price": 3.0}]


async def test_order_rejects_allergen_item(client, seeded_menu, monkeypatch):
    token = await register_user(client)
    await client.put("/api/users/me/preferences", json={"allergies": ["dairy"]}, headers=auth_headers(token))

    stub_agent_model(monkeypatch, [
        ai_tool_call("order", {"items": [{"name": "Caramel Latte", "quantity": 1}]}),
        ai_text("Sorry, that contains dairy which you're allergic to."),
    ])

    resp = await client.post("/api/chat", json={"message": "order me a caramel latte"},
                             headers=auth_headers(token))
    assert resp.status_code == 200
    assert resp.json()["order"] is None


async def test_chat_history_persists_only_user_and_assistant_messages(client, monkeypatch):
    token = await register_user(client)
    stub_agent_model(monkeypatch, [
        ai_tool_call("update_profile", {"tastes": ["sweet"]}),
        ai_text("Sweet, noted!"),
    ])

    await client.post("/api/chat", json={"message": "I like sweet drinks"}, headers=auth_headers(token))
    history = (await client.get("/api/chat/history", headers=auth_headers(token))).json()

    # welcome + 1 user message + 1 assistant reply (no intermediate tool-call chatter)
    assert len(history) == 3
    assert [m["role"] for m in history] == ["assistant", "user", "assistant"]
    assert history[1]["content"] == "I like sweet drinks"
    assert history[2]["content"] == "Sweet, noted!"


async def test_favorites_flow(client, seeded_menu):
    token = await register_user(client)
    item_id = seeded_menu[0].id
    resp = await client.post(f"/api/users/me/favorites/{item_id}", headers=auth_headers(token))
    assert resp.status_code == 201
    favs = (await client.get("/api/users/me/favorites", headers=auth_headers(token))).json()
    assert favs[0]["menu_item"]["name"] == "Caramel Latte"
    resp = await client.delete(f"/api/users/me/favorites/{item_id}", headers=auth_headers(token))
    assert resp.status_code == 204

