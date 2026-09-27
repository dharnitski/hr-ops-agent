from google.adk.agents import Agent

from hr_agent.agents.payroll import payroll_agent
from hr_agent.agents.policy import policy_agent
from hr_agent.agents.pto import pto_agent
from hr_agent.config import MODEL_ID

INSTRUCTION = """\
You are the router of an HR operations assistant. You have no tools and answer no HR
questions yourself. Transfer each request to the specialist whose description matches it.

- If a request matches no specialist (e.g. an individual's salary, anything else), say plainly that
  you can't help with it. Do not improvise an answer or pick the nearest specialist.
- If the request is unclear, ask one clarifying question instead of guessing a specialist.
"""

root_agent = Agent(
    name="hr_ops_agent",
    model=MODEL_ID,
    description="Routes HR requests to specialist agents.",
    instruction=INSTRUCTION,
    sub_agents=[pto_agent, payroll_agent, policy_agent],
)
