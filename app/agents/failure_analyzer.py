

from app.exceptions.error_messages import LOG_EMPTY_ERROR_MESSAGE


def analyze_failure(log: str) -> str:
    """
    Recebe o log de uma execução da pipeline
    e prepara seu conteúdo para análise.
    """
    if not log.strip():
        raise ValueError(LOG_EMPTY_ERROR_MESSAGE)

    return log