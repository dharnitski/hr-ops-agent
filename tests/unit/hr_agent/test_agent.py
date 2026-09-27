from hr_agent.agent import root_agent
from hr_agent.agents.pto import pto_agent
from hr_agent.tools import find_employee, get_pto_balance, list_holidays
from hr_agent.toolsets import hcm_toolset


def test_root_agent_is_a_toolless_router() -> None:
    assert root_agent.name == "hr_ops_agent"
    assert root_agent.model
    assert not root_agent.tools
    assert root_agent.sub_agents == [pto_agent]


def test_router_declines_unmatched_requests() -> None:
    instruction = root_agent.instruction
    assert isinstance(instruction, str)
    assert "matches no specialist" in instruction


def test_pto_agent_tools() -> None:
    assert pto_agent.name == "pto_agent"
    assert pto_agent.description
    assert set(pto_agent.tools) == {find_employee, get_pto_balance, list_holidays, hcm_toolset}


def test_pto_instruction_forbids_guessing_ids() -> None:
    instruction = pto_agent.instruction
    assert isinstance(instruction, str)
    assert "Never guess" in instruction
    assert "error" in instruction


def test_hcm_toolset_exposes_only_pto_tools() -> None:
    assert hcm_toolset.tool_filter == ["get_employee", "submit_pto_request"]
