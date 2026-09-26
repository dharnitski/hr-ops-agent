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

## Running the MCP server

```bash
uv run python -m mcp_server.server   # Streamable HTTP at http://localhost:8000/mcp
```

The agent connects to it via `HCM_MCP_URL` (set in `hr_agent/.env`); start the server
before `adk web` / `adk run` or the agent's MCP tools will fail. Integration tests that need
it start their own copy on port 8000, so stop yours first.

## Running the standalone MCP client

`scratch/mcp_client.py` talks to the server with the plain `mcp` client (no ADK, no model).
With the server running, in a second terminal:

```bash
uv run python scratch/mcp_client.py  # lists tools, exercises errors and idempotent writes
```

It reads `HCM_MCP_URL` (default `http://localhost:8000/mcp`) and exits non-zero if a
replay or conflict check fails.

## Running the agent

With the MCP server running (see above), in a second terminal:

```bash
uv run adk web --port 8080 .         # dev UI at http://localhost:8080; pick hr_agent
uv run adk run hr_agent              # or chat in the terminal
```

`adk web` defaults to port 8000, which the MCP server uses, hence `--port 8080`.

Prompts to try (mock data: employees E1001–E1005, Bob Smith is E1002):

- `How much PTO does E1002 have?` — local tool, balance lookup.
- `PTO for Bob Smith` — resolves the name with `find_employee`, then looks up the balance.
- `Who is employee E1002?` — `get_employee` over MCP.
- `Submit PTO for E1002 from 2026-10-12 to 2026-10-14.` — `submit_pto_request` over MCP;
  expect a pending request with server-computed hours.
- `Submit PTO for E1002 from 2026-10-14 to 2026-10-12.` — expect a plain error about dates.
- `What's my PTO?` — should ask for an ID rather than guess.
- `Show me payroll run PR-2026-09.` — should decline; payroll is not exposed.

## Development

```bash
uv run ruff check .                  # lint
uv run pytest                        # unit tests (tests/unit)
uv run pytest tests/integration     # integration tests (need hr_agent/.env)
uv run adk eval hr_agent evals/      # eval gate
uv run python -m scratch.react_from_scratch  # no-framework ReAct loop (needs hr_agent/.env)
```
