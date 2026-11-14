import pytest

from app.services.steam_catalog import (
    compare_route,
    fetch_catalog,
    publish_maintenance_warning,
)
from app.services.steam_endpoints import STEAM_ROUTES, SteamRoute


@pytest.fixture(scope="session")
def steam_catalog() -> dict[str, object] | None:
    """Carrega o catálogo real uma vez para todos os testes de rota."""
    return fetch_catalog()


@pytest.mark.parametrize(
    "route",
    STEAM_ROUTES,
    ids=lambda route: route.path,
)
def test_steam_route_stays_maintainable(
    route: SteamRoute,
    steam_catalog: dict[str, object] | None,
) -> None:
    """Confere a rota no catálogo já carregado e só publica aviso.

    O teste passa mesmo quando a rota está antiga ou quando a Steam não
    responde. O aviso pede manutenção sem derrubar a pipeline.
    """
    check = compare_route(route, steam_catalog)
    if check.warning is not None:
        publish_maintenance_warning(check.warning)
