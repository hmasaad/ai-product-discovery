from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from discovery.engine import run_engine
from discovery.intel import load_signals, load_themes
from discovery.models import Gap, IntelPillar, Signal, SignalKind, Verdict

SAMPLE = Path(__file__).resolve().parents[1] / "data" / "sample"


def _signal(**overrides) -> Signal:
    payload = {
        "id": "sig-1",
        "pillar": IntelPillar.user,
        "kind": SignalKind.review,
        "title": "Onboarding checklist confuses new admins",
        "body": "New admins say the onboarding checklist is confusing and easy to skip.",
        "source": "Interview",
        "observed_at": date(2026, 9, 1),
        "strength": 0.6,
    }
    payload.update(overrides)
    return Signal(**payload)


def test_sample_workspace_judgments():
    opportunities = run_engine(
        load_signals(SAMPLE / "signals.json"),
        load_themes(SAMPLE / "themes.json"),
    )
    by_theme = {item.theme: item for item in opportunities}

    assert set(by_theme) == {
        "instrumentation",
        "self_serve",
        "grounded_ai",
        "natural_language",
        "session_replay",
        "dark_mode",
    }

    instrumentation = by_theme["instrumentation"]
    assert instrumentation.verdict is Verdict.pursue
    assert instrumentation.gap is Gap.unserved
    assert {item.signal_id for item in instrumentation.evidence} >= {
        "usr-instrument",
        "prd-stall",
        "mkt-privacy",
    }
    assert "mkt-amplitude" not in {item.signal_id for item in instrumentation.evidence}

    assert by_theme["self_serve"].verdict is Verdict.pursue
    assert by_theme["self_serve"].gap is Gap.contested
    assert by_theme["grounded_ai"].verdict is Verdict.pursue
    assert by_theme["grounded_ai"].gap is Gap.contested

    natural_language = by_theme["natural_language"]
    assert natural_language.verdict is Verdict.investigate
    assert any(check.id == "user_evidence" and not check.passed for check in natural_language.checks)

    replay = by_theme["session_replay"]
    assert replay.verdict is Verdict.park
    assert replay.gap is Gap.table_stakes
    assert "table stakes" in replay.rationale.lower()

    dark = by_theme["dark_mode"]
    assert dark.verdict is Verdict.park
    assert dark.scores.opportunity < 0.35

    for opportunity in opportunities:
        for score in (
            opportunity.scores.problem,
            opportunity.scores.opportunity,
            opportunity.scores.validation,
            opportunity.scores.confidence,
        ):
            assert 0 <= score <= 1


def test_single_signal_does_not_become_an_opportunity():
    assert run_engine([_signal()], []) == []


def test_unmatched_signals_form_an_emergent_cluster():
    second = _signal(
        id="sig-2",
        title="Admins keep missing the onboarding checklist",
        body="The onboarding checklist still confuses new admins a week later.",
    )
    opportunities = run_engine([_signal(), second], [])
    assert len(opportunities) == 1
    assert opportunities[0].theme.startswith("emergent-")
    assert "checklist" in opportunities[0].label


def test_review_cannot_be_filed_as_market_intel():
    with pytest.raises(ValidationError):
        _signal(pillar=IntelPillar.market, kind=SignalKind.review)


def test_duplicate_signal_ids_are_rejected(tmp_path: Path):
    signal = _signal().model_dump(mode="json")
    path = tmp_path / "signals.json"
    path.write_text(__import__("json").dumps([signal, signal]), encoding="utf-8")
    with pytest.raises(ValueError, match="Duplicate signal id"):
        load_signals(path)
