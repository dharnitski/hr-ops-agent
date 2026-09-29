"""Unit tests for hr_agent/toolsets.py's header_provider: caller-identity header (M6.1) and
Cloud Run ID-token auth. No network/ADC -- google.oauth2.id_token.fetch_id_token is mocked.
"""

from types import SimpleNamespace
from typing import Any, cast

import pytest
from google.adk.agents.readonly_context import ReadonlyContext

from hr_agent import toolsets


@pytest.fixture(autouse=True)
def _clear_id_token_cache() -> None:
    toolsets._id_token_cache.clear()


def _ctx(state: dict[str, Any] | None = None) -> ReadonlyContext:
    # A real ReadonlyContext needs a live InvocationContext; _caller_headers only ever reads
    # `.state`, so a minimal stand-in keeps this test hermetic (no ADK session machinery).
    return cast(ReadonlyContext, SimpleNamespace(state=state or {}))


def test_caller_headers_empty_when_no_caller_id_and_no_audience(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(toolsets, "HCM_MCP_AUDIENCE", "")
    assert toolsets._caller_headers(_ctx()) == {}


def test_caller_headers_includes_caller_id(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(toolsets, "HCM_MCP_AUDIENCE", "")
    headers = toolsets._caller_headers(_ctx({toolsets.CALLER_EMPLOYEE_ID_STATE_KEY: "E1002"}))
    assert headers == {toolsets.CALLER_EMPLOYEE_ID_HEADER: "E1002"}


def test_caller_headers_attaches_id_token_when_audience_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(toolsets, "HCM_MCP_AUDIENCE", "https://mcp-server.example.run.app")
    monkeypatch.setattr(
        toolsets.google.oauth2.id_token, "fetch_id_token", lambda *_args: "fake-token"
    )
    headers = toolsets._caller_headers(_ctx())
    assert headers == {"Authorization": "Bearer fake-token"}


def test_cached_id_token_reuses_token_within_ttl(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []
    monkeypatch.setattr(
        toolsets.google.oauth2.id_token,
        "fetch_id_token",
        lambda _request, audience: calls.append(audience) or "token-1",
    )
    first = toolsets._cached_id_token("aud")
    second = toolsets._cached_id_token("aud")
    assert first == second == "token-1"
    assert len(calls) == 1


def test_cached_id_token_refreshes_after_ttl(monkeypatch: pytest.MonkeyPatch) -> None:
    tokens = iter(["token-1", "token-2"])
    monkeypatch.setattr(
        toolsets.google.oauth2.id_token,
        "fetch_id_token",
        lambda *_args: next(tokens),
    )
    now = [0.0]
    monkeypatch.setattr(toolsets.time, "monotonic", lambda: now[0])

    assert toolsets._cached_id_token("aud") == "token-1"
    now[0] = toolsets._ID_TOKEN_REFRESH_SECONDS + 1
    assert toolsets._cached_id_token("aud") == "token-2"


def test_cached_id_token_rejects_non_str_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(toolsets.google.oauth2.id_token, "fetch_id_token", lambda *_args: None)
    with pytest.raises(TypeError, match="expected str"):
        toolsets._cached_id_token("aud")
