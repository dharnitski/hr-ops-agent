# Dashboard for the M5 launch bar (M8.2): request success, tool error rate, p95 turn latency,
# cost per task. Sources differ per panel, see docs/08-dashboard.md.

locals {
  engine_requests = "aiplatform.googleapis.com/reasoning_engine/request_count"
  engine_resource = "resource.type=\"aiplatform.googleapis.com/ReasoningEngine\""
  tool_results    = "logging.googleapis.com/user/${google_logging_metric.tool_results.name}"
  turn_latency    = "logging.googleapis.com/user/${google_logging_metric.turn_latency.name}"

  # A task is one user turn. Every turn starts exactly one entry `invoke_agent` (the router, or
  # the last-active specialist on a follow-up turn, which skips the router) plus one more per
  # `transfer_to_agent`, so turns = all invoke_agent counts - transfer calls. Counting only the
  # root agent undercounts follow-up turns (measured: 5 of 9).
  # Cumulative histograms from `--otel_to_cloud` (OTLP via telemetry.googleapis.com), queried
  # as PromQL. Dots in OTel names need the UTF-8 selector form.
  tokens_by_type = "sum(increase({\"gen_ai.client.token.usage_sum\",\"gen_ai.token.type\"=\"%s\"}[$${__interval}]))"
  tasks          = "(sum(increase({\"gen_ai.invoke_agent.duration_count\"}[$${__interval}])) - sum(increase({\"gen_ai.execute_tool.duration_count\",\"gen_ai.tool.name\"=\"transfer_to_agent\"}[$${__interval}])))"
  cost_per_task_promql = join(" / ", [
    "((${format(local.tokens_by_type, "input")} * ${var.price_input_per_mtok_usd} / 1000000) + (${format(local.tokens_by_type, "output")} * ${var.price_output_per_mtok_usd} / 1000000))",
    local.tasks,
  ])
}

# Counts one row per tool result/exception from the AuditLogPlugin (hr_agent/audit.py). The
# line is a Python dict repr in stderr, not JSON, so labels are regex-extracted. Only
# allowlisted fields (tool name, status, code) become labels: no IDs, no balances.
resource "google_logging_metric" "tool_results" {
  name        = "hr_agent_tool_results"
  description = "Tool results and exceptions from the hr_agent audit log, by tool/status/code."
  filter      = <<-EOT
    ${local.engine_resource}
    logName:"reasoning_engine_stderr"
    textPayload:"audit.py"
    (textPayload:"'event': 'tool_result'" OR textPayload:"'event': 'tool_error'")
  EOT

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
    unit        = "1"
    labels {
      key         = "tool"
      value_type  = "STRING"
      description = "Tool name"
    }
    labels {
      key         = "event"
      value_type  = "STRING"
      description = "tool_result, or tool_error for an exception"
    }
    labels {
      key         = "status"
      value_type  = "STRING"
      description = "Handler status (success/error); empty for transfer_to_agent, paused or schema-rejected calls"
    }
    labels {
      key         = "code"
      value_type  = "STRING"
      description = "Business error code, e.g. forbidden"
    }
  }

  label_extractors = {
    tool   = "REGEXP_EXTRACT(textPayload, \"'tool': '([^']+)'\")"
    event  = "REGEXP_EXTRACT(textPayload, \"'event': '([^']+)'\")"
    status = "REGEXP_EXTRACT(textPayload, \"'status': '([^']+)'\")"
    code   = "REGEXP_EXTRACT(textPayload, \"'code': '([^']+)'\")"
  }

  depends_on = [google_project_service.services]
}

# One row per user turn (`turn_complete`, AuditLogPlugin.after_run_callback) with its
# wall-clock duration. The platform `reasoning_engine/request_latencies` metric was measured
# at 264ms for a turn that took 3.65s end to end, so it can't back the p95 bar.
resource "google_logging_metric" "turn_latency" {
  name        = "hr_agent_turn_latency_ms"
  description = "Wall-clock duration of each completed user turn, from the hr_agent audit log."
  filter      = <<-EOT
    ${local.engine_resource}
    logName:"reasoning_engine_stderr"
    textPayload:"audit.py"
    textPayload:"'event': 'turn_complete'"
  EOT

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "DISTRIBUTION"
    unit        = "ms"
  }

  value_extractor = "REGEXP_EXTRACT(textPayload, \"'duration_ms': (\\\\d+)\")"

  bucket_options {
    exponential_buckets {
      num_finite_buckets = 30
      growth_factor      = 1.4
      scale              = 100
    }
  }

  depends_on = [google_project_service.services]
}

resource "google_monitoring_dashboard" "launch_bar" {
  dashboard_json = jsonencode({
    displayName = "hr-ops-agent launch bar"
    mosaicLayout = {
      columns = 12
      tiles = [
        {
          width = 6, height = 4
          widget = {
            title = "Request success rate (proxy for task success)"
            xyChart = {
              dataSets = [{
                targetAxis = "Y1"
                plotType   = "LINE"
                timeSeriesQuery = {
                  timeSeriesFilterRatio = {
                    numerator = {
                      filter      = "metric.type=\"${local.engine_requests}\" ${local.engine_resource} metric.label.\"response_code_class\"=\"2xx\""
                      aggregation = { alignmentPeriod = "3600s", perSeriesAligner = "ALIGN_DELTA", crossSeriesReducer = "REDUCE_SUM" }
                    }
                    denominator = {
                      filter      = "metric.type=\"${local.engine_requests}\" ${local.engine_resource}"
                      aggregation = { alignmentPeriod = "3600s", perSeriesAligner = "ALIGN_DELTA", crossSeriesReducer = "REDUCE_SUM" }
                    }
                  }
                }
              }]
              yAxis = { scale = "LINEAR" }
            }
          }
        },
        {
          xPos = 6, width = 6, height = 4
          widget = {
            title = "Tool error rate (business errors excl. forbidden, and exceptions)"
            xyChart = {
              dataSets = [{
                targetAxis     = "Y1"
                plotType       = "LINE"
                legendTemplate = "business errors (excl. forbidden)"
                timeSeriesQuery = {
                  timeSeriesFilterRatio = {
                    numerator = {
                      filter      = "metric.type=\"${local.tool_results}\" ${local.engine_resource} metric.label.\"status\"=\"error\" metric.label.\"code\"!=\"forbidden\" metric.label.\"tool\"!=\"transfer_to_agent\""
                      aggregation = { alignmentPeriod = "3600s", perSeriesAligner = "ALIGN_DELTA", crossSeriesReducer = "REDUCE_SUM" }
                    }
                    denominator = {
                      filter      = "metric.type=\"${local.tool_results}\" ${local.engine_resource} metric.label.\"tool\"!=\"transfer_to_agent\""
                      aggregation = { alignmentPeriod = "3600s", perSeriesAligner = "ALIGN_DELTA", crossSeriesReducer = "REDUCE_SUM" }
                    }
                  }
                }
                }, {
                targetAxis     = "Y1"
                plotType       = "LINE"
                legendTemplate = "tool exceptions"
                timeSeriesQuery = {
                  timeSeriesFilterRatio = {
                    numerator = {
                      filter      = "metric.type=\"${local.tool_results}\" ${local.engine_resource} metric.label.\"event\"=\"tool_error\""
                      aggregation = { alignmentPeriod = "3600s", perSeriesAligner = "ALIGN_DELTA", crossSeriesReducer = "REDUCE_SUM" }
                    }
                    denominator = {
                      filter      = "metric.type=\"${local.tool_results}\" ${local.engine_resource} metric.label.\"tool\"!=\"transfer_to_agent\""
                      aggregation = { alignmentPeriod = "3600s", perSeriesAligner = "ALIGN_DELTA", crossSeriesReducer = "REDUCE_SUM" }
                    }
                  }
                }
              }]
              yAxis = { scale = "LINEAR" }
            }
          }
        },
        {
          yPos = 4, width = 6, height = 4
          widget = {
            title = "Turn latency p95 (ms; bars: 5s read / 10s write)"
            xyChart = {
              dataSets = [{
                targetAxis = "Y1"
                plotType   = "LINE"
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter      = "metric.type=\"${local.turn_latency}\" ${local.engine_resource}"
                    aggregation = { alignmentPeriod = "3600s", perSeriesAligner = "ALIGN_PERCENTILE_95" }
                  }
                }
              }]
              thresholds = [
                { value = 5000, label = "read bar" },
                { value = 10000, label = "write bar" },
              ]
              yAxis = { scale = "LINEAR" }
            }
          }
        },
        {
          xPos = 6, yPos = 4, width = 6, height = 4
          widget = {
            title = "Cost per task (USD; bars: $0.01 read / $0.02 write)"
            xyChart = {
              dataSets = [{
                targetAxis      = "Y1"
                plotType        = "LINE"
                timeSeriesQuery = { prometheusQuery = local.cost_per_task_promql }
              }]
              thresholds = [
                { value = 0.01, label = "read bar" },
                { value = 0.02, label = "write bar" },
              ]
              yAxis = { scale = "LINEAR" }
            }
          }
        },
        {
          yPos = 8, width = 6, height = 4
          widget = {
            title = "Tool results by tool / status / code"
            xyChart = {
              dataSets = [{
                targetAxis = "Y1"
                plotType   = "STACKED_BAR"
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter      = "metric.type=\"${local.tool_results}\" ${local.engine_resource}"
                    aggregation = { alignmentPeriod = "3600s", perSeriesAligner = "ALIGN_DELTA", crossSeriesReducer = "REDUCE_SUM", groupByFields = ["metric.label.\"tool\"", "metric.label.\"status\"", "metric.label.\"code\""] }
                  }
                }
              }]
              yAxis = { scale = "LINEAR" }
            }
          }
        },
        {
          xPos = 6, yPos = 8, width = 6, height = 4
          widget = {
            title = "Tokens per hour by type"
            xyChart = {
              dataSets = [{
                targetAxis      = "Y1"
                plotType        = "STACKED_BAR"
                timeSeriesQuery = { prometheusQuery = "sum by (\"gen_ai.token.type\") (increase({\"gen_ai.client.token.usage_sum\"}[$${__interval}]))" }
              }]
              yAxis = { scale = "LINEAR" }
            }
          }
        },
      ]
    }
  })
}
