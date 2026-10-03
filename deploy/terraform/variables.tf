variable "project_id" {
  type        = string
  description = "Google Cloud project that hosts the agent and mcp_server."
}

variable "region" {
  type        = string
  description = "Region for Cloud Run and Artifact Registry (Agent Engine is deployed separately)."
  default     = "us-central1"
}

variable "mcp_server_image" {
  type        = string
  description = "Initial mcp-server image. Terraform ignores later changes: new images ship via Cloud Build + `gcloud run deploy`."
}
