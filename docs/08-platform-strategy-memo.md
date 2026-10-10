# Platform strategy memo: HR operations agents, next 12-24 months

To: engineering and HR technology leadership. Date: 2026-10-10. Decision requested: fund a
gated pilot, not a full rollout. Companion docs: `docs/08-reference-architecture.md`,
`docs/08-roi-cost-model.md`.

## Recommendation

**Buy where a vendor already covers the task; build the layer around it that vendors will not.**
Concretely:

1. **Own the tool layer** (the MCP server: schemas, authorization, limits, audit). It is the
   durable asset: it encodes who may do what with HR data and works with any agent runtime.
2. **Own the standards**: the eval standard, guardrail standard and launch bar. They are what
   lets us accept, compare or reject any agent, built or bought.
3. **Rent the agent runtime and model.** Stay on Agent Engine and the current model tier, and
   keep both swappable (model ID is an env var; the tool layer does not import the agent).
4. **Prefer the HCM vendor's built-in assistant for in-system self-service** if it meets the
   launch bar. Build only for what crosses systems (HCM, handbook, ticketing, approvals) or
   needs controls the vendor does not offer.

## Where we are

A working single-region prototype on mock data: three specialist agents behind a router, an
IAM-gated MCP server, server-side authorization, confirmation on writes, audit log,
31 eval cases gating changes, deployed to Agent Engine and Cloud Run, with traces, a dashboard
and alerts. Measured: about $0.0026 and 2 to 7 seconds per turn. **Not done:** real HCM
integration, real authentication (`identify_caller` is a stub), shared state for rate limits
and idempotency, any real traffic.

## Options

| | Build (this path) | Buy (vendor assistant) | Hybrid (recommended) |
|---|---|---|---|
| Time to first value | Slowest: needs HCM integration and SSO | Fastest | Pilot on one read-only use case |
| Fit to our data and processes | Highest | Limited to what the vendor exposes | High where it matters |
| Control of authorization, audit, evals | Full | Whatever the vendor ships | Full for our layer; test the vendor's against our bar |
| Cross-system tasks | Possible | Usually not | Possible |
| Ongoing cost | About 0.2 FTE plus platform churn | Per-seat licence (unquoted) | Both, smaller |
| Lock-in | Low if tool layer stays portable | Highest | Medium |

Licence price, vendor roadmaps and which assistants meet the bar are **unknown**; this memo
does not assume them. Step 1 below resolves that.

## Why not full build

Per `docs/08-roi-cost-model.md`, break-even is about 7,500 employees under assumptions that
are unmeasured, and the cost is engineering time, not inference. Below roughly 3,000
employees the case is weak. Building commodity self-service (PTO balance) that a vendor ships
spends the scarce resource on the least differentiated part.

## Why own the tool layer and standards

- Every serious failure mode found so far was caught at this layer or by these standards: a
  tool that returned balances to any caller (M6.2), stateful sessions breaking on scale-out
  (M8.4), a loop that cost 20x per turn (M8.4), and prompt-only rules that did not hold.
- The model and runtime churn fast: model IDs retire on short notice (2.5 retires
  2026-10-20), the agent framework's confirmation and compaction APIs are marked experimental,
  the deploy CLI changes flags between releases, and the MCP SDK replaced its server class
  between major versions. The tool layer and evals survive all of that; the agent code does not.
- Anything we buy can be judged against the same eval set and guardrail standard.

## Roadmap

| Window | Goal | Exit gate (all measured) |
|---|---|---|
| 0-3 months | Resolve buy vs build for self-service: evaluate the HCM vendor's assistant against our launch bar. Replace `identify_caller` with verified SSO. Connect the tool layer to real HCM, read-only. Move rate limits and idempotency to a shared store. | Real identity end to end; zero unauthorized access in adversarial evals on real data shapes; load test across both Cloud Run instances. |
| 3-9 months | Pilot to one population (about 500 to 1,000 employees), read-only plus PTO requests with confirmation. Instrument deflection and real cost per turn. | Task success and latency within the launch bar on live traffic; deflection and inquiry cost measured; cost model rerun on real numbers. |
| 9-18 months | Scale if the rerun clears break-even; otherwise stop or move to buy. Add approvals and payroll workflows only after a security review. Add model-tier routing only if cost per turn passes about $0.05. | Pilot-level metrics hold at 5x volume; incident drill repeated with no unalerted failure. |
| 18-24 months | Reassess platform: runtime, framework, vendor landscape. | Triggers in `docs/07-deployment-tradeoffs.md` or a vendor meeting the bar for cross-system tasks. |

## Risks

| Risk | Impact | Mitigation |
|---|---|---|
| Unverified identity reaches production | Anyone can act as any employee | Gate 0-3 on verified SSO; do not widen beyond mock data before it |
| Benefits fail to materialize (deflection below about 20%) | Build never pays back | Measure deflection in the pilot; stop rule at the 9-month gate |
| Framework and runtime churn | Recurring rework | Keep logic in the tool layer; pin versions; re-verify flags each upgrade |
| Silent failure of a dependency | Cost, latency, user trust | Turn guard and four alerts are in place; add a standing drill |
| Sensitive data in logs or traces | Privacy incident | Allowlisted audit, trace content off; re-verify after every redeploy (two env vars vanished once) |
| Single-person knowledge | Slow recovery | Runbook, reference architecture and standards are written down |

## Decisions needed

1. Approve a vendor-assistant evaluation against our launch bar (owner: HR technology).
2. Approve SSO and real HCM read-only integration as the next engineering milestone.
3. Agree the stop rule: below the deflection and cost thresholds at the 9-month gate, we stop
   building and move to buy.
