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

# Cost panel inputs (M8.2). Standard paid tier for MODEL_ID in hr_agent/config.py, from
# ai.google.dev/gemini-api/docs/pricing, checked 2026-10-06. Update both when the model changes.
variable "price_input_per_mtok_usd" {
  type        = number
  description = "USD per 1M input tokens for the configured model."
  default     = 0.30
}

variable "price_output_per_mtok_usd" {
  type        = number
  description = "USD per 1M output tokens for the configured model (assumed to include thinking tokens; unverified)."
  default     = 2.50
}
