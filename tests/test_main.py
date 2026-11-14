from unittest.mock import AsyncMock, patch

import httpx
from fastapi.testclient import TestClient

from app.exceptions.error_messages import (
    INVALID_APP_ID_MESSAGE,
    STEAM_API_ERROR_MESSAGE,
)
from app.main import app

client = TestClient(app)


def test_home_returns_success() -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {"message": "Ava_14 API está funcionando!"}


def test_health_returns_success() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_get_game_news_returns_success() -> None:
    # Define os dados fictícios que serão retornados pelo serviço.
    # Esses dados simulam uma resposta válida da função get_game_news().
    expected_news = [
        {
            "gid": "12345",
            "title": "Notícia de teste",
            "url": "https://example.com/news",
            "author": "Steam",
            "contents": "Conteúdo de teste",
        }
    ]

    # Substitui temporariamente a função get_game_news do módulo app.main.
    # O AsyncMock permite simular uma função assíncrona (async).
    # Dessa forma, nenhuma requisição real será enviada à Steam.
    with patch(
        "app.main.get_game_news",
        new_callable=AsyncMock,
    ) as mock_get_game_news:
        # Define o retorno fictício da função simulada.
        # Quando a rota chamar get_game_news(730), receberá expected_news.
        mock_get_game_news.return_value = expected_news

        # Simula uma requisição HTTP GET à rota de notícias do jogo 730.
        # O TestClient executa a aplicação FastAPI sem iniciar um servidor externo.
        response = client.get("/games/730/news")

    assert response.status_code == 200
    assert response.json() == expected_news

    # Verifica se a função simulada foi chamada uma única vez,
    # e se recebeu corretamente o ID 730 como argumento.
    mock_get_game_news.assert_awaited_once_with(730)


def test_get_game_news_returns_bad_gateway() -> None:
    # Cria uma requisição HTTP fictícia para simular o erro.
    request = httpx.Request(
        "GET",
        "https://api.steampowered.com",
    )

    # Simula uma falha de comunicação HTTP.
    http_error = httpx.ConnectError(
        "Erro de conexão",
        request=request,
    )

    # Substitui a função real por um AsyncMock.
    with patch(
        "app.main.get_game_news",
        new_callable=AsyncMock,
    ) as mock_get_game_news:
        # Configura o mock para lançar a exceção HTTP.
        mock_get_game_news.side_effect = http_error

        # Executa a chamada à rota.
        response = client.get("/games/730/news")

    # Verifica se a API retornou HTTP 502.
    assert response.status_code == 502

    # Verifica se a mensagem de erro está correta.
    assert response.json() == {"detail": STEAM_API_ERROR_MESSAGE}

    # Verifica se o serviço foi chamado uma única vez.
    mock_get_game_news.assert_awaited_once_with(730)


def test_get_game_news_returns_bad_gateway_on_http_status_error() -> None:
    # Cria uma requisição HTTP fictícia.
    request = httpx.Request(
        "GET",
        "https://api.steampowered.com",
    )

    # Cria uma resposta HTTP fictícia com status 404.
    steam_response = httpx.Response(
        404,
        request=request,
    )

    # Cria uma exceção HTTPStatusError associada à resposta 404.
    http_error = httpx.HTTPStatusError(
        "Notícia não encontrada.",
        request=request,
        response=steam_response,
    )

    # Substitui temporariamente a função real por um AsyncMock.
    with patch(
        "app.main.get_game_news",
        new_callable=AsyncMock,
    ) as mock_get_game_news:
        # Configura o mock para lançar a exceção HTTPStatusError.
        mock_get_game_news.side_effect = http_error

        # Executa a chamada à rota.
        response = client.get("/games/730/news")

    # Verifica se a rota converteu o erro para HTTP 502.
    assert response.status_code == 502

    # Verifica se a mensagem retornada corresponde à exceção.
    assert response.json() == {"detail": "Notícia não encontrada."}

    # Verifica se o serviço foi chamado uma única vez com o ID 730.
    mock_get_game_news.assert_awaited_once_with(730)


def test_get_game_news_returns_bad_gateway_on_steam_server_error() -> None:
    # Cria uma requisição HTTP fictícia.
    request = httpx.Request(
        "GET",
        "https://api.steampowered.com",
    )

    # Simula uma resposta HTTP 500 da Steam.
    steam_response = httpx.Response(
        500,
        request=request,
    )

    # Cria uma exceção associada à resposta HTTP 500.
    http_error = httpx.HTTPStatusError(
        "Erro interno na Steam.",
        request=request,
        response=steam_response,
    )

    # Substitui a função real por um AsyncMock.
    with patch(
        "app.main.get_game_news",
        new_callable=AsyncMock,
    ) as mock_get_game_news:
        # Configura o mock para lançar a exceção.
        mock_get_game_news.side_effect = http_error

        # Executa a chamada à rota.
        response = client.get("/games/730/news")

    # Verifica se nossa API retornou HTTP 502.
    assert response.status_code == 502

    # Verifica se a mensagem da exceção foi repassada.
    assert response.json() == {"detail": "Erro interno na Steam."}

    # Verifica se o serviço foi chamado uma única vez.
    mock_get_game_news.assert_awaited_once_with(730)


def test_get_game_news_returns_bad_request() -> None:
    # Substitui a função real por um AsyncMock.
    with patch(
        "app.main.get_game_news",
        new_callable=AsyncMock,
    ) as mock_get_game_news:
        # Simula a função lançando ValueError para um app_id inválido.
        mock_get_game_news.side_effect = ValueError(INVALID_APP_ID_MESSAGE)

        # Executa a rota com ID de jogo igual a zero.
        response = client.get("/games/0/news")

    # Verifica se a API retornou HTTP 400.
    assert response.status_code == 400

    # Verifica se a mensagem de erro está correta.
    assert response.json() == {"detail": INVALID_APP_ID_MESSAGE}

    # Verifica se o serviço foi chamado uma única vez com app_id igual a zero.
    mock_get_game_news.assert_awaited_once_with(0)
