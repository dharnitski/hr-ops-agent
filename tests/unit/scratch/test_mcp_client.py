"""Result-shape handling of the scratch MCP client with a fake client: no server."""

from types import SimpleNamespace
from typing import Any, cast

import pytest
from mcp import Client

from scratch import mcp_client


class _FakeClient:
    def __init__(self, result: object = None, exc: Exception | None = None) -> None:
        self._result, self._exc = result, exc

    async def call_tool(self, _name: str, _args: dict[str, Any]) -> object:
        if self._exc:
            raise self._exc
        return self._result


async def _call(fake: _FakeClient) -> dict[str, Any]:
    return await mcp_client.call(cast(Client, fake), "t", {})


def _result(
    *, is_error: bool = False, structured: dict[str, Any] | None = None, texts: tuple[str, ...] = ()
) -> SimpleNamespace:
    return SimpleNamespace(
        is_error=is_error,
        structured_content=structured,
        content=[SimpleNamespace(text=t) for t in texts],
    )


async def test_unwraps_result_envelope() -> None:
    client = _FakeClient(_result(structured={"result": {"status": "success"}}))
    assert await _call(client) == {"status": "success"}  # type: ignore[arg-type]


async def test_returns_unwrapped_structured_content_as_is() -> None:
    client = _FakeClient(_result(structured={"status": "success"}))
    assert await _call(client) == {"status": "success"}  # type: ignore[arg-type]


async def test_tool_level_error_is_tagged_with_text() -> None:
    client = _FakeClient(_result(is_error=True, texts=("bad", "input")))
    assert await _call(client) == {"is_error": True, "text": "bad input"}  # type: ignore[arg-type]


async def test_protocol_error_is_tagged() -> None:
    client = _FakeClient(exc=ValueError("boom"))
    assert await _call(client) == {"transport_error": "ValueError: boom"}  # type: ignore[arg-type]


async def test_missing_structured_content_yields_empty_dict() -> None:
    assert await _call(_FakeClient(_result())) == {}  # type: ignore[arg-type]


def test_check_passes_and_exits_on_failure(capsys: pytest.CaptureFixture[str]) -> None:
    mcp_client.check(True, "fine")
    assert "[ok] fine" in capsys.readouterr().out
    with pytest.raises(SystemExit):
        mcp_client.check(False, "broken")
    assert "[FAIL] broken" in capsys.readouterr().out
