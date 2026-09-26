# When to use an agent

Default to the least autonomous pattern that meets the requirement. Autonomy buys
flexibility and costs predictability, latency, tokens, and auditability.

## Three patterns

| Pattern | Control flow | Wins when | Main cost |
|---|---|---|---|
| Workflow | Fixed in code; LLM only at leaf steps (classify, draft, extract) | Steps are known and order matters; compliance needs a reproducible path | Brittle to inputs the flow didn't anticipate |
| Single agent | LLM picks tools in a loop | Few tools, open-ended questions, one domain | Nondeterministic path; cost and latency scale with steps |
| Multi-agent | Router delegates to specialists | Tool count or context outgrows one prompt; domains need different permissions | Extra hops, routing errors, harder evals and tracing |

## HR examples

- **Workflow — payroll-cutoff reminder.** Trigger, query approvers with pending items, send
  notice. The path never varies and the action is outward-facing, so an LLM deciding whether
  to send is pure risk. At most use an LLM to draft the wording.
- **Single agent — PTO/holiday Q&A (this repo).** Questions vary ("Jane's PTO and next
  holiday?") but the tools are three read-only functions in one domain. The loop in
  `hr_agent/agent.py` is enough.
- **Multi-agent — "I'm moving states: what changes for benefits, withholding, and PTO?"**
  Spans benefits, payroll, and policy, each with different data sensitivity. Specialists
  allow per-domain tools, permissions, and evals; a single agent would hold all tools and
  all data in one context.

## Where reliability comes from

Not from prompt wording. From layers outside the model:

- **Tool contracts:** typed args, docstrings as the model-facing spec, errors returned as
  data with actionable messages (`hr_agent/tools.py`).
- **Bounded loop:** `MAX_STEPS`, tool failures as observations
  (`scratch/react_from_scratch.py`). `MAX_STEPS` bounds steps, not cost.
- **Tests and evals:** unit tests pin tool behavior; integration tests assert the tool
  trajectory before the wording; evals (Module 5) gate CI.
- **Hard gates in code:** anything that must never happen (wrong-employee access, unapproved
  write) is enforced in the tool/server layer, not requested in the prompt.

Prompt rules such as "never guess an ID" reduce failures but give no guarantee. Treat them
as the soft layer over the hard ones.

## Risk the framework doesn't handle: access control

ADK runs the tools; it does not decide who may see whose data. Today any caller can ask
`get_pto_balance` for any employee ID, and `find_employee` will resolve any name. The
"ambiguous means ask, don't pick" rule is prompt-enforced only.

Owner: the MCP server (Module 2) must authorize every call against the caller's identity,
taken from the transport (token/session), never from a model-supplied argument. Module 6
adds human-in-the-loop approval and the audit log. Until then this agent is safe only on
mock data.
