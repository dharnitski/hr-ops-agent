"""Loop mechanics with a scripted fake model: no network or credentials."""

from types import SimpleNamespace

import pytest
from google.genai import types

from scratch import react_from_scratch as rfs


def _call(name: str, **args) -> types.Part:
    return types.Part(function_call=types.FunctionCall(name=name, args=args))


def _response(*parts: types.Part, prompt=10, output=5):
    content = types.Content(role="model", parts=list(parts))
    return SimpleNamespace(
        candidates=[SimpleNamespace(content=content)],
        text="".join(p.text or "" for p in parts),
        usage_metadata=SimpleNamespace(prompt_token_count=prompt, candidates_token_count=output),
    )


@pytest.fixture
def script(monkeypatch):
    """Install scripted model responses; returns the list of histories the model was shown."""

    def _install(*responses):
        queue = list(responses)
        seen = []

        def fake_generate(history):
            seen.append(list(history))
            return queue.pop(0) if queue else queue_exhausted()

        def queue_exhausted():
            raise AssertionError("model called more times than scripted")

        monkeypatch.setattr(rfs, "generate", fake_generate)
        return seen

    return _install


def test_execute_tool_success():
    result = rfs.execute_tool("get_pto_balance", {"employee_id": "E1002"})
    assert result["status"] == "success"


def test_execute_tool_unknown_name_is_observation():
    result = rfs.execute_tool("delete_everything", {})
    assert result["status"] == "error"
    assert "get_pto_balance" in result["error"]


def test_execute_tool_bad_args_is_observation():
    result = rfs.execute_tool("get_pto_balance", {"wrong": 1})
    assert result["status"] == "error"
    assert "Bad arguments" in result["error"]


def test_execute_tool_exception_is_observation(monkeypatch):
    def boom(employee_id: str) -> dict:
        raise RuntimeError("db down")

    monkeypatch.setitem(rfs.TOOLS, "get_pto_balance", boom)
    result = rfs.execute_tool("get_pto_balance", {"employee_id": "E1002"})
    assert result == {"status": "error", "error": "get_pto_balance failed: RuntimeError: db down"}


def test_direct_answer_makes_one_model_call(script):
    script(_response(types.Part(text="Hello")))
    stats = rfs.Stats()
    assert rfs.run("hi", stats) == "Hello"
    assert (stats.model_calls, stats.tool_calls) == (1, 0)
    assert (stats.prompt_tokens, stats.output_tokens) == (10, 5)
    assert len(stats.latencies) == 1


def test_tool_result_is_fed_back_to_model(script):
    seen = script(
        _response(_call("get_pto_balance", employee_id="E1003")),
        _response(types.Part(text="16 sick hours")),
    )
    stats = rfs.Stats()
    assert rfs.run("sick time for E1003?", stats) == "16 sick hours"
    assert (stats.model_calls, stats.tool_calls) == (2, 1)
    # Second call sees: user, model function_call turn, user function_response turn.
    history = seen[1]
    assert [c.role for c in history] == ["user", "model", "user"]
    response = history[2].parts[0].function_response
    assert response.name == "get_pto_balance"
    assert response.response["result"]["sick_hours"] == 16.0


def test_parallel_calls_answered_in_single_turn(script):
    seen = script(
        _response(_call("list_holidays", year=2026), _call("get_pto_balance", employee_id="E1003")),
        _response(types.Part(text="done")),
    )
    stats = rfs.Stats()
    rfs.run("two things", stats)
    assert stats.tool_calls == 2
    assert [p.function_response.name for p in seen[1][2].parts] == [
        "list_holidays",
        "get_pto_balance",
    ]


def test_model_turn_appended_unmodified(script):
    first = _response(_call("list_holidays", year=2026))
    seen = script(first, _response(types.Part(text="ok")))
    rfs.run("holidays?", rfs.Stats())
    assert seen[1][1] is first.candidates[0].content


def test_unknown_tool_does_not_crash_loop(script):
    seen = script(_response(_call("nope")), _response(types.Part(text="sorry")))
    assert rfs.run("x", rfs.Stats()) == "sorry"
    assert seen[1][2].parts[0].function_response.response["result"]["status"] == "error"


def test_max_steps_stops_runaway_loop(script, monkeypatch):
    monkeypatch.setattr(rfs, "MAX_STEPS", 3)
    script(*[_response(_call("get_pto_balance", employee_id="E1002")) for _ in range(3)])
    stats = rfs.Stats()
    answer = rfs.run("loop forever", stats)
    assert "3 steps" in answer
    assert stats.model_calls == 3


def test_stats_summary_lists_counters():
    stats = rfs.Stats()
    stats.model_calls, stats.tool_calls = 2, 1
    stats.latencies = [1.0, 2.5]
    summary = stats.summary()
    assert "model_calls=2" in summary
    assert "tool_calls=1" in summary
    assert "1.0s, 2.5s" in summary
