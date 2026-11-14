import os

import pytest

CONTROLLED_FAILURE_MESSAGE: str = (
    "Falha controlada para demonstrar o diagnóstico da pipeline."
)


@pytest.mark.skipif(
    os.environ.get("CI_CONTROLLED_FAILURE") != "true",
    reason="A falha controlada roda só no job dedicado da pipeline.",
)
def test_controlled_pipeline_failure() -> None:
    """Erro proposital para o check deste job aparecer como falha.

    O job tests não define CI_CONTROLLED_FAILURE, então ignora este
    teste. A aplicação e o aviso da Steam seguem no outro job.
    """
    raise AssertionError(CONTROLLED_FAILURE_MESSAGE)
