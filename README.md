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
