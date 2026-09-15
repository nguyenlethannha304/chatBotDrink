from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.llm_versions import current_version
from app.routers import auth, chat, menu, users

app = FastAPI(
    title="chatBotDrinkRecommendation",
    description="Personalized drink recommendations powered by Langchain + OpenAI.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# All routes live under /api so the frontend can proxy a single path prefix
app.include_router(auth.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(menu.router, prefix="/api")
app.include_router(users.router, prefix="/api")


@app.get("/api/health", tags=["health"])
async def health():
    version = current_version()
    return {
        "status": "ok",
        "llm_provider": version.provider,
        "llm_model": version.model,
        "prompt_name": version.prompt_name,
        "prompt_version": version.prompt_version,
        "prompt_hash": version.prompt_hash,
    }
