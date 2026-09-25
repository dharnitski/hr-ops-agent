# ADK requires the agent package's __init__.py to contain `from . import agent`, so
# `root_agent` is found when loaded by name (`adk run hr_agent`, `adk web`, `adk deploy`).
# Docs: https://adk.dev/deploy/cloud-run/ (agent project requirements) and
# https://adk.dev/tutorials/multi-tool-agent/ (project setup).
# The `as agent` alias marks an intentional re-export for ruff (F401). The installed loader
# also tries `hr_agent.agent` directly: google/adk/cli/utils/agent_loader.py.
from . import agent as agent
