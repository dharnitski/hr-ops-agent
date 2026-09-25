# Course: HR Ops Agent

Self-study course built by pairing on a capstone: an **HR Ops Agent** over mock HCM data
(employees, PTO balances, holidays, payroll records) that answers questions and performs
actions such as submitting PTO requests or flagging payroll discrepancies.

Focus areas: Google ADK, Vertex AI / Agent Engine, MCP, multi-agent orchestration, agent
evaluation, guardrails for HR/payroll data, observability, and inference cost.

Tutor rules, resume behavior, and session bootstrapping live in the "Tutor mode" section
of `AGENTS.md` — read that first. Progress, decisions, and interview notes live in
`docs/PROGRESS.md`.

---

## API currency notes (checked 2026-09-25)

The syllabus below was written against an earlier mental model of the ADK/Vertex AI
surface. Checked current docs/release notes before Module 1; here's what differs and how
the syllabus is adjusted. Re-verify anything model/API-specific at the point we touch it —
this stack moves fast and these notes will drift.

- **ADK is on 2.x, not 1.x.** `google-adk` 2.0 went GA 2026-05-19; latest is ~2.6.3.
  Breaking change from 1.x: import namespace moved — top-level `from google.adk import
  Context`, agents from `from google.adk.agents import Agent` (not `from adk.agents import
  Agent`). All Module 1 code should target 2.x imports from the start.
- **Workflow Runtime is new in 2.x.** A graph-based deterministic execution engine
  (routing, fan-out/fan-in, loops, retry, state, human-in-the-loop, nested workflows,
  declarative YAML definitions). Module 3's "ADK workflow vs. LLM-driven delegation"
  comparison should use this rather than assuming only the older
  `SequentialAgent`/`ParallelAgent`/`LoopAgent` primitives. **Open question to verify
  hands-on in Module 3:** whether those older workflow-agent classes still exist alongside
  Workflow Runtime or are superseded — check current `adk-docs` at that point.
- **MCP integration import path confirmed:** `from google.adk.tools.mcp_tool.mcp_toolset
  import MCPToolset`. Matches the Module 2 plan as written; also note an in-flight
  compatibility issue between adk-python and `mcp` 2.x SDK — pin versions deliberately in
  `pyproject.toml` and check `google/adk-python` issues if MCP connection errors look
  version-related.
- **Model IDs: move off Gemini 2.5.** Gemini 2.5 Pro/Flash/Flash-Lite are scheduled to
  shut down 2026-10-20 on the Gemini API used via Vertex/Agent Platform — essentially
  during this course. Default to a **Gemini 3.x Flash** model (e.g. `gemini-3.8-flash`,
  GA since 2026-09-02) as the cheap/fast tier and a **Gemini 3.x Pro** model (currently
  preview, e.g. `gemini-3.1-pro-preview`) as the capable tier. Keep the model ID in `.env`
  (`MODEL_ID` or similar) so this is a one-line change when IDs move again — treat exact
  IDs as volatile; confirm against `ai.google.dev/gemini-api/docs/models` or the Vertex
  model garden at Module 1 step 1 and again before Module 8's tier-routing comparison.
- **Platform rebrand:** "Vertex AI Agent Builder" / Agentspace were folded into what
  Google now calls the **Gemini Enterprise Agent Platform** ("formerly Vertex AI") as of
  Cloud Next April 2026. Current docs live under
  `docs.cloud.google.com/gemini-enterprise-agent-platform/...`. Agent Engine itself and the
  ADK CLI deploy commands are unchanged in shape; expect doc URLs and some console labels
  to say "Gemini Enterprise" instead of "Vertex AI". Module 7 deliverable should use current
  terminology but it's fine to keep saying "Agent Engine" for the compute product.
- **Agent Engine deployment confirmed as planned:** `adk deploy agent_engine
  --project=$PROJECT_ID --region=$LOCATION_ID`, `adk deploy cloud_run ...`, `adk deploy gke
  ...`. Agent Engine deploys need a GCS staging bucket. Some deploy args can load from the
  agent's `.env`.
- **Memory Bank still current** for Module 4 long-term memory, now documented as "Agent
  Platform Memory Bank"; ADK auto-orchestrates store/retrieve calls against it when
  configured with `VertexAiMemoryBankService` (name subject to the same 2.x import-path
  churn — recheck at Module 4).

None of the above changes the module structure or learning goals below; it changes which
symbols/model IDs/URLs to type. Adjustments are folded into the relevant steps below where
it matters (env var choices, model IDs, import paths).

---

## Module 1 — Foundations and first ADK agent

1. Environment: `uv` venv, deps, choose Vertex AI (ADC login) or AI Studio key,
   `hr_agent/.env` from `.env.example`, GCP budget alert. Default model: a Gemini 3.x Flash
   ID (confirm current one — see currency notes above).
2. Mock data module (employees with manager, PTO and sick hours; 2026 holidays).
3. Tools: `get_pto_balance(employee_id)`, `list_holidays(year)`. Docstrings and type hints
   as the model-facing contract; return dicts with a `status` field; errors returned as
   data, not exceptions.
4. ADK agent: `root_agent` with name, model from env, description, instruction (never
   guess IDs, report tool errors plainly), tools. Unit tests for the tools.
5. Run with `adk web` / `adk run`; test prompts incl. missing ID, unknown ID, name instead
   of ID. Walk through the trace of one turn.
6. Break-it experiments: vague docstring, removed instruction rule, tool raising an
   exception, two questions in one message. Record findings.
7. Rebuild the agent with no framework in `scratch/react_from_scratch.py` using
   `google-genai` function calling with auto-calling disabled: loop, `MAX_STEPS`, tool
   errors as observations, token/latency counters.
8. Add `find_employee(name)` to both versions; decide zero/multiple-match behavior; note
   the access-control gap for Module 6.
9. Write `docs/01-when-to-use-an-agent.md`: workflow vs. single agent vs. multi-agent,
   three HR examples, where reliability comes from, one HR-data risk the framework
   doesn't handle.

## Module 2 — Tools and MCP

Build `mcp_server/` with the Python MCP SDK exposing HCM tools (`get_employee`,
`get_payroll_run`, `submit_pto_request`). Typed schemas, clear descriptions, idempotent
writes, structured errors. Connect it to the ADK agent via ADK's MCP toolset
(`google.adk.tools.mcp_tool.mcp_toolset.MCPToolset`), and to a second MCP client to prove
reuse. Tests for the server. Deliverable: `docs/02-tool-contract-guidelines.md`.

## Module 3 — Multi-agent orchestration

Root router plus specialists: PTO agent, read-only payroll agent, policy Q&A agent with
RAG over a sample HR handbook. Compare LLM-driven delegation with ADK workflow /
deterministic flows — check current docs for Workflow Runtime vs. the older
`SequentialAgent`/`ParallelAgent`/`LoopAgent` primitives before building this. Rebuild one
flow in LangGraph for comparison. Deliverable: architecture diagram and
`docs/03-adk-vs-langgraph.md`.

## Module 4 — Memory, state, context engineering

Session state (current employee, pending actions), long-term memory (Agent Platform
Memory Bank when on Agent Engine), trimming and summarizing tool output, keeping sensitive
data out of context unless needed.

## Module 5 — Evaluation

30–50 case eval set (happy path, ambiguous, adversarial incl. prompt injection in a
document and requests for others' salary). Trajectory and response evals with `adk eval`,
an LLM-as-judge rubric, and a launch bar (task success, zero unauthorized access, p95
latency, cost per task). Wire evals into CI as a gate. Deliverable:
`docs/05-eval-standard.md`.

## Module 6 — Safety and governance

Permission boundaries enforced in the tool/MCP layer (act as the requesting user),
human-in-the-loop via ADK callbacks (reads auto, PTO writes need user confirmation,
payroll needs manager approval), audit log of every tool call, rate and blast-radius
limits. Deliverable: `docs/06-guardrail-standard.md`.

## Module 7 — Deploy to the cloud

Deploy the same agent to Vertex AI Agent Engine, Cloud Run, and GKE (`adk deploy
agent_engine`, `adk deploy cloud_run`, `adk deploy gke`). Least-privilege service account,
Secret Manager, CI/CD with eval gate, staging then prod. Compare with Google's Agent
Starter Pack layout. Tear down unused resources. Deliverable:
`docs/07-deployment-tradeoffs.md`.

## Module 8 — Observability, cost, Staff-level artifacts

OpenTelemetry traces to Cloud Trace; dashboard of task success, tool error rate, latency,
cost per task. Model-tier routing (Flash vs. Pro — confirm current Gemini 3.x IDs) with
measured savings. A failure drill with an RCA. Deliverables:
`docs/08-reference-architecture.md`, `docs/08-platform-strategy-memo.md` (12–24 months,
build vs. buy), `docs/08-roi-cost-model.md`.
