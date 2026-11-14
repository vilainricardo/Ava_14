from types import SimpleNamespace
from unittest.mock import patch

import pytest
from cursor_sdk import CursorAgentError

from app.agents.failure_analyzer import FailureAnalysisError, analyze_failure
from app.exceptions.error_messages import (
    CURSOR_API_KEY_MISSING_MESSAGE,
    FAILURE_ANALYSIS_INCOMPLETE_MESSAGE,
    FAILURE_ANALYSIS_START_ERROR_MESSAGE,
    LOG_EMPTY_ERROR_MESSAGE,
)


def test_analyze_failure_returns_agent_analysis(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verifica o caminho em que o agente conclui a análise.

    Nenhuma chamada real é feita. monkeypatch coloca uma chave fictícia
    no ambiente, e patch substitui _execute_analysis por uma função controlada.
    SimpleNamespace imita o objeto que o SDK devolveria, contendo apenas
    os campos que analyze_failure lê.
    """
    monkeypatch.setenv("CURSOR_API_KEY", "cursor_test")
    log = "AssertionError: assert 1 == 2"
    analysis = "Causa provável: a asserção compara valores diferentes."

    with patch(
        "app.agents.failure_analyzer._execute_analysis",
        return_value=SimpleNamespace(
            status="finished",
            result=analysis,
            error_message=None,
        ),
    ) as prompt:
        result = analyze_failure(log)

    # O texto devolvido ao chamador é a análise, não o log original.
    assert result == analysis

    # O primeiro argumento da chamada é a mensagem enviada ao agente.
    message = prompt.call_args.args[0]
    assert log in message
    assert "Descrição da falha" in message

    # O segundo argumento carrega modelo, chave e a lista de ferramentas.
    options = prompt.call_args.args[1]
    assert options.model == "composer-2.5"
    assert options.api_key == "cursor_test"
    assert options.tools == []
    assert options.local.custom_tools is not None
    assert "consultar_rota_steam" in options.local.custom_tools


def test_analyze_failure_includes_diff(monkeypatch: pytest.MonkeyPatch) -> None:
    """Confere que um diff com conteúdo entra na mensagem do agente."""
    monkeypatch.setenv("CURSOR_API_KEY", "cursor_test")
    diff = "--- a/tests/test_ci_failure.py\n+++ b/tests/test_ci_failure.py"

    with patch(
        "app.agents.failure_analyzer._execute_analysis",
        return_value=SimpleNamespace(
            status="finished",
            result="Análise com diff.",
            error_message=None,
        ),
    ) as prompt:
        analyze_failure("AssertionError: assert 1 == 2", diff=diff)

    assert diff in prompt.call_args.args[0]


def test_analyze_failure_omits_blank_diff(monkeypatch: pytest.MonkeyPatch) -> None:
    """Confere que um diff só com espaços não é enviado ao agente."""
    monkeypatch.setenv("CURSOR_API_KEY", "cursor_test")

    with patch(
        "app.agents.failure_analyzer._execute_analysis",
        return_value=SimpleNamespace(
            status="finished",
            result="Análise sem diff.",
            error_message=None,
        ),
    ) as prompt:
        analyze_failure("AssertionError: assert 1 == 2", diff="   ")

    assert "Diff das alterações" not in prompt.call_args.args[0]


def test_analyze_failure_rejects_empty_log() -> None:
    """Um log vazio gera ValueError e não chega a chamar o agente.

    O patch existe para observar a chamada. assert_not_called confirma
    que a validação aconteceu antes de qualquer contato com o Cursor.
    """
    with (
        patch("app.agents.failure_analyzer._execute_analysis") as prompt,
        pytest.raises(ValueError, match=LOG_EMPTY_ERROR_MESSAGE),
    ):
        analyze_failure("")

    prompt.assert_not_called()


def test_analyze_failure_rejects_whitespace_log() -> None:
    """Um log formado apenas por espaços segue a mesma regra do log vazio."""
    with (
        patch("app.agents.failure_analyzer._execute_analysis") as prompt,
        pytest.raises(ValueError, match=LOG_EMPTY_ERROR_MESSAGE),
    ):
        analyze_failure("   ")

    prompt.assert_not_called()


def test_analyze_failure_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sem CURSOR_API_KEY, a análise para antes de criar o agente.

    O .env é carregado na importação. delenv esconde a chave durante
    este teste, esteja ela no arquivo ou no terminal. raising=False
    evita erro quando a variável já estava ausente.
    """
    monkeypatch.delenv("CURSOR_API_KEY", raising=False)

    with (
        patch("app.agents.failure_analyzer._execute_analysis") as prompt,
        pytest.raises(FailureAnalysisError, match=CURSOR_API_KEY_MISSING_MESSAGE),
    ):
        analyze_failure("AssertionError: assert 1 == 2")

    prompt.assert_not_called()


def test_analyze_failure_reports_startup_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Uma falha ao iniciar o agente vira FailureAnalysisError.

    side_effect faz o substituto de _execute_analysis lançar CursorAgentError,
    que é o erro do SDK para autenticação, rede ou configuração. O teste
    verifica a mensagem usada pela aplicação, sem depender do texto
    exato vindo do Cursor.
    """
    monkeypatch.setenv("CURSOR_API_KEY", "cursor_test")

    with (
        patch(
            "app.agents.failure_analyzer._execute_analysis",
            side_effect=CursorAgentError("chave inválida"),
        ),
        pytest.raises(
            FailureAnalysisError,
            match=FAILURE_ANALYSIS_START_ERROR_MESSAGE,
        ),
    ):
        analyze_failure("AssertionError: assert 1 == 2")


def test_analyze_failure_reports_incomplete_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Uma execução que começa e termina com erro também é reportada.

    Aqui _execute_analysis devolve um resultado com status "error". Isso é
    diferente do teste anterior: a chamada existiu, mas não produziu
    uma análise utilizável.
    """
    monkeypatch.setenv("CURSOR_API_KEY", "cursor_test")

    with (
        patch(
            "app.agents.failure_analyzer._execute_analysis",
            return_value=SimpleNamespace(
                status="error",
                result="",
                error_message="execução interrompida",
            ),
        ),
        pytest.raises(
            FailureAnalysisError,
            match=FAILURE_ANALYSIS_INCOMPLETE_MESSAGE,
        ),
    ):
        analyze_failure("AssertionError: assert 1 == 2")
