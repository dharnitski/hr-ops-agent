resource "google_artifact_registry_repository" "images" {
  repository_id = "hr-ops-agent"
  location      = var.region
  format        = "DOCKER"
  description   = "Container images for hr-ops-agent (mcp_server on Cloud Run)"
  depends_on    = [google_project_service.services]
}
