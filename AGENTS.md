# hr-ops-agent — project conventions

## What this is
An HR operations agent built on Google ADK. HCM tools are exposed via an MCP server
(`mcp_server/`) and consumed by the agent (`hr_agent/`). Evaluated with `adk eval`
(`evals/`) and deployed to Agent Engine, Cloud Run, or GKE (`deploy/`).

## Layout
- `hr_agent/` — ADK agent package. Starts single-agent (Module 1), grows into a
  multi-agent system (Module 3). Keep agent definitions, prompts, and orchestration here.
- `mcp_server/` — HCM tools implemented as an MCP server (Module 2). Tool schemas and
  handlers live here; the agent talks to this over MCP, not by importing it directly.
- `evals/` — eval sets and configs for `adk eval` (Module 5). Each eval set should be
  runnable in isolation and wired into the CI eval gate.
- `tests/` — unit tests for tools and guardrails. Mirrors `hr_agent/` and `mcp_server/`
  structure.
- `deploy/` — `agent_engine/`, `cloud_run/`, `gke/` deployment configs (Module 7).
- `docs/` — one-pagers, architecture doc, strategy memo.
- `scratch/` — throwaway experiments (e.g. `react_from_scratch.py`). Not imported by
  production code; not covered by CI.

## Conventions
- Python >= 3.14. Lint with `ruff`, format with `ruff format`.
- Secrets go in `.env` (never committed — see `.gitignore`). Use `.env.example` for
  documenting required variables.
- New HCM tools: add the handler in `mcp_server/`, add a matching unit test in `tests/`,
  and add/extend an eval case in `evals/` if it changes agent behavior.
- CI (`.github/workflows/`) runs lint, unit tests, and the eval gate on every PR.
