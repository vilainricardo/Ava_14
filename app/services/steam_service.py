
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter
import httpx

from app.services.steam_endpoints import GET_GAME_NEWS, STEAM_WEB_API_URL


class SteamGameNews(BaseModel):
    model_config = ConfigDict(extra="ignore")

    gid: str
    title: str
    url: str
    author: str | None = None
    contents: str | None = None


class SteamNewsResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    appnews: dict[str, object]


async def get_game_news(app_id: int) -> list[SteamGameNews]:
    if app_id <= 0:
        raise ValueError("O AppID deve ser maior que zero.")

    url: str = f"{STEAM_WEB_API_URL}{GET_GAME_NEWS}"

    async with httpx.AsyncClient(timeout=15.0) as client:
        response: httpx.Response = await client.get(
            url,
            params={
                "appid": app_id,
                "count": 10,
                "maxlength": 300,
            },
        )
        response.raise_for_status()

        payload: dict[str, object] = TypeAdapter(
            dict[str, object]
        ).validate_python(response.json())

    news_data: object = payload.get("appnews")

    if not isinstance(news_data, dict):
        raise ValueError("Resposta inválida da Steam.")

    articles_data: object = news_data.get("newsitems")

    if not isinstance(articles_data, list):
        raise ValueError("A Steam não retornou uma lista de notícias.")

    return [
        SteamGameNews.model_validate(article)
        for article in articles_data
    ]
