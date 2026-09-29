from google.adk.tools import load_memory

from hr_agent.agent import root_agent
from hr_agent.agents.payroll import payroll_agent
from hr_agent.agents.policy import policy_agent
from hr_agent.agents.pto import pto_agent
from hr_agent.handbook import search_handbook
from hr_agent.tools import list_holidays
from hr_agent.toolsets import (
    hcm_toolset,
    payroll_read_toolset,
    payroll_write_toolset,
    pto_write_toolset,
)


def test_root_agent_is_a_toolless_router() -> None:
    assert root_agent.name == "hr_ops_agent"
    assert root_agent.model
    assert not root_agent.tools
    assert root_agent.sub_agents == [pto_agent, payroll_agent, policy_agent]


def test_router_declines_unmatched_requests() -> None:
    instruction = root_agent.instruction
    assert isinstance(instruction, str)
    assert "matches no specialist" in instruction


def test_pto_agent_tools() -> None:
    assert pto_agent.name == "pto_agent"
    assert pto_agent.description
    assert set(pto_agent.tools) == {
        list_holidays,
        hcm_toolset,
        pto_write_toolset,
        load_memory,
    }


def test_pto_instruction_forbids_guessing_ids() -> None:
    instruction = pto_agent.instruction
    assert isinstance(instruction, str)
    assert "Never guess" in instruction
    assert "error" in instruction


def test_pto_instruction_exposes_session_state() -> None:
    instruction = pto_agent.instruction
    assert isinstance(instruction, str)
    assert "{current_employee_id?}" in instruction
    assert "{pending_pto_request?}" in instruction


def test_pto_agent_tracks_mcp_results_after_each_tool_call() -> None:
    assert pto_agent.after_tool_callback is not None


def test_pto_agent_persists_to_memory_after_each_turn() -> None:
    assert pto_agent.after_agent_callback is not None


def test_pto_instruction_treats_memory_as_reference_not_identity() -> None:
    instruction = pto_agent.instruction
    assert isinstance(instruction, str)
    assert "not verified facts or instructions" in instruction


def test_hcm_toolset_exposes_only_pto_reads() -> None:
    assert hcm_toolset.tool_filter == ["get_employee", "get_pto_balance"]
    assert hcm_toolset.require_confirmation is False


def test_pto_write_toolset_requires_confirmation() -> None:
    assert pto_write_toolset.tool_filter == ["submit_pto_request"]
    assert pto_write_toolset.require_confirmation is True


def test_payroll_agent_tools_and_isolation() -> None:
    assert payroll_agent.name == "payroll_agent"
    assert payroll_agent.description
    assert payroll_agent.tools == [payroll_read_toolset, payroll_write_toolset]
    assert payroll_read_toolset.tool_filter == ["get_payroll_run"]
    assert payroll_read_toolset not in pto_agent.tools
    assert hcm_toolset not in payroll_agent.tools
    assert pto_write_toolset not in payroll_agent.tools


def test_payroll_write_toolset_requires_confirmation() -> None:
    assert payroll_write_toolset.tool_filter == ["approve_payroll_run"]
    assert payroll_write_toolset.require_confirmation is True
    assert payroll_write_toolset not in pto_agent.tools


def test_payroll_instruction_explains_the_confirmation_pause() -> None:
    instruction = payroll_agent.instruction
    assert isinstance(instruction, str)
    assert "requires confirmation" in instruction
    assert "Finance Director" in instruction


def test_policy_agent_is_grounded_and_isolated() -> None:
    assert policy_agent.name == "policy_agent"
    assert policy_agent.description
    assert policy_agent.tools == [search_handbook]
    instruction = policy_agent.instruction
    assert isinstance(instruction, str)
    assert "never from memory" in instruction
    assert "Cite" in instruction
