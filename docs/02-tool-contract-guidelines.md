# Tool contract guidelines

A tool contract is the schema, docstring, and error shape a model sees. The model can only
act on what it says; only the server can enforce anything. Rules below come from
`mcp_server/` (M2.1–M2.5).

## Schemas

- **Strict on the wire, lenient in handlers.** Constrain inputs with
  `Annotated[..., Field(pattern/length)]` so the MCP layer rejects malformed IDs and dates
  before the handler runs and publishes the constraint in the input schema. Handlers still
  normalize (strip/upper) so direct callers and tests aren't brittle.
- **Reject unknown arguments** (`additionalProperties: false`). Otherwise a misspelled
  argument on a write tool succeeds silently with the value dropped. Also blocks smuggled
  fields (`salary`, `approve`) that a later change might start honoring. Requires patching
  the generated arg model (`server.py`); tests catch an `mcp` upgrade breaking it.
- **Typed outputs as `TypedDict` unions on `status`**, with `Literal` error codes, published
  as `outputSchema`. Clients branch on `status` and `code`, never on message text.
- **Rule of thumb for validation placement:** format (regex, length) goes in the schema;
  meaning (impossible date, end before start) is result data (`invalid_dates`), because the
  model can correct it from a message.

## Errors

- **Business errors are results:** `{"status": "error", "code": <Literal>, "error": <message>}`.
  The code is for programs, the message is for the model: say what was wrong and what a
  valid input looks like.
- **Schema violations are protocol errors** (`isError`, raw pydantic text). Clients and the
  agent must handle both paths.
- **Known weakness:** the pydantic text has no example ID and is poor model guidance. A
  server-side rewrite was tried and dropped as too complex; revisit only if agent evals show
  it hurts recovery.

## Writes

- **Caller-supplied idempotency key.** A server-generated key can't dedupe an agent retry.
  Same key + same args replays the original (`replayed: true`); same key + different args is
  `idempotency_conflict`. Failed requests don't consume the key, so a corrected retry works.
- **The model supplies intent, not derived facts.** Hours are computed server-side (weekdays
  minus holidays). Any value the server can compute is never an argument.
- **Say what the write does not do** in the description ("not instantly approved", "does
  not reduce the balance") so the model doesn't over-promise to the user.

## Data and identity

- **Minimize returns.** `get_employee` returns id/name/title only; `get_payroll_run` returns
  aggregates only. Sensitive fields need a separate tool with its own authorization, not a
  wider default payload.
- **Caller identity comes from the transport** (headers/credentials), never a model-supplied
  argument. The model can be prompt-injected; the transport can't. Not implemented yet
  (Module 6); today any caller can query any ID.

## Descriptions and exposure

- Docstring = first line what it does; then when to use it, what it does not return, an
  example value for every ID argument, and the success/error shapes.
- **Expose the minimum.** `pto_agent`'s `hcm_toolset` uses `tool_filter` to expose only
  `get_employee` and `submit_pto_request`. `get_payroll_run` is exposed separately through
  `payroll_agent`'s own read-only `payroll_toolset` (Module 3); the split keeps PTO writes
  and payroll reads on different specialists with different permissions. Fewer tools per
  toolset means better selection and a smaller blast radius.

## Known gaps (deferred)

- **Overdraw race:** balance isn't decremented and pending requests aren't counted, so
  concurrent requests can exceed it. Fix with a real store and transactional check.
- **No human confirmation on PTO writes.** Idempotency stops duplicates, not wrong requests.
  HITL callback in Module 6.
- **No authorization or audit log** at the server. Module 6.
