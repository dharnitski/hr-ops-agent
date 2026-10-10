# ROI and cost model

Whether this agent pays for itself, and which cost lines matter. **Only two inputs are
measured**: inference cost per turn ($0.0026, 9 mixed turns, `docs/08-dashboard.md`) and turn
latency. Everything else is an assumption to be replaced with the first pilot's data. Written
2026-10-10; no real traffic or HCM data has been seen (mock data only).

## Result

- **Inference is not the cost.** At 20,000 employees it is about $78/month, 1% of total cost.
  The cost is the engineers who build and maintain the agent.
- **Break-even is about 7,500 employees** under the base assumptions below. Below that, the
  agent costs more than the HR time it saves; above it, savings grow linearly.
- **The two assumptions that move break-even are deflection rate and the cost of an
  HR-handled inquiry.** Neither is measured. Model price, model tier and infra are second-order.

## Assumptions

| Input | Base | Source |
|---|---|---|
| Conversations per employee per month | 0.5 | Assumed |
| Turns per conversation | 3 | Assumed |
| Cost per turn | $0.0026 | **Measured**: flash-lite at $0.30/$2.50 per 1M tokens, about 6.5k input tokens per turn |
| Deflection (conversation resolved without an HR contact) | 40% | Assumed; only PTO, holidays and handbook questions are in scope |
| Cost of an HR-handled inquiry | $5 (6 min at $50/h loaded) | Assumed |
| Build, amortized over 24 months | $4,167/month | Assumed: 6 engineer-months at $200k/yr loaded, including real HCM integration and SSO that do not exist yet |
| Maintenance | $3,333/month | Assumed: 0.2 engineer at $200k/yr loaded |

Monthly benefit = employees x conversations x deflection x inquiry cost
= $1.00 per employee per month at base. Monthly cost = $7,500 fixed + inference + infra.

## Base case

| Employees | Turns/month | Inference | Benefit | Net (inference + fixed) |
|---|---|---|---|---|
| 1,000 | 1,500 | $3.90 | $1,000 | -$6,504 |
| 5,000 | 7,500 | $19.50 | $5,000 | -$2,520 |
| 7,500 | 11,250 | $29.25 | $7,500 | about $0 |
| 20,000 | 30,000 | $78.00 | $20,000 | +$12,422 |

Infra is excluded from Net; see below, it adds tens of dollars, not thousands.

## Sensitivity: break-even employees

| Deflection | Inquiry $5 | Inquiry $10 |
|---|---|---|
| 20% | 15,100 | 7,500 |
| 40% | 7,500 | 3,800 |
| 60% | 5,000 | 2,500 |

A 5x worse cost per turn ($0.013, from longer prompts or more thinking tokens) moves
break-even by under 2%, because inference is still under $0.10 per employee-month.

## Other cost lines

| Line | Estimate | Status |
|---|---|---|
| Agent Engine runtime | Bounded above by about $350/month if a 4 vCPU / 8 GiB instance ran all month ($0.0994/vCPU-h, $0.0105/GiB-h); billed on active time, so lower | **Rates unverified**: the official pricing page could not be read; a third-party source lists lower rates. Allocation per instance not checked. |
| Memory Bank | Cents to a few dollars: one fact per turn, $0.085 per 1M writes and per 3M reads, $0.30/GiB-month (checked 2026-10-01, `docs/COURSE.md`) | A third-party source lists $0.25 per 1,000 events; at 11k turns that is still under $10/month. Reconcile on the bill. |
| Cloud Run `mcp-server` | Near zero: scales to zero, 0 to 2 instances | Cost is latency (about 4.5s cold start), not money |
| Logging, Trace, Monitoring | Unmeasured | Audit lines are small and allowlisted; check billing export after a week of traffic |
| Eval gate | About $0.16 per run (31 cases, 2 turns each at the measured rate; judge calls add some) | Estimate; manual trigger only |

## Risk-adjusted view

- **Failure cost is latency and trust, not dollars.** The M8.4 drill made turns cost about 20x
  ($0.052). A day-long outage at 250 turns/day is about $13. `TurnGuardPlugin` now caps a turn
  at 12 model calls and the alerts fire within minutes (`docs/08-failure-drill-rca.md`).
- **Model-tier routing (M8.3, skipped) cannot move the result.** Even routing everything to a
  tier that costs 10x ($0.026/turn) is $780/month at 20,000 employees, about 10% of fixed cost;
  saving 100% of today's inference is under $80. Revisit only if per-turn cost passes about
  $0.05 or volume passes about 1M turns/month.
- **Not priced:** an unauthorized-access incident, a wrong PTO or payroll answer, and a
  failed audit. The guardrail stack (`docs/06-guardrail-standard.md`) exists to make these
  rare, but the model does not put a dollar value on them. Any one real incident at HR scale
  could exceed a year of savings.
- **Not in the benefit:** employee time saved waiting for HR, faster payroll approvals, fewer
  errors. All real, none measured.

## What to measure first

1. **Deflection**: share of conversations that end without a follow-up HR contact within a
   week. Needs the HR ticket system as a second data source; today's dashboard cannot see it.
2. **Cost of an HR inquiry**: from HR's own ticket data, not this table.
3. **Turns per conversation and conversations per employee**: from `turn_complete` logs.
4. **Real cost per turn** with real prompts and real HCM payloads (tool results will be larger
   than mock data); confirm output tokens include thinking.
5. **Runtime, Memory Bank and observability lines** from the billing export after a week.
6. **Task success**: the eval gate is offline; define an online proxy before claiming a number.

## What would change the answer

- Break-even depends on the 24-month build amortization. If real HCM integration and SSO cost
  double, break-even roughly doubles with them.
- If the audience is under about 3,000 employees, the case rests on benefits the model does not
  count; buying the HCM vendor's built-in assistant (if any) likely beats building
  (`docs/08-platform-strategy-memo.md`).
