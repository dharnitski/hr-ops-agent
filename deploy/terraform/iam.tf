variable "agent_runtime_roles" {
  type        = list(string)
  description = "Project roles for the Agent Engine runtime SA. Cover model calls, sessions and memories, plus writing OTel traces (M8.1) and metrics (M8.2: the token/duration series behind the cost panel)."
  default     = ["roles/aiplatform.user", "roles/telemetry.tracesWriter", "roles/monitoring.metricWriter"]
}

resource "google_project_iam_member" "agent_runtime" {
  for_each = toset(var.agent_runtime_roles)
  project  = var.project_id
  role     = each.value
  member   = "serviceAccount:${google_service_account.agent_runtime.email}"
}

# The agent's ID token is the only way in: mcp-server rejects unauthenticated calls.
# Losing this binding silently breaks every turn (M8.4 drill), so a plan that destroys it fails.
# To remove or replace it on purpose, delete the lifecycle block in a reviewed change first.
resource "google_cloud_run_v2_service_iam_member" "agent_invokes_mcp_server" {
  name     = google_cloud_run_v2_service.mcp_server.name
  location = google_cloud_run_v2_service.mcp_server.location
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.agent_runtime.email}"

  lifecycle {
    prevent_destroy = true
  }
}
