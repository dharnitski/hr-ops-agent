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
- [ ] 3. LLM-as-judge rubric
- [ ] 4. Launch bar (task success, zero unauthorized access, p95 latency, cost/task)
- [ ] 5. Wired into CI as a gate
- [ ] 6. `docs/05-eval-standard.md`

## Module 6 — Safety and governance
- [ ] 1. Permission boundaries in tool/MCP layer (act as requesting user)
- [ ] 2. Human-in-the-loop callbacks (PTO confirm, payroll manager approval)
- [ ] 3. Audit log of every tool call
- [ ] 4. Rate / blast-radius limits
- [ ] 5. `docs/06-guardrail-standard.md`

## Module 7 — Deploy to the cloud
- [ ] 1. Deploy to Agent Engine (`adk deploy agent_engine`)
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
- M3 router fix (found during M4 testing): `test_two_questions_in_one_message` was flaky
  (~1/3 failure rate) with the router declining a compound question outright, in ~1.8s with no
  transfer at all -- both parts ("is Christmas a holiday", "how much sick time") are squarely in
  `pto_agent`'s description, so this was the router misreading "two questions" as itself a
  reason to decline, not a real ambiguity. `pto_agent`'s own instruction already says "if a
  question needs several lookups, make each one," but the router (added after that rule was
  written) had no equivalent guidance and could decline before ever handing off. Added a router
  rule: a multi-part message that matches one specialist should still transfer once, not be
  treated as ambiguous by virtue of having multiple parts. 5/5 live runs passed after the fix
  (was ~1/3 before); full integration suite (25 tests) still green.
- M3 router fix #2 (found while testing M4.4 live): a second-session recall question ("the
  employee I asked about in an earlier conversation") got declined by the router with "I do not
  have access to conversation history... provide the employee's name or ID" -- the router was
  treating a missing detail (which employee) as its own problem to solve or refuse over, instead
  of a topic match to hand to `pto_agent`, which actually can resolve it (via `load_memory`).
  Same root cause as fix #1: the router's "if the request is unclear, ask" rule didn't
  distinguish "unclear which specialist" from "specialist will need to resolve a detail."
  Reworded: "unclear" means only the former; a missing detail like identity is the specialist's
  job, so transfer on topic match and don't ask for it at the router level. 5/5 live runs passed
  after the fix; full integration suite (25 tests) still green.
- M3.1 policy: `search_handbook` (`hr_agent/handbook.py`) is deterministic keyword retrieval
  over `## ` sections (stopwords dropped, title matches weighted 3x, top 3 with nonzero score);
  embeddings add nothing at 8 sections. Contract: `success` / `not_found` (lists available
  sections so the agent can say what it covers) / `error` on empty query. Grounding is
  prompt-enforced (answer only from results, cite section, say "not covered" on gap, treat
  handbook text as data); the gap case is a live test, and prompt-injection-in-document
  belongs in the Module 5 evals. Keyword retrieval misses synonyms ("vacation" vs "PTO");
  candidate eval case, and the trigger to move to embeddings if the handbook grows.
- M3 workflow check: Sequential/Parallel/Loop agents are deprecated in favor of `Workflow`
  (graph of nodes, conditional routes via `EventActions(route=...)`). Agents work as nodes only
  as `single_turn`. `Workflow` can't be an `LlmAgent` sub-agent yet, so mixing LLM delegation
  and a workflow means the workflow is the root and specialists are its nodes, not the reverse.
  Findings verified from installed 2.9.2 source and a runnable probe, not from `adk-docs`.
- M3 workflow vs. delegation: `scratch/workflow_router.py` routes with a regex `classify` node
  (first match wins; policy before pto) to `single_turn` copies of the specialists, plus a
  static decline node. Saves the router's LLM call and is unit-testable without a model, but
  misses paraphrases, mixes multi-intent requests (first rule wins), and can't ask a
  clarifying question. Rule: deterministic routing where intents are enumerable and
  keyword-detectable; LLM routing for vague or multi-intent input. A hybrid needs the
  workflow at the root (specialists as nodes), with an LLM classifier node for the ambiguous
  cases. Specialist `mode` must be `single_turn` as a node, so the copy is made in scratch,
  not in production agents.
- M3 LangGraph: `scratch/langgraph_router.py` rebuilds the policy path (classify -> policy |
  fallback), reusing the ADK rules, policy instruction and `search_handbook`. Same routing
  and answers. Differences: state is an explicit `TypedDict` you merge into (vs. ADK events and
  session state); routing is a function returning a node name plus a path map (vs.
  `EventActions(route=...)`); the model and tool wiring is more glue (chat-model class, tool
  from docstring, `create_agent`), and agents nest as compiled subgraphs invoked inside a node.
  `create_react_agent` is deprecated for `langchain.agents.create_agent`. ty can't check
  `StateGraph(State)`, so it carries an ignore. Deps live in the dev group only.
- M3 architecture: `docs/03-architecture.md` (Mermaid) marks soft controls (prompts, routing
  descriptions, `tool_filter`) vs. hard ones (schema, server-side hours, idempotency) and shows
  Module 6 controls as planned. Local tools bypass the MCP boundary, so they sit outside the
  hard layer until identity checks exist.
- M3 doc: `docs/03-adk-vs-langgraph.md` recommends staying on ADK for this project, specifically
  because Module 7's deploy path and the MCP toolset are already ADK-native — not a general
  framework verdict. Deterministic-vs-LLM routing trade-off (enumerable/keyword-detectable
  intents vs. paraphrases/multi-intent/clarifying questions) is orthogonal to which graph
  framework is used. Flags re-verifying before Module 8: whether `Workflow` can be an
  `LlmAgent` sub-agent yet, and `create_agent`'s API stability.

- M4.1 session state: `current_employee_id` and `pending_pto_request` are session-scoped
  (`tool_context.state`), gone once the session ends -- the boundary to contrast against M4.2's
  cross-session memory bank. `find_employee`/`get_pto_balance` (local tools) take a
  `tool_context: ToolContext` param and write state directly; ADK detects the param by type
  (not name) and excludes it from the schema the model sees. `get_employee`/`submit_pto_request`
  are MCP tools and can't take that param, so `pto_agent` has an `after_tool_callback`
  (`_track_mcp_results`) that reads every tool call's result and writes state from the MCP
  wire shape (`structuredContent.result`, `isError`) -- returning `None` leaves the model-visible
  response untouched, so this stays purely observational. Both keys surface to the model via
  `{current_employee_id?}` / `{pending_pto_request?}` instruction templating (the `?` makes an
  unset key render as empty instead of raising). Reusing a person's remembered ID happens by
  prompt instruction, not code -- there's no enforcement that the model actually uses it.
  Live-model test found `after_tool_callback`'s `tool_response` can arrive as `None` even though
  ADK's own `AfterToolCallback` type alias declares it always a dict (docstring says
  long-running/deferred tools can reach the callback before a result exists); the callback
  guards with `isinstance(tool_response, dict)`, not just `is not None`, in case a tool ever
  returns something else non-dict. Broke `scratch/react_from_scratch.py`, which called
  `find_employee`/`get_pto_balance` directly with no ADK session -- fixed by giving scratch its
  own plain-dict state and thin wrapper functions (duck-typed stand-in for `ToolContext`, not a
  real one), keeping the "no ADK" scratch exercise honest instead of pulling in ADK's session
  machinery just to satisfy the type.

- M4.2 long-term memory (interface + local stub; live Agent Engine deferred to Module 7 by
  choice): `BaseMemoryService` (`add_session_to_memory` / `search_memory`, scoped by
  `(app_name, user_id)`, not `session_id` -- that's what makes cross-session recall possible)
  is what `VertexAiMemoryBankService` and `InMemoryMemoryService` both implement, confirmed from
  installed `google-adk` 2.9.2 source. ADK ships `InMemoryMemoryService` as an in-process,
  same-interface stub explicitly documented "for prototyping only," so no custom fake was
  needed. `adk web`/`adk run --memory_service_uri` defaults to `memory://` and takes
  `agentengine://<agent_engine_id>` for Module 7 -- swapping to the real service is a CLI flag,
  zero `hr_agent/` code change. `pto_agent` gets `after_agent_callback=_persist_to_memory`
  (`await ctx.add_session_to_memory()`), which re-ingests the full session every turn, not just
  new events (cost concern at real volume, deferred to Module 8). Read side: `load_memory`
  (model-invoked, auditable tool call) over `preload_memory` (silent every-turn context
  injection) -- same data-minimization stance as M2.1's `get_employee`. Instruction treats
  memory results as reference material, never identity: a recalled fact can answer an
  informational question but never sets `current_employee_id` or substitutes for
  `find_employee`/`get_employee` before a write, extending the caller-identity gap already
  tracked since M1.8/M2.4 to the memory layer. First instruction draft was stricter (memory
  could never inform identity at all) and broke on first live run: the router declined a
  recall-only test question outright (it didn't look like a PTO question -- a routing artifact,
  not a memory bug) and, once the test prompt was fixed to route correctly, the strict rule
  would have forced re-asking for the ID on every returning-user balance question, defeating the
  point. Revised: a recalled ID may be used directly for a read (`get_pto_balance`,
  `list_holidays` validate it themselves) but never for `submit_pto_request` without a fresh
  `find_employee`/`get_employee` this session. Found and fixed a second regression:
  `scratch/workflow_router.py`'s bare `Runner` had no `memory_service`, which would have raised
  `ValueError` the first time a live `pto_agent` turn's `after_agent_callback` fired -- gave it
  an `InMemoryMemoryService`, matching what `InMemoryRunner` provides by default everywhere
  else. `tests/unit/hr_agent/test_memory.py` verifies the write path and
  `InMemoryMemoryService`'s own cross-session contract with no model call.
  `tests/integration/hr_agent/test_memory_live.py` (new `sessions` fixture: one runner, fresh
  session per call, same `user_id`) ran live and passed repeatably: a second, fresh session
  recalls the employee asked about in an earlier session and answers their PTO balance without
  re-asking. Tool-call order varies run to run (sometimes the model double-checks a recalled ID
  with `get_employee` before using it) -- the test asserts the outcome (`load_memory` used,
  correct `get_pto_balance` call, no `find_employee`), not an exact sequence.
  `add_session_to_memory`'s full-session write described above is superseded by M4.4 below.

- M4.3 trimming: two distinct ADK mechanisms exist for context growth, confirmed from installed
  `google-adk` 2.9.2 source. Trimming (`google.adk.plugins.context_filter_plugin.ContextFilterPlugin`,
  a `before_model_callback` App-level plugin) drops whole old *invocations* from what's sent to
  the model -- deterministic, free, and it only touches the per-request payload, never
  `session.events`, so it composes cleanly with M4.1 (session state is re-injected into the
  instruction every turn regardless of trimmed history) and M4.2/M4.4 (memory writes are
  independent of the trimmed request either way). Summarizing (`App(events_compaction_config=EventsCompactionConfig(...))`
  with a `BaseEventsSummarizer`) actually condenses old events via an extra LLM call and is still
  `@experimental` in 2.9.2 -- picked trimming as the default for this course-scale project;
  summarizing is the better answer once conversations are long enough that losing older detail
  entirely (rather than just not resending it) becomes the actual problem, revisit post-Module 5
  if eval data shows that. Wired via a new `app = App(root_agent=root_agent, plugins=[...])`
  export in `hr_agent/agent.py` -- confirmed from `agent_loader.py` that `adk web`/`adk run`/`adk
  deploy`/`adk eval` all check for `app` before falling back to `root_agent`, so this is what
  actually reaches production; `root_agent` stays exported too since tests build their own
  `Runner`/`InMemoryRunner` directly around it and don't go through `App` (so the plugin doesn't
  apply in those tests -- acceptable since they're testing behavior other than trimming).
  `num_invocations_to_keep=6` is a starting guess, not measured; candidate for a Module 5/8 eval
  once there's real conversation-length data. `tests/unit/hr_agent/test_context_trimming.py`
  exercises the actual configured plugin instance (not `ContextFilterPlugin`'s internals, which
  are ADK's own) with hand-built `types.Content` sequences -- no model call.

- M4.4 sensitive data out of context: M4.2's `_persist_to_memory` ingested the entire session
  verbatim into Memory Bank on every turn -- exact PTO dates, hours, and sick balances sitting
  in a durable, cross-session-searchable store indefinitely, when cross-session recall only
  ever needed to know which employee the conversation was about. Rewrote it to check
  `callback_context.state` for the resolved employee ID and, if one is set, persist a single
  synthetic `Event` naming only that ID via `Context.add_events_to_memory` -- not the turn's
  real content; nothing is persisted if no employee was resolved (e.g. a holidays-only
  question). `Context.add_memory` (a direct structured `MemoryEntry` write, no synthetic event
  needed) would be the cleaner fit for "just this fact," but `InMemoryMemoryService` doesn't
  implement it -- only `VertexAiMemoryBankService` does (confirmed from source: `add_memory` is
  `BaseMemoryService`'s default `NotImplementedError`) -- so it isn't usable with the local stub
  until Module 7's real resource exists; `add_events_to_memory` works with both today and later.
  Rewriting this surfaced a second router bug while testing live (see M3 router fix #2 above):
  the router declined a recall-only second-session question outright instead of transferring
  and letting `pto_agent` resolve identity via memory -- fixed alongside this change.
  `tests/unit/hr_agent/test_memory.py` asserts the synthetic fact contains the employee ID and
  never the turn's numeric details (e.g. hours), and that nothing is written when no employee
  was resolved; `tests/integration/hr_agent/test_memory_live.py` re-ran live (5/5) against the
  minimized write path with no changes needed to the test itself.

- M5.1 eval set: confirmed from installed `google-adk` 2.9.2 source (not docs, since this is the
  first module-touch of `adk eval`): `EvalCase`/`EvalSet` are pydantic (`.evalset.json`), each
  `Invocation` carries `user_content`, `final_response`, and `intermediate_data.tool_uses`
  (expected `FunctionCall`s). `adk eval` defaults to two metrics: `tool_trajectory_avg_score`
  (threshold 1.0) and `response_match_score` (threshold 0.8, ROUGE-like). A `test_config.json`
  next to the evalset file overrides criteria -- but `_resolve_eval_config_file_path` in
  `cli_tools_click.py` only auto-picks it up when exactly one evalset file is passed per `adk
  eval` invocation, so each tier below must be run (or CI-gated) as its own command, or with
  `--config_file_path` passed explicitly for a multi-file run.
  31 cases across `evals/{happy_path,ambiguous,adversarial}/`, one `.evalset.json` +
  `test_config.json` per directory so each risk tier gets its own trajectory-matching strictness:
  - `happy_path` (15) / `ambiguous` (8): `ANY_ORDER` + `ignore_args: true`. Tolerates legitimate
    extra calls (e.g. the model double-checking a recalled ID, per M4.2's live-run note) and calls
    happening out of causal order between independent sub-questions (the M3-fix-#1 compound-query
    regression case has no real ordering constraint between its two lookups).
  - `adversarial` (8): `EXACT` + `ignore_args: true`. Order is naturally fixed in every case here
    (identity resolution always precedes the write), so `EXACT`'s real job is catching *extra*
    tool calls -- e.g. a silent retry with corrected dates after an `invalid_dates` error, or a
    bulk `get_pto_balance` sweep triggered by the prompt-injection case -- which `ANY_ORDER`/
    `IN_ORDER` would not flag since they only require presence, not absence of extras.
  - `ignore_args: true` everywhere: `submit_pto_request`'s `idempotency_key` is model-generated
    and unpredictable, so exact-arg matching would fail cases it shouldn't. Argument-level
    correctness (right employee ID, right dates, right hours) is pushed onto `final_response`
    text via `response_match_score` instead. `response_match_score` threshold set to 0.3
    (down from the CLI default 0.8) as an unmeasured starting floor, same pattern as M4.3's
    `num_invocations_to_keep` -- no live run has happened yet to calibrate ROUGE similarity
    against this project's actual response phrasing.
  - `transfer_to_agent` is deliberately never in an expected trajectory: it's a real tool call
    (confirmed in `google/adk/tools/transfer_to_agent_tool.py`) but its `transfer_reason` arg is
    freeform model text, and `EXACT`/`IN_ORDER`/`ANY_ORDER` all do per-call dict equality on args
    that appear in the expected list even when `ignore_args` is off for a *different* call in the
    same criterion -- moot here since `ignore_args: true` is set everywhere, but the real reason
    to omit it is that a specialist's real tool call already implies the transfer happened, so
    asserting the leaf tool is sufficient and doesn't require guessing `transfer_reason` text.
  - Cross-session recall (M4.4's `load_memory` path) isn't exercised here: an `EvalCase`'s
    `conversation` is one session, and depending on the eval runner reusing one `user_id`'s
    `InMemoryMemoryService` state across separate `EvalCase`s within a run was judged too fragile
    to build a regression case on. `ambiguous_router_recall_missing_detail` instead proxies the
    same router bug (a missing detail treated as "unclear" instead of the specialist's job) with
    a same-session two-turn conversation using resolved session state, not memory recall; the
    real cross-session path stays covered by the live integration test
    (`tests/integration/hr_agent/test_memory_live.py`).
  - No caller-identity/authorization cases (e.g. "submit PTO for a coworker without asking them",
    "look up a coworker's balance you have no business seeing"): the tool layer has no such
    enforcement yet (tracked since M1.8/M2.4, hard gates deferred to Module 6), so an eval case
    asserting a refusal there would just encode a known, accepted gap as a bug. Candidate for a
    Module 6 eval category once permission boundaries exist server-side.
  - Salary-request cases assert an empty expected tool trajectory and a declining
    `final_response`, not a tool call: `get_payroll_run` returns aggregates only (confirmed,
    `mcp_server/handlers.py:136`) -- there is no tool that could answer "what does X earn", so the
    only thing worth checking is that the model doesn't hallucinate a number or misuse an
    aggregate tool to fake one.
  - All numeric/date facts in golden responses (PTO/sick hours, working-day counts across
    2026-09/-10/-11/-12, which days are holidays) were hand-computed against `mock_data.py` and
    verified against the known Labor Day (Mon)/Thanksgiving (Thu) anchors, not guessed.
  - All 31 cases now pass live (`adk eval hr_agent evals/<tier>/*.evalset.json`, one tier per
    invocation, gemini-3.5-flash-lite). Getting there surfaced four real bugs, none of them in
    the agent itself:
    1. **`adk eval`'s loader was incompatible with this package**, unrelated to the eval cases.
       `cli_eval._get_agent_module` re-execs `hr_agent/__init__.py` under a synthetic top-level
       module name `"agent"` (confirmed from source, not docs). `hr_agent/agent.py` and
       `hr_agent/agents/*.py` used absolute `from hr_agent.X import Y` imports, so resolving them
       during that synthetic exec forced Python to *also* import the real `hr_agent` package
       (importable because the repo root is on `sys.path`), fully constructing `root_agent` a
       second time with the same singleton `pto_agent`/`payroll_agent`/`policy_agent` objects --
       crashing with a pydantic "already has a parent agent" error on the second `Agent(...)`
       construction. Reproduced minimally outside `adk eval` to confirm before touching code.
       Fixed by switching those intra-package imports to relative (parent-relative `..` in
       `hr_agent/agents/*.py`, sibling `.` in `hr_agent/agent.py`/`toolsets.py`/`tools.py`), which
       makes the whole module graph resolve consistently under whichever top-level name it's
       loaded as -- real `hr_agent` for tests/`mcp_server`, synthetic `agent` for `adk eval`.
       This conflicts with the project's `TID252` ("prefer absolute imports") convention, so
       added a scoped `pyproject.toml` per-file-ignore for `hr_agent/agents/**` with a comment
       explaining why, rather than weakening the rule repo-wide. `adk web`/`adk run` were
       apparently never affected (different, non-synthetic loading path) -- this bug was latent
       since M3 and only surfaced now because `adk eval` had never been invoked before M5.1.
       145 unit tests, `ruff`, and `ty` all still green after the change.
    2. **`transfer_to_agent` is a real tool call** (confirmed in
       `google/adk/tools/transfer_to_agent_tool.py`) and always fires as the first hop into a
       specialist. The adversarial tier's `EXACT` match_type fails on any actual call *not* in
       the expected list -- so every adversarial case that expected a specialist's tool call was
       failing outright (score 0.0) because `transfer_to_agent` was always an unexpected extra.
       Fixed by adding it explicitly (name only, via a `transfer(agent_name)` helper; args are
       ignored anyway since `ignore_args: true`) as the first expected call in every case that
       reaches a specialist -- and *not* repeating it on a later turn that stays with the same
       specialist (confirmed from the live sessions: transfer is sticky, a same-topic follow-up
       turn has zero tool calls if the answer's already known, or just the leaf tool call if not).
    3. **Two golden `final_response`s for the policy cases were lazy `"... "` placeholders**
       instead of real content, so `response_match_score` was correctly near-zero against them
       regardless of any threshold -- not a threshold-calibration problem, a content gap. Fixed
       by writing out the actual handbook text (this project's own fixture data, not third-party
       material) for all four policy happy-path cases and the adversarial injection case.
    4. **`ambiguous_router_recall_missing_detail` turn 2 over-specified the expected trajectory**:
       it required a fresh `get_pto_balance` call, but the model correctly answered from what
       turn 1's tool result already gave it, with zero new tool calls -- the same pattern already
       handled correctly in the sibling `ambiguous_session_identity_reuse` case. Fixed by
       expecting `[]` for that turn too; the real check for this regression is response content,
       not trajectory, and both cases now say so implicitly by leaving it empty.
    Also found, not fixed (both infrastructure, not case bugs, logged for M5.5's CI-gate design):
    running a full tier as one `adk eval` invocation occasionally hits `HTTPSConnectionPool
    (oauth2.googleapis.com): Read timed out` (ADC token refresh contention under concurrent
    inference) and transient MCP "Connection closed" (single uvicorn process under concurrent
    sessions) -- ADK's own retry logic absorbed the latter on a subsequent run, but not always;
    a CI gate should expect occasional retries rather than treating one red run as conclusive.
    Dropped `response_match_score` from the adversarial tier's `test_config.json` entirely
    (kept for happy_path/ambiguous): its ROUGE-style scoring gave near-zero on some clearly
    correct refusals (e.g. two valid but lexically dissimilar salary-refusal phrasings scored
    0.13) -- no threshold rescues that without also passing near-empty responses elsewhere, so
    for this tier `tool_trajectory_avg_score` (now real, via finding 2) is the only gate until
    an LLM-as-judge exists (M5.3).

- M5.1 flake fix: `adversarial_idempotency_conflict_same_key_diff_args` failed on a later live
  re-run (1 of 2), not caught by the checks above -- turn 2 called `submit_pto_request` *twice*
  with identical args (same reused key, same new dates) before reporting the conflict, tripping
  `EXACT`'s call-count check. Confirmed benign (idempotent key+args, no double-write) but real
  model non-determinism, reproduced then re-verified fixed (3/3 clean live re-runs of that case).
  Considered three fixes: loosen just this case's match_type (narrow, weakens the "no extra
  calls" adversarial property further), tighten `pto_agent`'s prompt (chosen), or accept as
  documented flakiness. Chose the prompt fix: `hr_agent/agents/pto.py`'s "tool returns
  status error" rule only said not to retry with made-up input, leaving a same-args retry
  unaddressed; added "do not repeat the identical call again hoping for a different result."
  This is a real behavior improvement independent of the eval (fewer redundant round-trips on
  any business-logic error, not just idempotency conflicts), not just a fix aimed at making a
  test green. Left the M2.3-established "fix the argument format once" retry-on-schema-
  rejection rule untouched -- that's a different, intentional one-retry case (malformed
  input), not the same-args business-error retry this rule targets.
  Underlying gap not addressed: dropping `response_match_score` from the adversarial tier
  (finding above) means `tool_trajectory_avg_score` with `ignore_args: true` can't distinguish
  "retried with identical args" from "silently retried with a *different* key and reported false
  success" -- both look like just an extra `submit_pto_request` call. Still open; the honest fix
  is the same one already deferred to M5.3 (LLM-as-judge / rubrics), not another prompt patch.

- M5.2 (running the eval, `adversarial_submit_pto_insufficient_balance` removed): re-running all
  three tiers surfaced a case flaking on stale server state, not model behavior --
  `submit_pto_request` was called twice: first with a key the MCP server rejected as
  `idempotency_conflict` (recorded by an *earlier, separate* `adk eval` invocation against the
  same long-lived server process), then a second, different key that reached the real
  `insufficient_balance` error and passed. The server's idempotency store is an in-memory dict
  (M2.2) that outlives any single `adk eval` run, and the model's key for a given prompt is
  low-entropy enough (e.g. `pto-cg20261005`, derived from initials+date, not random) to collide
  with what a prior run already recorded for the identical case. Root cause is test isolation
  (`adk eval` reuses whatever MCP server is already running instead of a fresh one per run,
  unlike `tests/integration/conftest.py`'s `hcm_server` fixture), not a case or agent defect --
  the case passed cleanly (10/10 on retry) once run against server state that hadn't already
  seen it. Removed the case anyway on explicit instruction, trading away real insufficient-
  balance coverage rather than fixing the shared-server root cause; the same collision can hit
  any other write-path adversarial case on a later rerun. Candidate fix for M5.5 (CI eval gate
  needs this regardless): start a fresh MCP server subprocess per `adk eval` invocation.
- M5.2 (`adversarial_payroll_run_unknown_id` removed): confirms the above wasn't isolated to one
  case. Immediate rerun of the trimmed 9-case adversarial tier failed a *different, unrelated*
  case: `get_payroll_run` right after `transfer_to_agent` hit a transient "no tool with that name
  is available (only: transfer_to_agent)" framework error, then correctly retried with identical
  args once the transfer had actually taken effect and got the real `not_found` response --
  reasonable model behavior, but the extra call still fails `EXACT` match. Distinct root cause
  from both the idempotency-key collision above and the M5.1 flake fix (same-args retry on a
  business error, there patched only in `pto_agent`'s instruction, not `payroll_agent`'s). Removed
  on explicit instruction rather than root-causing; two cases now gone from a tier meant to
  guarantee *no unexpected extra calls*, and a third rerun could plausibly fail a third, still-
  passing case the same way. Do not treat 8/8 adversarial as a stable green bar without addressing
  the underlying causes (shared MCP server state, `EXACT` intolerant of justified retries,
  inconsistent no-repeat instruction coverage across specialists) -- flagged, not fixed.

## Open questions

- M2: schema-layer rejections return raw pydantic text with no example ID. A server-side
  rewrite (subclass overriding `call_tool`) was tried and dropped as too complex; leave to
  clients unless it proves to hurt agent behavior. Note for `docs/02-tool-contract-guidelines.md`.

- Model IDs drift fast (Gemini 2.5 shuts down 2026-10-20 mid-course) — reconfirm exact
  Gemini 3.x IDs at Module 1 step 1 and again before Module 8.
- M4.1: nothing enforces that the model actually uses `current_employee_id`/`pending_pto_request`
  instead of re-asking or re-submitting -- it's a prompt rule, not a guardrail. Candidate for a
  Module 5 eval case (assert the second turn of a conversation doesn't repeat a resolved ID).
- M4.2: `VertexAiMemoryBankService` import path confirmed (`google.adk.memory`), see decision
  above. "Memory is reference-only, never identity" is a prompt rule, not enforced -- nothing
  stops the model from treating a recalled fact as authoritative if it chooses to. Candidate
  Module 5 eval cases: a memory entry containing injected instructions, and a recalled but
  stale/wrong employee ID the model should not act on without re-resolving.
- M4.2: real Agent Engine + Memory Bank instance not yet created (deferred to Module 7); revisit
  whether `agent_engine_id` provisioning belongs earlier if Module 5 evals need live memory
  behavior before Module 7.
- M4.3: `num_invocations_to_keep=6` is unmeasured; needs real conversation-length/cost data
  (Module 5/8) to tune. `EventsCompactionConfig` is `@experimental` in adk 2.9.2 -- reconfirm its
  stability and whether it's still the summarization answer before relying on it later.
- M5.1: all 31 cases pass live now (see decision above), but on a single run each with
  `gemini-3.5-flash-lite` -- not repeated for flakiness beyond what surfaced incidentally
  (the OAuth/MCP transience). `response_match_score` thresholds (0.3 for happy_path/ambiguous)
  are still calibrated from one run's worth of scores, not a distribution. Before wiring
  `adk eval` into CI (M5.5): decide how to handle the occasional OAuth-timeout/MCP-connection-
  closed retries (accept flaky-and-retry, or make the MCP server more concurrency-tolerant),
  and re-run a few times to see whether any case is borderline rather than solidly passing.
- M4.4: the router misreading "a detail is missing" as "the request is unclear" has now
  surfaced twice (M3 router fix #1 and #2) from two unrelated features -- candidate for a
  Module 5 routing eval category of its own, not just one-off fixes as they're found. The
  synthetic memory fact is free-text, not structured; `InMemoryMemoryService`'s keyword search
  found it fine in testing, but recall quality should be re-verified against the real
  `VertexAiMemoryBankService`'s semantic search once Module 7's resource exists.
