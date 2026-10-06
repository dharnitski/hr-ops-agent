# Deployment tradeoffs: why Agent Engine

Why the agent runs on Vertex AI Agent Engine, what that cost, and when to move. Scoped to
Agent Engine; Cloud Run/GKE for the agent were skipped by decision (2026-09-29), so
statements about them are reasoning, not hands-on findings. The how-to is
`docs/07-deployment-procedure.md`. Pinned to `google-adk` 2.9.2 (2026-10-05).

## Decision

The agent runs on Agent Engine; `mcp_server` runs on Cloud Run. They are deployed
differently on purpose: the agent is an ADK app that needs sessions and memory, while
`mcp_server` is a small stateless, independently deployable service (M2) that must be
IAM-gated and must not drag in the ADK dependency tree (83 modules vs. 1383 before the
mock-data move).

## What Agent Engine gave us

- **No container to own.** `adk deploy agent_engine` packages the folder; no Dockerfile,
  registry or local Docker daemon for the agent.
- **Sessions and Memory Bank on the same resource.** Cross-session recall (M4.2) needed no
  extra infrastructure; the deployed agent uses it automatically.
- **Telemetry is a flag.** `--otel_to_cloud` plus one IAM role gave Cloud Trace spans (M8.1).
- **Per-agent runtime identity.** A custom SA via `.agent_engine_config.json` replaced the
  broad Google-managed default (M7.4).
- **Low idle cost.** Nothing to keep warm for the agent itself.

## What it cost

Every item below failed silently or late, so each one is now a runbook step.

- **Opaque packaging.** The deploy reads neither `pyproject.toml` nor `uv.lock`: `mcp` had to
  be added via a hand-written `requirements.txt`, and a sibling package needs
  `--extra_packages`. Local tests can't see this (shared `PYTHONPATH`).
- **Runtime pinned to Python 3.11** regardless of `requires-python` (3.14). Version-gated
  stdlib (`typing.override`) breaks at import time only in the deployed container.
- **Silent no-ops.** A relative `--env_file` deployed with zero env vars; a mistyped command
  left `updateTime` unchanged. Success has to be checked on the live resource, not the exit code.
- **Not fully in Terraform.** `adk deploy` owns code, env and identity, so the engine is the
  one live resource outside IaC. Identity lives in a file the deploy auto-reads; deleting it
  reverts to the default SA.
- **Thin debugging loop.** Failures surface as `FAILED_PRECONDITION` on first query; the real
  error is in Cloud Logging, where cached console entries can mislead.
- **Moving CLI surface.** `--env_file` now warns as deprecated; `--staging_bucket` is unused.
  Expect to re-verify flags each upgrade.
- **Needs a second service for tools.** The agent can't host the MCP server, so HCM runs on
  Cloud Run with its own IAM, ID-token auth and a cold start (first MCP `initialize` ~4.5s).

## Against the alternatives (not built here)

| | Agent Engine | Cloud Run | GKE |
|---|---|---|---|
| Ops burden | Lowest | Low (own the image) | Highest |
| Sessions/memory | Built in | Bring your own | Bring your own |
| Dependency/runtime control | Pinned runtime, opaque packaging | Full (Dockerfile) | Full |
| Scaling/networking control | Limited to what the config exposes | Good | Full |
| Fit | One agent, Google-managed state | Agent plus custom HTTP surface | Many services, existing platform team |

Cloud Run would remove the Python pin and packaging surprises at the price of owning
session/memory wiring. GKE only pays off with an existing cluster and platform team, which
this project doesn't have.

## When to revisit

- A dependency or Python version the managed runtime can't provide.
- Networking the config doesn't expose (private-only egress, VPC-bound tools), not tested here.
- Needing session/memory behavior Agent Engine's managed services don't offer.
- Cost or latency at real traffic; no usage data exists yet, so this is unmeasured.
- A second agent that should share one service and pipeline.

## Teardown

`docs/07-deployment-procedure.md` lists the commands: `terraform destroy` for everything
Terraform owns, plus deleting the reasoning engine by hand (and with it Memory Bank).
