# Agent Engine runtime identity. Read by `hr_agent/.agent_engine_config.json`; `adk deploy`
# attaches it to the reasoning engine, which Terraform does not manage (see README).
resource "google_service_account" "agent_runtime" {
  account_id   = "hr-agent-runtime"
  display_name = "hr-ops-agent Agent Engine runtime"
  depends_on   = [google_project_service.services]
}

# mcp_server only serves mock data and calls no Google APIs, so this identity holds no roles.
# Replaces the default Compute Engine SA, which carries roles/editor.
resource "google_service_account" "mcp_server_runtime" {
  account_id   = "mcp-server-runtime"
  display_name = "mcp-server Cloud Run runtime"
  depends_on   = [google_project_service.services]
}
