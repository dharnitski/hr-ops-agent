resource "google_cloud_run_v2_service" "mcp_server" {
  name                = local.mcp_server_name
  location            = var.region
  ingress             = "INGRESS_TRAFFIC_ALL"
  deletion_protection = false # course project; flip to true for a real deployment

  template {
    service_account                  = google_service_account.mcp_server_runtime.email
    timeout                          = "300s"
    max_instance_request_concurrency = 80

    scaling {
      min_instance_count = 0
      max_instance_count = 2
    }

    containers {
      image = var.mcp_server_image

      ports {
        container_port = 8080
      }

      env {
        name  = "MCP_ALLOWED_HOSTS"
        value = local.mcp_server_host
      }

      resources {
        limits = {
          cpu    = "1000m"
          memory = "512Mi"
        }
        cpu_idle          = true
        startup_cpu_boost = true
      }
    }
  }

  # Images ship via Cloud Build + `gcloud run deploy` (docs/07-deployment-procedure.md), as
  # ASP does for app code. Don't let a plan roll the service back to the initial tag.
  lifecycle {
    ignore_changes = [
      template[0].containers[0].image,
      client,
      client_version,
    ]
  }

  depends_on = [google_project_service.services]
}
