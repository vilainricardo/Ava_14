import httpx
import pytest

from app.services.steam_catalog import (
    compare_route,
    fetch_catalog,
    publish_maintenance_warning,
)
from app.services.steam_endpoints import SteamRoute


def _method(
    version: int,
    parameters: list[dict[str, object]],
) -> dict[str, object]:
    return {
        "name": "GetNewsForApp",
        "version": version,
        "parameters": parameters,
    }


def _catalog(methods: list[dict[str, object]]) -> dict[str, object]:
    return {
        "apilist": {
            "interfaces": [
                {
                    "name": "ISteamNews",
                    "methods": methods,
                }
            ]
        }
    }


def test_compare_route_reports_parameter_changes() -> None:
    catalog = _catalog(
        [
            _method(
                1,
                [
                    {
                        "name": "appid",
                        "type": "uint32",
                        "optional": False,
                        "description": "AppID",
                    }
                ],
            ),
            _method(
                2,
                [
                    {
                        "name": "appid",
                        "type": "uint32",
                        "optional": False,
                        "description": "AppID do jogo",
                    },
                    {
                        "name": "feeds",
                        "type": "string",
                        "optional": True,
                        "description": "Feeds desejados",
                    },
                ],
            ),
        ]
    )

    check = compare_route(SteamRoute("ISteamNews", "GetNewsForApp", 1), catalog)

    assert check.warning is not None
    assert "/ISteamNews/GetNewsForApp/v1/" in check.warning
    assert "/ISteamNews/GetNewsForApp/v2/" in check.warning
    assert "feeds" in check.warning
    assert "Parâmetros alterados" in check.warning
    assert "precisa de manutenção" in check.warning


def test_compare_route_is_silent_when_version_matches() -> None:
    catalog = _catalog(
        [
            _method(
                2,
                [
                    {
                        "name": "appid",
                        "type": "uint32",
                        "optional": False,
                        "description": "AppID",
                    }
                ],
            )
        ]
    )

    check = compare_route(SteamRoute("ISteamNews", "GetNewsForApp", 2), catalog)

    assert check.warning is None
    assert check.current_path == "/ISteamNews/GetNewsForApp/v2/"


def test_compare_route_warns_when_catalog_has_a_newer_version() -> None:
    catalog = _catalog(
        [
            _method(
                3,
                [
                    {
                        "name": "count",
                        "type": "uint32",
                        "optional": True,
                        "description": "Quantidade",
                    }
                ],
            )
        ]
    )

    check = compare_route(SteamRoute("ISteamNews", "GetNewsForApp", 2), catalog)

    assert check.warning is not None
    assert "/ISteamNews/GetNewsForApp/v2/" in check.warning
    assert "/ISteamNews/GetNewsForApp/v3/" in check.warning
    assert "não veio no catálogo" in check.warning
    assert "count" in check.warning


def test_fetch_catalog_returns_none_when_steam_fails() -> None:
    def mock_response(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, request=request)

    catalog = fetch_catalog(transport=httpx.MockTransport(mock_response))

    assert catalog is None


def test_publish_maintenance_warning_uses_github_annotation(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("GITHUB_ACTIONS", "true")

    with pytest.warns(UserWarning, match="precisa de manutenção"):
        publish_maintenance_warning(
            "O sistema está funcionando, mas precisa de manutenção."
        )

    captured = capsys.readouterr()
    assert captured.out.startswith("::warning::")
