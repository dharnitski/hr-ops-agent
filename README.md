# hr-ops-agent

An HR operations agent built on [Google ADK](https://google.github.io/adk-docs/), with HCM
(Human Capital Management) tools exposed as an MCP server, evaluated with `adk eval`, and
deployable to Agent Engine, Cloud Run, or GKE.

## Repo layout

```
hr-ops-agent/
├── hr_agent/            # ADK agent package (Module 1, grows into multi-agent in M3)
├── mcp_server/          # HCM tools as an MCP server (Module 2)
├── evals/               # eval sets + configs for adk eval (Module 5)
├── tests/               # unit/ (hermetic, in CI) and integration/ (real boundaries, on demand)
├── deploy/              # agent_engine/, cloud_run/, gke/ (Module 7)
├── docs/                # one-pagers, architecture doc, strategy memo
├── scratch/             # react_from_scratch.py and experiments
├── .github/workflows/   # CI: lint, tests, eval gate
├── AGENTS.md            # project conventions for AI coding agents
├── pyproject.toml
├── .gitignore           # must include .env
└── README.md
```

## Getting started

Dependencies are managed with [uv](https://docs.astral.sh/uv/).

```bash
uv sync                              # creates .venv, installs deps + dev extras
cp .env.example hr_agent/.env               # fill in secrets, never commit .env
```

## Development

```bash
uv run ruff check .                  # lint
uv run pytest                        # unit tests (tests/unit)
uv run pytest tests/integration     # integration tests (need hr_agent/.env)
uv run adk eval hr_agent evals/      # eval gate
uv run python -m scratch.react_from_scratch  # no-framework ReAct loop (needs hr_agent/.env)
```
