import httpx
import pytest

from app.exceptions.error_messages import (
    INVALID_APP_ID_MESSAGE,
    STEAM_INVALID_RESPONSE_MESSAGE,
    STEAM_NEWS_LIST_ERROR_MESSAGE,
    STEAM_NEWS_NOT_FOUND_MESSAGE,
    STEAM_NEWS_UNAVAILABLE_MESSAGE,
    STEAM_REQUEST_ERROR_MESSAGE,
)
from app.services.steam_service import get_game_news


@pytest.mark.parametrize("version", [1, 2])
@pytest.mark.anyio
async def test_get_game_news_returns_articles(version: int) -> None:
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
    transport: httpx.MockTransport = httpx.MockTransport(mock_steam_response)

    # Executa o serviço usando o transporte simulado.
    articles = await get_game_news(730, version, transport=transport)

    # Confirma que o serviço interpretou a resposta corretamente.
    assert len(articles) == 1
    assert articles[0].gid == "12345"
    assert articles[0].title == "Notícia de teste"


@pytest.mark.parametrize("version", [1, 2])
@pytest.mark.anyio
async def test_get_game_news_rejects_invalid_app_id(version: int) -> None:
    with pytest.raises(ValueError, match=INVALID_APP_ID_MESSAGE):
        await get_game_news(0, version)


@pytest.mark.parametrize("version", [1, 2])
@pytest.mark.anyio
async def test_get_game_news_rejects_invalid_response_structure(version: int) -> None:
    # Simula uma resposta da Steam com HTTP 200,
    # mas com uma estrutura JSON diferente da esperada.
    def mock_steam_response(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "unexpected": "invalid response",
            },
        )

    # Cria um transporte HTTP simulado para evitar
    # uma chamada real à API da Steam.
    transport: httpx.MockTransport = httpx.MockTransport(mock_steam_response)

    # Verifica se o serviço lança a exceção esperada
    # e se utiliza a mensagem centralizada correspondente.
    with pytest.raises(TypeError) as error:
        await get_game_news(730, version, transport=transport)

    assert str(error.value) == STEAM_INVALID_RESPONSE_MESSAGE


@pytest.mark.parametrize("version", [1, 2])
@pytest.mark.anyio
async def test_get_game_news_rejects_invalid_newsitems(version: int) -> None:
    # Simula uma resposta HTTP 200 da Steam.
    # A estrutura appnews existe, mas newsitems não é uma lista.
    def mock_steam_response(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "appnews": {
                    "newsitems": "conteúdo inválido",
                },
            },
        )

    # Cria um transporte HTTP simulado para evitar
    # uma chamada real à API da Steam.
    transport: httpx.MockTransport = httpx.MockTransport(mock_steam_response)

    # Verifica se o serviço lança TypeError quando newsitems
    # não possui o tipo esperado.
    with pytest.raises(TypeError) as error:
        await get_game_news(730, version, transport=transport)

    # Confirma que a exceção utiliza a mensagem centralizada.
    assert str(error.value) == STEAM_NEWS_LIST_ERROR_MESSAGE


@pytest.mark.parametrize("version", [1, 2])
@pytest.mark.anyio
async def test_get_game_news_handles_http_error(version: int) -> None:
    # Simula uma resposta HTTP 500 da API da Steam,
    # indicando uma falha interna no servidor.
    def mock_steam_response(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            500,
            json={
                "error": "Internal Server Error",
            },
        )

    # Cria um transporte HTTP simulado para evitar
    # uma chamada real à API da Steam.
    transport: httpx.MockTransport = httpx.MockTransport(mock_steam_response)

    # Verifica se o serviço identifica a resposta HTTP 500
    # e lança a exceção HTTPStatusError esperada.
    with pytest.raises(httpx.HTTPStatusError) as error:
        await get_game_news(730, version, transport=transport)

    # Confirma que a mensagem personalizada foi utilizada.
    assert str(error.value) == STEAM_NEWS_UNAVAILABLE_MESSAGE

    # Confirma que o código de status recebido foi HTTP 500.
    assert error.value.response.status_code == 500


@pytest.mark.parametrize("version", [1, 2])
@pytest.mark.anyio
async def test_get_game_news_handles_not_found(version: int) -> None:
    # Simula uma resposta HTTP 404 da Steam.
    def mock_steam_response(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=404,
            json={"error": "Not Found"},
            request=request,
        )

    transport = httpx.MockTransport(mock_steam_response)

    # Verifica se o serviço lança a exceção com a mensagem esperada.
    with pytest.raises(httpx.HTTPStatusError) as error:
        await get_game_news(730, version, transport=transport)

    assert str(error.value) == STEAM_NEWS_NOT_FOUND_MESSAGE
    assert error.value.response.status_code == 404


@pytest.mark.parametrize("version", [1, 2])
@pytest.mark.anyio
async def test_get_game_news_handles_unexpected_http_error(version: int) -> None:
    # Simula uma resposta HTTP 429 da Steam (resposta genérica para todos os outros http errors).
    def mock_steam_response(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=429,
            json={"error": "Too Many Requests"},
            request=request,
        )

    transport = httpx.MockTransport(mock_steam_response)

    # Verifica se o serviço utiliza a mensagem genérica.
    with pytest.raises(httpx.HTTPStatusError) as error:
        await get_game_news(730, version, transport=transport)

    assert str(error.value) == STEAM_REQUEST_ERROR_MESSAGE
    assert error.value.response.status_code == 429
