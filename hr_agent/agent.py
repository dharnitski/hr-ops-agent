from google.adk.agents import Agent
from google.adk.apps import App
from google.adk.plugins.context_filter_plugin import ContextFilterPlugin

from hr_agent.agents.payroll import payroll_agent
from hr_agent.agents.policy import policy_agent
from hr_agent.agents.pto import pto_agent
from hr_agent.config import MODEL_ID

# Module 4.3: without this, every turn resends the full conversation -- every past tool call
# and result -- to the model forever. Keeps the last 6 user-initiated invocations (roughly a
# short back-and-forth); older ones are dropped from what's sent to the model, never from
# session.events, so session state (M4.1) and memory writes (M4.2, which reads session.events
# directly) are unaffected. Deterministic and free, unlike EventsCompactionConfig's
# LLM-summarization path, which also costs a model call and is still @experimental in adk 2.9.2
# (see docs/PROGRESS.md M4.3).
NUM_INVOCATIONS_TO_KEEP = 6

INSTRUCTION = """\
You are the router of an HR operations assistant. You have no tools and answer no HR
questions yourself. Transfer each request to the specialist whose description matches it.

- A message can ask more than one thing. If every part matches the same specialist, still
  transfer once -- that specialist handles multi-part questions itself. Only decline or ask
  for clarification if some part matches no specialist, or you genuinely can't tell which one
  applies; having more than one part is not by itself a reason to decline.
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

# adk web/adk run/adk deploy look for `app` before falling back to `root_agent`
# (google/adk/cli/utils/agent_loader.py), so this is what actually carries the plugin to
# production; tests that build their own Runner around `root_agent` directly don't get it.
app = App(
    name="hr_agent",
    root_agent=root_agent,
    plugins=[ContextFilterPlugin(num_invocations_to_keep=NUM_INVOCATIONS_TO_KEEP)],
)
