# Guardrail standard

Four independent layers protect every write (and the two self-service reads that expose
personal data): permission boundaries, human-in-the-loop confirmation, an audit log, and
rate/blast-radius limits (M6.1–M6.4). They compose rather than substitute for each other —
each one catches a failure mode the others don't. Rules below come from `mcp_server/`,
`hr_agent/toolsets.py`, `hr_agent/audit.py`, and `hr_agent/agents/`.

## The four layers

| Layer | Where enforced | Stops |
|---|---|---|
| Permission boundaries | `mcp_server/handlers.py` (hard); prompt rules (soft) | A caller acting on someone else's data, or without a qualifying role |
| HITL confirmation | ADK's `require_confirmation` on the MCP toolset | A write executing the instant the model decides to call it — hallucinated input, prompt injection |
| Audit log | `AuditLogPlugin`, app-wide | No record of what happened — after-the-fact investigation, not prevention |
| Rate / blast-radius limits | `mcp_server/handlers.py` | A single call, or a burst of calls, doing more damage than one legitimate action should |

Only the first and last are hard, server-side gates. Confirmation depends on a human paying
attention; the audit log depends on someone looking at it. None of the four assumes the model
behaves — each is designed to hold even when it doesn't.

## Permission boundaries (M6.1)

Caller identity flows from the transport only, never a tool argument the model could supply:
`hr_agent/toolsets.py`'s `header_provider` turns session state (`caller_employee_id`) into an
`x-caller-employee-id` header per MCP call; the server reads it via a `ctx: Context` parameter
that isn't part of the published schema — the model never sees it, so it can't be prompt-
injected into passing a different one.

Two enforcement shapes, picked by what the tool exposes:

- **Self-only** (`get_employee`, `get_pto_balance`, `submit_pto_request`): `forbidden` unless
  the target ID matches the caller's own — checked before any lookup or idempotency-store
  access, so an unauthorized caller can't learn whether a target even exists.
- **Role-gated** (`get_payroll_run`: Payroll Specialist or Finance Director;
  `approve_payroll_run`: Finance Director only): no per-employee scoping question, only who
  holds the role. The two write-adjacent tools use different reader sets deliberately —
  separation of duties, not an oversight.

**Known gap:** no production code sets `caller_employee_id` (no login flow yet) — every MCP
tool fails closed for a real user until Module 7+ adds real auth. Correct today, not
acceptable to ship past that point.

## Human-in-the-loop confirmation (M6.2)

Every write (`submit_pto_request`, `approve_payroll_run`) pauses for explicit human approval
before it executes, via ADK's native `require_confirmation` (`ToolConfirmation`,
`@experimental` in ADK 2.9.2) rather than a hand-rolled `before_tool_callback` gate: the tool
call emits an `adk_request_confirmation` function call with a hint, and only resumes once the
human approves or rejects. Both `adk web` and `adk run` render and drive that exchange
natively.

`require_confirmation` is a **toolset-wide** flag, not per-tool — `McpToolset` applies it to
every tool it serves. That's why every specialist that has a write tool carries two toolsets,
not one: reads stay auto, the write gets its own toolset instance
(`pto_write_toolset`, `payroll_write_toolset`) with `require_confirmation=True`. Get this
wrong (one toolset covering both a read and a write) and the read pauses too.

Confirmation is **not** authorization — it runs *after* the permission check, not instead of
it. A caller with no valid role never reaches the pause; they get `forbidden` first.

**Known gap:** `ToolConfirmation` is `@experimental`; reconfirm its stability (or find its
replacement) before Module 7 deploys this for real.

## Audit log (M6.3)

`AuditLogPlugin` (`hr_agent/audit.py`) hooks `before_tool_callback`/`after_tool_callback`/
`on_tool_error_callback` at the **plugin** level (`google.adk.plugins.BasePlugin`), wired
app-wide via `App(plugins=[...])` — it fires once per tool call across every specialist and
both local and MCP tools, unlike a per-agent `after_tool_callback`, which only sees that one
agent's own calls.

**Records are allowlisted, not blocklisted.** `args`/`result` dicts are redacted down to
identifiers and outcomes (`employee_id`, `run_id`, `status`, `code`, `request_id`,
`run_status`, `replayed`) — a field must be named to reach the log. This drops free-text
business-error messages, which can embed a balance (`submit_pto_request`'s "Request needs 16h
but balance is 8h."), and a tool exception logs its type name only, never `str(error)`. When
adding a field to a result, decide deliberately whether it belongs in the audit trail; the
default is that it doesn't.

**Known gaps:**
- A plugin only applies to the `App` it's registered on. Code (or a test) that runs
  `root_agent` directly bypasses it entirely — `hr_agent/agent.py`'s own comment flags this for
  `ContextFilterPlugin` too.
- The ADK-generated confirmation-pause/reject dict has no `status`/`code` field to redact to,
  so a paused or rejected write logs an empty `result` — the call, agent, tool, and caller are
  still recorded, just not which of the two outcomes it was.

## Rate and blast-radius limits (M6.4)

Two independent, complementary bounds, both server-side:

- **Rate limiting** bounds *how often* a caller may write: an in-memory sliding window of call
  timestamps keyed by `(caller_id, tool_name)`, 20 calls per 60s. Every call attempt counts,
  including one that fails later validation — otherwise a caller could probe with malformed
  input for unlimited free attempts. Per-tool, not shared: exhausting `submit_pto_request`'s
  budget doesn't block `approve_payroll_run`.
- **Blast radius** bounds *how much* a single call can do, independent of frequency:
  `submit_pto_request` rejects any request over 160h (20 working days) regardless of balance
  or confirmation. `approve_payroll_run` has no equivalent — one call approves exactly one
  already-bounded run, so its blast-radius protection is the role gate, confirmation, and rate
  limit alone.

Both checks run before the idempotency store or any business validation, folded into the same
helper that already checks caller identity — so a rejected call for either reason never
touches the write path.

**Known gaps:** the limiter is one process's in-memory dict — doesn't survive a restart, won't
be shared across replicas once Module 7 runs more than one. Thresholds (20 calls/60s, 160h)
are engineering judgment, not measured against real usage; M6.3's audit log is the intended
source of that data once there's real traffic.

## Adding a new write tool

1. **Identity or role check, first, before any lookup.** Self-only if the tool exposes one
   person's data; role-gated if it's an aggregate or organizational action. Never trust an
   `employee_id`-shaped argument as identity.
2. **Idempotency key**, caller-supplied, checked before any store mutation. Same key + same
   args replays; same key + different args conflicts. A failed call must not consume the key.
3. **`require_confirmation=True` on its own toolset** — not shared with any read tool, and not
   shared with a different write tool unless they should genuinely pause together.
4. **Rate limit + blast-radius check**, folded into the same precondition helper as identity
   and idempotency-key validation, before the idempotency store. Decide whether the tool has a
   continuous "how much" dimension worth capping (like PTO hours) or is already a bounded unit
   of work (like approving one run).
5. **No new agent instruction needed** for a plain `{"status": "error", "code": ...}` result —
   the router-level "tell the user plainly what went wrong" rule already covers it. Only add an
   instruction rule for a result shape the model would otherwise misread, like a confirmation
   pause (which isn't a normal error at all).
6. **Nothing to wire for the audit log** — the plugin is app-wide and tool-agnostic. Only touch
   `hr_agent/audit.py` if the new result carries a field worth allowlisting.
7. **Unit tests need a reset fixture** for any new module-level store (idempotency map, rate
   counter) — this codebase's test suite reuses the same caller IDs across many test
   functions, and state that isn't reset between tests eventually trips its own guardrail.

## Known open gaps across all four layers

- No production code sets `caller_employee_id` — every MCP tool is correctly unreachable for a
  real user until Module 7+ auth exists.
- The idempotency store is unscoped by caller (M2.2) — two legitimate employees reusing the
  same key string collide with a spurious conflict.
- No eval case exercises confirmation pause/resume, a caller-identity `forbidden` case, rate
  limiting, or the blast-radius cap — each needs an `adk eval` pattern this suite doesn't have
  yet.
- No dashboard or alerting reads the audit log; it is written, not yet watched (Module 8).
