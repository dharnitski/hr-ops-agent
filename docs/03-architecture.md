# Architecture

```mermaid
flowchart LR
    user([User])

    subgraph adk["ADK process — hr_agent/"]
        router["hr_ops_agent<br/>router, no tools<br/>declines unmatched"]
        pto["pto_agent"]
        payroll["payroll_agent"]
        policy["policy_agent"]
        local_pto["local tool<br/>list_holidays"]
        local_pol["local tool<br/>search_handbook<br/>(keyword retrieval)"]
        ts_hcm["hcm_toolset<br/>filter: get_employee,<br/>get_pto_balance,<br/>submit_pto_request"]
        ts_pay["payroll_toolset<br/>filter: get_payroll_run"]
    end

    subgraph mcp["MCP server — mcp_server/"]
        schema["schema validation<br/>strict args, typed outputs"]
        handlers["handlers<br/>get_employee<br/>get_pto_balance<br/>submit_pto_request<br/>get_payroll_run"]
        store[("mock HCM data<br/>+ idempotency store<br/>in memory")]
    end

    handbook[("handbook<br/>sections")]

    user --> router
    router -- transfer_to_agent --> pto
    router -- transfer_to_agent --> payroll
    router -- transfer_to_agent --> policy
    pto --> local_pto
    pto --> ts_hcm
    payroll --> ts_pay
    policy --> local_pol --> handbook
    ts_hcm -- "Streamable HTTP" --> schema
    ts_pay -- "Streamable HTTP" --> schema
    schema --> handlers --> store

    subgraph planned["Planned — Module 6"]
        identity["caller identity<br/>from transport"]
        hitl["HITL confirm / approval"]
        audit["audit log"]
    end
    identity -.-> schema
    hitl -.-> ts_hcm
    audit -.-> handlers

    classDef soft fill:#fff3cd,stroke:#b58900,color:#000
    classDef hard fill:#d4edda,stroke:#2e7d32,color:#000
    classDef plan fill:#f5f5f5,stroke:#888,stroke-dasharray: 4 3,color:#000
    class router,pto,payroll,policy,ts_hcm,ts_pay soft
    class schema,handlers,store hard
    class identity,hitl,audit plan
```

**Legend.** Yellow = soft controls (prompt rules, routing descriptions, `tool_filter`): the
model or in-process config can bypass them. Green = hard controls (schema validation,
server-computed hours, idempotency): enforced regardless of what the model sends. Dashed
grey = planned, not built.

- `list_holidays` is the only remaining local tool; it isn't employee-scoped, so there's no
  caller-identity question for it. `find_employee` and `get_pto_balance` (originally local,
  see M1.8) are retired: balance lookups now go through the MCP layer's `get_pto_balance`,
  self-service only like `get_employee`; name-based lookup has no MCP equivalent and was
  dropped rather than given one (M6.2).
- Each specialist opens its own MCP session; `tool_filter` is per toolset.
- The deterministic-router and LangGraph alternatives live in `scratch/` and are not part
  of this flow.
