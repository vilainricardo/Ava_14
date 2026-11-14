import pytest
from app.exceptions.error_messages import LOG_EMPTY_ERROR_MESSAGE
from app.agents.failure_analyzer import analyze_failure


def test_analyze_failure_returns_log() -> None:
    log = "AssertionError: assert 1 == 2"

    result = analyze_failure(log)

    assert result == log


def test_analyze_failure_rejects_empty_log() -> None:
    with pytest.raises(ValueError, match=LOG_EMPTY_ERROR_MESSAGE):
        analyze_failure("")

def test_analyze_failure_rejects_whitespace_log() -> None:
    with pytest.raises(ValueError, match=LOG_EMPTY_ERROR_MESSAGE):
        analyze_failure("   ")