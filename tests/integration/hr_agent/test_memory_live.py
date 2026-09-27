"""Live model calls: PTO conversations persist across sessions via long-term memory (M4.2).

Unlike session state (test_session_state_live.py), this survives a fresh session for the same
user. A recalled employee ID may be used for a read (get_pto_balance validates it on its own)
but never for submit_pto_request without a fresh find_employee/get_employee this session --
see the pto_agent instruction and docs/PROGRESS.md M4.2.
"""

from collections.abc import Awaitable, Callable

import pytest

from tests.integration.hr_agent.conftest import Turn

NewSession = Callable[[], Awaitable[Callable[[str], Awaitable[Turn]]]]

pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("hcm_server")]


async def test_second_session_recalls_employee_for_a_balance_lookup(
    sessions: NewSession,
) -> None:
    first_session = await sessions()
    first = await first_session("How much PTO does E1002 have?")
    assert first.tool_calls == [("get_pto_balance", {"employee_id": "E1002"})]

    second_session = await sessions()
    second = await second_session(
        "What's the PTO balance for the employee I asked about in an earlier conversation?"
    )

    # The exact sequence varies run to run (e.g. the model sometimes double-checks a recalled ID
    # with get_employee before using it) -- what matters is that memory was consulted and the
    # right employee's balance came back, without asking the user to repeat the ID.
    assert "load_memory" in [name for name, _ in second.tool_calls]
    assert ("get_pto_balance", {"employee_id": "E1002"}) in second.tool_calls
    assert not [name for name, _ in second.tool_calls if name == "find_employee"]
