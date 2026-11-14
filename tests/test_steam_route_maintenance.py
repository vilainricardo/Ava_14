import os
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import patch

import pytest

from app.agents.failure_analyzer import explain_maintenance_warning
from app.config import BASE_DIR
from app.services.steam_catalog import (
    compare_route,
    fetch_catalog,
    publish_maintenance_warning,
)
from app.services.steam_endpoints import STEAM_ROUTES, SteamRoute

# Marcador fixo para a Actions achar e atualizar o mesmo comentário do PR.
MAINTENANCE_REPORT_MARKER: str = "<!-- ava14-steam-maintenance -->"
MAINTENANCE_REPORT_PATH: Path = BASE_DIR / "maintenance-report.md"
NO_MAINTENANCE_MESSAGE: str = "Nenhuma rota precisa de manutenção."


def record_maintenance_report(
    warning: str,
    explanation: str,
    path: Path | None = None,
) -> None:
    """Acrescenta o aviso e a explicação ao relatório da Actions.

    A primeira gravação escreve o marcador. As seguintes só acrescentam
    seções, para várias rotas caberem no mesmo comentário. Fora da
    Actions, não cria arquivo.
    """
    if os.environ.get("GITHUB_ACTIONS") != "true":
        return

    target: Path = MAINTENANCE_REPORT_PATH if path is None else path
    section: str = (
        f"### Aviso\n\n{warning.strip()}\n\n### Explicação\n\n{explanation.strip()}\n"
    )
    if target.exists():
        current: str = target.read_text(encoding="utf-8")
        if not current.endswith("\n"):
            current += "\n"
        target.write_text(f"{current}\n{section}", encoding="utf-8")
        return

    target.write_text(
        f"{MAINTENANCE_REPORT_MARKER}\n\n{section}",
        encoding="utf-8",
    )


def write_clear_maintenance_report(path: Path | None = None) -> None:
    """Grava que não há manutenção quando nenhum aviso foi registrado.

    Se o arquivo já tem avisos, ele permanece. Fora da Actions, não
    cria arquivo.
    """
    if os.environ.get("GITHUB_ACTIONS") != "true":
        return

    target: Path = MAINTENANCE_REPORT_PATH if path is None else path
    if target.exists():
        return

    target.write_text(
        f"{MAINTENANCE_REPORT_MARKER}\n\n{NO_MAINTENANCE_MESSAGE}\n",
        encoding="utf-8",
    )


@pytest.fixture(scope="session", autouse=True)
def maintenance_report_session() -> Iterator[None]:
    """Prepara o relatório desta execução e completa se ninguém avisou.

    No início remove um relatório deixado por outra execução. No fim,
    se nenhuma rota gravou aviso, publica a frase de que não há
    manutenção pendente.
    """
    if os.environ.get("GITHUB_ACTIONS") == "true" and MAINTENANCE_REPORT_PATH.exists():
        MAINTENANCE_REPORT_PATH.unlink()
    yield
    write_clear_maintenance_report()


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
    if check.warning is None:
        return

    publish_maintenance_warning(check.warning)
    explanation: str = explain_maintenance_warning(check.warning)
    print(explanation, flush=True)
    if os.environ.get("GITHUB_ACTIONS") == "true":
        notice: str = " ".join(explanation.split())
        print(f"::notice::{notice}", flush=True)
        record_maintenance_report(check.warning, explanation)


def test_maintenance_report_records_warning_and_explanation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O relatório começa no marcador e guarda o aviso e a explicação.

    O agente entra simulado. Uma segunda rota acrescenta outra seção
    sem repetir o marcador, e o fechamento sem avisos não apaga o que
    já foi gravado.
    """
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    report_path: Path = tmp_path / "maintenance-report.md"
    warning = "A rota /ISteamNews/GetNewsForApp/v1/ está desatualizada."
    explanation = "A v1 ficou para trás do catálogo."

    with patch(
        "app.agents.failure_analyzer.analyze_failure",
        return_value=explanation,
    ):
        recorded: str = explain_maintenance_warning(warning)

    record_maintenance_report(warning, recorded, report_path)
    record_maintenance_report("Segundo aviso.", "Segunda explicação.", report_path)
    write_clear_maintenance_report(report_path)

    text: str = report_path.read_text(encoding="utf-8")
    assert text.startswith(MAINTENANCE_REPORT_MARKER)
    assert text.count(MAINTENANCE_REPORT_MARKER) == 1
    assert warning in text
    assert explanation in text
    assert "Segundo aviso." in text
    assert "Segunda explicação." in text


def test_clear_maintenance_report_when_no_warning(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sem avisos, o relatório leva o marcador e a frase de manutenção em dia."""
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    report_path: Path = tmp_path / "maintenance-report.md"

    write_clear_maintenance_report(report_path)

    text: str = report_path.read_text(encoding="utf-8")
    assert text.startswith(MAINTENANCE_REPORT_MARKER)
    assert NO_MAINTENANCE_MESSAGE in text
