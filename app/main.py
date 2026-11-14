import httpx
from fastapi import FastAPI, HTTPException

from app.exceptions.error_messages import STEAM_API_ERROR_MESSAGE
from app.services.steam_service import (
    SteamGameNews,
    get_game_news,
)

app: FastAPI = FastAPI(
    title="Ava_14",
    description="Integração com a Steam e geração de conteúdo com IA.",
    version="1.0.0",
)


@app.get("/")
def home() -> dict[str, str]:
    return {"message": "Ava_14 API está funcionando!"}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "healthy"}


@app.get("/games/{app_id}/news", response_model=list[SteamGameNews])
async def get_game_news_endpoint(app_id: int) -> list[SteamGameNews]:
    try:
        return await get_game_news(app_id)
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error

    except httpx.HTTPStatusError as error:
        raise HTTPException(
            status_code=502,
            detail=str(error),
        ) from error
    except httpx.HTTPError as error:
        raise HTTPException(
            status_code=502,
            detail=STEAM_API_ERROR_MESSAGE,
        ) from error
    except TypeError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error
