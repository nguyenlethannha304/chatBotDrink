import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import MenuItem
from app.services import llm


@pytest.fixture(autouse=True)
def no_llm(monkeypatch):
    """Tests never hit Ollama: force deterministic fallback paths."""
    monkeypatch.setattr(llm, "invoke_llm", lambda prompt: (_ for _ in ()).throw(RuntimeError("no LLM in tests")))
    monkeypatch.setattr(llm, "extract_list", lambda question, answer: None)


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


@pytest_asyncio.fixture
async def client(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def seeded_menu(db_session):
    items = [
        MenuItem(name="Caramel Latte", description="Espresso with milk and caramel.",
                 ingredients=["espresso", "milk", "caramel syrup"], price=4.50, category="cafe"),
        MenuItem(name="Iced Americano", description="Espresso over ice.",
                 ingredients=["espresso", "water", "ice"], price=3.00, category="cafe"),
        MenuItem(name="Mango Smoothie", description="Mango blended with yogurt.",
                 ingredients=["mango", "yogurt", "honey", "ice"], price=5.50, category="fruit juice"),
        MenuItem(name="Berry Banana Blast", description="Berries and banana with almond milk.",
                 ingredients=["strawberry", "banana", "almond milk"], price=5.75, category="fruit juice"),
        MenuItem(name="Chamomile Honey Tea", description="Caffeine-free chamomile with honey.",
                 ingredients=["chamomile", "honey"], price=3.25, category="tea"),
        MenuItem(name="Sold Out Soda", description="Unavailable drink.",
                 ingredients=["soda water"], price=2.00, category="soda", available=False),
    ]
    db_session.add_all(items)
    await db_session.commit()
    return items


async def register_user(client, phone="+14155550100", name="Alice", address="1 Main St"):
    resp = await client.post("/api/auth/register",
                             json={"phone": phone, "name": name, "address": address})
    assert resp.status_code == 201, resp.text
    return resp.json()["access_token"]


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def complete_onboarding(client, token, allergies="dairy"):
    """Answer all 5 onboarding questions; returns the last response."""
    answers = ["sweet, creamy", "coffee and juice", "iced", "any is fine", allergies]
    resp = None
    for answer in answers:
        resp = await client.post("/api/chat", json={"message": answer}, headers=auth_headers(token))
        assert resp.status_code == 200, resp.text
    return resp
