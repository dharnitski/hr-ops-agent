# Failure drill and RCA (M8.4)

Status: drill run 2026-10-07; action items open.

## Drill

Remove `roles/run.invoker` for `hr-agent-runtime` on the `mcp-server` Cloud Run service
(`google_cloud_run_v2_service_iam_member.agent_invokes_mcp_server`), as a bad IAM refactor
would. Inject and restore through Terraform (targeted destroy, then apply). Probe the deployed
engine with `:streamQuery` (`docs/07-deployment-procedure.md`): one PTO-balance turn and one
PTO-request (write) turn, each after giving an employee ID.

## Hypothesis (written before injecting)

The agent can't call HCM, so every turn has no tools. Expected user-visible behavior: the
agent says it can't look this up, or answers without data. Expected worst case: it states a
balance it didn't fetch.

| Panel | Prediction | Why |
|---|---|---|
| Request success rate | No change (~100%) | The engine still returns 200 with text; a failed tool is not a failed request. |
| Tool error rate | No change or no data | No tool result is ever emitted when the MCP toolset fails to load (the blind spot found in 8.2), so the metric has nothing to count. This is the panel most likely to look green. |
| Turn latency p95 | Down or flat | Fewer tool hops. A retry/timeout on the 403 could push it up instead. |
| Cost per task | Slightly down | Fewer model round trips. Not distinguishable from normal variance. |

First signal, in order of expectation: Cloud Run request logs (`mcp-server`, HTTP 403 on
`/mcp`), then agent stderr / Cloud Trace (`MCP send` span errors), then nothing on the
dashboard. Expected time to detect from the dashboard alone: never.

## Timeline (UTC, 2026-10-07)

| Time | Event |
|---|---|
| 14:47 | Baseline probe: PTO balance returns via `get_pto_balance` (10.3s, cold start); write turn pauses at confirmation (2.2s). |
| ~14:52 | `terraform destroy -target` removes the invoker binding. |
| 14:53:12 | First 403 on `mcp-server` `/mcp`. IAM propagation took seconds. |
| 14:53-14:55 | Probe: balance turn takes 112.6s (about 75 `load_memory` calls, 22 `transfer_to_agent`); write turn takes 9.8s and also loops. 324 403s, 324 engine ERROR tracebacks ("Failed to create MCP session"). |
| ~16:55 | `terraform apply` restores the binding (plan: 1 to add, no other drift). Binding was absent about 2 hours, but only the probes above sent traffic. |
| 16:56 | Recovery probe matches baseline: tools fire, balance returned, write pauses at confirmation. Last 403 was 14:55:11. |

## What happened vs. hypothesis

| Item | Predicted | Observed |
|---|---|---|
| User-visible behavior | Agent says it can't look it up | Agent looped, then told the user to contact HR and named the internal `pto_agent`. It did not invent a balance. |
| Turn latency | Down or flat | 112.6s turn; hourly p95 in the log metric was 110,442ms against a 5s bar. The panel caught it. |
| Cost per task | Slightly down | About 20x per turn: roughly 380k input tokens over the 2 failing turns vs about 13k over the 2 baseline turns (5-minute PromQL buckets, approximate). |
| Tool error rate | No change or no data | Zero errors: no `status=error` or `tool_error` in the audit log. The loop's `load_memory` results dilute the denominator. The panel reads green. |
| Request success | No change | Not read in the panel. Both probes returned normally, so no 5xx. |
| First signal | Cloud Run 403s | Cloud Run 403s and engine ERROR tracebacks, both within seconds. |

Three predictions were wrong (user-visible behavior, latency, cost), all from assuming a
tool-less agent stops quietly. It retries without bound.

## Root cause

Technical: `roles/run.invoker` was missing for `hr-agent-runtime` on `mcp-server`, so every
MCP session creation returned 403 and the toolset load failed.

Systemic, in order of importance:

1. **Silent degradation.** A failed MCP toolset load does not fail the turn. The agent runs
   without its tools, and the model compensates with `load_memory` and `transfer_to_agent`.
2. **No bound on the loop.** Nothing caps model calls, tool calls or transfers per turn, so
   one broken dependency produced about 20x the cost and 112s of latency per turn.
3. **No alert.** The dashboard is passive. The failure was visible only to someone looking at
   the latency and cost panels or the Cloud Run logs.
4. **Fallback leaks internals.** The model's apology names `pto_agent` and tells the user
   there is a loop.

## Detection gap

- The panel built for correctness, tool error rate, was blind: tool-load failure emits no
  tool result (the 8.2 blind spot, now confirmed on a real failure).
- Latency and cost panels did move, but they are symptoms and the headline panels do not
  alert. With real traffic this would have burned money until someone opened the dashboard.
- The strongest direct signal, 403s on `mcp-server` and the engine's "Failed to create MCP
  session" ERROR, is not on the dashboard.
- Request success stayed green by design: it measures HTTP, not tasks.

## Action items

| # | Item | Closes | Where |
|---|---|---|---|
| 1 | Log-based metric on engine ERROR "Failed to create MCP session" plus a Cloud Monitoring alert policy (any occurrence in 5 min), and a dashboard panel for it | Detection gap 1, 3 | `deploy/terraform/monitoring.tf` |
| 2 | Alert on turn p95 above the 10s bar and on cost per task above a multiple of baseline | Detection gap 2 | `deploy/terraform/monitoring.tf` |
| 3 | Cap model calls per turn (ADK `RunConfig.max_llm_calls`, or a plugin that aborts after N `load_memory` / transfer calls) and fail the turn with a fixed message | Root cause 1, 2 | `hr_agent/` |
| 4 | Fail the turn cleanly (not tool-less) when the MCP toolset can't load; user-facing message must not name internal agents | Root cause 1, 4 | `hr_agent/` |
| 5 | Eval case for "HCM unreachable" once item 4 exists | Regression guard | `evals/` |
| 6 | Guard the binding: `lifecycle { prevent_destroy = true }` makes a planned destroy of it fail loudly, and a post-apply smoke probe (runbook step) catches changes that slip past | Root cause (technical) | `deploy/terraform/iam.tf`, `docs/07-deployment-procedure.md` |

Items 1, 3 and 4 are the minimum for a launch.
