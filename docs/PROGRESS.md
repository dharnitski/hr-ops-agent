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
- [x] 1. `mcp_server/` with `get_employee` (M2.1)
- [x] 2. `get_payroll_run`, `submit_pto_request` (M2.2)
- [x] 3. Typed schemas, idempotent writes, structured errors (M2.3)
- [x] 4. Connect via ADK MCP toolset (M2.4)
- [x] 5. Second MCP client proving reuse
- [x] 6. Tests for the server
- [x] 7. `docs/02-tool-contract-guidelines.md`

## Module 3 — Multi-agent orchestration
- [x] 1. Root router + PTO agent, read-only payroll agent, policy Q&A agent (RAG over handbook)
- [x] 2. Verify current Workflow Runtime vs. Sequential/Parallel/Loop agent status
- [x] 3. Compare LLM-driven delegation vs. ADK workflow/deterministic flows
- [x] 4. Rebuild one flow in LangGraph
- [x] 5. Architecture diagram
- [x] 6. `docs/03-adk-vs-langgraph.md`

## Module 4 — Memory, state, context engineering
- [x] 1. Session state (current employee, pending actions)
- [ ] 2. Long-term memory (Agent Platform Memory Bank on Agent Engine) -- interface/local stub
      done (`InMemoryMemoryService`); live Agent Engine resource deferred to Module 7 by choice
- [x] 3. Trimming/summarizing tool output
- [x] 4. Sensitive data kept out of context unless needed

## Module 5 — Evaluation
- [x] 1. 30–50 case eval set (happy path, ambiguous, adversarial: prompt injection, salary requests)
- [x] 2. Trajectory + response evals via `adk eval`
- [x] 3. LLM-as-judge rubric
- [x] 4. Launch bar (task success, zero unauthorized access, p95 latency, cost/task)
- [x] 5. Wired into CI as a gate
- [x] 6. `docs/05-eval-standard.md`

## Module 6 — Safety and governance
- [x] 1. Permission boundaries in tool/MCP layer (act as requesting user)
- [x] 2. Human-in-the-loop callbacks (PTO confirm, payroll manager approval)
- [x] 3. Audit log of every tool call
- [x] 4. Rate / blast-radius limits
- [x] 5. `docs/06-guardrail-standard.md`

## Module 7 — Deploy to the cloud
- [x] 1. Deploy to Agent Engine (`adk deploy agent_engine`)
- [x] 2. ~~Deploy to Cloud Run (`adk deploy cloud_run`)~~ — skipped, staying on Agent Engine
      only (2026-09-29 scope decision, see Decisions)
- [x] 3. ~~Deploy to GKE (`adk deploy gke`)~~ — skipped, same decision
- [ ] 4. Least-privilege service account, Secret Manager
- [ ] 5. CI/CD with eval gate, staging then prod
- [ ] 6. Compare with Agent Starter Pack layout
- [ ] 7. Tear down unused resources
- [ ] 8. `docs/07-deployment-tradeoffs.md` (scoped to Agent Engine only) -- distinct from
      `docs/07-deployment-procedure.md` (added 2026-09-29): that one's the how-to-redeploy
      runbook; this one's still the why-Agent-Engine analysis, not yet written.

## Module 8 — Observability, cost, Staff-level artifacts
- [ ] 1. OpenTelemetry traces to Cloud Trace
- [ ] 2. Dashboard: task success, tool error rate, latency, cost/task
- [ ] 3. Model-tier routing (Flash vs. Pro) with measured savings
- [ ] 4. Failure drill + RCA
- [ ] 5. `docs/08-reference-architecture.md`
- [ ] 6. `docs/08-platform-strategy-memo.md`
- [ ] 7. `docs/08-roi-cost-model.md`

---

## Decisions

Current state and the reasoning behind it, by module. Superseded/resolved debugging detail has
been cut; see git history for the blow-by-blow if needed.

### Module 1
- Vertex AI (ADC) over an AI Studio API key -- aligns with the Module 7 Agent Engine deploy
  path. Model ID via `MODEL_ID` in `.env` (re-verify before Module 8; Gemini 2.5 retires
  2026-10-20).
- Tools return `{"status": ...}` dicts; errors are data with actionable messages, never
  exceptions. IDs normalized (strip/upper).
- `find_employee`/`get_pto_balance` started as local tools with no caller-identity check
  (flagged then, closed in M6.2 -- see below).
- Pattern rule: least autonomy that meets the requirement. Hard gates (authorization, write
  approval) belong in the tool/server layer; prompt rules are the soft layer only.
- `scratch/react_from_scratch.py`: framework-free ReAct loop (`google-genai`, auto-calling
  disabled). `MAX_STEPS` bounds steps, not cost or latency.

### Module 2
- MCP server over Streamable HTTP (shared service, independent deploy, headers carry caller
  identity later). `mcp 2.x`'s `MCPServer` replaces `FastMCP`; handlers are pure functions,
  `server.py` is thin wiring.
- Data minimization: `get_employee`/`get_payroll_run` return only non-sensitive fields (no
  balances, no per-employee pay).
- Errors carry a machine-readable `code` plus message. Schema-layer rejections (malformed ID,
  unknown argument) are protocol errors (`ToolError`, `additionalProperties: false`), distinct
  from business errors (`{"status": "error", "code": ...}`) -- the agent must handle both.
- `submit_pto_request` takes a caller-supplied `idempotency_key` (server-generated keys can't
  dedupe a retry): same key + same args replays the original; same key + different args is
  `idempotency_conflict`; failed requests don't consume the key. Hours are computed
  server-side (weekdays minus holidays), never model-supplied.
- `McpToolset` (`MCPToolset` is a deprecated alias) with `tool_filter` scoping each specialist
  to only the tools it needs.
- `docs/02-tool-contract-guidelines.md`: format constraints go in the schema (published
  contract); semantic checks are result data (model-readable message).

### Module 3
- `hr_agent/agent.py` is a toolless router (`sub_agents=[...]`); specialists live in
  `hr_agent/agents/`. A specialist's `description` is the routing contract -- widen it when it
  gains a tool, or the router misroutes around it.
- Two router bugs found and fixed live: (1) a multi-part message matching one specialist was
  being declined as "ambiguous" just for having multiple parts; (2) a missing detail (e.g.
  "the employee I asked about earlier") was being treated as "unclear, ask the user" at the
  router level instead of handed to the specialist that can actually resolve it (via memory).
  Root cause both times: the router's "if unclear, ask" rule didn't distinguish "unclear which
  specialist" from "specialist will need to resolve a detail."
- `search_handbook`: deterministic keyword retrieval (stopwords dropped, title matches
  weighted, top 3 nonzero) -- sufficient at 8 sections; embeddings would add nothing yet.
  Misses synonyms ("vacation" vs "PTO"); candidate eval case and the trigger to revisit if the
  handbook grows.
- ADK's `Workflow` (graph of nodes, conditional routing) supersedes the deprecated
  Sequential/Parallel/Loop agents, but can't yet be an `LlmAgent` sub-agent -- mixing LLM
  delegation and a workflow means the workflow is the root, not the reverse. Rule of thumb:
  deterministic routing where intents are enumerable/keyword-detectable; LLM routing for vague
  or multi-intent input.
- `docs/03-adk-vs-langgraph.md`: recommends staying on ADK for this project specifically
  because Module 7's deploy path and the MCP toolset are already ADK-native -- not a general
  framework verdict.

### Module 4
- Session state (`current_employee_id`, `pending_pto_request`) lives in `tool_context.state`,
  gone once the session ends. Local tools write it directly; MCP tools can't take a
  `ToolContext`, so `pto_agent`'s `after_tool_callback` (`_track_mcp_results`) reads each MCP
  result's wire shape (`structuredContent.result` / `isError`) and writes state from that,
  purely observational. Both keys are prompt-templated (`{current_employee_id?}`); reuse is a
  prompt rule, not enforced (see Open questions).
- Long-term memory: `BaseMemoryService` (`add_session_to_memory`/`search_memory`, scoped by
  `(app_name, user_id)`) is what both `InMemoryMemoryService` (in-process stub, used today) and
  `VertexAiMemoryBankService` (real resource, Module 7) implement -- swapping is a CLI flag on
  `adk web`/`adk run`, zero `hr_agent/` code change. Read side uses `load_memory` (an
  auditable, model-invoked tool call) over `preload_memory` (silent injection), matching M2's
  data-minimization stance. Memory is reference-only, never identity: a recalled ID may be
  used directly for a read, but never for a write (`submit_pto_request`) without re-resolving
  the employee this session -- prompt rule only, not enforced.
- `_persist_to_memory` writes one synthetic fact per turn ("this user asked about employee X"),
  not the raw conversation -- avoids storing exact PTO dates/hours/balances indefinitely in a
  durable, cross-session-searchable store. `Context.add_memory` would be the cleaner direct
  write but isn't implemented by `InMemoryMemoryService`, only by the real service.
- Context growth: `ContextFilterPlugin` (`before_model_callback`, drops whole old invocations
  from the model payload, deterministic and free) chosen over `EventsCompactionConfig`
  (LLM-summarized, still `@experimental`) for this project's scale. Wired via an `App(...)`
  export in `hr_agent/agent.py` (confirmed `adk web`/`run`/`deploy`/`eval` all prefer `app` over
  `root_agent`); `num_invocations_to_keep=6` is an unmeasured starting guess.

### Module 5
- 29 cases across `evals/{happy_path,ambiguous,adversarial}/` (started at 31; two removed in
  M6.2 when their only premise -- `find_employee`'s name matching -- was retired), one
  `.evalset.json` + `test_config.json` per tier so each risk tier gets its own strictness.
- `happy_path`/`ambiguous`: `ANY_ORDER` + `ignore_args: true` (tolerates a legitimate extra
  double-check call, and calls between independent sub-questions happening in either order).
  `adversarial`: `EXACT` + `ignore_args: true` (order is already fixed by "resolve identity
  before writing"; the real job is catching *extra* calls, e.g. a silent retry or a bulk sweep
  triggered by prompt injection). `ignore_args: true` everywhere because
  `submit_pto_request`'s `idempotency_key` is model-generated and unpredictable --
  argument-level correctness is checked via `response_match_score` on the final text instead.
- `transfer_to_agent` is a real tool call and always the first hop into a specialist, so it's
  included explicitly as the first expected call in every case that reaches one (not repeated
  on a same-specialist follow-up turn).
- `response_match_score` threshold is an unmeasured floor (0.3, down from the 0.8 default);
  dropped entirely for the adversarial tier, where ROUGE-style scoring penalized correct but
  lexically different refusals -- replaced there by an LLM-as-judge rubric metric
  (`rubric_based_final_response_quality_v1`, one generic + one per adversarial category:
  salary refusal, prompt injection, specific rejection reason, idempotency replay/conflict).
- No cross-session recall case exists (an `EvalCase` is one session); the router-recall
  regression is instead proxied with a same-session two-turn case using resolved state. The
  real cross-session path is covered by `tests/integration/hr_agent/test_memory_live.py`.
- Salary-request cases expect an empty tool trajectory plus a declining response:
  `get_payroll_run` only ever returns aggregates, so no tool call could legitimately answer
  "what does X earn."
- Launch bar (four dimensions, each with a threshold and a note on what actually gates today):
  **task success** -- binary, all cases must pass; gated in CI since M5.5. **Zero unauthorized
  access** -- zero-tolerance bar, but no eval case existed until Module 6 shipped server-side
  permission boundaries; still not mechanically gated in CI (see Open questions). **p95
  latency** (<5s read, <10s write) and **cost/task** (<$0.01 read, <$0.02 write on
  `gemini-3.5-flash-lite`) -- unmeasured starting floors, alert-only until Module 8's
  instrumentation exists.
- CI gate: `scripts/run_eval_gate.py` runs one `adk eval` invocation per tier, each against a
  *fresh* MCP server subprocess (a shared long-lived server was the root cause of most
  flakiness found while building this: stale idempotency-key collisions across runs,
  transient "Connection closed" under concurrent sessions), with a bounded retry that only
  matches known-transient failure text (OAuth token-refresh timeout, MCP connection reset) --
  a real failure fails immediately. The `eval` CI job only runs live once GCP Workload Identity
  Federation credentials are configured (not yet, by design -- a cost/IAM decision for the
  project owner) and even then only on manual `workflow_dispatch`, since every run is billed.
  `lint`/`test` run automatically on every push/PR regardless.
- `docs/05-eval-standard.md`: the standard for adding a case and reading gate results --
  tier-selection rule, a per-metric blind-spot table, the launch-bar table, and a checklist
  covering two traps already hit once each: a placeholder golden response, and a hardcoded
  idempotency key that becomes one-time-use against a server that isn't restarted.

### Module 6
- **M6.1 (permission boundaries):** caller identity flows from the transport only, never a
  model-supplied argument. `McpToolset(header_provider=...)` turns a session-state key
  (`caller_employee_id`, `hr_agent/toolsets.py`) into an `x-caller-employee-id` header per MCP
  session; the server reads it via a `ctx: Context` parameter that isn't part of the published
  schema (confirmed: the model never sees it). `get_employee`/`get_pto_balance`/
  `submit_pto_request` are self-only (`forbidden` unless `employee_id` matches the caller,
  checked before any lookup or idempotency-store access, so an unauthorized caller can't learn
  whether a target even exists). `get_payroll_run` is role-gated instead (`title` in
  `"Payroll Specialist"`/`"Finance Director"`) since it's aggregate-only with no per-employee
  scoping question.
  No production code sets `caller_employee_id` yet (no login flow) -- all four MCP tools
  correctly fail closed for a real user until Module 7+ adds real auth. Test fixtures set it
  explicitly.
- **M6.2 (closed the gap M6.1 missed):** `get_pto_balance` was still the pre-M2 *local* tool
  (`hr_agent/tools.py`) with no caller-identity check at all -- the one tool that actually
  returns balances, since `get_employee` never did. Found live via `adk web`: one session could
  read E1002's balance, then E1003's, with no auth. Moved `get_pto_balance` to the MCP layer
  with the same self-only check as `get_employee`. `find_employee` was retired outright rather
  than ported: self-only means "may only ever see your own record," and a name search is
  inherently a search across everyone else's names too, so there's no self-only version worth
  building. `hr_agent/tools.py` now holds only `list_holidays` (not employee-scoped, no
  identity question applies). `scratch/react_from_scratch.py` got its own local copies of
  `find_employee`/`get_pto_balance` (it has no ADK session to carry MCP/header machinery) and
  its own short instruction, rather than depending on production internals that no longer
  exist in that shape. 9 of the 31 eval cases exercised the retired name-lookup path or the
  underlying vulnerability directly; fixed in place where incidental (swap name for ID, drop
  the resolution step), rewritten to expect "asks for an ID" where the case's entire premise
  was resolving someone else's name, and removed outright (2 cases) where no replacement
  exists for `find_employee`'s matching/not-found behavior. Not run live (see Open questions).
- Left open: idempotency store is still one global dict keyed only by `idempotency_key`
  (M2.2), unscoped by caller -- two different, both-legitimate employees choosing the same key
  string still collide. Audit log and rate/blast-radius limits (checklist items 3-4) not
  started.
- **M6.2 (HITL callbacks):** used ADK's native `require_confirmation` (`@experimental`,
  `FeatureName.TOOL_CONFIRMATION`) rather than a hand-rolled `before_tool_callback` gate --
  `MCPTool`/`FunctionTool` already pause the call, emit an `adk_request_confirmation`
  long-running function call with a hint, and resume on the next turn's `FunctionResponse`;
  `adk web`/`adk run` already render and drive that exchange. `require_confirmation` is a
  toolset-wide flag (`McpToolset`), not per-tool, so `hcm_toolset` (`hr_agent/toolsets.py`) was
  split: reads (`get_employee`, `get_pto_balance`) stay auto, and the new `pto_write_toolset`
  carries `submit_pto_request` alone with `require_confirmation=True`. Verified live
  (`tests/integration/hr_agent/test_pto_confirmation_live.py`, 3 cases: pause happens, confirm
  submits, reject doesn't) rather than through `adk web`'s UI, because no production code sets
  `caller_employee_id` yet (see Open questions) -- a chat session there gets `forbidden` from
  every HCM tool regardless of this feature, so the Runner/Event API was the only way to
  exercise the confirmed path end to end.
  Payroll manager approval (the other half of this step) added a minimal write tool,
  `approve_payroll_run` (`mcp_server/handlers.py`): moves a run `draft` -> `approved`,
  idempotent the same way as `submit_pto_request`, gated by the same `require_confirmation`
  mechanism via a new `payroll_write_toolset` (split from `payroll_read_toolset`, formerly
  `payroll_toolset`, for the same toolset-wide-flag reason as `pto_write_toolset`). Role check
  is `Finance Director` only -- stricter than `get_payroll_run`'s reader set (which also
  includes `Payroll Specialist`): separation of duties, matching "manager approval" in
  `docs/COURSE.md`. Unlike `submit_pto_request`, the write does mutate shared mock state
  (`PAYROLL_RUNS[...]["status"]`) rather than leaving it to a downstream approval step, since
  approval *is* the state change here; unit tests reset it via an autouse fixture
  (`tests/unit/mcp_server/test_handlers.py`). Covered by handler unit tests, MCP-boundary
  integration tests (`tests/integration/mcp_server/test_server_http.py`), and the same
  toolset-config unit tests as PTO's -- no new live agent-level confirmation test, since
  M6.2's PTO test already proved the generic ADK mechanism; re-testing the identical mechanism
  through a second tool would be redundant. Not wired into any eval case yet (M5 gap, not
  addressed here).
- **M6.3 (audit log):** `AuditLogPlugin` (`hr_agent/audit.py`), a `google.adk.plugins.
  BasePlugin` hooked into `before_tool_callback`/`after_tool_callback`/`on_tool_error_callback`
  and wired app-wide via `App(plugins=[...])` in `hr_agent/agent.py` -- fires once per tool
  call across every specialist and both local and MCP tools, unlike a per-agent
  `after_tool_callback` (e.g. `pto_agent`'s `_track_mcp_results`), which only sees that one
  agent's own calls. Caller identity comes from session state
  (`CALLER_EMPLOYEE_ID_STATE_KEY`), the same transport-established value M6.1 already trusts --
  never a tool argument.
  Every field is allowlisted, not blocklisted: `args`/`result` dicts are redacted down to
  identifiers and outcomes (`employee_id`, `run_id`, `status`, `code`, ...), dropping anything
  not explicitly named -- including free-text business-error messages, which can embed a
  balance (e.g. `submit_pto_request`'s "Request needs 16h but balance is 8h."). A tool
  exception logs its type name only (`on_tool_error_callback`), not `str(error)`, for the same
  reason. Emits via the standard `logging` module (logger `hr_agent.audit`) -- a real sink
  (Cloud Logging, BigQuery) is a Module 7+ decision, not this one.
  Known gap: the ADK-generated confirmation-pause/reject dict (`{"error": "This tool call
  requires confirmation..."}`) has no `status`/`code` field to redact to, so a paused or
  rejected write logs an empty `result` -- the call itself, agent, tool, and caller are still
  recorded, just not which of the two outcomes it was. Not fixed here because the alternative
  (pattern-matching that ADK-internal string) is more fragile than the fidelity it would buy.
  A plugin only applies to the `App` it's registered on, not to an `Agent` run directly --
  `tests/integration/hr_agent/conftest.py`'s `ask`/`conversation`/`sessions` fixtures build
  their `Runner` around `root_agent`, so none of them exercise this plugin (same caveat
  `hr_agent/agent.py`'s own comment already notes for `ContextFilterPlugin`). Verified instead
  by a dedicated live test running `app` directly
  (`tests/integration/hr_agent/test_audit_log_live.py`) against the real MCP server, confirming
  the hand-fabricated MCP wire shape in the unit tests matches a real `MCPTool.run_async`
  result and that the real `pto_hours` figure does not reach the log.
- **M6.4 (rate / blast-radius limits):** two independent, complementary bounds, both in
  `mcp_server/handlers.py` since the server is the hard boundary (tool/MCP layer, per M1's
  pattern rule) -- neither depends on the model or the confirmation step behaving correctly.
  **Rate limiting** (`_check_rate_limit`): an in-memory sliding window of call timestamps
  keyed by `(caller_id, tool_name)`, 20 calls per 60s, folded into `_check_caller_and_key`/
  `_check_approver_and_key` so it runs on every call attempt -- including one that fails
  later validation -- before the idempotency store or any lookup; an exact-replay call still
  consumes a slot (simpler than special-casing it, and arguably correct: a flood of replays is
  still a flood). Per-tool, not shared across `submit_pto_request` and `approve_payroll_run`,
  so exhausting one doesn't block the other. **Blast radius** (`MAX_REQUEST_HOURS`): a single
  `submit_pto_request` may not exceed 160h (20 working days) regardless of balance or
  confirmation, checked in `_check_request` before the balance check so it fires even for a
  request that would also fail on balance. `approve_payroll_run` has no equivalent cap -- one
  call approves exactly one already-bounded run, so its blast-radius protection is the role
  gate, confirmation, and rate limit alone (no continuous "how much" dimension to cap, unlike
  PTO's hours).
  New error codes (`rate_limited`, `exceeds_limit`) are plain `{"status": "error", "code":
  ...}` results -- no new agent instruction rule needed, since the existing generic "tell the
  user plainly what went wrong" rule (M1) already covers them, same as `insufficient_balance`
  or `invalid_state`. Only `submit_pto_request` and `approve_payroll_run` needed new module-
  level reset fixtures for `_write_call_times`, mirroring the existing `_pto_requests`/
  `_payroll_approvals` pattern -- required because the counter is process-lifetime state and
  the existing test suite reuses the same caller IDs across dozens of test functions. Chose 20
  calls/60s specifically so it comfortably clears the live HTTP integration suite's real call
  volume against a single session-scoped server subprocess (same class of shared-state
  friction M5's eval gate hit) without weakening the limit to the point of being decorative;
  the unit-level rate-limit tests use `monkeypatch` on `RATE_LIMIT_MAX_CALLS` instead of making
  20 real calls. No live agent-level test added for either limit: both are plain business-error
  results the agent already knows how to relay, unlike M6.2's confirmation pause, which needed
  its own mechanism-level proof.
- **`identify_caller` (2026-09-29, prompted by M7's live deploy making the "always forbidden"
  gap visible for the first time):** every MCP tool has been correctly unreachable for a real
  user since M6.1 -- nothing ever set `caller_employee_id`, because there's no login flow, and
  building one is out of this course's syllabus (a real identity-provider integration, not an
  ADK/agent-pattern topic). Rather than build real auth or leave the gap, added
  `identify_caller(employee_id, tool_context)` (`hr_agent/tools.py`): a plain local tool that
  writes `tool_context.state[CALLER_EMPLOYEE_ID_STATE_KEY]` from the user's own stated ID.
  Explicitly labeled in its docstring as NOT authentication -- it answers "which identity is
  this session claiming", never "is that claim true"; every self-only/role check still runs
  unconditionally against whatever ID gets claimed (see Open Questions on the actual security
  gap this leaves). Added to `pto_agent` and `payroll_agent`'s tool lists (not the toolless
  router, which stays intent-only); both instructions now expose `{caller_employee_id?}` and
  tell the model to ask once per conversation, before any self-service/role-restricted tool,
  and never re-ask once it's set.
  Verified live via `adk web` (not just unit tests, since this is model behavior, not just
  wiring): a PTO question with no identity got asked for an employee ID rather than guessing
  or silently failing; after supplying E1002, `identify_caller` then `get_pto_balance` both
  fired and the real balance came back; a follow-up asking about E1003 in the *same* session
  reused the established identity (no re-ask) and correctly got `forbidden` -- proving the stub
  grants exactly one identity per session, not blanket access.
  Redeployed to Agent Engine (same `--env_file`/`--extra_packages=mcp_server` command as
  before) and re-ran the identical three-turn check against the live resource via a real
  session (`async_create_session`, not a bare `session_id` string -- `stream_query` silently
  no-ops on one that was never created): identical result over the actual cloud path --
  ask -> `identify_caller` + `get_pto_balance` succeed -> a different employee ID in the same
  session gets `forbidden`. The full HCM-reachability-plus-identity arc is now provably
  working end to end on the deployed agent, not just locally.
  Checked all 29 eval cases against this change: 28 already pre-seed `caller_employee_id` in
  `session_input.state` (M6.1's original test-fixture pattern), so the new instruction rule
  ("ask if empty") never fires for them -- unaffected. One adversarial case does not
  (`adversarial_submit_pto_malformed_employee_id`, which tests a malformed *subject* ID being
  rejected at the MCP schema layer): its expected trajectory now likely breaks, since the model
  would ask for the caller's own ID before ever attempting `submit_pto_request`. Not fixed here
  -- the eval gate only runs on manual `workflow_dispatch`, not CI, so this is a known
  regression to catch and correct (either pre-seed that case's state too, or accept the new
  behavior and update its expected trajectory) before the next real eval run, not a live
  breakage today.

### Module 7
- **M7.1 (Agent Engine deploy):** `adk deploy agent_engine --project=hr-ops-agent-509718
  --region=us-central1 --display_name="hr-ops-agent (Module 7.1)" hr_agent`, run 2026-09-28.
  Live resource: `projects/976559775904/locations/us-central1/reasoningEngines/
  3717518632499019776`. API drift vs. `docs/COURSE.md`'s original notes and the fix required
  are logged there (staging bucket no longer needed; empty `.env` values now hard-fail the
  deploy -- `HCM_API_BASE_URL`/`HCM_API_KEY`, two dead placeholders from before mock data
  replaced a real HCM integration, were deleted from `hr_agent/.env` and `.env.example`).
  Scope decision made before deploying, not after: `HCM_MCP_URL` still points at
  `localhost:8000`, unreachable from the cloud, so every tool call on the deployed agent
  fails with a connection error -- accepted deliberately for this step, which is about
  proving the deploy mechanics (auth, packaging, IAM) work, not about a working end-to-end
  agent yet. Revisit MCP reachability as its own decision when it actually blocks a later
  step (e.g. Cloud Run).
  The auto mode classifier blocks both `adk deploy` commands (flagged "Production Deploy")
  and writes to `.claude/settings.local.json` (flagged "Self-Modification") -- granting a
  Bash permission for cloud deploys has to be a manual action the user takes themselves; the
  user added `.claude/settings.local.json` (gitignored, machine-local, not `settings.json`)
  with `"Bash(adk deploy *)"`/`"Bash(uv run adk deploy *)"` allow rules.
  **Second deploy blocker, found live via the playground:** the deployed agent crashed on
  import with `ModuleNotFoundError: No module named 'mcp'`. Root cause in
  `cli_deploy.py`: when the agent folder has no `requirements.txt` of its own, the deploy tool
  generates one containing only `google-adk[a2a]==<version>` (plus `google-cloud-aiplatform`,
  appended automatically) -- it does not read `pyproject.toml`/`uv.lock` at all. `mcp` is not
  a hard dependency of `google-adk` itself (lazily imported only when MCP-tool features are
  used), so it never reached the deployed container even though this project depends on it
  directly. Fixed with a hand-written `hr_agent/requirements.txt` containing just `mcp==2.2.0`
  (the version this project is actually tested against); `google-adk`/`google-cloud-aiplatform`
  still get auto-appended since the file doesn't declare `google-cloud-aiplatform` itself.
  Redeployed in place with `--agent_engine_id=3717518632499019776` (updates the existing
  resource rather than creating a second one) -- succeeded.
  **Third deploy blocker, found live via Cloud Logging (not the playground -- the console's
  log viewer surfaced a stale cached entry from the first crash, which cost a round-trip
  before the timestamps were checked directly against the resource's `updateTime` via the
  REST API):** `ImportError: cannot import name 'override' from 'typing'`. Agent Engine's
  managed runtime pins **Python 3.11** regardless of this project's own `requires-python`
  (3.14) -- `typing.override` is stdlib-only since 3.12. Fixed in `hr_agent/audit.py` by
  importing from `typing_extensions` instead (a strict superset, re-exports the stdlib
  version when available; already a hard dependency of `google-adk`, so no new
  `requirements.txt` entry needed) with a `# noqa: UP035` since ruff's `target-version =
  "py314"` would otherwise "fix" it back. Confirmed via `git grep` that no other file in
  `hr_agent/` uses 3.12+-only syntax.
  **Verified working end to end** by querying the deployed resource directly over its
  `:streamQuery` REST API (`class_method: stream_query`), not by asking the user to retest in
  the UI: a policy question correctly routed to `policy_agent`, called `search_handbook`, and
  returned a grounded, cited answer -- full multi-step tool orchestration with no crash. A PTO
  question never reached `get_pto_balance` (the one path that would have hit the expected
  `localhost:8000` connection failure): with no real caller identity in session state,
  `pto_agent` reasoned from its own self-only-permission instruction and declined the lookup
  proactively across three separate phrasings, rather than calling the tool and getting
  `forbidden` back. Not a deploy problem -- a legitimate demonstration that M6.1's
  permission-boundary reasoning holds even on a cold deploy with no auth wired in, just not
  the exact failure mode originally expected to observe.
- **7.2/7.3 skipped (2026-09-29):** user chose to stay on Agent Engine rather than also
  deploying to Cloud Run and GKE. Downstream Module 7 items narrow accordingly: item 6's
  Agent Starter Pack comparison and item 8's `docs/07-deployment-tradeoffs.md` now cover
  Agent Engine only, not a cross-target comparison. This also forces a decision on HCM/MCP
  reachability (open since M7.1) directly against Agent Engine, since there's no longer a
  later Cloud Run step to defer it to.
- **HCM reachability decision (2026-09-29):** deploy `mcp_server` itself to Cloud Run (private,
  `--no-allow-unauthenticated`) as a supporting service -- the agent's own compute stays on
  Agent Engine per the decision above; this doesn't reopen 7.2/7.3, since `mcp_server` was
  already meant to be an independently-deployed shared service (M2 decision). In progress;
  first piece done: `mcp_server/server.py`'s `main()` now reads `HOST`/`PORT` (Cloud Run
  injects `PORT`; local default stays `127.0.0.1:8000`, unchanged) and an opt-in
  `MCP_ALLOWED_HOSTS` that, when set, enables `TransportSecuritySettings` DNS-rebinding
  Host-header validation -- this `mcp` version disables that protection entirely when no
  `transport_security` is passed (verified hands-on: it's *not* a localhost-only default as
  initially assumed), so leaving `MCP_ALLOWED_HOSTS` unset once deployed silently reproduces
  today's unprotected posture rather than failing loud. Verified locally: wrong `Host` header
  -> 421, correct one -> passes through to normal handling. Cloud Run IAM (who may call in) and
  this setting (what Host header the server itself accepts) are separate, complementary
  checks -- IAM alone doesn't need this, but it's a cheap second layer once public-network
  bound.
  Second finding, blocking containerization: `mcp_server/handlers.py` still imported mock
  data from `hr_agent.mock_data` (a "Temporary" M2.3 debt that was never paid off -- flagged
  in a comment, not tracked as an open question). Importing `hr_agent` at all runs its
  `__init__.py` (`from . import agent`, required so ADK's agent loader finds `root_agent`),
  which imports `hr_agent/agent.py` and, transitively, all of `google.adk` -- measured
  hands-on: importing `mcp_server.handlers` pulled in 1383 modules, 222 of them
  `google.adk.*`, before the fix. Contradicts M2's own "shared service, independent deploy"
  design goal and would have meant shipping the full ADK/Vertex dependency tree into what
  should be a small stateless container -- bigger image, slower cold start, and a server
  that only starts today because `hr_agent/agent.py`'s module-level code happens not to need
  network/credentials at import time (that's luck, not a guarantee).
  Fixed at the root rather than patched around: mock data moved to `mcp_server/mock_data.py`
  (the HCM tool boundary now owns HCM data), `mcp_server/handlers.py` imports it locally,
  and `hr_agent/tools.py` (`list_holidays`) plus `scratch/react_from_scratch.py` import it
  from `mcp_server.mock_data` instead -- dependency direction is agent-depends-on-server
  mock data, never the reverse. Verified: importing `mcp_server.handlers` now pulls in 83
  modules, zero `google.adk`, zero `hr_agent`; full unit suite (189 cases) and
  lint/format/type-check still pass.
  Containerized: `deploy/cloud_run/mcp_server.Dockerfile` (`python:3.14-slim`, matching
  `requires-python`/`.python-version` -- Agent Engine's Python-3.11 pin from M7.1 doesn't
  apply here, this container is fully self-controlled), installing only
  `mcp_server/requirements.txt` (`mcp==2.2.0`, same pin as `hr_agent/requirements.txt`) via
  `uv pip install --system`, not `uv sync`/`uv.lock` -- the whole point of the mock-data fix
  above was that mcp_server must not pull in google-adk. `MCP_ALLOWED_HOSTS` deliberately not
  baked into the image (depends on the Cloud Run URL, known only after first deploy).
  Docker Desktop's daemon wasn't running in this environment, so the actual `docker build`
  couldn't be exercised; verified the equivalent by hand instead -- a throwaway venv pinned to
  Python 3.14 (matching the base image, not the host shell's default `python3` which turned
  out to be 3.11 and hit the exact `typing.TypedDict`-needs-3.12+ class of bug M7.1 already
  found once with Agent Engine, confirming the version pin matters), `pip install`ing only
  `mcp_server/requirements.txt`, with only `mcp_server/` copied in (no `hr_agent` importable
  at all). Confirmed clean start and correct Host-allowlist behavior (wrong host -> 421,
  correct host -> normal protocol-level 400, not silently open) against a simulated Cloud Run
  hostname. Re-verify the real `docker build` once Docker Desktop is available, before
  trusting this over the manual reproduction.
  Client-side ID-token auth implemented: `hr_agent/config.py` adds `HCM_MCP_AUDIENCE` (empty
  default -- explicit opt-in, same pattern as `MCP_ALLOWED_HOSTS` on the server side, not an
  inference from `HCM_MCP_URL`'s shape). `hr_agent/toolsets.py`'s `_caller_headers` attaches
  `Authorization: Bearer <token>` via `google.oauth2.id_token.fetch_id_token` (ADC -- works
  against Agent Engine's runtime service account with no extra wiring) only when the audience
  is set; caller-identity header logic (M6.1) is unchanged and independent -- Cloud Run IAM
  (can this caller reach the service at all) and the `x-caller-employee-id` header (which
  employee is this, for `mcp_server`'s self-only checks) are separate concerns that happen to
  share a header-injection function. Tokens cached in-process keyed by audience, refreshed
  after 50 minutes (Google ID tokens run ~1h) rather than fetched per call. A non-`str`
  return from `fetch_id_token` (it's an untyped API) raises `TypeError` rather than caching
  or silently stringifying garbage.
  New `tests/unit/hr_agent/test_toolsets.py` (6 cases, `fetch_id_token` mocked -- no
  network/ADC): empty-audience/no-caller-id gives `{}`, caller-id-only path unchanged,
  audience-configured path attaches the bearer token, cache reuse within TTL, cache refresh
  past TTL, and the non-str-token rejection. `_caller_headers`/`toolsets.py` had no prior unit
  coverage at all (a pre-existing gap from M6.1, not introduced here) -- this is the first.
  195 unit tests pass; verified local-dev default (`HCM_MCP_AUDIENCE` unset) still returns
  `{}` with no caller/audience, unchanged from before this change.
  Deployed for real (2026-09-29), user approved: `run.googleapis.com`/`cloudbuild.googleapis.com`/
  `artifactregistry.googleapis.com` enabled; Artifact Registry repo `hr-ops-agent`
  (us-central1); image built via `gcloud builds submit --config=deploy/cloud_run/cloudbuild.yaml`
  (Cloud Build, not local `docker build` -- Docker Desktop's daemon still wasn't running, and
  this sidesteps that entirely, no local Docker needed for the real deploy either); deployed
  private (`--no-allow-unauthenticated`) to Cloud Run as service `mcp-server` in us-central1 ->
  `https://mcp-server-976559775904.us-central1.run.app`; `MCP_ALLOWED_HOSTS` updated to that
  service's own hostname post-deploy (couldn't be known before the URL was assigned).
  Found a second `--env_file` fact while wiring the redeploy, corrects the M7.1 note that
  called it a no-op: read `cli_deploy.py` directly (adk 2.9.2) -- unlike `--staging_bucket`
  (genuinely unused), `--env_file` still works when given an explicit path; only the *default*
  (`agent_folder/.env`) is what M7.1 exercised. So `hr_agent/.env` stays localhost-only for
  local dev, and a new `hr_agent/.env.agent_engine` (gitignored via the existing `.env.*`
  pattern, mirrors `hr_agent/.env` but with the real `HCM_MCP_URL`/`HCM_MCP_AUDIENCE`) is
  passed via `--env_file` for the Agent Engine deploy -- resolves the local-vs-deployed env
  tension M7.1 punted on, rather than living with the accepted divergence.
  IAM grant (`roles/run.invoker` for `service-976559775904@gcp-sa-aiplatform-re.
  iam.gserviceaccount.com`, the reasoning engine's real effective identity, confirmed by
  reading the live resource rather than assumed) run by the user after the classifier refused
  it for me -- same class of gate as M7.1's deploy-command block, correctly not something to
  route around.
  Redeploy hit two more real bugs, both caught by checking actual results rather than trusting
  a clean CLI exit:
  1. First redeploy used `--env_file=hr_agent/.env.agent_engine` as a *relative* path. `adk
     deploy`'s `to_agent_engine` calls `os.chdir(temp_folder_path)` before it checks
     `os.path.exists(env_file)` -- the relative path silently resolved to nothing post-chdir,
     `env_vars` stayed `{}`, and the deploy "succeeded" with **zero env vars set at all**
     (confirmed via `GET .../reasoningEngines/...`: `deploymentSpec` was completely empty).
     No warning, no error -- would have shipped silently broken. Fixed by passing an absolute
     path; confirmed via the same GET that all five vars (including the real
     `HCM_MCP_URL`/`HCM_MCP_AUDIENCE`) landed correctly the second time.
  2. Second redeploy failed outright (`streamQuery` -> `FAILED_PRECONDITION`); Cloud Logging
     (filtered to `resource.labels.reasoning_engine_id` + timestamp after the redeploy, per
     M7.1's staleness lesson) showed `ModuleNotFoundError: No module named 'mcp_server'` from
     `hr_agent/tools.py`'s `from mcp_server.mock_data import HOLIDAYS`. Root cause: the
     mock-data-move fix (above) added a real cross-package dependency, but `adk deploy
     agent_engine hr_agent` only packages the `hr_agent` folder itself -- invisible in every
     local test because both packages sit on the same installed `PYTHONPATH` there. Fixed
     with `--extra_packages=mcp_server`, which bundles it alongside `hr_agent` in the
     deployed source tree; `server.py`/`handlers.py` ride along unused (harmless) since only
     `mcp_server.mock_data` is ever imported by the agent side.
  **Verified live end to end** via `:streamQuery` (not just "deploy succeeded"): a payroll-run
  question routed to `payroll_agent`, called `get_payroll_run(run_id="PR-2026-09")` over the
  real network, and got back `mcp_server`'s actual `forbidden` business-error response (M6.1's
  role check) -- not a connection error, not a Cloud Run IAM rejection, a real round trip
  through the Host-allowlist, the ID-token auth, and the server's own guardrail logic. A PTO
  question similarly reached `get_pto_balance(employee_id="E1002")` and got the self-only
  `forbidden` response. Both relayed in plain language by the agent. This resolves the M7.1
  open item ("not yet confirmed... just deployed, not walked through") for real -- Module 6's
  guardrails are now provably exercised against the live deployed agent, not just locally and
  in integration tests.

## Open questions

- Model IDs drift fast (Gemini 2.5 retires 2026-10-20 mid-course) -- reconfirm exact Gemini
  3.x IDs before Module 8's tier-routing work.
- Nothing enforces that the model actually uses `current_employee_id`/`pending_pto_request`
  instead of re-asking or re-submitting, or that it treats memory as reference-only rather than
  identity -- both are prompt rules, not guardrails. Candidate Module 5 eval cases: a repeated
  ID on a second turn, a memory entry with injected instructions, a stale/wrong recalled ID.
- Real Agent Engine + Memory Bank instance not yet created (deferred to Module 7); revisit
  whether provisioning belongs earlier if Module 5 evals need live memory behavior sooner.
- `num_invocations_to_keep=6` is unmeasured; needs real conversation-length/cost data. Reconfirm
  `EventsCompactionConfig`'s stability before relying on summarization over trimming.
- Eval thresholds (`response_match_score` 0.3) and the "all cases pass" claim are from one live
  run each on `gemini-3.5-flash-lite`, not a distribution -- re-run a few times before treating
  the suite as a stable green bar, especially after M6.2's rewrites (none run live yet).
- The router's "unclear vs. a detail the specialist should resolve" distinction has needed two
  separate fixes already from unrelated features -- candidate for its own eval category rather
  than one-off fixes as they're found.
- `identify_caller` (see M6 decisions) is a stub, not real auth -- anyone chatting with the
  agent can claim any employee ID with zero verification, and today's self-only/role checks
  would then correctly honor that claim as if it were true. Fine for a course/demo; would be a
  real vulnerability if this ever shipped as *the* identity mechanism. Replacing it with a
  verified login (SSO/OIDC) remains out of this course's syllabus, per the scope discussion
  that led to building the stub -- revisit if this project is ever used beyond the course.
  No live fixture exercises an authorized `get_payroll_run` or `approve_payroll_run` call
  (payroll-role caller) end to end -- `identify_caller` only sets an ID, and no mock employee
  in `mcp_server/mock_data.py` needs a specific *caller* role tested this way yet.
- Eval suite is down to 29 cases and thinner on the "ambiguous" category after `find_employee`'s
  retirement; still no case exercising the one self-only scenario that matters most -- a caller
  asking about a *different*, valid employee ID and getting `forbidden` from the live agent
  (only `mcp_server` tests cover that today).
- Global idempotency store is unscoped by caller (flagged since M2.2) -- two legitimate
  employees reusing the same key string collide with a spurious conflict.
- `require_confirmation`/`ToolConfirmation` (M6.2) is `@experimental` in ADK 2.9.2 -- reconfirm
  it's stable (or find its replacement) before Module 7 deploys this for real; re-verify the
  `adk web`/`adk run` HITL prompt UX too, since that's also new.
- `approve_payroll_run` (M6.2) has no eval case; adding one needs an `adk eval` case that
  models the confirmation pause and resume, which no existing case does -- work out that
  pattern before the eval suite claims payroll approval is covered.
- M6.4's rate limiter is a single process's in-memory dict -- fine for one `mcp_server`
  instance, but doesn't survive a restart and won't be shared across replicas once Module 7
  deploys more than one. Revisit with a real backing store (Redis, Cloud Armor) at that point.
- M6.4's thresholds (20 calls/60s, 160h/request) are engineering judgment calls, not measured
  against real usage -- same unmeasured-floor caveat as M5's eval thresholds and M4.3's
  `num_invocations_to_keep`. No audit-log-driven signal yet for what normal call volume or
  request size actually looks like (M6.3's audit log is the natural source once there's real
  traffic to look at).
- M7.1's live Agent Engine instance and the `mcp-server` Cloud Run service (plus its Artifact
  Registry image) are all still running -- tear them all down once Module 7 wraps, per
  checklist item 7. No GKE resources exist to also tear down (7.3 skipped). HCM reachability
  itself is resolved (see the M7 decisions above: `mcp_server` on Cloud Run, IAM-gated,
  verified live end to end) -- no longer open.
- `hr_agent`'s deploy now has an undeclared assumption baked into a manual command
  (`--extra_packages=mcp_server`, needed because `hr_agent/tools.py` imports
  `mcp_server.mock_data`): nothing enforces that a future redeploy remembers this flag, or
  that `--env_file` gets an absolute path -- both failed silently (empty env, then
  `ModuleNotFoundError`) rather than erroring clearly. Worth a checklist item 5 (CI/CD)
  concern: a real deploy pipeline should make both mistakes structurally impossible, not
  rely on remembering this paragraph.
