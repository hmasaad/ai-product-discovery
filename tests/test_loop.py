from datetime import date

from discovery.agents.loop import DevelopmentLoopAgent
from discovery.engine import run_engine
from discovery.models import IntelPillar, ReviewStatus, Signal, SignalKind, Theme, Verdict


def _signal(**overrides) -> Signal:
    payload = {
        "id": "complaints",
        "pillar": IntelPillar.user,
        "kind": SignalKind.feedback,
        "title": "Monthly spending is opaque",
        "body": "Users struggle to see where spending goes.",
        "source": "Support",
        "observed_at": date(2026, 9, 2),
        "strength": 0.9,
        "polarity": "pain",
        "volume": 23,
        "tags": ["frequency:high", "severity:moderate-high"],
    }
    payload.update(overrides)
    return Signal(**payload)


def _spending(status: ReviewStatus = ReviewStatus.approved):
    theme = Theme(
        id="spending",
        label="Spending explanations",
        keywords=["spending"],
        problem="Users struggle to understand where their money is going each month.",
        idea_title="AI Financial Spending Analyst",
        idea_summary="Explain the month from transactions people already have.",
        solutions=["YNAB", "Monarch", "Copilot", "Spreadsheets"],
        mvp=[
            "Automatic spending analysis",
            "Monthly explanation",
            "Anomaly detection",
            "Personalized recommendations",
        ],
        risks=["Financial trust", "Privacy", "Incorrect recommendations"],
        open_questions=[
            "Will users trust AI recommendations?",
            "What level of personalization is expected?",
        ],
        experiment="Prototype → 20 users → measure engagement",
    )
    signals = [
        _signal(),
        _signal(
            id="tools",
            pillar=IntelPillar.market,
            kind=SignalKind.competitor,
            title="Budgeting tools",
            body="Existing tools visualize spending but provide limited contextual explanations.",
            source="Market notes",
            strength=0.7,
            polarity="movement",
            volume=8,
            tags=[],
        ),
    ]
    opportunity = run_engine(signals, [theme], "Young professionals")[0]
    opportunity.status = status
    return opportunity


def test_approved_brief_closes_the_loop():
    opportunity = _spending()
    loop = DevelopmentLoopAgent().write(
        opportunity,
        "AI Financial Spending Analyst exists because young professionals cannot see the month.",
    )
    assert [stage.title for stage in loop.stages] == [
        "AI Product Discovery Agent",
        "Opportunity Graph",
        "AI Product Manager",
        "PRD",
        "AI Software Architect",
        "AI Developer Agent",
        "AI QA Agent",
        "AI Review Agent",
        "Production",
        "Product Analytics",
        "Product Discovery",
    ]
    prd = loop.stages[3]
    assert prd.status.value == "ready"
    assert "Problem: Users struggle to understand where their money is going each month." in prd.lines
    assert "Goal: Prototype → 20 users → measure engagement" in prd.lines
    assert "Story: As Young professionals, Automatic spending analysis." in prd.lines
    assert loop.pm_brief.startswith("Opportunity: AI Financial Spending Analyst")
    assert "Scope stops at the recommended experiment. Open questions stay open." in loop.pm_brief
    assert "Why this opportunity exists:" in loop.pm_brief
    developer = loop.stages[5]
    assert developer.lines == [
        "Implement: Automatic spending analysis.",
        "Implement: Monthly explanation.",
        "Implement: Anomaly detection.",
        "Implement: Personalized recommendations.",
        "Done when: Prototype → 20 users → measure engagement",
    ]
    assert loop.stages[8].summary == "In the experiment. Prototype → 20 users → measure engagement"
    assert loop.return_signals[0].title == "AI Financial Spending Analyst experiment"
    assert loop.return_signals[0].body == "Prototype → 20 users → measure engagement"
    assert loop.stages[-1].status.value == "returned"
    assert loop.stages[-1].summary == "These measurements re-enter product discovery."


def test_unapproved_brief_stops_before_the_prd():
    loop = DevelopmentLoopAgent().write(_spending(ReviewStatus.pending_review))
    assert loop.stages[2].status.value == "ready"
    assert loop.stages[2].summary.endswith("The PRD waits for approval.")
    assert loop.stages[3].status.value == "waiting"
    assert loop.stages[8].status.value == "waiting"
    assert loop.return_signals == []


def test_parked_opportunity_stays_in_discovery():
    opportunity = _spending()
    opportunity.verdict = Verdict.park
    opportunity.status = ReviewStatus.approved
    loop = DevelopmentLoopAgent().write(opportunity)
    assert loop.stages[0].status.value == "ready"
    assert loop.stages[2].summary == "Parked opportunities stay in discovery."
    assert loop.pm_brief == ""
    assert all(stage.status.value == "waiting" for stage in loop.stages[2:])


def test_contradicting_evidence_holds_production():
    theme = Theme(
        id="coach",
        label="Financial coaching",
        keywords=["budgeting"],
        problem="People struggle to decide what to do with their money.",
        idea_title="AI Financial Coach",
        idea_summary="Coach the next money decision.",
        mvp=["A monthly money note"],
        experiment="Prototype the note with ten owners.",
    )
    signals = [
        _signal(
            id="ask",
            title="Owners ask for a budgeting coach",
            body="Customers keep asking for help budgeting.",
            tags=[],
            volume=4,
        ),
        _signal(
            id="education",
            pillar=IntelPillar.product,
            kind=SignalKind.analytics,
            title="low engagement with existing education content",
            body="Budgeting guides are rarely finished.",
            source="Product analytics",
            strength=0.85,
            polarity="neutral",
            volume=1,
            tags=[],
        ),
    ]
    opportunity = run_engine(signals, [theme], "Small business owners")[0]
    opportunity.status = ReviewStatus.approved
    loop = DevelopmentLoopAgent().write(opportunity)
    review = next(stage for stage in loop.stages if stage.title == "AI Review Agent")
    production = next(stage for stage in loop.stages if stage.title == "Production")
    assert review.status.value == "hold"
    assert "low engagement with existing education content" in review.summary
    assert production.status.value == "waiting"
    assert loop.return_signals == []
