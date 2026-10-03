# Architecture

```mermaid
flowchart LR
    user([User])

    subgraph ae["Agent Engine — hr_agent/ App"]
        plugins["App plugins<br/>ContextFilterPlugin (last 6 invocations)<br/>AuditLogPlugin (every tool call)"]
        router["hr_ops_agent<br/>router, no tools<br/>declines unmatched"]
        pto["pto_agent"]
        payroll["payroll_agent"]
        policy["policy_agent"]
        local_pto["local tools<br/>list_holidays, identify_caller<br/>load_memory"]
        local_pay["local tool<br/>identify_caller"]
        local_pol["local tool<br/>search_handbook<br/>(keyword retrieval)"]
        ts_hcm["hcm_toolset<br/>get_employee, get_pto_balance"]
        ts_ptow["pto_write_toolset<br/>submit_pto_request<br/>require_confirmation"]
        ts_payr["payroll_read_toolset<br/>get_payroll_run"]
        ts_payw["payroll_write_toolset<br/>approve_payroll_run<br/>require_confirmation"]
        hdr["header_provider<br/>x-caller-employee-id from session state<br/>+ Google ID token"]
    end

    subgraph mcp["MCP server — mcp_server/ (Cloud Run)"]
        schema["schema validation<br/>strict args, typed outputs"]
        authz["authorization<br/>self-only, role checks<br/>(Payroll Specialist / Finance Director)"]
        limits["write limits<br/>rate limit per caller+tool<br/>MAX_REQUEST_HOURS"]
        handlers["handlers<br/>get_employee, get_pto_balance<br/>submit_pto_request<br/>get_payroll_run, approve_payroll_run"]
        store[("mock HCM data<br/>+ idempotency store<br/>in memory")]
    end

    handbook[("handbook<br/>sections")]
    memory[("Memory Bank<br/>one fact per turn: employee ID")]

    user --> router
    router -- transfer_to_agent --> pto
    router -- transfer_to_agent --> payroll
    router -- transfer_to_agent --> policy
    pto --> local_pto
    pto --> ts_hcm
    pto --> ts_ptow
    payroll --> local_pay
    payroll --> ts_payr
    payroll --> ts_payw
    policy --> local_pol --> handbook
    local_pto <-- "load_memory / after_agent_callback" --> memory
    ts_hcm --> hdr
    ts_ptow --> hdr
    ts_payr --> hdr
    ts_payw --> hdr
    hdr -- "Streamable HTTP" --> schema
    schema --> authz --> limits --> handlers --> store
    plugins -.-> router

    classDef soft fill:#fff3cd,stroke:#b58900,color:#000
    classDef hard fill:#d4edda,stroke:#2e7d32,color:#000
    classDef human fill:#d6e9f8,stroke:#1f6fb2,color:#000
    class router,pto,payroll,policy,ts_hcm,ts_payr,plugins,local_pto,local_pay soft
    class schema,authz,limits,handlers,store hard
    class ts_ptow,ts_payw human
```

**Legend.** Yellow = soft controls (prompt rules, routing descriptions, `tool_filter`): the
model or in-process config can bypass them. Green = hard controls (schema validation,
caller-identity and role checks, rate and size limits, server-computed hours, idempotency):
enforced server-side regardless of what the model sends. Blue = human-in-the-loop: ADK pauses
every call for explicit user approval (`require_confirmation`).

## Control flow

- **Caller identity** is never a tool argument. It is set in session state (by
  `identify_caller`, a stand-in for a real login — not authentication) and sent by the
  `header_provider` as `x-caller-employee-id`; the MCP server checks it on every call and
  fails closed when absent. `get_employee`, `get_pto_balance` and `submit_pto_request` are
  self-only; `get_payroll_run` needs Payroll Specialist or Finance Director;
  `approve_payroll_run` needs Finance Director.
- **Writes** (`submit_pto_request`, `approve_payroll_run`) stack three layers: user
  confirmation (soft), then server-side identity/role, rate limit (20 calls/60s per
  caller+tool) and `MAX_REQUEST_HOURS` (hard). Confirmation does not replace the server checks.
- **Audit**: `AuditLogPlugin` fires once per tool call across all specialists, local and MCP,
  logging allowlisted identifiers and outcomes only, never balances or error text.
- **Context**: `ContextFilterPlugin` trims what is sent to the model, not `session.events`,
  so session state and memory writes are unaffected.
- **Memory**: `pto_agent` reads via `load_memory` and writes one synthetic fact (the employee
  in context) after each turn, not the transcript. Deployed, this is the Agent Engine Memory
  Bank; locally, an in-memory stub. Memory-sourced IDs are never used for a write.

## Deployment

- `hr_agent/` deploys to Agent Engine with a least-privilege runtime service account
  (`hr_agent/.agent_engine_config.json`).
- `mcp_server/` runs on Cloud Run (image from `deploy/cloud_run/`; service, service accounts,
  IAM and Artifact Registry from `deploy/terraform/`). When `HCM_MCP_AUDIENCE` is set the
  agent attaches a Google ID token for Cloud Run's IAM check; that is infra auth, separate
  from caller identity. Locally the server is plain `http://localhost:8000/mcp`.
- Cloud Run / GKE for the agent itself was skipped; see `docs/07-deployment-procedure.md`.

## Notes

- `list_holidays` isn't employee-scoped, so it has no caller-identity check.
  `find_employee` is gone and `get_pto_balance` moved to the MCP layer (M6.2).
- Each toolset opens its own MCP session (four per process); `tool_filter` and
  `require_confirmation` are toolset-wide, which is why reads and writes are split.
- The deterministic-router and LangGraph alternatives live in `scratch/` and are not part of
  this flow.
