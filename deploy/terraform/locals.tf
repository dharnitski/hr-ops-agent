locals {
  services = [
    "aiplatform.googleapis.com",
    "artifactregistry.googleapis.com",
    "cloudbuild.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "iam.googleapis.com",
    "run.googleapis.com",
    "serviceusage.googleapis.com",
  ]

  mcp_server_name = "mcp-server"

  # Deterministic Cloud Run URL form. Known before the service exists, which removes the
  # post-first-deploy `MCP_ALLOWED_HOSTS` fix-up step from the runbook.
  mcp_server_host = "${local.mcp_server_name}-${data.google_project.this.number}.${var.region}.run.app"
}

data "google_project" "this" {
  project_id = var.project_id
}
