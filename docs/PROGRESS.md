# Progress

Checklist mirrors `docs/COURSE.md`. Check off a step only when its done-criteria are met
(code/tests pass, review happened, interview questions asked). Resume at the first
unchecked step.

## Module 1 — Foundations and first ADK agent
- [x] 1. Environment: uv venv, deps, Vertex AI or AI Studio choice, `hr_agent/.env`, budget alert
- [x] 2. Mock data module (employees, PTO/sick hours, 2026 holidays)
- [x] 3. Tools: `get_pto_balance(employee_id)`, `list_holidays(year)`
- [x] 4. ADK agent (`root_agent`) + unit tests for tools
- [x] 5. Run with `adk web` / `adk run`; test prompts; walk one trace
- [x] 6. Break-it experiments (vague docstring, removed rule, exception, double question)
- [x] 7. `scratch/react_from_scratch.py` — no-framework rebuild
- [x] 8. `find_employee(name)` in both versions; access-control gap noted
- [x] 9. `docs/01-when-to-use-an-agent.md`

## Module 2 — Tools and MCP
- [ ] `mcp_server/` with `get_employee`, `get_payroll_run`, `submit_pto_request`
- [ ] Typed schemas, idempotent writes, structured errors
- [ ] Connect via ADK MCP toolset
- [ ] Second MCP client proving reuse
- [ ] Tests for the server
- [ ] `docs/02-tool-contract-guidelines.md`

## Module 3 — Multi-agent orchestration
- [ ] Root router + PTO agent, read-only payroll agent, policy Q&A agent (RAG over handbook)
- [ ] Verify current Workflow Runtime vs. Sequential/Parallel/Loop agent status
- [ ] Compare LLM-driven delegation vs. ADK workflow/deterministic flows
- [ ] Rebuild one flow in LangGraph
- [ ] Architecture diagram
- [ ] `docs/03-adk-vs-langgraph.md`

## Module 4 — Memory, state, context engineering
- [ ] Session state (current employee, pending actions)
- [ ] Long-term memory (Agent Platform Memory Bank on Agent Engine)
- [ ] Trimming/summarizing tool output
- [ ] Sensitive data kept out of context unless needed

## Module 5 — Evaluation
- [ ] 30–50 case eval set (happy path, ambiguous, adversarial: prompt injection, salary requests)
- [ ] Trajectory + response evals via `adk eval`
- [ ] LLM-as-judge rubric
- [ ] Launch bar (task success, zero unauthorized access, p95 latency, cost/task)
- [ ] Wired into CI as a gate
- [ ] `docs/05-eval-standard.md`

## Module 6 — Safety and governance
- [ ] Permission boundaries in tool/MCP layer (act as requesting user)
- [ ] Human-in-the-loop callbacks (PTO confirm, payroll manager approval)
- [ ] Audit log of every tool call
- [ ] Rate / blast-radius limits
- [ ] `docs/06-guardrail-standard.md`

## Module 7 — Deploy to the cloud
- [ ] Deploy to Agent Engine (`adk deploy agent_engine`)
- [ ] Deploy to Cloud Run (`adk deploy cloud_run`)
- [ ] Deploy to GKE (`adk deploy gke`)
- [ ] Least-privilege service account, Secret Manager
- [ ] CI/CD with eval gate, staging then prod
- [ ] Compare with Agent Starter Pack layout
- [ ] Tear down unused resources
- [ ] `docs/07-deployment-tradeoffs.md`

## Module 8 — Observability, cost, Staff-level artifacts
- [ ] OpenTelemetry traces to Cloud Trace
- [ ] Dashboard: task success, tool error rate, latency, cost/task
- [ ] Model-tier routing (Flash vs. Pro) with measured savings
- [ ] Failure drill + RCA
- [ ] `docs/08-reference-architecture.md`
- [ ] `docs/08-platform-strategy-memo.md`
- [ ] `docs/08-roi-cost-model.md`

---

## Decisions

- M1.3: Tools return `{"status": ...}` dicts, errors as data with actionable messages
  (ID format, available years). IDs normalized (strip/upper). Tests live in `tests/unit/`;
  integration tests in `tests/integration/`, on demand.
- M1.1: Chose Vertex AI (ADC) over AI Studio API key — aligns with Agent Engine deploy
  path in Module 7. Model ID set via `MODEL_ID` in `.env`, currently `gemini-3.5-flash-lite`
  (re-verify before Module 8 tier-routing work; Gemini 2.5 retires 2026-10-20).

- M1.5: Behavior of the five test prompts is covered by live integration tests
  (`tests/integration/hr_agent/test_agent_live.py`), asserting trajectory before wording.

- M1.7: Manual loop appends the model turn unmodified (thought signatures must round-trip
  on Gemini 3.x). Tool failures returned as observations. `MAX_STEPS` bounds steps only,
  not cost; token/time budgets and idempotent writes are deferred to Modules 2/6.
- M1.8: `find_employee` returns id/name/title only (no balances); `ambiguous` status for
  multiple matches, prompt-enforced (hard gate deferred to Module 6 HITL/callbacks).
  Caller-identity authorization belongs in the MCP server, with identity from the
  transport, not a model-supplied argument (Modules 2/6).

- M1.9: Pattern choice rule: least autonomy that meets the requirement. Hard gates
  (authorization, write approval) live in the tool/server layer; prompt rules are the soft
  layer only.

- M2.1: Streamable HTTP transport (shared service, independent deploy, headers carry caller
  identity). `get_employee` returns id/name/title only (data minimization). Handlers are
  pure functions; `server.py` is thin wiring. mcp 2.x: `MCPServer` replaces `FastMCP`.
  ID-lookup logic is duplicated with the agent's local tools until M2.3; not shared across
  the MCP boundary.

## Open questions

- Module 3: does ADK 2.x still ship `SequentialAgent`/`ParallelAgent`/`LoopAgent`
  alongside the new Workflow Runtime, or are they superseded? Verify against current
  `adk-docs` when we get there.
- Model IDs drift fast (Gemini 2.5 shuts down 2026-10-20 mid-course) — reconfirm exact
  Gemini 3.x IDs at Module 1 step 1 and again before Module 8.
- Confirm `VertexAiMemoryBankService` (or current equivalent name) import path at Module 4.
