from datetime import date

from discovery.brief import render_product_brief
from discovery.engine import run_engine
from discovery.intel import load_signals, load_themes
from discovery.models import IntelPillar, Signal, SignalKind, Theme, Verdict
from discovery.paths import sample_dir


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


def test_spending_analyst_brief_is_evidence_and_an_experiment():
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
            body=(
                "Existing tools visualize spending but provide "
                "limited contextual explanations."
            ),
            source="Market notes",
            strength=0.7,
            polarity="movement",
            volume=8,
            tags=[],
        ),
        _signal(
            id="trend",
            pillar=IntelPillar.market,
            kind=SignalKind.trend,
            title="Spending questions are up",
            body="Search interest in spending explanations is rising.",
            source="Search",
            strength=0.6,
            polarity="movement",
            volume=4,
            tags=[],
        ),
        _signal(
            id="analytics",
            pillar=IntelPillar.product,
            kind=SignalKind.analytics,
            title="Monthly review is opened",
            body="The spending review is opened several times a month.",
            source="Product analytics",
            strength=0.5,
            polarity="adoption",
            volume=3,
            tags=[],
        ),
    ]
    opportunities = run_engine(signals, [theme], "Young professionals")
    assert len(opportunities) == 1
    brief = opportunities[0].product_brief
    assert brief is not None
    assert brief.problem == "Users struggle to understand where their money is going each month."
    assert brief.target_users == "Young professionals"
    assert brief.observed_pain == "High frequency / moderate-high severity"
    assert brief.existing_solutions == ["YNAB", "Monarch", "Copilot", "Spreadsheets"]
    assert brief.gap == (
        "Existing tools visualize spending but provide limited contextual explanations."
    )
    assert brief.opportunity == "AI Financial Spending Analyst"
    assert brief.mvp == [
        "Automatic spending analysis",
        "Monthly explanation",
        "Anomaly detection",
        "Personalized recommendations",
    ]
    assert brief.evidence == [
        "23 user complaints",
        "8 competitor observations",
        "4 market signals",
        "3 internal analytics signals",
    ]
    assert brief.risks == ["Financial trust", "Privacy", "Incorrect recommendations"]
    assert brief.open_questions == [
        "Will users trust AI recommendations?",
        "What level of personalization is expected?",
    ]
    assert brief.experiment == "Prototype → 20 users → measure engagement"
    rendered = render_product_brief(brief)
    labels = [
        "PRODUCT OPPORTUNITY",
        "Problem",
        "Target users",
        "Observed pain",
        "Existing solutions",
        "Gap",
        "Opportunity",
        "Potential MVP",
        "Evidence",
        "Risks",
        "Open questions",
        "Recommended experiment",
    ]
    positions = [rendered.index(label) for label in labels]
    assert positions == sorted(positions)
    assert "• Automatic spending analysis" in rendered
    assert "Prototype → 20 users → measure engagement" in rendered
    assert "build this" not in rendered.lower()


def test_unnamed_questions_stay_open():
    theme = Theme(
        id="export",
        label="Export speed",
        keywords=["export"],
        problem="Export is slow.",
        idea_title="Faster export",
        idea_summary="Look at the export path.",
        experiments=["Time the export with five users."],
    )
    signals = [
        _signal(
            id="slow",
            title="Export is slow",
            body="The monthly export takes too long.",
            volume=1,
            tags=[],
        ),
        _signal(
            id="again",
            title="Export still stalls",
            body="People retry the export and give up.",
            volume=1,
            tags=[],
            strength=0.4,
        ),
    ]
    brief = run_engine(signals, [theme], "Analysts").pop().product_brief
    assert brief is not None
    assert "How frequently?" in brief.open_questions
    assert "Is the market large enough?" in brief.open_questions
    assert brief.experiment == "Time the export with five users."
    assert brief.observed_pain == "Frequency is not measured / severity is not measured"


def test_northstar_brief_recommends_an_experiment():
    audience = "Product managers at B2B SaaS companies"
    root = sample_dir()
    opportunities = run_engine(
        load_signals(root / "signals.json"),
        load_themes(root / "themes.json"),
        audience,
    )
    guided = next(item for item in opportunities if item.id == "opp-instrumentation")
    assert guided.verdict is Verdict.pursue
    brief = guided.product_brief
    assert brief is not None
    assert brief.target_users == audience
    assert brief.opportunity == "Guided tracking plans"
    assert brief.observed_pain == "Frequency is not measured / moderate-high severity"
    assert brief.existing_solutions == ["No existing solution is in the evidence."]
    assert brief.gap == "No existing solution is in the evidence, so the pain is unserved."
    assert brief.evidence == [
        "2 user complaints",
        "0 competitor observations",
        "1 market signal",
        "2 internal analytics signals",
    ]
    assert brief.mvp[0] == "Draft the event spec"
    assert brief.open_questions[0] == "Will a guided plan stay trusted after the first week?"
    assert brief.experiment.startswith("Pilot guided tracking plans")
    replay = next(item for item in opportunities if item.id == "opp-session_replay")
    assert replay.product_brief is not None
    assert replay.product_brief.experiment.startswith("Before building replay")
