from datetime import date

from discovery.engine import run_engine
from discovery.intel import load_signals, load_themes
from discovery.models import Gap, IntelPillar, Signal, SignalKind, Theme, Verdict
from discovery.paths import sample_dir


def _signal(**overrides) -> Signal:
    payload = {
        "id": "requests",
        "pillar": IntelPillar.user,
        "kind": SignalKind.review,
        "title": "37 customer requests",
        "body": "Customers keep asking for help categorizing spending.",
        "source": "Support inbox",
        "observed_at": date(2026, 9, 1),
        "strength": 0.95,
        "polarity": "demand",
        "volume": 37,
    }
    payload.update(overrides)
    return Signal(**payload)


def _coach():
    theme = Theme(
        id="coach",
        label="Financial coaching",
        keywords=["budgeting", "coach", "categorizing"],
        problem="People struggle to decide what to do with their money.",
        idea_title="AI Financial Coach",
        idea_summary="Coach the next money decision from the transactions a business already has.",
    )
    signals = [
        _signal(body="Customers keep asking for an AI coach for budgeting and categorizing."),
        _signal(
            id="competitor",
            pillar=IntelPillar.market,
            kind=SignalKind.competitor,
            title="competitor activity",
            body="Two budgeting apps shipped a coach this quarter.",
            source="Changelog",
            strength=0.8,
            polarity="movement",
            volume=1,
        ),
        _signal(
            id="support",
            kind=SignalKind.feedback,
            title="recurring support complaints",
            body="Support sees recurring complaints about budgeting categories.",
            source="Support",
            strength=0.9,
            polarity="pain",
            volume=1,
        ),
        _signal(
            id="usage",
            pillar=IntelPillar.product,
            kind=SignalKind.usage,
            title="growing usage of budgeting features",
            body="Budgeting screens are opened more often each month.",
            source="Product analytics",
            strength=0.7,
            polarity="adoption",
            volume=1,
            metrics={"budgeting_usage_growth": 1.4},
        ),
        _signal(
            id="education",
            pillar=IntelPillar.product,
            kind=SignalKind.analytics,
            title="low engagement with existing education content",
            body="Budgeting guides and lessons are rarely finished.",
            source="Product analytics",
            strength=0.85,
            polarity="neutral",
            volume=1,
        ),
        _signal(
            id="advisors",
            kind=SignalKind.forum,
            title="users may prefer human advisors",
            body="Several owners say they would rather call a person than use a budgeting coach.",
            source="Community",
            strength=0.75,
            polarity="neutral",
            volume=1,
        ),
        _signal(
            id="trust",
            kind=SignalKind.feedback,
            title="high trust requirements",
            body="Owners will not let a budgeting coach move money without a high trust bar.",
            source="Interview",
            strength=0.6,
            polarity="neutral",
            volume=1,
        ),
    ]
    return signals, [theme]


def test_financial_coach_is_challenged_from_both_sides():
    signals, themes = _coach()
    opportunities = run_engine(signals, themes, "Small business owners")
    assert len(opportunities) == 1
    challenge = opportunities[0].challenge
    assert opportunities[0].title == "AI Financial Coach"
    assert challenge is not None
    assert [point.text for point in challenge.supporting] == [
        "37 customer requests",
        "recurring support complaints",
        "competitor activity",
        "growing usage of budgeting features",
    ]
    assert [point.text for point in challenge.contradicting] == [
        "low engagement with existing education content",
        "users may prefer human advisors",
        "high trust requirements",
    ]
    assert challenge.challenge.startswith(
        "Contradicting evidence: low engagement with existing education content."
    )
    by_id = {item.id: item for item in challenge.questions}
    assert [item.question for item in challenge.questions] == [
        "Is the problem real?",
        "Who experiences it?",
        "How frequently?",
        "How painful?",
        "What alternatives exist?",
        "Is the market large enough?",
        "Is this technically feasible?",
        "What would users pay?",
        "What evidence contradicts it?",
    ]
    assert by_id["real"].status == "supported"
    assert "37 customer requests" in by_id["real"].answer
    assert by_id["who"].answer == "Small business owners."
    assert "37 customer requests" in by_id["frequency"].answer
    assert by_id["painful"].answer == "Severity is not measured."
    assert by_id["market_size"].answer == "No market-size evidence."
    assert by_id["feasible"].answer == "No feasibility evidence."
    assert by_id["pay"].answer == "No willingness-to-pay evidence."
    assert by_id["contradiction"].status == "contradicted"
    assert "High trust requirements" in by_id["contradiction"].answer
    assert "Users may prefer human advisors" in by_id["alternatives"].answer


def test_northstar_names_an_unchallenged_case_and_a_contradiction():
    root = sample_dir()
    opportunities = run_engine(
        load_signals(root / "signals.json"),
        load_themes(root / "themes.json"),
        "Product managers at B2B SaaS companies",
    )
    by_theme = {item.theme: item for item in opportunities}
    instrumentation = by_theme["instrumentation"]
    assert instrumentation.verdict is Verdict.pursue
    assert instrumentation.challenge is not None
    assert instrumentation.challenge.contradicting == []
    assert "unchallenged" in instrumentation.challenge.challenge
    assert any("Stall rate 62%" in item.answer for item in instrumentation.challenge.questions)
    replay = by_theme["session_replay"]
    assert replay.gap is Gap.table_stakes
    assert replay.challenge is not None
    assert replay.challenge.contradicting
    assert replay.challenge.challenge.startswith("Contradicting evidence:")
