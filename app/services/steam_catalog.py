import os
import warnings
from dataclasses import dataclass

import httpx

from app.services.steam_endpoints import (
    GET_SUPPORTED_API_LIST,
    STEAM_WEB_API_URL,
    SteamRoute,
)


@dataclass(frozen=True)
class SteamParameter:
    """Parâmetro de um método, como veio no catálogo da Steam."""

    name: str
    type_name: str
    optional: bool
    description: str


@dataclass(frozen=True)
class RouteCheck:
    """Resultado da comparação de uma rota com o catálogo."""

    called_path: str
    current_path: str | None
    warning: str | None


def fetch_catalog(
    transport: httpx.BaseTransport | None = None,
) -> dict[str, object] | None:
    """Busca o catálogo público de métodos da Steam.

    Devolve None quando a Steam não responde ou o corpo não é um objeto.
    A falha não se propaga: a pipeline continua e avisa que não conferiu.
    """
    url: str = f"{STEAM_WEB_API_URL}{GET_SUPPORTED_API_LIST}"
    try:
        with httpx.Client(timeout=30.0, transport=transport) as client:
            response: httpx.Response = client.get(url)
            response.raise_for_status()
            payload: object = response.json()
    except (httpx.HTTPError, ValueError):
        return None

    if not isinstance(payload, dict):
        return None
    return {str(key): value for key, value in payload.items()}


def compare_route(
    route: SteamRoute,
    catalog: dict[str, object] | None,
) -> RouteCheck:
    """Compara a versão chamada com a maior versão listada no catálogo.

    Os números e os parâmetros saem só da resposta da Steam. Esta função
    não escolhe uma versão mais nova por conta própria.
    """
    if catalog is None:
        return RouteCheck(
            called_path=route.path,
            current_path=None,
            warning=_unavailable_message(route.path),
        )

    versions: dict[int, tuple[SteamParameter, ...]] = _method_versions(
        catalog,
        route.interface,
        route.method,
    )
    if not versions:
        return RouteCheck(
            called_path=route.path,
            current_path=None,
            warning=_unavailable_message(route.path),
        )

    latest_version: int = max(versions)
    current_path: str = f"/{route.interface}/{route.method}/v{latest_version}/"
    if route.version >= latest_version:
        return RouteCheck(
            called_path=route.path,
            current_path=current_path,
            warning=None,
        )

    called_parameters: tuple[SteamParameter, ...] | None = versions.get(route.version)
    return RouteCheck(
        called_path=route.path,
        current_path=current_path,
        warning=_outdated_message(
            route.path,
            current_path,
            called_parameters,
            versions[latest_version],
        ),
    )


def publish_maintenance_warning(message: str) -> None:
    """Registra o aviso sem interromper a execução.

    No GitHub Actions, a linha ::warning:: aparece na interface da
    execução e não muda o resultado do job. Fora da pipeline, o
    UserWarning entra no resumo do Pytest.
    """
    warnings.warn(message, UserWarning, stacklevel=2)
    if os.environ.get("GITHUB_ACTIONS") == "true":
        single_line: str = " ".join(message.split())
        print(f"::warning::{single_line}", flush=True)


def describe_route(
    interface: str,
    method: str,
    version: int,
    transport: httpx.BaseTransport | None = None,
) -> str:
    """Consulta o catálogo e descreve se a rota pedida precisa de manutenção."""
    route: SteamRoute = SteamRoute(interface, method, version)
    check: RouteCheck = compare_route(route, fetch_catalog(transport))
    if check.warning is not None:
        return check.warning
    return f"A rota {check.called_path} está na versão mais alta listada pela Steam."


def _method_versions(
    catalog: dict[str, object],
    interface: str,
    method: str,
) -> dict[int, tuple[SteamParameter, ...]]:
    apilist: object = catalog.get("apilist")
    if not isinstance(apilist, dict):
        return {}

    interfaces: object = apilist.get("interfaces")
    if not isinstance(interfaces, list):
        return {}

    versions: dict[int, tuple[SteamParameter, ...]] = {}
    for item in interfaces:
        if not isinstance(item, dict) or item.get("name") != interface:
            continue
        methods: object = item.get("methods")
        if not isinstance(methods, list):
            continue
        for entry in methods:
            parsed: tuple[int, tuple[SteamParameter, ...]] | None = _parse_method(
                entry,
                method,
            )
            if parsed is not None:
                versions[parsed[0]] = parsed[1]
    return versions


def _parse_method(
    entry: object,
    method: str,
) -> tuple[int, tuple[SteamParameter, ...]] | None:
    if not isinstance(entry, dict) or entry.get("name") != method:
        return None
    version: object = entry.get("version")
    if isinstance(version, bool) or not isinstance(version, int):
        return None

    parameters: list[SteamParameter] = []
    raw_parameters: object = entry.get("parameters")
    if isinstance(raw_parameters, list):
        for raw_parameter in raw_parameters:
            parameter: SteamParameter | None = _parse_parameter(raw_parameter)
            if parameter is not None:
                parameters.append(parameter)
    return version, tuple(parameters)


def _parse_parameter(raw_parameter: object) -> SteamParameter | None:
    if not isinstance(raw_parameter, dict):
        return None
    name: object = raw_parameter.get("name")
    if not isinstance(name, str) or not name:
        return None
    type_name: object = raw_parameter.get("type")
    description: object = raw_parameter.get("description")
    return SteamParameter(
        name=name,
        type_name=type_name if isinstance(type_name, str) else "",
        optional=bool(raw_parameter.get("optional", False)),
        description=description if isinstance(description, str) else "",
    )


def _unavailable_message(called_path: str) -> str:
    return (
        "O sistema está funcionando, mas precisa de manutenção. "
        f"A rota {called_path} não pôde ser conferida porque o catálogo "
        "da Steam não trouxe esse método."
    )


def _outdated_message(
    called_path: str,
    current_path: str,
    called_parameters: tuple[SteamParameter, ...] | None,
    current_parameters: tuple[SteamParameter, ...],
) -> str:
    parts: list[str] = [
        "O sistema está funcionando, mas precisa de manutenção.",
        f"A rota {called_path} está desatualizada.",
        f"A versão mais alta no catálogo é {current_path}.",
        _parameter_changes(called_parameters, current_parameters),
    ]
    return " ".join(parts)


def _parameter_changes(
    called_parameters: tuple[SteamParameter, ...] | None,
    current_parameters: tuple[SteamParameter, ...],
) -> str:
    if called_parameters is None:
        listed: str = ", ".join(
            _format_parameter(parameter) for parameter in current_parameters
        )
        return (
            "A lista de parâmetros da rota chamada não veio no catálogo. "
            f"Parâmetros da versão mais alta: {listed or 'nenhum'}."
        )

    called_by_name: dict[str, SteamParameter] = {
        parameter.name: parameter for parameter in called_parameters
    }
    current_by_name: dict[str, SteamParameter] = {
        parameter.name: parameter for parameter in current_parameters
    }
    added: list[str] = [
        _format_parameter(current_by_name[name])
        for name in current_by_name
        if name not in called_by_name
    ]
    removed: list[str] = [
        _format_parameter(called_by_name[name])
        for name in called_by_name
        if name not in current_by_name
    ]
    changed: list[str] = [
        (
            f"{name} de {_format_parameter(called_by_name[name])} "
            f"para {_format_parameter(current_by_name[name])}"
        )
        for name in current_by_name
        if name in called_by_name and called_by_name[name] != current_by_name[name]
    ]
    return (
        f"Parâmetros incluídos: {_join(added)}. "
        f"Parâmetros removidos: {_join(removed)}. "
        f"Parâmetros alterados: {_join(changed)}."
    )


def _format_parameter(parameter: SteamParameter) -> str:
    presence: str = "opcional" if parameter.optional else "obrigatório"
    return (
        f"{parameter.name} ({parameter.type_name}, {presence}): {parameter.description}"
    )


def _join(items: list[str]) -> str:
    if not items:
        return "nenhum"
    return "; ".join(items)
