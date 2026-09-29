from datetime import date

from discovery.agents.market import MarketResearchAgent, classify_market
from discovery.intel import load_signals, load_themes
from discovery.models import IntelPillar, MarketFacet, Signal, SignalKind, Theme

SAMPLE = __import__("pathlib").Path(__file__).resolve().parents[1] / "data" / "sample"


def _signal(**overrides) -> Signal:
    payload = {
        "id": "sig",
        "pillar": IntelPillar.market,
        "kind": SignalKind.trend,
        "title": "Search interest increased",
        "body": "Search interest increased for AI-powered personal finance.",
        "source": "Search trends",
        "observed_at": date(2026, 9, 1),
        "strength": 0.8,
        "polarity": "movement",
    }
    payload.update(overrides)
    return Signal(**payload)


def _finance_theme() -> Theme:
    return Theme(
        id="planning",
        label="AI-powered personal finance",
        keywords=["personal finance", "financial planning"],
        problem="People still assemble financial plans by hand.",
        idea_title="Automated financial planning",
        idea_summary="Draft a plan from the accounts people already have.",
    )


def test_market_signal_matches_the_research_brief():
    theme = _finance_theme()
    signals = [
        _signal(
            id="launch",
            kind=SignalKind.competitor,
            title="Competitor A launched an AI budget coach",
            body="Competitor A launched a coaching product for personal finance.",
            source="Competitor A changelog",
        ),
        _signal(
            id="request",
            pillar=IntelPillar.user,
            kind=SignalKind.review,
            title="Users increasingly request automated planning",
            body="Customers keep asking for automated financial planning.",
            source="App reviews",
            polarity="demand",
        ),
        _signal(
            id="search",
            title="Search interest increased for AI personal finance",
            body="Search interest increased for AI-powered personal finance.",
        ),
        _signal(
            id="startups",
            kind=SignalKind.competitor,
            title="Multiple startups entering personal finance",
            body="Multiple startups entering the personal finance space.",
            source="Startup watch",
        ),
    ]
    published = MarketResearchAgent().analyze(signals, [theme])
    assert len(published) == 1
    signal = published[0]
    assert signal.trend == "AI-powered personal finance"
    statements = [item.statement for item in signal.evidence]
    assert any("launched" in item.lower() for item in statements)
    assert any(item.lower().startswith("users") for item in statements)
    assert any("search interest" in item.lower() for item in statements)
    assert any("startup" in item.lower() for item in statements)
    assert signal.implication == "Opportunity for automated financial planning."
    assert MarketFacet.competitor_launch in signal.facets
    assert MarketFacet.complaint in signal.facets
    assert MarketFacet.startup in signal.facets


def test_product_usage_is_not_a_market_signal():
    usage = _signal(
        id="usage",
        pillar=IntelPillar.product,
        kind=SignalKind.usage,
        title="People open the planner",
        body="The financial planning screen is already used weekly.",
        polarity="adoption",
    )
    assert classify_market(usage) == []
    assert MarketResearchAgent().analyze([usage, usage.model_copy(update={"id": "usage-2"})], []) == []


def test_northstar_market_signals_cover_the_main_trends():
    published = MarketResearchAgent().analyze(
        load_signals(SAMPLE / "signals.json"),
        load_themes(SAMPLE / "themes.json"),
    )
    by_theme = {item.theme: item for item in published}
    assert "self_serve" in by_theme
    assert "instrumentation" in by_theme
    assert "grounded_ai" in by_theme
    self_serve = by_theme["self_serve"]
    assert MarketFacet.startup in self_serve.facets
    assert MarketFacet.complaint in self_serve.facets
    assert self_serve.implication.startswith("Opportunity")
    assert MarketFacet.regulatory in by_theme["instrumentation"].facets
    assert "natural_language" not in by_theme
    assert by_theme["dark_mode"].implication == "Customer complaints keep returning to Dark theme."
