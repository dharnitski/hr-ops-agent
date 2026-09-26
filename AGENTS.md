# hr-ops-agent — project conventions

## What this is
An HR operations agent built on Google ADK. HCM tools are exposed via an MCP server
(`mcp_server/`) and consumed by the agent (`hr_agent/`). Evaluated with `adk eval`
(`evals/`) and deployed to Agent Engine, Cloud Run, or GKE (`deploy/`).

## Layout
- `hr_agent/` — ADK agent package: definitions, prompts, orchestration. Single-agent
  (Module 1), growing into multi-agent (Module 3).
- `mcp_server/` — HCM tool schemas/handlers as an MCP server (Module 2). The agent talks
  to it over MCP, never by direct import.
- `evals/` — `adk eval` sets/configs (Module 5). Each set runs standalone and is wired
  into the CI eval gate.
- `tests/unit/` — fast, hermetic tests for tools and guardrails, mirroring
  `hr_agent/`/`mcp_server/` (e.g. `tests/unit/hr_agent/test_tools.py`). No network, model
  calls, credentials, or subprocesses; mock or fake anything external.
- `tests/integration/` — tests that cross a real boundary: a running MCP server, the ADK
  agent wiring, or live model/GCP calls. May need `.env`/credentials; slower and
  non-deterministic. Mark model-calling tests `@pytest.mark.integration`.
- `deploy/` — `agent_engine/`, `cloud_run/`, `gke/` configs (Module 7).
- `docs/` — one-pagers, architecture doc, strategy memo.
- `scratch/` — throwaway experiments (e.g. `react_from_scratch.py`); not imported by
  production code, not covered by CI.

## Conventions
- Python >= 3.14 via `uv` (`uv sync`, `uv add`, `uv run ...`) — no bare `pip`/`venv`.
- Lint with `ruff`, format with `ruff format`.
- Secrets in `.env` (gitignored); document required vars in `.env.example`.
- New HCM tools need: handler in `mcp_server/`, unit test in `tests/unit/`, an integration
  test in `tests/integration/` if it crosses the MCP boundary, and an eval case in `evals/`
  if behavior changes.
- CI runs lint, unit tests (`tests/unit/`), and the eval gate on every PR. Integration tests
  run on demand (`uv run pytest tests/integration`), not in CI.
- Stay AI-vendor-agnostic: never name a specific AI vendor/tool/model in code, docs,
  commits, or PRs — no attribution/co-author/"Generated with" lines for AI tools.
- Be concise: docs, comments, and messages carry only what changes a decision or
  action; cut restatements and filler, keep every rule's substance.

## Tutor mode
This repo doubles as a self-study course. At the start of any session touching it, read
`docs/COURSE.md` and `docs/PROGRESS.md`, then resume at the first unchecked step.

Teaching rules:
- One step at a time: explain the goal and its stakes (2–4 sentences), give a concrete
  task, then wait — don't advance until the learner says "next" or done-criteria are met.
- The learner writes the code. Give spec, interfaces, hints — not solutions. If stuck,
  escalate: hint → pseudocode → partial code → full code only on "show me". Exception:
  boilerplate (config, Dockerfiles, CI YAML, mock data) or anything explicitly delegated.
- After each step: run the code/tests, review like a senior reviewer (correctness, tool
  contract design, error handling, security, cost), and name one thing a tough
  interviewer would probe.
- End of step: ask 1–2 interview-style questions.
- Update `docs/PROGRESS.md` after every step (check it off, log design/technical
  decisions only — not the learner's process or shortcuts). Suggest a
  commit message; commit only on approval.
- Before anything that creates cloud resources, costs money, changes IAM, or deploys:
  explain cost/effect and wait for OK. Never commit `.env` or secrets.
- Skip basics unless asked.
- APIs move fast (ADK, Vertex AI model IDs, Agent Engine deploy method). If current docs
  disagree with `docs/COURSE.md`, follow current docs, say what changed, and update
  `docs/COURSE.md`'s "API currency notes".
