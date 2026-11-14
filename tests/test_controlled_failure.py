import os
import traceback
from pathlib import Path
from unittest.mock import patch

import pytest

from app.agents.failure_analyzer import explain_pipeline_failure
from app.config import BASE_DIR

CONTROLLED_FAILURE_MESSAGE: str = (
    "Falha controlada para demonstrar o diagnóstico da pipeline."
)
FAILURE_REPORT_MARKER: str = "<!-- ava14-pipeline-failure -->"
FAILURE_REPORT_PATH: Path = BASE_DIR / "failure-report.md"


def record_failure_report(
    log: str,
    explanation: str,
    path: Path | None = None,
) -> None:
    """Grava a falha e a análise para o comentário do Pull Request.

    Fora da Actions, não cria arquivo. O teste continua e levanta o
    erro original depois desta gravação.
    """
    if os.environ.get("GITHUB_ACTIONS") != "true":
        return

    target: Path = FAILURE_REPORT_PATH if path is None else path
    section: str = (
        f"### Falha\n\n{log.strip()}\n\n### Explicação\n\n{explanation.strip()}\n"
    )
    target.write_text(
        f"{FAILURE_REPORT_MARKER}\n\n{section}",
        encoding="utf-8",
    )


@pytest.mark.skipif(
    os.environ.get("CI_CONTROLLED_FAILURE") != "true",
    reason="A falha controlada roda só no job dedicado da pipeline.",
)
def test_controlled_pipeline_failure() -> None:
    """Erro proposital para o check deste job aparecer como falha.

    Antes de relançar o erro, pede a análise ao agente e grava o
    relatório. O job tests não define CI_CONTROLLED_FAILURE, então
    ignora este teste. A aplicação e o aviso da Steam seguem no outro job.
    """
    try:
        raise AssertionError(CONTROLLED_FAILURE_MESSAGE)
    except AssertionError:
        log: str = traceback.format_exc().strip()
        explanation: str = explain_pipeline_failure(log)
        print(explanation, flush=True)
        if os.environ.get("GITHUB_ACTIONS") == "true":
            notice: str = " ".join(explanation.split())
            print(f"::notice::{notice}", flush=True)
            record_failure_report(log, explanation)
        raise


def test_controlled_pipeline_failure_records_analysis_and_reraises(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A análise é gravada e o AssertionError original continua."""
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    report_path: Path = tmp_path / "failure-report.md"
    explanation = "A asserção foi levantada de propósito."

    with (
        patch(
            "tests.test_controlled_failure.explain_pipeline_failure",
            return_value=explanation,
        ),
        patch(
            "tests.test_controlled_failure.FAILURE_REPORT_PATH",
            report_path,
        ),
        pytest.raises(AssertionError, match=CONTROLLED_FAILURE_MESSAGE),
    ):
        test_controlled_pipeline_failure()

    text: str = report_path.read_text(encoding="utf-8")
    assert text.startswith(FAILURE_REPORT_MARKER)
    assert CONTROLLED_FAILURE_MESSAGE in text
    assert explanation in text
