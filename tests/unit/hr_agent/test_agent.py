from hr_agent.agent import root_agent
from hr_agent.tools import get_pto_balance, list_holidays


def test_root_agent_name_and_model():
    assert root_agent.name == "hr_ops_agent"
    assert root_agent.model


def test_root_agent_tools():
    assert set(root_agent.tools) == {get_pto_balance, list_holidays}


def test_instruction_forbids_guessing_ids():
    assert "Never guess" in root_agent.instruction
    assert "error" in root_agent.instruction
