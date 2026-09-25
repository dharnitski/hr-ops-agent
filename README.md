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
├── tests/               # unit tests for tools and guardrails
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

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env  # fill in secrets, never commit .env
```

## Development

```bash
ruff check .        # lint
pytest               # unit tests
adk eval hr_agent evals/  # eval gate
```
