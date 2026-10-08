# Eval standard

`adk eval` regression suite for `hr_agent`. Rules below come from `evals/` and
`scripts/run_eval_gate.py` (M5.1–M5.5).

## Structure

`evals/{happy_path,ambiguous,adversarial,hcm_down}/` — one `.evalset.json` plus one `test_config.json`
per tier. Each tier gets its own trajectory-matching strictness because the property each
tier is meant to guarantee is different:

- **`happy_path`** (15 cases) / **`ambiguous`** (6 cases): `ANY_ORDER` + `ignore_args: true`.
  These tiers exist to check the model reaches the right tools and the right answer, not the
  exact shape of how it got there. `ANY_ORDER` tolerates legitimate extra calls (e.g. the
  model double-checking a recalled ID) and calls firing out of causal order between
  independent sub-questions in a compound query.
- **`adversarial`** (8 cases): `EXACT` + `ignore_args: true`. These cases exist to guarantee
  *no unexpected extra calls* — a silent retry, a bulk lookup triggered by a prompt-injection
  attempt, a second write after the first should have been rejected. `EXACT`'s job here is
  catching absence of extras, not just presence of the required ones.
- **`hcm_down`** (2 cases): `EXACT` + `ignore_args: true`, plus `response_match_score` 0.8
  because the reply is a fixed string. The gate runs this tier with **no MCP server** and
  `HCM_MCP_URL` pointed at a dead port (`NO_SERVER_TIERS` in `scripts/run_eval_gate.py`).
  Expects `transfer_to_agent` and the turn guard's unavailable message, with no retries or
  loops (M8.4). Only the router hop calls the model.
- **`ignore_args: true` everywhere**: `submit_pto_request`'s `idempotency_key` is
  model-generated and unpredictable, so exact-arg matching would fail cases it shouldn't.
  Argument-level correctness (right employee, right dates, right hours) is pushed onto
  `final_response` text instead.
- **`transfer_to_agent` is a real tool call** (confirmed in
  `google/adk/tools/transfer_to_agent_tool.py`) and is the first hop into every specialist.
  It belongs in every expected trajectory that reaches a specialist (name only — its
  `transfer_reason` arg is freeform text, moot anyway since `ignore_args: true` is set), but
  is **not** repeated on a later same-topic turn: transfer is sticky, so a follow-up either
  makes zero tool calls (answer already known) or just the leaf call.

## What each metric catches, and what it doesn't

- **`tool_trajectory_avg_score`** (threshold 1.0 everywhere): checks which tools were
  called, in what order, with what args (all relaxed per-tier above). Blind to response
  text — a case can score 1.0 while the final answer is garbage (e.g. "connection was
  closed, please try again" scored 1.0 because the *tools* called were still correct; see
  M5.3). Never rely on this alone for a case where wording matters.
- **`response_match_score`** (ROUGE-like, threshold 0.3 on `happy_path`/`ambiguous`, not used
  on `adversarial`): checks response text against a golden string. Cheap, but penalizes
  correct answers that are lexically dissimilar to the golden — two valid salary-refusal
  phrasings scored 0.13 apart for no behavioral reason. That's why it's dropped from
  `adversarial` entirely rather than tuned lower: no threshold rescues that without also
  passing near-empty responses elsewhere.
- **Rubric-based LLM-as-judge** (`rubric_based_final_response_quality_v1`, `adversarial`
  only, threshold 0.8, `judge_model` pinned to this project's `MODEL_ID`, `num_samples: 5`
  for majority-vote ties): checks response *content* against a natural-language rubric, not
  a fixed string. This is what actually catches the trajectory-blind case above — a rubric
  scoring "does this response state a specific rejection reason, not a transport error" can
  fail a case that `tool_trajectory_avg_score` passed. One generic criterion-level rubric
  (`no_fabricated_outcome`, in `test_config.json`) applies to every adversarial invocation;
  case-specific rubrics (`declines_salary_disclosure`, `rejects_injected_instruction`,
  `states_specific_rejection_reason`, `no_duplicate_created`,
  `reports_idempotency_conflict`) live on `Invocation.rubrics` in the evalset and only apply
  when `rubric_type == "FINAL_RESPONSE_QUALITY"` matches exactly — a mismatched type string
  is silently dropped, not an error, so double-check it when adding one.
- **None of the above cover cross-session memory recall** (`load_memory`): an `EvalCase`
  conversation is one session, and relying on the eval runner reusing one `user_id`'s
  `InMemoryMemoryService` state across separate cases was judged too fragile to build a
  regression case on. Worse for the real backend: `adk eval` never passes a `memory_service`,
  and the runner falls back to `InMemoryMemoryService()` (no flag or env override, adk 2.9.2),
  so a case would silently test the stub, not Memory Bank. That path is covered only by live
  integration tests, outside this suite and outside CI: `test_memory_live.py` (stub) and
  `test_memory_bank_live.py` (real Memory Bank, billed).

## Launch bar (docs/PROGRESS.md M5.4)

Four dimensions; only one is mechanically gated today.

| Dimension | Bar | Enforced by CI today? |
|---|---|---|
| Task success | All 31 cases pass their tier's criteria | On demand only — `scripts/run_eval_gate.py` via manual `workflow_dispatch` (live, billed model calls); not on PRs |
| Zero unauthorized access | Zero tolerance | Not by evals — enforcement is server-side (caller-identity, self-only and role checks, Module 6) and covered by `mcp_server` unit tests. Cases seed `caller_employee_id` but none asserts `forbidden` (e.g. a different, valid employee ID, or a wrong-role payroll caller) against the live agent. Documented gap. |
| p95 latency | <5s read turn, <10s write turn | No — measured on the dashboard (`docs/08-dashboard.md`), alert-only. Unmeasured starting floor; the dashboard can't split read from write turns. |
| Cost/task | <$0.01 read, <$0.02 write on the configured Flash tier | No — measured on the dashboard (`docs/08-dashboard.md`), alert-only. First reading ~$0.0026/turn on 9 mixed turns. |

Task success is a fixed regression suite, not a sampled rate — "all cases pass," not "N%
pass." Do not treat this table's unenforced rows as silently satisfied; they are open blockers on
calling the agent launch-ready, independent of what the CI gate can mechanically check.

## CI gate mechanics (`scripts/run_eval_gate.py`)

- One `adk eval hr_agent <evalset>` invocation **per tier**: `test_config.json` auto-pickup
  only works when exactly one evalset file is passed per invocation.
- A **fresh MCP server subprocess per attempt**, never a shared long-lived one. Root cause
  logged in M5.2/M5.3: a shared server's in-memory idempotency store outlives any single
  `adk eval` run, so a low-entropy model-generated key (or a case's hardcoded literal key,
  e.g. `demo-key-1`) can collide with what an earlier run already recorded, turning a
  should-succeed turn into a false `idempotency_conflict`.
- **Bounded retry (3 attempts, fresh server each time)**, gated on matching one of a fixed
  set of transient-failure markers (`oauth2.googleapis.com`, `Read timed out`, `Connection
  closed`) already documented as occasional, not agent bugs. A failure that doesn't match
  fails immediately — no blanket retry-on-red. Do not widen the marker list to make an
  actual regression go away; if a new failure mode turns out to be genuinely transient,
  confirm that first (reproduce, root-cause) the way M5.1–M5.3 did, then add its exact text.
- Prints the launch-bar coverage caveat above on every run so a green gate can't be misread
  as "everything in M5.4 is covered."

## Adding a new eval case

1. **Pick the tier by what property it's meant to guarantee**, not by topic: does it need to
   tolerate extra/out-of-order calls (`happy_path`/`ambiguous`), or must it fail on any
   unexpected call (`adversarial`)?
2. **Write the golden `final_response` for real** — not a placeholder string. Two lazy
   `"... "` placeholders silently zeroed out `response_match_score` for real cases in M5.1
   until caught; the metric can't tell a placeholder from a genuine failure.
3. **Decide if it needs a rubric.** If correctness depends on response *content* in a way a
   fixed string can't capture (a refusal, a specific error explanation, "don't fabricate
   success"), add a case rubric with `"type": "FINAL_RESPONSE_QUALITY"` rather than trying to
   force `response_match_score` to cover it.
4. **If it writes with `submit_pto_request` and needs to test idempotency behavior against a
   fixed key**, know that the key becomes a one-time-use fixture from the server's point of
   view: the case will only pass against a server that hasn't already recorded that key.
   `scripts/run_eval_gate.py`'s per-attempt fresh server handles this in CI; running the case
   manually against a long-lived `mcp_server` will not reproduce a clean pass on a second try.
5. **Authorization cases are now fair game, and the most valuable missing kind.** Module 6
   enforces caller identity and role server-side, so a refusal (`forbidden`) is intended
   behavior, not a gap. Seed `caller_employee_id` under `session_input.state`, as the existing
   cases do; it reaches the server through the same header path real traffic takes. Never
   encode the caller as a tool argument.
6. **Expect `transfer_to_agent`** as the first call in any expected trajectory that reaches a
   specialist for the first time in that conversation, and omit it on a same-specialist
   follow-up turn.

## Known open gaps

- No authorization case: a caller asking about a *different*, valid employee ID and getting
  `forbidden`, or a caller with the wrong role on `get_payroll_run`/`approve_payroll_run`. Only
  `mcp_server` tests cover that today.
- No case models the `require_confirmation` pause and resume (`submit_pto_request`,
  `approve_payroll_run`), and `approve_payroll_run` has no case at all; work out the
  confirmation pattern before claiming payroll approval is covered.
- No case exercises cross-session memory recall, stale/incorrect recalled identity used
  without re-resolution, or a memory entry containing injected instructions (candidates
  noted since M4.2/M4.4).
- No case exercises the router treating "a detail is missing" as "the request is unclear"
  as a category of its own — two real bugs of this shape were caught by hand (M3 router
  fixes #1/#2), not by this suite.
- `response_match_score` thresholds (0.3) and rubric `num_samples`/`judge_model` choices are
  calibrated from limited live runs, not a measured distribution. Revisit with real
  production data once Module 8's dashboard exists.
