from tests.conftest import register_user


async def test_list_menu(client, seeded_menu):
    resp = await client.get("/api/menu")
    assert resp.status_code == 200
    assert len(resp.json()) == 6


async def test_create_update_delete_item(client):
    resp = await client.post("/api/menu", json={
        "name": "Test Fizz", "description": "Bubbly.", "ingredients": ["soda water", "lime"],
        "price": 2.5, "category": "soda",
    })
    assert resp.status_code == 201
    item_id = resp.json()["id"]

    resp = await client.put(f"/api/menu/{item_id}", json={"price": 3.0, "available": False})
    assert resp.status_code == 200
    assert resp.json()["price"] == 3.0
    assert resp.json()["available"] is False

    resp = await client.delete(f"/api/menu/{item_id}")
    assert resp.status_code == 204


async def test_create_duplicate_name_rejected(client, seeded_menu):
    resp = await client.post("/api/menu", json={
        "name": "Caramel Latte", "description": "dup", "ingredients": [],
        "price": 1.0, "category": "cafe",
    })
    assert resp.status_code == 409


async def test_invalid_price_rejected(client):
    resp = await client.post("/api/menu", json={
        "name": "Free Drink", "description": "x", "ingredients": [],
        "price": 0, "category": "cafe",
    })
    assert resp.status_code == 422


async def test_admin_key_enforced_when_configured(client, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "admin_api_key", "secret-key")

    body = {"name": "Locked", "description": "x", "ingredients": [], "price": 1.0, "category": "cafe"}
    resp = await client.post("/api/menu", json=body)
    assert resp.status_code == 403
    resp = await client.post("/api/menu", json=body, headers={"X-Admin-Key": "secret-key"})
    assert resp.status_code == 201
