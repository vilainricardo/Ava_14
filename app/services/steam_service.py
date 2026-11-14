
import httpx
from pydantic import BaseModel, ConfigDict, TypeAdapter
from app.exceptions.error_messages import INVALID_APP_ID_MESSAGE, STEAM_NEWS_LIST_ERROR_MESSAGE, STEAM_INVALID_RESPONSE_MESSAGE

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


async def get_game_news(
        app_id: int,
        transport: httpx.AsyncBaseTransport | None = None,
        ) -> list[SteamGameNews]:
    if app_id <= 0:
        raise ValueError(INVALID_APP_ID_MESSAGE)

    url: str = f"{STEAM_WEB_API_URL}{GET_GAME_NEWS}"

    async with httpx.AsyncClient(
        timeout=15.0, 
        transport=transport
        ) as client:

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
        raise TypeError(STEAM_INVALID_RESPONSE_MESSAGE)

    articles_data: object = news_data.get("newsitems")

    if not isinstance(articles_data, list):
        raise TypeError(STEAM_NEWS_LIST_ERROR_MESSAGE)

    return [
        SteamGameNews.model_validate(article)
        for article in articles_data
    ]
