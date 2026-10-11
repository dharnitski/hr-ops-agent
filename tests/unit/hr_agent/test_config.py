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


@pytest.mark.parametrize(
    ("value", "expected"),
    [(None, True), ("true", True), ("", True), ("0", True), ("false", False), ("FALSE", False)],
)
def test_write_confirmation_off_only_for_explicit_false(
    monkeypatch: pytest.MonkeyPatch, value: str | None, expected: bool
) -> None:
    if value is None:
        monkeypatch.delenv("HCM_REQUIRE_CONFIRMATION", raising=False)
    else:
        monkeypatch.setenv("HCM_REQUIRE_CONFIRMATION", value)
    importlib.reload(config)
    assert config.REQUIRE_WRITE_CONFIRMATION is expected
