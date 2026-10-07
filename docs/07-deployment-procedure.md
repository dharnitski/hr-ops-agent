# Deployment procedure

How to deploy and redeploy this project's two live pieces: the agent (Agent Engine) and
`mcp_server` (Cloud Run, a supporting service — 7.2/7.3 skipped the agent itself running on
Cloud Run/GKE; see `docs/PROGRESS.md`'s Module 7 decisions for why). Current live resources,
project `hr-ops-agent-509718`, region `us-central1`:

Everything except the Agent Engine resource is managed by `deploy/terraform/`; change it
there, not with ad hoc `gcloud`.

| Resource | ID / URL |
|---|---|
| Agent Engine (the agent) | `reasoningEngines/3717518632499019776` |
| Cloud Run service (`mcp_server`) | `mcp-server` → `https://mcp-server-976559775904.us-central1.run.app` (also reachable at the older-style `https://mcp-server-rqllted7qq-uc.a.run.app`, which `gcloud run services describe` and the console show; same service. `MCP_ALLOWED_HOSTS` is set to the first form only, so use that one in `HCM_MCP_URL`) |
| Artifact Registry repo | `hr-ops-agent` (Docker, us-central1) |
| Memory Bank | The Agent Engine resource above; nothing separate to provision. The deployed agent uses it automatically; `MEMORY_BANK_AGENT_ENGINE_ID` in `.env` is only for `tests/integration/hr_agent/test_memory_bank_live.py` |
| Agent Engine runtime identity | `hr-agent-runtime@hr-ops-agent-509718.iam.gserviceaccount.com` (custom, `roles/aiplatform.user` only — see `docs/PROGRESS.md`'s M7.4) |

## Infrastructure (Terraform)

APIs, the Artifact Registry repo, both runtime service accounts and their IAM, and the
`mcp-server` Cloud Run service live in `deploy/terraform/` (applied 2026-10-02). Not managed
there: the Agent Engine resource (`adk deploy` owns it) and the Cloud Run image tag. For a
fresh project:

```bash
cd deploy/terraform
# edit vars/env.tfvars (project_id, mcp_server_image), then add `import` blocks only for
# resources that already exist
terraform init && terraform apply -var-file=vars/env.tfvars
```

The `roles/run.invoker` binding for `hr-agent-runtime` has `prevent_destroy`, so a plan that
removes it fails (M8.4). To change it on purpose, remove the `lifecycle` block in a reviewed
change first.

State is local and gitignored. An agent session can't run `apply` (blocked by this project's
permission classifier); run it yourself. Passing `-auto-approve` is needed if you launch it
from a non-interactive shell.

## Redeploy `mcp_server` (Cloud Run)

Whenever `mcp_server/` changes. Builds via Cloud Build — no local Docker daemon needed.

```bash
gcloud builds submit \
  --config=deploy/cloud_run/cloudbuild.yaml \
  --substitutions=_IMAGE=us-central1-docker.pkg.dev/hr-ops-agent-509718/hr-ops-agent/mcp-server:v1 \
  --project=hr-ops-agent-509718 .

gcloud run deploy mcp-server \
  --image=us-central1-docker.pkg.dev/hr-ops-agent-509718/hr-ops-agent/mcp-server:v1 \
  --region=us-central1 --project=hr-ops-agent-509718
```

Only the image is passed: scaling, port, ingress, env and identity are owned by
`deploy/terraform/cloud_run.tf`, so don't repeat them here (a flag here would drift from
Terraform). Terraform ignores the image after creation, so this deploy and `terraform plan`
don't fight.
The image tag (`:v1` above) doesn't bump itself — pick a new tag per real change, or `gcloud
run deploy` will happily redeploy the exact same image again. `deploy/cloud_run/cloudbuild.yaml`
exists only because `mcp_server.Dockerfile` isn't literally named `Dockerfile` at the repo
root — `gcloud builds submit --tag` can't find it otherwise.

`MCP_ALLOWED_HOSTS` and the agent's `roles/run.invoker` grant are set by Terraform, so there
is no first-deploy fix-up step. The host is derived from the project number
(`mcp-server-<PROJECT_NUMBER>.<region>.run.app`). The invoker is Agent Engine's actual runtime
identity (`spec.effectiveIdentity` on the reasoning engine), the custom `hr-agent-runtime` SA
since M7.4. If you change that identity, change `service_accounts.tf`/`iam.tf` and apply.
Confirm the live value via `GET reasoningEngines/{id}`, don't assume.

## Redeploy the agent (Agent Engine)

Whenever `hr_agent/` (or anything it imports, including `mcp_server/mock_data.py`) changes.

```bash
uv run adk deploy agent_engine \
  --project=hr-ops-agent-509718 --region=us-central1 \
  --agent_engine_id=3717518632499019776 \
  --env_file="$(pwd)/hr_agent/.env.agent_engine" \
  --extra_packages=mcp_server \
  --otel_to_cloud \
  --display_name="hr-ops-agent (Module 7.1)" \
  hr_agent
```

`hr_agent/.agent_engine_config.json` (`{"service_account": "hr-agent-runtime@..."}`) is
auto-read from the agent folder — no flag needed, but don't delete it, or the next deploy
silently reverts `effectiveIdentity` to the Google-managed default (M7.4).

Both flags are load-bearing, not optional flourishes:

- **`--env_file` must be an absolute path.** `adk deploy` `chdir`s into its own temp staging
  folder *before* checking whether `env_file` exists. A relative path silently resolves to
  nothing there — the deploy still "succeeds", but with **zero env vars set**, no warning, no
  error. Verify after every deploy (see below); don't trust a clean exit code alone.
- **`--extra_packages=mcp_server` is required** because `hr_agent/tools.py` imports
  `mcp_server.mock_data`. `adk deploy agent_engine hr_agent` only packages the `hr_agent`
  folder by default — this cross-package import is invisible in every local test (both
  packages share one installed `PYTHONPATH` there) and only breaks in the deployed container
  (`ModuleNotFoundError: No module named 'mcp_server'`).
- **`--otel_to_cloud`** (M8.1) exports traces, metrics and logs to Cloud Trace/Monitoring/
  Logging. It sets `GOOGLE_CLOUD_AGENT_ENGINE_ENABLE_TELEMETRY=true` and, unless already set,
  `ADK_CAPTURE_MESSAGE_CONTENT_IN_SPANS=false`. The runtime SA needs `roles/telemetry.tracesWriter`
  (in `deploy/terraform/iam.tf`); without it, spans are silently dropped. Verify env var
  `GOOGLE_CLOUD_AGENT_ENGINE_ENABLE_TELEMETRY` after deploy like the others.
- `hr_agent/.env.agent_engine` (gitignored, mirrors `hr_agent/.env` but points `HCM_MCP_URL`/
  `HCM_MCP_AUDIENCE` at the Cloud Run service instead of `localhost:8000`) exists so local dev
  (`hr_agent/.env`) and the deployed agent can point at different servers without one
  overwriting the other. If Cloud Run's URL ever changes (a new service, a new region), update
  this file, not `hr_agent/.env`.

## Verify a redeploy actually worked

Don't trust "Deployed to Agent Platform" alone — both bugs above produced a clean exit with a
broken result. Check the live resource, then exercise it.

**1. Confirm the env vars actually landed:**

```bash
TOKEN=$(gcloud auth print-access-token)
curl -s -H "Authorization: Bearer $TOKEN" \
  "https://us-central1-aiplatform.googleapis.com/v1/projects/976559775904/locations/us-central1/reasoningEngines/3717518632499019776" \
  | python3 -c "
import json,sys
d=json.load(sys.stdin)
print('updateTime:', d.get('updateTime'))
print('effectiveIdentity:', d['spec'].get('effectiveIdentity'))
[print(' ', e['name'],'=',e['value']) for e in d['spec']['deploymentSpec'].get('env',[])]
"
```

Empty `env` output means the `--env_file` bug above happened again. Check `updateTime`
against when you ran the deploy first — an unchanged timestamp means the deploy never
reached the resource at all (e.g. a mistyped command with flags dropped), not that it ran
and did nothing. `effectiveIdentity` should read `hr-agent-runtime@...`, not the
`gcp-sa-aiplatform-re` default — if it reverted, `.agent_engine_config.json` was likely
missing from the agent folder for that deploy.

**2. Exercise a real conversation** (then find its trace in Cloud Trace Explorer; no span should
carry message text or a balance). `stream_query` needs a *real* session — a made-up
`session_id` string silently produces zero events (learned the hard way):

```bash
TOKEN=$(gcloud auth print-access-token)
SESSION=$(curl -s -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  "https://us-central1-aiplatform.googleapis.com/v1/projects/976559775904/locations/us-central1/reasoningEngines/3717518632499019776:query" \
  -d '{"class_method": "async_create_session", "input": {"user_id": "verify"}}' \
  | python3 -c "import json,sys; print(json.load(sys.stdin)['output']['id'])")

curl -s -N -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  "https://us-central1-aiplatform.googleapis.com/v1/projects/976559775904/locations/us-central1/reasoningEngines/3717518632499019776:streamQuery?alt=sse" \
  -d "{\"class_method\": \"stream_query\", \"input\": {\"user_id\": \"verify\", \"session_id\": \"$SESSION\", \"message\": \"What is my remaining PTO balance?\"}}"
```

Expect a request for an employee ID (no caller identity yet — see `identify_caller` in
`docs/PROGRESS.md`'s Module 6 decisions); a follow-up call with `"message": "My employee ID is
E1002"` on the same `$SESSION` should then show `identify_caller` and `get_pto_balance` both
firing, with a real balance in the final text.

Run this probe after every `terraform apply` and every redeploy, not only after agent
changes: IAM and network changes break the agent without touching its code (M8.4 drill). The
reply "I can't reach the HR system right now" means `mcp-server` is unreachable; check the
invoker binding and Cloud Run first.

**3. Check Cloud Logging directly if something's wrong** — the Cloud Console log viewer can
surface a stale cached entry from a previous failure. Cross-check against the resource's own
`updateTime`:

```bash
gcloud logging read '
resource.type="aiplatform.googleapis.com/ReasoningEngine"
resource.labels.reasoning_engine_id="3717518632499019776"
timestamp>="<updateTime from the GET above>"
severity>=WARNING
' --project=hr-ops-agent-509718 --limit=30
```

## Other gotchas already hit (not redeploy-specific, but will resurface)

- **Python version mismatch**: Agent Engine's managed runtime pins Python 3.11 regardless of
  this project's own `requires-python` (3.14) — 3.12+-only stdlib breaks at import time only
  in the deployed container. Prefer `typing_extensions` over stdlib `typing` for anything
  version-gated.
- **No `requirements.txt`**: if the agent folder has none, `adk deploy` writes one containing
  only `google-adk[a2a]` — it does not read `pyproject.toml`/`uv.lock`. Any dependency ADK
  itself doesn't hard-require (here: `mcp`) needs a hand-written `hr_agent/requirements.txt`.
- **Empty `.env` values hard-fail the deploy API** (`Required field is not set`) — a `KEY=`
  line that does nothing locally breaks a cloud deploy. Audit both `hr_agent/.env` and
  `hr_agent/.env.agent_engine` for empty values before deploying.
- **`mcp`'s DNS-rebinding protection is silently disabled** unless `mcp_server/server.py`'s
  `main()` gets a non-empty `MCP_ALLOWED_HOSTS` — the library's own backwards-compat default
  for no `transport_security` is *off*, not localhost-only.

## Teardown (Module 7 checklist item 7 — not done yet)

```bash
cd deploy/terraform && terraform destroy -var-file=vars/env.tfvars
# Agent Engine resource (not in Terraform): delete via console, or DELETE on reasoningEngines/{id}
```

`destroy` removes Cloud Run, the Artifact Registry repo (and its images), both service
accounts and their IAM. APIs stay enabled (`disable_on_destroy = false`). Do this once Module
7 and this course module are actually done, not before — idle Cloud Run/Agent Engine cost is
low but real.
