from tests.conftest import auth_headers, register_user


async def test_register_returns_token(client):
    token = await register_user(client)
    resp = await client.get("/api/users/me", headers=auth_headers(token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["phone"] == "+14155550100"
    assert body["onboarding_completed"] is False


async def test_register_duplicate_phone_rejected(client):
    await register_user(client)
    resp = await client.post("/api/auth/register",
                             json={"phone": "+14155550100", "name": "Bob", "address": "2 Oak St"})
    assert resp.status_code == 409


async def test_register_invalid_phone_rejected(client):
    resp = await client.post("/api/auth/register",
                             json={"phone": "abc123", "name": "Bob", "address": "2 Oak St"})
    assert resp.status_code == 422


async def test_login_existing_user(client):
    await register_user(client)
    resp = await client.post("/api/auth/login", json={"phone": "+14155550100"})
    assert resp.status_code == 200
    assert resp.json()["access_token"]


async def test_login_normalizes_phone_format(client):
    await register_user(client, phone="+14155550100")
    resp = await client.post("/api/auth/login", json={"phone": "+1 (415) 555-0100"})
    assert resp.status_code == 200


async def test_login_unknown_phone(client):
    resp = await client.post("/api/auth/login", json={"phone": "+19998887766"})
    assert resp.status_code == 404


async def test_protected_route_requires_token(client):
    resp = await client.get("/api/users/me")
    assert resp.status_code == 401


async def test_invalid_token_rejected(client):
    resp = await client.get("/api/users/me", headers=auth_headers("not-a-jwt"))
    assert resp.status_code == 401
