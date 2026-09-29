from datetime import date

from discovery.engine import detect_candidates, run_engine
from discovery.intel import load_context, load_signals, load_themes
from discovery.models import IntelPillar, Signal, SignalKind, Theme
from discovery.paths import sample_dir


def _signal(**overrides) -> Signal:
    payload = {
        "id": "complaint",
        "pillar": IntelPillar.user,
        "kind": SignalKind.review,
        "title": "Manual transaction categories",
        "body": "Users repeatedly complain about manually categorizing financial transactions.",
        "source": "Support inbox",
        "observed_at": date(2026, 9, 1),
        "strength": 0.9,
    }
    payload.update(overrides)
    return Signal(**payload)


def _finance():
    theme = Theme(
        id="categorization",
        label="Transaction categorization",
        keywords=["categorizing", "categorization", "transactions"],
        problem="Transaction categorization is time-consuming.",
        idea_title="AI-powered adaptive transaction categorization",
        idea_summary="Learn each business's corrections and apply them to the next import.",
    )
    complaint = _signal()
    solutions = _signal(
        id="apps",
        pillar=IntelPillar.market,
        kind=SignalKind.competitor,
        title="Categorization apps still need a human pass",
        body="Existing apps provide categorization, but require manual correction.",
        source="App store",
        strength=0.6,
        polarity="movement",
    )
    return [complaint, solutions], [theme]


def test_finance_signal_becomes_the_example_chain():
    signals, themes = _finance()
    candidates = detect_candidates(signals, themes, "Small business owners")
    assert len(candidates) == 1
    chain = candidates[0].chain
    assert chain.signal == (
        "Users repeatedly complain about manually categorizing financial transactions."
    )
    assert chain.problem == "Transaction categorization is time-consuming."
    assert chain.segment == "Small business owners"
    assert chain.pain == "Manually categorizing financial transactions."
    assert chain.existing_solutions == (
        "Existing apps provide categorization, but require manual correction."
    )
    assert chain.gap == "Existing apps provide categorization, but require manual correction."
    assert chain.opportunity == "AI-powered adaptive transaction categorization"

    opportunities = run_engine(signals, themes, "Small business owners")
    assert len(opportunities) == 1
    assert opportunities[0].chain == chain


def test_a_lone_signal_is_still_a_candidate():
    signal = _signal(id="only-one", title="Export is slow", body="The weekly export takes too long.")
    assert run_engine([signal], []) == []
    candidates = detect_candidates([signal], [], "Small business owners")
    assert len(candidates) == 1
    assert candidates[0].review_id == ""
    assert candidates[0].chain.signal == "The weekly export takes too long."
    assert candidates[0].chain.problem == "The weekly export takes too long."
    assert candidates[0].chain.opportunity == "Investigate Export is slow"


def test_northstar_chain_uses_the_audience_and_the_theme():
    audience = load_context(sample_dir() / "context.json").audience
    signals = load_signals(sample_dir() / "signals.json")
    themes = load_themes(sample_dir() / "themes.json")
    opportunities = run_engine(signals, themes, audience)
    instrumentation = next(item for item in opportunities if item.theme == "instrumentation")
    chain = instrumentation.chain
    assert chain is not None
    assert chain.segment == "Product managers at B2B SaaS companies"
    assert chain.problem.startswith("Teams stall before the product is trustworthy")
    assert chain.opportunity == "Guided tracking plans"
    assert "unserved" in chain.gap or "No existing solution" in chain.gap

    candidates = detect_candidates(signals, themes, audience)
    assert {signal_id for candidate in candidates for signal_id in candidate.signal_ids} == {
        signal.id for signal in signals
    }
