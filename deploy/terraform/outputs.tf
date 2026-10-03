output "agent_runtime_service_account" {
  description = "Set as `service_account` in hr_agent/.agent_engine_config.json."
  value       = google_service_account.agent_runtime.email
}

output "mcp_server_url" {
  description = "Use as HCM_MCP_URL / HCM_MCP_AUDIENCE for the deployed agent."
  value       = "https://${local.mcp_server_host}"
}

output "image_repository" {
  value = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.images.repository_id}"
}
