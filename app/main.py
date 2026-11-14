
from fastapi import FastAPI

from app.config import get_steam_api_key

app: FastAPI = FastAPI(
    title="Ava_14",
    description="Integração com a Steam e geração de conteúdo com IA.",
    version="1.0.0",
)


@app.get("/")
def home() -> dict[str, str]:
    return {
        "message": "Ava_14 API está funcionando!"
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "healthy"
    }


@app.get("/config-check")
def config_check() -> dict[str, bool]:
    return {
        "steam_api_configured": bool(get_steam_api_key())
    }
