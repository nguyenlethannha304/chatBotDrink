# chatBotDrinkRecommendation

A chatbot that gives personalized drink recommendations from a shop's menu, powered by **FastAPI + Langchain** (Ollama, OpenAI, or Gemini), with a **React + Tailwind** frontend and **PostgreSQL** storage.

## Features

- **Phone-number registration & login** (JWT session, no password for MVP)
- **Conversational onboarding** — the bot asks about tastes, drink types, temperature, caffeine, and allergies, then extracts structured preferences with the LLM
- **Chat-based recommendations** — only from the shop's menu, personalized to the user's profile and conversation context
- **Hard allergen safety** — drinks containing a user's allergens are filtered out *in code* before the LLM ever sees the menu, so it can never recommend them
- **Profile management** — update preferences/allergies via chat ("I'm allergic to peanuts now") or the profile page; save favorite drinks
- **Menu admin API** — CRUD endpoints (optionally protected with `ADMIN_API_KEY`)
- **Seeded menu** — 15 sample drinks (5 cafe, 5 tea, 5 fruit juice)

## Quick start (Docker)

```bash
cp .env.example .env      # edit secrets / choose LLM provider
docker-compose up --build
```

**LLM provider** is set with `LLM_PROVIDER` in `.env`:
- `openai` or `gemini` — set the matching API key (`OPENAI_API_KEY` / `GEMINI_API_KEY`); no local model needed
- `ollama` — free local model; start with `docker compose --profile ollama up --build` (first start downloads ~4.7 GB)

Recommendations fall back to deterministic preference ranking if the LLM is unreachable.

| Service    | URL                          |
|------------|------------------------------|
| Frontend   | http://localhost:3000        |
| API        | http://localhost:8000        |
| API docs   | http://localhost:8000/docs   |
| Ollama     | http://localhost:11434       |
| PostgreSQL | localhost:5432               |

## Local development (without Docker)

Requirements: Python 3.12, Node 20, PostgreSQL, [Ollama](https://ollama.com).

```bash
# Backend
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export DATABASE_URL=postgresql+asyncpg://drinkbot:change-me@localhost:5432/drinkbot
export OLLAMA_BASE_URL=http://localhost:11434
alembic upgrade head
python -m app.seed
uvicorn app.main:app --reload

# Frontend (separate terminal) — dev server proxies /api to :8000
cd frontend
npm install
npm run dev            # http://localhost:5173

# Ollama (separate terminal)
ollama pull llama3.1 && ollama serve
```

## Running tests

```bash
cd backend
.venv/bin/python -m pytest -v
```

Tests use an in-memory SQLite database and never call Ollama (LLM calls are mocked / forced onto deterministic fallback paths). Coverage includes allergen exclusion, recommendation filtering, preference extraction parsers, auth/JWT, phone validation, onboarding flow, and menu CRUD.

## Configuration

All configuration is via environment variables (see [.env.example](.env.example)):

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | Async SQLAlchemy Postgres URL |
| `JWT_SECRET`, `JWT_ALGORITHM`, `JWT_EXPIRES_MINUTES` | Session tokens |
| `LLM_PROVIDER` | `ollama`, `openai`, or `gemini` |
| `OLLAMA_BASE_URL`, `OLLAMA_MODEL` | Local Ollama settings |
| `OPENAI_API_KEY`, `OPENAI_MODEL` | OpenAI settings |
| `GEMINI_API_KEY`, `GEMINI_MODEL` | Gemini settings |
| `CORS_ORIGINS` | Comma-separated allowed origins |
| `ADMIN_API_KEY` | If set, menu write endpoints require the `X-Admin-Key` header |

## API overview

| Method | Path | Description |
|---|---|---|
| POST | `/api/auth/register` | Register (phone, name, address) → JWT |
| POST | `/api/auth/login` | Login by phone → JWT |
| POST | `/api/chat` | Send a chat message (onboarding or recommendation) |
| GET | `/api/chat/history` | Full chat history |
| GET/PUT | `/api/users/me/preferences` | View / update preferences |
| GET/POST/DELETE | `/api/users/me/favorites[/{id}]` | Manage favorites |
| GET/POST/PUT/DELETE | `/api/menu[/{id}]` | Menu CRUD (admin) |

Full interactive docs at `/docs`.

## Architecture notes

- **Allergen enforcement**: `backend/app/services/recommendation.py` expands declared allergies into ingredient keywords (dairy → milk, cream, yogurt, …), removes unsafe drinks from the candidate list before prompting the LLM, and validates the LLM's picks against that safe list — hallucinated or unsafe names are dropped.
- **Onboarding**: a 5-question state machine (`onboarding_step` on the user). Answers are extracted by the LLM with deterministic keyword parsers as fallback, so onboarding works even if Ollama is down.
- **Chat**: non-streaming; each turn is persisted. During normal chat, messages hinting at profile changes trigger LLM-based preference extraction and a DB update.

## Deployment

See [DEPLOYMENT.md](DEPLOYMENT.md) for a scalable AWS approach.
