# chatBotDrinkRecommendation

# chatBotDrinkRecommendation

A chatbot that gives personalized drink recommendations and takes orders from a shop's menu, powered by **FastAPI + Langchain + OpenAI** (tool-calling), with a **React + Tailwind** frontend and **PostgreSQL** storage.

## Features

- **Phone-number registration & login** (JWT session, no password for MVP)
- **AI chat agent** — a single tool-calling assistant with 3 functions: `update_profile`, `recommend_drink`, and `order`. It asks about tastes/allergies naturally, recommends drinks, and places orders — no rigid scripted flow
- **Chat-based recommendations** — only from the shop's menu, personalized to the user's profile and conversation context
- **Hard allergen safety** — drinks containing a user's allergens are filtered out *in code* before the AI ever sees the menu or places an order, so it can never recommend or order them
- **Profile management** — update preferences/allergies via chat ("I'm allergic to peanuts now") or the profile page; save favorite drinks
- **Ordering** — confirm a drink (or several) in chat and the assistant places the order
- **Menu admin API** — CRUD endpoints (optionally protected with `ADMIN_API_KEY`)
- **Seeded menu** — 15 sample drinks (5 cafe, 5 tea, 5 fruit juice)

## Quick start (Docker)

```bash
cp .env.example .env      # edit secrets, set OPENAI_API_KEY
docker-compose up --build
```

Recommendations fall back to deterministic preference ranking if the LLM is unreachable.

| Service    | URL                          |
|------------|------------------------------|
| Frontend   | http://localhost:3000        |
| API        | http://localhost:8000        |
| API docs   | http://localhost:8000/docs   |
| PostgreSQL | localhost:5432               |

## Local development (without Docker)

Requirements: Python 3.12, Node 20, PostgreSQL, an OpenAI API key.

```bash
# Backend
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export DATABASE_URL=postgresql+asyncpg://drinkbot:change-me@localhost:5432/drinkbot
export OPENAI_API_KEY=sk-...
alembic upgrade head
python -m app.seed
uvicorn app.main:app --reload

# Frontend (separate terminal) — dev server proxies /api to :8000
cd frontend
npm install
npm run dev            # http://localhost:5173
```

## Running tests

```bash
cd backend
.venv/bin/python -m pytest -v
```

Tests use an in-memory SQLite database and never call a real LLM — the chat agent's model is replaced with a scripted fake that plays back tool calls deterministically. Coverage includes allergen exclusion, recommendation filtering, auth/JWT, phone validation, the chat agent's 3 tools, and menu CRUD.

## Configuration

All configuration is via environment variables (see [.env.example](.env.example)):

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | Async SQLAlchemy Postgres URL |
| `JWT_SECRET`, `JWT_ALGORITHM`, `JWT_EXPIRES_MINUTES` | Session tokens |
| `OPENAI_API_KEY`, `OPENAI_MODEL` | OpenAI settings for the chat agent |
| `CORS_ORIGINS` | Comma-separated allowed origins |
| `ADMIN_API_KEY` | If set, menu write endpoints require the `X-Admin-Key` header |

## API overview

| Method | Path | Description |
|---|---|---|
| POST | `/api/auth/register` | Register (phone, name, address) → JWT |
| POST | `/api/auth/login` | Login by phone → JWT |
| POST | `/api/chat` | Send a chat message to the AI agent (may update profile, recommend, and/or place an order) |
| GET | `/api/chat/history` | Full chat history |
| GET/PUT | `/api/users/me/preferences` | View / update preferences |
| GET/POST/DELETE | `/api/users/me/favorites[/{id}]` | Manage favorites |
| GET/POST/PUT/DELETE | `/api/menu[/{id}]` | Menu CRUD (admin) |

Full interactive docs at `/docs`.

## Architecture notes

- **Allergen enforcement**: `backend/app/services/recommendation.py` expands declared allergies into ingredient keywords (dairy → milk, cream, yogurt, …). The `recommend_drink` and `order` tool executors in `backend/app/services/agent.py` filter/reject unsafe drinks in code, so the LLM can never recommend or order them regardless of what it asks for.
- **Chat agent**: `backend/app/services/agent.py` binds 3 tools (`update_profile`, `recommend_drink`, `order`) to the OpenAI chat model via Langchain's `bind_tools`. Each turn loops (bounded iterations): the model either replies directly or calls a tool, whose result is fed back until a final reply is produced.
- **Chat**: non-streaming; each turn persists the user message and the final assistant reply (intermediate tool calls are not persisted).

## Deployment

See [DEPLOYMENT.md](DEPLOYMENT.md) for a scalable AWS approach.
