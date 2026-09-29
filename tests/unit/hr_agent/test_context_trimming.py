"""M4.3: ContextFilterPlugin trims old invocations from what's sent to the model, without
touching session.events (session state and memory keep seeing the full history). Tests the
plugin actually wired into hr_agent.agent.app, at the num_invocations_to_keep we configured --
not ContextFilterPlugin's internals, which are ADK's own and already covered upstream."""

from google.adk.agents import Context
from google.adk.models.llm_request import LlmRequest
from google.genai import types

from hr_agent.agent import NUM_INVOCATIONS_TO_KEEP, app


def _user_turn(text: str) -> types.Content:
    return types.Content(role="user", parts=[types.Part(text=text)])


def _model_turn(text: str) -> types.Content:
    return types.Content(role="model", parts=[types.Part(text=text)])


def test_app_configures_the_context_filter_plugin_first() -> None:
    # Index 0 matters: the other tests here grab app.plugins[0] specifically.
    assert app.plugins[0].__class__.__name__ == "ContextFilterPlugin"
    assert {p.__class__.__name__ for p in app.plugins} == {
        "ContextFilterPlugin",
        "AuditLogPlugin",
    }


async def test_old_invocations_are_dropped_from_the_model_request(
    callback_context: Context,
) -> None:
    plugin = app.plugins[0]
    invocation_count = NUM_INVOCATIONS_TO_KEEP + 2
    contents = []
    for i in range(invocation_count):
        contents.append(_user_turn(f"question {i}"))
        contents.append(_model_turn(f"answer {i}"))
    llm_request = LlmRequest(contents=contents)

    await plugin.before_model_callback(callback_context=callback_context, llm_request=llm_request)

    remaining_user_turns = [
        part.text
        for content in llm_request.contents
        if content.role == "user" and content.parts
        for part in content.parts
        if part.text
    ]
    assert remaining_user_turns == [
        f"question {i}" for i in range(invocation_count - NUM_INVOCATIONS_TO_KEEP, invocation_count)
    ]


async def test_fewer_invocations_than_the_limit_are_kept_in_full(
    callback_context: Context,
) -> None:
    plugin = app.plugins[0]
    contents = [_user_turn("only question"), _model_turn("only answer")]
    llm_request = LlmRequest(contents=list(contents))

    await plugin.before_model_callback(callback_context=callback_context, llm_request=llm_request)

    assert llm_request.contents == contents
