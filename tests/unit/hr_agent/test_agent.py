from hr_agent.agent import hcm_toolset, root_agent
from hr_agent.tools import find_employee, get_pto_balance, list_holidays


def test_root_agent_name_and_model() -> None:
    assert root_agent.name == "hr_ops_agent"
    assert root_agent.model


def test_root_agent_tools() -> None:
    assert set(root_agent.tools) == {find_employee, get_pto_balance, list_holidays, hcm_toolset}


def test_instruction_forbids_guessing_ids() -> None:
    instruction = root_agent.instruction
    assert isinstance(instruction, str)
    assert "Never guess" in instruction
    assert "error" in instruction


def test_hcm_toolset_exposes_only_pto_tools() -> None:
    assert hcm_toolset.tool_filter == ["get_employee", "submit_pto_request"]
