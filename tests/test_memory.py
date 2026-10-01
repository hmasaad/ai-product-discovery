from datetime import date

from discovery.agents.memory import QUESTIONS, ProductMemoryAgent
from discovery.engine import run_engine
from discovery.intel import load_competitors, load_context, load_memory, load_signals, load_themes
from discovery.models import MemoryKind, MemoryRecord, ReviewEntry, ReviewStatus
from discovery.paths import sample_dir


def _memory():
    root = sample_dir()
    context = load_context(root / "context.json")
    signals = load_signals(root / "signals.json")
    themes = load_themes(root / "themes.json")
    catalog = load_competitors(root / "competitors.json")
    outcomes = load_memory(root / "memory.json")
    opportunities = run_engine(signals, themes, context.audience)
    reviews = [
        ReviewEntry(
            opportunity_id="opp-dark_mode",
            action=ReviewStatus.rejected,
            note="Not a roadmap bet",
            created_at="2026-09-29T12:00:00+00:00",
        )
    ]
    return ProductMemoryAgent().remember(
        context,
        signals,
        opportunities,
        reviews,
        catalog,
        themes,
        outcomes,
    )


def test_four_questions_are_answered_from_memory():
    memory = _memory()
    agent = ProductMemoryAgent()
    today = date(2026, 9, 29)

    seen = agent.ask(memory, QUESTIONS[0], today)
    assert seen.answer.startswith("Yes.")
    assert "Event instrumentation appears in 2 feedback items." in seen.answer

    rejected = agent.ask(memory, QUESTIONS[1], today)
    assert rejected.answer == (
        "Export to PDF was rejected on 29 Mar 2026. Finance team already had a spreadsheet."
    )

    repeated = agent.ask(memory, QUESTIONS[2], today)
    assert "Event instrumentation appears in 2 feedback items." in repeated.answer
    assert "Dark theme appears in 2 feedback items." in repeated.answer

    untested = agent.ask(memory, QUESTIONS[3], today)
    assert untested.answer.startswith(
        "These opportunities have a pursue verdict and no recorded experiment result:"
    )
    assert "Guided tracking plans" in untested.answer
    assert "Bundled session replay" not in untested.answer

    named = agent.ask(memory, "Why did we reject export to PDF six months ago?", today)
    assert named.answer == rejected.answer
    missing = agent.ask(memory, "Have we seen lunar billing before?", today)
    assert missing.answer == "No. That problem is not in memory."


def test_a_recorded_experiment_is_no_longer_untested():
    root = sample_dir()
    context = load_context(root / "context.json")
    signals = load_signals(root / "signals.json")
    themes = load_themes(root / "themes.json")
    opportunities = run_engine(signals, themes, context.audience)
    outcomes = [
        MemoryRecord(
            id="done",
            kind=MemoryKind.failed_experiments,
            title="Guided tracking plans",
            detail="The pilot did not move the stall rate.",
            observed_at=date(2026, 9, 20),
            subject="opp-instrumentation",
        )
    ]
    memory = ProductMemoryAgent().remember(
        context,
        signals,
        opportunities,
        [],
        load_competitors(root / "competitors.json"),
        themes,
        outcomes,
    )
    answer = ProductMemoryAgent().ask(memory, QUESTIONS[3], date(2026, 9, 29))
    assert "Guided tracking plans" not in answer.answer
    failed = memory.of_kind(MemoryKind.failed_experiments)
    assert failed[0].title == "Guided tracking plans"
    assert any(
        record.kind is MemoryKind.decisions and record.title == "Guided tracking plans"
        for record in memory.records
    )
