# ADK convention: the agent package exposes its `agent` submodule so `root_agent` is found
# when the package is loaded by name (`adk run hr_agent`, `adk web`). The loader also tries
# `hr_agent.agent` directly, so this is belt-and-braces; the explicit alias marks it as an
# intentional re-export for ruff (F401).
# Loader lookup order: google/adk/cli/utils/agent_loader.py (AgentLoader docstring).
from . import agent as agent
