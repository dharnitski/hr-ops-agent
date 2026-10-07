# Alerts for the failure modes found in the M8.4 drill (docs/08-failure-drill-rca.md): a lost
# HCM dependency, a runaway turn, and the latency and cost it causes. The dashboard is passive;
# these page.

locals {
  alert_channels = [for c in google_monitoring_notification_channel.email : c.id]

  # Same series as the dashboard's cost panel, over a fixed 10-minute window (alerts have no
  # $__interval).
  alert_tokens_by_type = "sum(increase({\"gen_ai.client.token.usage_sum\",\"gen_ai.token.type\"=\"%s\"}[10m]))"
  alert_tasks          = "(sum(increase({\"gen_ai.invoke_agent.duration_count\"}[10m])) - sum(increase({\"gen_ai.execute_tool.duration_count\",\"gen_ai.tool.name\"=\"transfer_to_agent\"}[10m])))"
  alert_cost_per_task = join(" / ", [
    "((${format(local.alert_tokens_by_type, "input")} * ${var.price_input_per_mtok_usd} / 1000000) + (${format(local.alert_tokens_by_type, "output")} * ${var.price_output_per_mtok_usd} / 1000000))",
    local.alert_tasks,
  ])

  mcp_session_failures = "logging.googleapis.com/user/${google_logging_metric.mcp_session_failures.name}"
  turns_aborted        = "logging.googleapis.com/user/${google_logging_metric.turns_aborted.name}"
}

resource "google_monitoring_notification_channel" "email" {
  count        = var.alert_email == "" ? 0 : 1
  display_name = "hr-ops-agent alerts"
  type         = "email"
  labels       = { email_address = var.alert_email }
}

# ADK logs this ERROR when the MCP session can't be created (IAM, network, server down). The
# drill produced 324 in two minutes, seconds after the invoker binding was removed.
resource "google_logging_metric" "mcp_session_failures" {
  name        = "hr_agent_mcp_session_failures"
  description = "Engine ERRORs for a failed MCP session: the agent lost its HCM tools."
  filter      = <<-EOT
    ${local.engine_resource}
    severity>=ERROR
    textPayload:"Failed to create MCP session"
  EOT

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
    unit        = "1"
  }

  depends_on = [google_project_service.services]
}

# `turn_aborted` lines from TurnGuardPlugin (hr_agent/turn_guard.py): the turn ended early
# with a fixed message, either because HCM tools didn't load or the model-call budget ran out.
resource "google_logging_metric" "turns_aborted" {
  name        = "hr_agent_turns_aborted"
  description = "Turns ended early by TurnGuardPlugin, by reason."
  filter      = <<-EOT
    ${local.engine_resource}
    logName:"reasoning_engine_stderr"
    textPayload:"audit.py"
    textPayload:"'event': 'turn_aborted'"
  EOT

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
    unit        = "1"
    labels {
      key         = "reason"
      value_type  = "STRING"
      description = "tools_unavailable or model_call_budget_exceeded"
    }
  }

  label_extractors = {
    reason = "REGEXP_EXTRACT(textPayload, \"'reason': '([^']+)'\")"
  }

  depends_on = [google_project_service.services]
}

resource "google_monitoring_alert_policy" "mcp_session_failures" {
  display_name = "hr-agent: MCP session failures"
  combiner     = "OR"
  conditions {
    display_name = "any failed MCP session in 5 minutes"
    condition_threshold {
      filter          = "metric.type=\"${local.mcp_session_failures}\" ${local.engine_resource}"
      comparison      = "COMPARISON_GT"
      threshold_value = 0
      duration        = "0s"
      aggregations {
        alignment_period     = "300s"
        per_series_aligner   = "ALIGN_DELTA"
        cross_series_reducer = "REDUCE_SUM"
      }
      trigger { count = 1 }
    }
  }
  documentation {
    mime_type = "text/markdown"
    content   = "The agent can't create an MCP session, so it has lost its HCM tools. Check `roles/run.invoker` for `hr-agent-runtime` on `mcp-server` and the service's health. Runbook: docs/08-failure-drill-rca.md."
  }
  notification_channels = local.alert_channels
}

resource "google_monitoring_alert_policy" "turns_aborted" {
  display_name = "hr-agent: turns aborted by the turn guard"
  combiner     = "OR"
  conditions {
    display_name = "any aborted turn in 5 minutes"
    condition_threshold {
      filter          = "metric.type=\"${local.turns_aborted}\" ${local.engine_resource}"
      comparison      = "COMPARISON_GT"
      threshold_value = 0
      duration        = "0s"
      aggregations {
        alignment_period     = "300s"
        per_series_aligner   = "ALIGN_DELTA"
        cross_series_reducer = "REDUCE_SUM"
      }
      trigger { count = 1 }
    }
  }
  documentation {
    mime_type = "text/markdown"
    content   = "Users are getting the fixed failure message. Group by `reason` in the log metric: `tools_unavailable` means HCM is unreachable; `model_call_budget_exceeded` means a turn looped."
  }
  notification_channels = local.alert_channels
}

resource "google_monitoring_alert_policy" "turn_latency" {
  display_name = "hr-agent: turn latency p95 over the bar"
  combiner     = "OR"
  conditions {
    display_name = "turn latency p95 above bar over 10 minutes"
    condition_threshold {
      filter          = "metric.type=\"${local.turn_latency}\" ${local.engine_resource}"
      comparison      = "COMPARISON_GT"
      threshold_value = var.latency_alert_ms
      duration        = "0s"
      aggregations {
        alignment_period   = "600s"
        per_series_aligner = "ALIGN_PERCENTILE_95"
      }
      trigger { count = 1 }
    }
  }
  documentation {
    mime_type = "text/markdown"
    content   = "Turn latency p95 is over the launch bar. A single cold start (~10s) can trip this; a sustained breach is a loop or a slow dependency. See docs/08-dashboard.md."
  }
  notification_channels = local.alert_channels
}

resource "google_monitoring_alert_policy" "cost_per_task" {
  display_name = "hr-agent: cost per task over the bar"
  combiner     = "OR"
  conditions {
    display_name = "cost per task above bar over 10 minutes"
    condition_prometheus_query_language {
      query               = "${local.alert_cost_per_task} > ${var.cost_per_task_alert_usd}"
      duration            = "0s"
      evaluation_interval = "60s"
    }
  }
  documentation {
    mime_type = "text/markdown"
    content   = "Cost per task is above the launch bar. The drill showed about 20x per turn when the agent looped without tools. See docs/08-failure-drill-rca.md."
  }
  notification_channels = local.alert_channels
}
