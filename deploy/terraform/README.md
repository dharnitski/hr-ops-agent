# Terraform

Infra for the one project (`hr-ops-agent-509718`), modeled on Agent Starter Pack's
`deployment/terraform/`, collapsed to a single environment (no staging/prod split, no CI
runner, no GitHub/WIF yet -- those belong to M7.5 CI/CD).

Managed: API enablement, Artifact Registry repo, `hr-agent-runtime` and `mcp-server-runtime`
service accounts, their IAM, the `mcp-server` Cloud Run service.

Not managed, on purpose:
- **Agent Engine reasoning engine.** `adk deploy agent_engine` owns its code, env and
  identity (`hr_agent/.agent_engine_config.json`). ASP creates it from a dummy source and
  `ignore_changes` the code; not worth it for one engine already live.
- **Cloud Run image tag.** Ignored after creation; ship via `docs/07-deployment-procedure.md`.

```bash
cd deploy/terraform
terraform init
terraform plan  -var-file=vars/env.tfvars
terraform apply -var-file=vars/env.tfvars
```

State is local and gitignored (it adopted the hand-made M7 resources via one-time `import`
blocks, applied 2026-10-02). Losing it means re-importing the service accounts, repo and
service. Move to a GCS backend before CI runs `apply`.
`mcp-server` runs as `mcp-server-runtime` (no roles), not the default Compute SA
(`roles/editor`).
