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
- [x] `mcp_server/` with `get_employee` (M2.1)
- [x] `get_payroll_run`, `submit_pto_request` (M2.2)
- [x] Typed schemas, idempotent writes, structured errors (M2.3)
- [x] Connect via ADK MCP toolset (M2.4)
- [x] Second MCP client proving reuse
- [x] Tests for the server
- [x] `docs/02-tool-contract-guidelines.md`

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

- M2.2: Errors carry a machine-readable `code` plus message. `get_payroll_run` returns
  aggregates only. `submit_pto_request`: caller-supplied `idempotency_key` (survives agent
  retries; server-generated keys can't dedupe a retry); same key + same args replays the
  original (`replayed: true`); same key + different args is `idempotency_conflict`; failed
  requests don't consume the key. Hours are computed server-side (weekdays minus holidays),
  never model-supplied. Balance is not decremented and pending requests aren't counted
  against it, so concurrent requests can overdraw; fix when state moves to a real store.

- M2.3: Wire contract is strict, handlers stay lenient. `Annotated[..., Field(pattern/length)]`
  on handler params is enforced by the MCP layer (a malformed ID or date is rejected as a
  `ToolError` before the handler runs) and published in the input schema; direct handler
  calls still normalize. Semantic date errors (impossible date, end < start) stay
  `invalid_dates` result data. Outputs are `TypedDict` unions on `status`, with `Literal`
  error codes and statuses published in `outputSchema`. Schema-layer rejections are
  protocol errors, not `{"status": "error"}` results; the agent must handle both. Unknown
  arguments are rejected (`additionalProperties: false`) so a misspelled write argument
  fails loudly; done by patching the generated arg model (no public option in mcp).

- M2.4: `McpToolset` (adk 2.9.2 + mcp 2.2.0 work together; `MCPToolset` is a deprecated alias)
  over Streamable HTTP, URL from `HCM_MCP_URL`. `tool_filter` exposes only `get_employee`
  and `submit_pto_request`; payroll stays unexposed until Module 3/6. `find_employee`,
  `get_pto_balance`, `list_holidays` remain local (no MCP equivalent yet). The model
  generates `idempotency_key` (prompt rule: fresh per request, reuse only on identical
  retry); a collision with different args fails loudly as `idempotency_conflict`. PTO writes
  have no user confirmation yet (Module 6 HITL). Integration test spawns the server as a
  subprocess on port 8000.

- M2 reuse: `scratch/mcp_client.py` (mcp `Client`, no `hr_agent`/`mcp_server` imports) exercises
  list/get/submit/idempotency from the published schemas alone. Findings: union return
  types arrive wrapped as `structuredContent: {"result": ...}`; business errors are
  results (`status: error`), while schema violations (malformed ID, unknown argument)
  arrive as `isError` results whose text is a raw pydantic message, so clients need both
  paths, and that text is poor model-facing guidance (candidate for M2.5 server tests /
  the tool-contract doc).

- M2 server tests: handler and dispatch-level unit tests already covered logic and schemas;
  the gap was the wire. `tests/integration/mcp_server/test_server_http.py` is a black-box
  suite (spawns the server, `mcp.Client`, no model or credentials) covering tool listing,
  `{"result": ...}` wrapping, replay/conflict, and rejection of malformed/unknown input
  without consuming the idempotency key. Not in CI (integration policy); cheap enough to
  add later.

- M2 doc: `docs/02-tool-contract-guidelines.md` rule of thumb: format constraints go in the
  schema (protocol error, published contract); semantic checks are result data (model-readable
  message). Idempotency keys are caller-supplied because only the caller knows a call is a
  retry; the model choosing keys is why the server fails loudly on key reuse with different args.

- M3.1 (partial: router + PTO agent): `hr_agent/agent.py` is a toolless router
  (`sub_agents=[pto_agent]`); specialists in `hr_agent/agents/`. Shared `config.py` (model,
  MCP URL) and `toolsets.py` (`hcm_toolset`) so later specialists import neither the router nor
  each other. Specialist `description` is the routing contract. Router declines unmatched
  requests. Integration `Turn` records `transfer_to_agent` separately from tool calls so
  trajectory assertions stay about real tools. Payroll and policy agents remain.
- M3.1 payroll: `payroll_agent` gets its own read-only `payroll_toolset`
  (`tool_filter=["get_payroll_run"]`, shared connection params, separate session). The filter
  is a soft boundary; the hard one is server-side authorization (Module 6). Misroute found:
  "Who is employee E1002?" was declined by the router because `pto_agent`'s description
  didn't mention employee lookup. Routing accuracy is set by the descriptions, so widen them
  when a specialist owns a tool; candidate for the Module 5 routing evals. Policy agent remains.

## Open questions

- M2: schema-layer rejections return raw pydantic text with no example ID. A server-side
  rewrite (subclass overriding `call_tool`) was tried and dropped as too complex; leave to
  clients unless it proves to hurt agent behavior. Note for `docs/02-tool-contract-guidelines.md`.

- Module 3: does ADK 2.x still ship `SequentialAgent`/`ParallelAgent`/`LoopAgent`
  alongside the new Workflow Runtime, or are they superseded? Verify against current
  `adk-docs` when we get there.
- Model IDs drift fast (Gemini 2.5 shuts down 2026-10-20 mid-course) — reconfirm exact
  Gemini 3.x IDs at Module 1 step 1 and again before Module 8.
- Confirm `VertexAiMemoryBankService` (or current equivalent name) import path at Module 4.
