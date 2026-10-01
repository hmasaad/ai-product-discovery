from discovery.agents.competitors import CompetitorIntelligenceAgent
from discovery.agents.market import MarketResearchAgent
from discovery.agents.users import UserIntelligenceAgent
from discovery.engine import run_engine
from discovery.engine.graph import build_opportunity_graph, trace, trace_kinds
from discovery.intel import load_competitors, load_context, load_signals, load_themes
from discovery.paths import sample_dir


def _northstar_graph():
    root = sample_dir()
    context = load_context(root / "context.json")
    signals = load_signals(root / "signals.json")
    themes = load_themes(root / "themes.json")
    opportunities = run_engine(signals, themes, context.audience)
    return build_opportunity_graph(
        context,
        opportunities,
        MarketResearchAgent().analyze(signals, themes),
        UserIntelligenceAgent().analyze(signals, themes),
        CompetitorIntelligenceAgent().analyze(load_competitors(root / "competitors.json"), signals),
    )


def test_instrumentation_traces_back_to_its_sources():
    graph = _northstar_graph()
    chosen = trace(graph, "opp-instrumentation")
    assert chosen is not None
    assert chosen.why.startswith("Guided tracking plans exists because")
    assert "Product managers at B2B SaaS companies" in chosen.why
    assert "The market trend is Event instrumentation." in chosen.why
    assert "The gap:" in chosen.why
    kinds = [trace_kinds(graph, path) for path in chosen.paths]
    assert ["market", "trend", "users", "problem", "opportunity"] in kinds
    assert ["market", "trend", "competitors", "gap", "opportunity"] in kinds
    assert chosen.feature is not None
    assert chosen.mvp is not None and "Pilot guided tracking plans" in chosen.mvp.detail
    assert chosen.product is not None and chosen.product.title == "Northstar"
    assert chosen.business_case is not None and chosen.business_case.title == "Pursue"
    assert chosen.hypothesis is not None
    assert chosen.hypothesis.title == "Users want guided tracking plans."
    assert chosen.experiment is not None and chosen.experiment.title == "Guided tracking plans fake door"
    assert chosen.observation is not None and chosen.observation.title == "No observation is recorded."
    assert chosen.learning is not None and chosen.learning.title == "No learning is recorded yet."
    assert chosen.new_hypothesis is not None
    assert chosen.new_hypothesis.title == "The next hypothesis waits for that observation."
    assert chosen.learning_path[-1].startswith("new_hypothesis-")
    assert "Test actionable recommendations" not in chosen.new_hypothesis.title
    titles = {source.title for source in chosen.sources}
    assert "Instrumentation took three weeks" in titles
    assert any("stall" in title.lower() or "instrumentation" in title.lower() for title in titles)


def test_self_serve_forks_toward_users_and_competitors():
    graph = _northstar_graph()
    chosen = trace(graph, "opp-self_serve")
    assert chosen is not None
    assert chosen.users is not None
    assert "25% of the feedback" in chosen.users.detail
    assert chosen.competitors is not None
    assert "Canvas" in chosen.competitors.detail or "self-serve" in chosen.competitors.detail.lower()
    kinds = [trace_kinds(graph, path) for path in chosen.paths]
    assert any(path[2:4] == ["users", "problem"] for path in kinds)
    assert any(path[2:4] == ["competitors", "gap"] for path in kinds)
