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
- [ ] 2. Deploy to Cloud Run (`adk deploy cloud_run`)
- [ ] 3. Deploy to GKE (`adk deploy gke`)
- [ ] 4. Least-privilege service account, Secret Manager
- [ ] 5. CI/CD with eval gate, staging then prod
- [ ] 6. Compare with Agent Starter Pack layout
- [ ] 7. Tear down unused resources
- [ ] 8. `docs/07-deployment-tradeoffs.md`

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
- No production code sets `caller_employee_id` (no login flow) -- all five MCP tools
  (including M6.2's `approve_payroll_run`) are correctly unreachable for a real user until
  real auth exists; decide whether that's acceptable to ship as-is or needs a stub identity
  source sooner. No live fixture exercises an authorized `get_payroll_run` or
  `approve_payroll_run` call (payroll-role caller) end to end.
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
- M7.1's live Agent Engine instance is still running (idle time isn't billed per Vertex AI
  pricing, but it's a real resource) -- tear it down along with the Cloud Run/GKE ones once
  Module 7's deploy-target comparison (checklist item 6) is done, per checklist item 7.
  Not yet confirmed via the playground that the deployed agent actually produces the expected
  "router works, tool call fails with a connection error" behavior -- do that before treating
  M7.1 as fully walked through, not just successfully deployed.
- HCM reachability from a cloud-deployed agent (flagged as accepted-for-now in M7.1) needs a
  real decision once Cloud Run comes up: either deploy `mcp_server` somewhere reachable, or
  keep testing deploy targets with tools deliberately broken.
