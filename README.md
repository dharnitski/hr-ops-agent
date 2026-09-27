# hr-ops-agent

An HR operations agent built on [Google ADK](https://google.github.io/adk-docs/), with HCM
(Human Capital Management) tools exposed as an MCP server, evaluated with `adk eval`, and
deployable to Agent Engine, Cloud Run, or GKE.

## Repo layout

```
hr-ops-agent/
├── hr_agent/            # ADK agent package: router + PTO/payroll/policy specialists (M1-M3)
├── mcp_server/          # HCM tools as an MCP server (Module 2)
├── evals/               # eval sets + configs for adk eval (Module 5)
├── tests/               # unit/ (hermetic, in CI) and integration/ (real boundaries, on demand)
├── deploy/              # agent_engine/, cloud_run/, gke/ (Module 7)
├── docs/                # one-pagers, architecture doc, strategy memo
├── scratch/             # throwaway experiments: ReAct loop, Workflow probes, LangGraph router
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

## Running the agent

With the MCP server running (see above), in a second terminal:

```bash
uv run adk web --port 8080 .         # dev UI at http://localhost:8080; pick hr_agent
uv run adk run hr_agent              # or chat in the terminal
```

`adk web` defaults to port 8000, which the MCP server uses, hence `--port 8080`.

`hr_agent.agent.root_agent` is a router with no tools of its own; it transfers each request
to the `pto_agent`, `payroll_agent`, or `policy_agent` specialist (see
[docs/03-architecture.md](docs/03-architecture.md)) and declines anything that matches none.

Prompts to try (mock data: employees E1001–E1005, Bob Smith is E1002; payroll run PR-2026-09):

- `How much PTO does E1002 have?` — `pto_agent`, local tool balance lookup.
- `PTO for Bob Smith` — resolves the name with `find_employee`, then looks up the balance.
- `Who is employee E1002?` — `get_employee` over MCP.
- `Submit PTO for E1002 from 2026-10-12 to 2026-10-14.` — `submit_pto_request` over MCP;
  expect a pending request with server-computed hours.
- `Submit PTO for E1002 from 2026-10-14 to 2026-10-12.` — expect a plain error about dates.
- `What's my PTO?` — should ask for an ID rather than guess.
- `Show me payroll run PR-2026-09.` — `payroll_agent`, `get_payroll_run` over MCP; expect
  read-only aggregates (period, pay date, status, headcount, total gross).
- `What's the PTO carryover policy?` — `policy_agent`, `search_handbook`; answers from the
  handbook and cites the section.
- `What's Bob Smith's salary?` — should decline; no specialist handles individual pay.

## Development

```bash
uv run ruff check .                  # lint
uv run pytest                        # unit tests (tests/unit)
uv run pytest tests/integration     # integration tests (need hr_agent/.env)

# eval gate (needs the MCP server running, see above): one evalset file per invocation so
# each risk tier's test_config.json is picked up (adk eval only auto-resolves it for a
# single-file run)
uv run adk eval hr_agent evals/happy_path/hr_ops_happy_path.evalset.json
uv run adk eval hr_agent evals/ambiguous/hr_ops_ambiguous.evalset.json
uv run adk eval hr_agent evals/adversarial/hr_ops_adversarial.evalset.json
```

## Scratch

Throwaway experiments in `scratch/`: not imported by production code, not covered by CI.

`scratch/mcp_client.py` talks to the MCP server with the plain `mcp` client (no ADK, no
model). With the server running (see above), in a second terminal:

```bash
uv run python scratch/mcp_client.py  # lists tools, exercises errors and idempotent writes
```

It reads `HCM_MCP_URL` (default `http://localhost:8000/mcp`) and exits non-zero if a
replay or conflict check fails.

`scratch/workflow_probe.py` is the smallest ADK 2.x `Workflow`: two function nodes and one
conditional route. No model, credentials, or MCP server needed.

```bash
uv run python scratch/workflow_probe.py  # prints which node handled each of two inputs
```

`scratch/workflow_router.py` is a deterministic ADK `Workflow` router over the existing
specialists (keyword rules, no router LLM call) — compare with the LLM router in
`hr_agent/agent.py`. PTO/payroll prompts need the MCP server running.

```bash
uv run python scratch/workflow_router.py
```

`scratch/langgraph_router.py` is a LangGraph rebuild of the same router flow (policy path
only), reusing the ADK router's keyword rules, policy instruction, and handbook tool
unchanged — see the ADK vs. LangGraph comparison doc in `docs/`.

```bash
uv run python -m scratch.langgraph_router
```

`scratch/react_from_scratch.py` is a no-framework ReAct loop (needs `hr_agent/.env`).

```bash
uv run python -m scratch.react_from_scratch
```
