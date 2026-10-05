import importlib

import pytest

from hr_agent import config

CAPTURE = "ADK_CAPTURE_MESSAGE_CONTENT_IN_SPANS"


def test_span_content_capture_defaults_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(CAPTURE, raising=False)
    importlib.reload(config)
    assert config.os.environ[CAPTURE] == "false"


def test_span_content_capture_explicit_override_wins(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(CAPTURE, "true")
    importlib.reload(config)
    assert config.os.environ[CAPTURE] == "true"
