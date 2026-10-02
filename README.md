# AI Product Discovery

An agent that turns market, user, and product evidence into product opportunities a person can review.

It does not ask “what should we build?” and invent an answer. Each cycle gathers evidence, names the problem, maps the gap, proposes a bet, and validates it against an explicit rubric. Approved memos are the handoff to a product manager.

```
                 AI PRODUCT DISCOVERY
                       AGENT
                          │
        ┌─────────────────┼─────────────────┐
        ↓                 ↓                 ↓
   Market Intel      User Intel       Product Intel
        │                 │                 │
   ┌────┴────┐       ┌────┴────┐       ┌────┴────┐
   │Competitor│       │Reviews  │       │Analytics│
   │Trends    │       │Feedback │       │Features │
   │News      │       │Forums   │       │Usage    │
   └──────────┘       └─────────┘       └─────────┘
        │                 │                 │
        └─────────────────┼─────────────────┘
                          ↓
                  Opportunity Engine
                          ↓
                Problem Identification
                          ↓
                  Opportunity Mapping
                          ↓
                    Idea Generation
                          ↓
                   Validation Agent
                          ↓
                 Product Opportunity
                          ↓
              ┌───────────┴───────────┐
              ↓                       ↓
          AI Product Manager      Human Review
```

## Run the sample

The sample workspace is Northstar, a fictional product-analytics company. Twenty signals are enough to see pursue, investigate, and park side by side.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
discovery demo
discovery serve
```

Open http://127.0.0.1:8000. Approve a bet and it shows up in the PM queue as a decision memo.

## Your own evidence

A workspace is three JSON files:

- `context.json` — product name, category, audience, mission
- `themes.json` — optional vocabulary for problems you already know how to describe
- `signals.json` — evidence

Each signal belongs to one pillar:

| Pillar | Kinds |
| --- | --- |
| market | `competitor`, `trend`, `news` |
| user | `review`, `feedback`, `forum` |
| product | `analytics`, `feature`, `usage` |

Set `polarity` to `pain`, `demand`, `adoption`, `movement`, or `neutral`. Strength is a number from 0 to 1. Metrics are optional and make a cluster falsifiable.

```bash
discovery ingest path/to/signals.json
discovery run
discovery list
discovery brief opp-instrumentation
discovery review opp-instrumentation approved --note "Pilot with five teams"
```

Drop more JSON into `data/inbox` and leave a cycle running:

```bash
discovery watch --interval 30
```

`discovery ingest` adds signals. Loading a workspace replaces the signal set and keeps review decisions when the same opportunity comes back.

## Market research agent

The market research agent runs on every cycle, ahead of the opportunity engine. It reads industry trends, emerging technology, competitor launches, pricing changes, market gaps, customer complaints, new startups, product launches, and regulatory changes.

Each result is a market signal:

```
Trend:
AI-powered personal finance

Evidence:
- Competitor A launched X
- Users increasingly request Y
- Search interest increased
- Multiple startups entering space

Potential implication:
Opportunity for automated financial planning
```

Open the Market tab in the review board, or run `discovery market`.

## User intelligence agent

The user intelligence agent clusters complaints from app reviews, support tickets, feature requests, surveys, interviews, community discussions, product analytics, and other feedback. Each cluster is a share of the feedback, and the stronger clusters become unmet needs.

```
1,284 user feedback items

Clustered problems
Authentication          18%
Performance             14%
Reporting               11%
Onboarding               9%
Notifications            7%

Unmet needs
Authentication — People cannot get authentication done.
```

A weak or one-off request stays in the chart and does not become an unmet need. Set `volume` on a signal when one record stands for many feedback items.

Open the Users tab, or run `discovery users`.

## Competitor intelligence agent

The competitor intelligence agent builds a matrix from `competitors.json`, then keeps reading. Dated moves become behavior, behavior becomes a feature trajectory, the trajectory becomes a strategic direction, and the direction leaves a potential market gap.

```
                    Product A   Product B   Product C
AI Assistant            ✓           ✓           ✗
Offline Mode            ✗           ✓           ✓
Automation              ✓           ✗           ✗
Analytics               ✓           ✓           ✓
Integrations            3           8           5
Pricing                $20         $30         $15

Feature trajectory
The field is moving toward AI assistance.

Potential market gap
Automation is only on Product A.
```

A capability that has been on for years stays a baseline. Only a change inside the last 540 days counts as a move. Open the Competitors tab, or run `discovery competitors`.

## Opportunity detection engine

Every signal becomes an opportunity candidate. Signals about the same problem share one chain.

```
Signal:
Users repeatedly complain about manually categorizing financial transactions.

Problem:
Transaction categorization is time-consuming.

User segment:
Small business owners

Pain:
Manually categorizing financial transactions.

Existing solutions:
Existing apps provide categorization, but require manual correction.

Gap:
Existing apps provide categorization, but require manual correction.

Opportunity:
AI-powered adaptive transaction categorization
```

A candidate with only one signal stays on the Detection tab until a second source arrives. The review board still requires that second source, plus the validation checks, before a verdict.

Open the Detection tab, or run `discovery detect`.

## Opportunity validation agent

Before an idea is handed to a product manager, a second agent challenges it. Supporting evidence and contradicting evidence are kept apart. A question with no evidence stays open. An empty against column is called unchallenged, not confirmed.

```
Opportunity: AI Financial Coach

Evidence for
✓ 37 customer requests
✓ competitor activity
✓ recurring support complaints
✓ growing usage of budgeting features

Evidence against
⚠ low engagement with existing education content
⚠ users may prefer human advisors
⚠ high trust requirements
```

The challenge also asks whether the problem is real, who feels it, how often, how painful it is, what alternatives exist, whether the market is large enough, whether it is feasible, what users would pay, and what evidence contradicts it.

Open the Validate tab, or run `discovery validate`.

## Product opportunity brief

The handoff to a product manager is a brief: the problem, the evidence, and one experiment. It does not say “build this.”

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PRODUCT OPPORTUNITY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Problem
Users struggle to understand where their
money is going each month.

Target users
Young professionals

Observed pain
High frequency / moderate-high severity

Existing solutions
YNAB
Monarch
Copilot
Spreadsheets

Gap
Existing tools visualize spending but provide
limited contextual explanations.

Opportunity
AI Financial Spending Analyst

Potential MVP
• Automatic spending analysis
• Monthly explanation
• Anomaly detection
• Personalized recommendations

Evidence
23 user complaints
8 competitor observations
4 market signals
3 internal analytics signals

Risks
• Financial trust
• Privacy
• Incorrect recommendations

Open questions
• Will users trust AI recommendations?
• What level of personalization is expected?

Recommended experiment
Prototype → 20 users → measure engagement
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

`discovery brief opp-instrumentation` prints that brief for a stored opportunity. The same document leads each memo.

## Product loop

An approved brief is the intake for the product manager. The later stages stay inside that brief. Production is the experiment, and the measurement re-enters discovery.

```
AI Product Discovery Agent
             ↓
      Opportunity Graph
             ↓
      AI Product Manager
             ↓
           PRD
             ↓
      AI Software Architect
             ↓
       AI Developer Agent
             ↓
          AI QA Agent
             ↓
       AI Review Agent
             ↓
       Production
             ↓
      Product Analytics
             │
             └───────────────┐
                             ↓
                    Product Discovery
```

A parked opportunity stays in discovery. A brief that is not approved stops before the PRD. Contradicting evidence holds the review, so the experiment does not start.

Open the Loop tab, or run `discovery loop opp-instrumentation`.

## Product intelligence memory

The agent keeps a record of the product, its features, users, problems, competitors, experiments, decisions, metrics, feedback, rejected ideas, successful ideas, and failed experiments. Questions are answered from that record.

```
Have we seen this problem before?
Why did we reject this feature six months ago?
Which customer problems are repeatedly appearing?
Which opportunities have strong evidence but haven't been tested?
```

A problem counts as seen before when two or more feedback items land on it. A rejection from six months ago is a rejected idea dated about half a year before the question. A pursue opportunity with no recorded experiment result is still untested.

Open the Memory tab, or run `discovery memory` and `discovery ask "Have we seen this problem before?"`.

## Opportunity intelligence engine

One path runs the six capabilities:

1. Signal ingestion
2. Problem clustering
3. Opportunity detection
4. Evidence graph
5. Opportunity validation
6. Opportunity → PRD handoff

The handoff writes a PRD only after the opportunity is approved. A parked opportunity stays in discovery.

Open the Engine tab, or run `discovery engine opp-instrumentation`.

## AI experimentation agent

The discovery agent asks what might be worth pursuing. The experimentation agent writes five testable hypotheses, then picks the least expensive experiment that can reduce the unknown. A full build is not that experiment.

1. Hypothesis Generator
2. Experiment Designer
3. Experiment Specification
4. Success Metric Designer
5. Experiment Executor
6. Results Analyzer
7. Learning Engine

Each hypothesis names a target segment, the expected behavior, a metric, a threshold, a time period, a confidence, and the evidence behind it. Confidence is High with two or more supporting signals, Medium with one, and Low when none are recorded.

For an open question about use, the designer compares four options:

| | Experiment | Cost | Information |
| --- | --- | --- | --- |
| A | Build full feature | Very High | High |
| B | Build prototype | Medium | High |
| C | Fake-door test | Low | Medium |
| D | Interview users | Very Low | Medium |

It selects C plus targeted interviews. A parked opportunity, or one that says not to schedule a build, selects interviews only.

Each selected experiment is then a specification: objective, hypothesis, audience, variant, control, success metrics, guardrail metrics, sample size, duration, decision threshold, risks, expected learning, and the outcomes continue, iterate, or reject. The fake-door threshold is a click-through rate of at least 8%. That bar is not an observed result.

A recorded success validates the opportunity and the product manager can take the brief. A recorded failure, a parked opportunity, or contradicting evidence that is still open is reject or iterate. With no result recorded, the product manager waits. A result counts only when memory stored it against that opportunity.

The execution agent then takes nine steps: create the experiment, configure the audience, configure the feature flag, start, monitor metrics, detect anomalies, stop when necessary, analyze results, and write the report. It reaches analytics, feature flags, the product database, the survey system, the A/B testing platform, user feedback, and the experiment dashboard. A flag, a start, and a stop change production, so they wait for approval. Approval records the instruction. No flag service is connected, so the variant does not start serving traffic.

The monitor watches the primary metric, the guardrails, and the quality signals while the experiment is running. The control is the behavioral baseline. A move of more than 2% is an anomaly. A guardrail that leaves the baseline while the variant is up is a warning. A guardrail 25% or more off the baseline, or a primary drop of 10%, is critical and the agent recommends a stop that still needs approval.

The results analysis writes a learning. It names the hypothesis, what was observed, the supporting evidence, and the contradicting evidence. When demand shows up and then fades, the interpretation is that initial demand exists and sustained value is not yet established. The next experiment tests retention. The analysis does not declare a winner.

Each experiment is also stored as a chain: opportunity, hypothesis, experiment, result, learning, decision. The next design reads that chain. When an earlier experiment found that clicks were high and follow-through was low, the next experiment tests actionable recommendations instead of informational recommendations.

The same agent keeps an experiment portfolio. Each row is an experiment with a status and a risk. Status is planned until a start is approved, running once it is, and complete once a result is stored. Risk follows the cost of the selected experiment. From the set, the agent calls out experiment conflicts, user overlap, resource consumption, statistical contamination, priority, and expected information gain.

The value engine ranks that set by expected information gain times decision impact, divided by experiment cost. High uncertainty produces high information gain. A high-impact decision that a low-cost experiment can settle is the one to prioritize. A finished experiment and an expensive build rank lower.

Open the Experiment tab, or run `discovery experiment opp-instrumentation`.

## Opportunity graph

Opportunities are not only a list. Each one sits on a path the agent can walk backward:

```
Market → Trend → Users → Problems → Opportunity → Feature → MVP
                 Competitors → Gaps → Opportunity → Product → Business case
```

`discovery graph opp-instrumentation` answers why that opportunity exists and lists the signals on the path. The same trace is on the Graph tab and on each memo.

The path continues after the opportunity:

```
Hypothesis → Experiment → Observation → Learning → Decision → Product change → New observation → New hypothesis
```

A new observation starts the next hypothesis, so the graph stays a learning system.

## How a judgment is made

Signals that share a workspace theme are clustered. At least two signals are required. Anything left over is clustered by shared language and marked emergent.

The validation agent then asks:

- Is there user evidence?
- Is there product evidence?
- Is there market context?
- Are there at least three independent signals?
- Is there a metric?
- Is there unmet pain or an explicit ask, rather than adoption of something that already exists?

**Pursue** requires user evidence, at least three signals, an opportunity score of 55 or higher, and most checks passing.

**Investigate** is a real cluster that is not decision-ready.

**Park** is a thin case, or table stakes: competitors already offer it and the evidence describes adoption rather than pain.

Scores are a review aid. The memo shows the checks, the gap, and the next evidence to collect.

## Extending intel

`IntelSource.fetch()` is the connector boundary in `src/discovery/intel.py`. A live source should return `Signal` records for one pillar. The sample data is a file source so a cycle can run from exports you already have: review pulls, interview notes, changelog notes, and analytics snapshots.
