
import httpx
import pytest

from app.exceptions.error_messages import INVALID_APP_ID_MESSAGE
from app.services.steam_service import get_game_news


@pytest.mark.anyio
async def test_get_game_news_returns_articles() -> None:
    # Simula a resposta que seria recebida da API da Steam.
    def mock_steam_response(request: httpx.Request) -> httpx.Response:
        # Verifica se o serviço enviou o AppID correto.
        assert request.url.params["appid"] == "730"

        return httpx.Response(
            200,
            json={
                "appnews": {
                    "newsitems": [
                        {
                            "gid": "12345",
                            "title": "Notícia de teste",
                            "url": "https://example.com/news",
                            "author": "Steam",
                            "contents": "Conteúdo de teste",
                        }
                    ]
                }
            },
        )

    # Cria um transporte que utiliza nossa resposta simulada.
    transport: httpx.MockTransport = httpx.MockTransport(
        mock_steam_response
    )

    # Executa o serviço usando o transporte simulado.
    articles = await get_game_news(730, transport=transport)

    # Confirma que o serviço interpretou a resposta corretamente.
    assert len(articles) == 1
    assert articles[0].gid == "12345"
    assert articles[0].title == "Notícia de teste"

@pytest.mark.anyio
async def test_get_game_news_rejects_invalid_app_id() -> None:
    with pytest.raises(ValueError, match=INVALID_APP_ID_MESSAGE):
        await get_game_news(0)