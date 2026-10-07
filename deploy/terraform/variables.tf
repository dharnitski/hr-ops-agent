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

# Alerting inputs (M8.4 RCA items 1 and 2).
variable "alert_email" {
  type        = string
  description = "Email for alert notifications. Empty creates the policies with no channel: incidents show in the console only."
  default     = ""
}

variable "latency_alert_ms" {
  type        = number
  description = "Alert when turn latency p95 over 10 minutes exceeds this. Default is the 10s write bar from the launch bar; a cold start (~10s) can trip it."
  default     = 10000
}

variable "cost_per_task_alert_usd" {
  type        = number
  description = "Alert when cost per task over 10 minutes exceeds this. Default is the $0.02 write bar, about 8x the measured baseline of $0.0026."
  default     = 0.02
}
