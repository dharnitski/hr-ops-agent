# ADK vs. LangGraph: routing this agent

Comparison from hands-on rebuilds, not vendor docs: `scratch/workflow_router.py` (ADK
`Workflow`, all three specialists) and `scratch/langgraph_router.py` (LangGraph, policy
path only). Both reuse the same rules, instructions, and tools unchanged. Findings are
pinned to `google-adk` 2.9.2 / `langgraph` 1.2.12 (2026-09-26) — re-verify before relying on
this, see "Re-test before trusting this" below.

## Routing primitive

- **ADK `Workflow`:** a graph of nodes and tuple edges (`("START", classify)`, then a dict
  mapping route names to nodes). A node is a plain function or an agent; a function node
  routes by returning `Event(output=..., actions=EventActions(route=...))`. Run with
  `Runner(node=workflow, ...)`. `SequentialAgent`/`ParallelAgent`/`LoopAgent` are deprecated
  in favor of this.
- **LangGraph `StateGraph`:** nodes are plain functions returning a partial state update;
  edges are explicit (`add_edge`, `add_conditional_edges` with a router function returning a
  key). Compiles to a runnable graph.
- Shape is nearly identical: classify node picks a route, route maps to a handler node,
  handler produces the answer. Neither is meaningfully harder to build once the rules exist.

## State model

- **ADK:** implicit — session + event history. An agent node in `single_turn` mode reads
  from node input, not conversation history, because chat-mode agents expect session state
  a bare `Workflow` run doesn't populate. This is why `single_turn()` copies the specialist
  agents in `workflow_router.py` rather than reusing them as-is (`hr_agent/agents/pto.py`
  etc. run fine under the LLM router, not under `Workflow`, without that copy).
- **LangGraph:** explicit — a `TypedDict` (`State` in `langgraph_router.py`) that every node
  reads and merges into. Nothing is implicit; what a node can see is exactly what's in the
  dict. `ty` cannot check `StateGraph(State)` — carries an ignore comment, a real (if minor)
  cost of the generic-graph API.
- Trade-off: ADK's session model is less code but the `single_turn` requirement is a
  non-obvious gotcha you only find by running it. LangGraph's explicit state is more
  boilerplate but nothing is surprising.

## Framework glue

- LangGraph needs a chat-model wrapper (`ChatGoogleGenerativeAI(..., vertexai=True,
  location="global")`), an agent constructor (`create_agent`, since
  `create_react_agent` is deprecated toward removal in V2.0), and tools passed as plain
  functions with docstrings — three extra concepts ADK's `Agent` class collapses into one
  constructor call.
- Agents nest as compiled subgraphs invoked inside a node (`policy_agent.invoke(...)` called
  from the `policy` node), vs. ADK where an agent *is* a node directly.
- Net: LangGraph is more explicit, ADK is more integrated. Neither is more capable for this
  slice.

## Where LLM-driven delegation beats a graph, and vice versa

- **Deterministic graph wins** when intents are enumerable and keyword-detectable (PTO vs.
  payroll vs. policy) and you want the routing decision to be unit-testable without a model
  call, cheaper (skips the router's LLM call), and reproducible.
- **LLM delegation wins** on paraphrases the regex misses, multi-intent input in one message
  (the rule-based classifier takes first match only — one rule wins, the rest is dropped),
  and cases needing a clarifying question before routing. The LLM router (`hr_agent/agent.py`)
  handles all three; `workflow_router.py` handles none.
- Neither framework changes this trade-off — it's deterministic-vs-LLM classification, not
  ADK-vs-LangGraph. A hybrid (deterministic graph at the root, an LLM classifier node for the
  ambiguous cases) is possible in either framework; not built here.

## Recommendation for this agent

**Stay on ADK.** Reasons specific to this project, not a general framework verdict:

1. Module 7's deploy path (`adk deploy agent_engine` / `cloud_run` / `gke`) is ADK-native;
   LangGraph would need its own deploy story, duplicating Module 7's work for no benefit here.
2. The MCP toolset integration (`McpToolset`, `tool_filter`) is already built and tested
   against ADK; porting it is extra work with no functional gain — LangGraph would talk to
   the same MCP server through a different client.
3. The routing gotchas found (the `single_turn` requirement, `Workflow` can't be an
   `LlmAgent` sub-agent) are now known and documented, not blocking.

**What would change this answer:** a team already standardized on LangChain/LangGraph
elsewhere (glue cost disappears), a requirement to run outside GCP/Agent Engine (Module 7's
ADK-specific deploy advantage disappears), or hitting a real limitation of `Workflow` at
scale that this small probe wouldn't surface (e.g. complex fan-out/fan-in, retry policies —
not exercised by either rebuild).

## Re-test before trusting this

Both `google-adk` and `langgraph`/`langchain` are moving fast (see `docs/COURSE.md` currency
notes; `create_react_agent` was already deprecated mid-course). Before citing this doc again,
re-check: whether `Workflow` can be an `LlmAgent` sub-agent yet (would remove the
`single_turn` workaround and the root-must-be-a-workflow constraint), and whether
`create_agent`'s API has moved again.
