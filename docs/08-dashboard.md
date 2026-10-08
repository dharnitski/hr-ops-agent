# Launch-bar dashboard (M8.2)

`deploy/terraform/monitoring.tf` defines the Cloud Monitoring dashboard "hr-ops-agent launch
bar" and the log-based metrics behind its panels. `deploy/terraform/alerts.tf` adds the alert
policies (see Alerts below). Thresholds come from `docs/05-eval-standard.md`.

| Panel | Source | Definition | Blind spots |
|---|---|---|---|
| Request success rate | Platform metric `reasoning_engine/request_count` (no IAM needed) | 2xx / all requests per hour | Request success, not task success: a wrong answer is a 200. Counts every engine API call, not just user turns. Real task success is the eval gate (offline, `scripts/run_eval_gate.py`); there is no online ground truth. |
| Tool error rate | Log-based metric `hr_agent_tool_results`, from the `AuditLogPlugin` line in stderr | (`status=error` or exception) excluding `forbidden` / all results excluding `transfer_to_agent` | `forbidden` is the guardrail working, so it is excluded from the headline (see the by-code panel). Schema-layer MCP rejections and confirmation pauses log an empty result, so they are not counted as errors. Counts only from metric creation. A failed MCP tool load ("Session not found", the agent then runs without tools) emits no tool result at all, so it is invisible here; the HCM lost panel and alerts cover it. |
| Turn latency p95 | Log-based distribution metric `hr_agent_turn_latency_ms`, from a `turn_complete` line that `AuditLogPlugin` writes per turn (`hr_agent/audit.py`) | p95 of wall-clock turn duration, hourly | Needs an agent redeploy; no data before it. A turn that raises is not logged. Can't split read from write turns, so both bars (5s, 10s) are drawn on one line. Includes Cloud Run cold start. The platform metric `reasoning_engine/request_latencies` is not used: it read 264ms for a turn measured at 3.65s. |
| Cost per task | OTel `gen_ai.client.token.usage` + `gen_ai.invoke_agent.duration` (PromQL) | (input tokens x input price + output tokens x output price) / turns, where turns = all `invoke_agent` counts - `transfer_to_agent` calls | Needs `roles/monitoring.metricWriter` on `hr-agent-runtime`. Prices are Terraform variables for one model (flash-lite); M8.3 tier routing needs a per-model split. Assumes output tokens include thinking. A "task" is one user turn, so a turn that only asks for an ID counts. Counting only the root agent undercounts follow-up turns, which skip the router (5 of 9 measured); the formula above matched 9 of 9. Excludes Memory Bank, Cloud Run and trace/log costs. |

| HCM lost | Log-based metrics `hr_agent_mcp_session_failures` (engine ERROR "Failed to create MCP session") and `hr_agent_turns_aborted` (`turn_aborted` line from `TurnGuardPlugin`, by reason) | Hourly counts | Counts from metric creation. `turns_aborted` needs the agent redeploy. Both are zero when healthy, so a flat line is good. |

Least trustworthy: cost per task. It rests on a hand-entered price table, an unverified
thinking-token assumption and a turn-based definition of a task. Request success is the
least informative.

## Alerts (M8.4)

The panels above are passive; these policies in `deploy/terraform/alerts.tf` notify. Set
`alert_email` to get email; with it empty the incidents show in the console only.

| Policy | Fires when | Notes |
|---|---|---|
| MCP session failures | any `hr_agent_mcp_session_failures` in 5 min | Direct signal for a lost HCM dependency. Fires within seconds in the drill. |
| Turns aborted | any `hr_agent_turns_aborted` in 5 min | Covers both `tools_unavailable` and `model_call_budget_exceeded`. |
| Turn latency p95 | p95 over 10 min above `latency_alert_ms` (10s) | A single cold start (~10s) can trip it. |
| Cost per task | cost per task over 10 min above `cost_per_task_alert_usd` ($0.02) | Same series as the cost panel. Stays quiet when there are no tasks. |

Labels carry only tool name, status and error code: no employee IDs, balances or question text.

Verify after any redeploy: the engine's `updateTime` advanced, then a few turns produce
`turn_complete` lines and a p95 point. After the 2026-10-06 redeploy two `OTEL_*` env vars
(`OTEL_SEMCONV_STABILITY_OPT_IN`, `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT`) were
no longer present on the resource; check a fresh trace in the Cloud Trace console for message
text.
