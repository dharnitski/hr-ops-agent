from hr_agent.agent import root_agent
from hr_agent.agents.payroll import payroll_agent
from hr_agent.agents.policy import policy_agent
from hr_agent.agents.pto import pto_agent
from hr_agent.handbook import search_handbook
from hr_agent.tools import find_employee, get_pto_balance, list_holidays
from hr_agent.toolsets import hcm_toolset, payroll_toolset


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
    assert set(pto_agent.tools) == {find_employee, get_pto_balance, list_holidays, hcm_toolset}


def test_pto_instruction_forbids_guessing_ids() -> None:
    instruction = pto_agent.instruction
    assert isinstance(instruction, str)
    assert "Never guess" in instruction
    assert "error" in instruction


def test_hcm_toolset_exposes_only_pto_tools() -> None:
    assert hcm_toolset.tool_filter == ["get_employee", "submit_pto_request"]


def test_payroll_agent_is_read_only_and_isolated() -> None:
    assert payroll_agent.name == "payroll_agent"
    assert payroll_agent.description
    assert payroll_agent.tools == [payroll_toolset]
    assert payroll_toolset.tool_filter == ["get_payroll_run"]
    assert payroll_toolset not in pto_agent.tools
    assert hcm_toolset not in payroll_agent.tools


def test_policy_agent_is_grounded_and_isolated() -> None:
    assert policy_agent.name == "policy_agent"
    assert policy_agent.description
    assert policy_agent.tools == [search_handbook]
    instruction = policy_agent.instruction
    assert isinstance(instruction, str)
    assert "never from memory" in instruction
    assert "Cite" in instruction
