import json
from pathlib import Path

from discovery.agent import DiscoveryAgent
from discovery.cli import main

SAMPLE = Path(__file__).resolve().parents[1] / "data" / "sample"


def test_review_survives_another_cycle(tmp_path: Path):
    agent = DiscoveryAgent(tmp_path)
    report = agent.demo(SAMPLE)
    themes = {item.theme for item in report.opportunities}
    assert "instrumentation" in themes

    updated = agent.apply_review(
        "opp-instrumentation",
        "approved",
        "Pilot with five stalled workspaces",
    )
    assert updated is not None
    assert updated.status.value == "approved"

    again = agent.run_cycle()
    kept = next(item for item in again.opportunities if item.id == "opp-instrumentation")
    assert kept.status.value == "approved"
    assert kept.review_note == "Pilot with five stalled workspaces"
    assert len(agent.reviews("opp-instrumentation")) == 1


def test_ingest_adds_to_an_existing_workspace(tmp_path: Path):
    agent = DiscoveryAgent(tmp_path)
    agent.load_workspace(SAMPLE)
    extra = tmp_path / "extra.json"
    extra.write_text(
        json.dumps(
            [
                {
                    "id": "usr-dark-3",
                    "pillar": "user",
                    "kind": "feedback",
                    "title": "Another dark mode request",
                    "body": "Please add dark mode to the settings page.",
                    "source": "Support",
                    "observed_at": "2026-09-15",
                    "strength": 0.2,
                    "polarity": "demand",
                }
            ]
        ),
        encoding="utf-8",
    )
    assert agent.ingest(extra) == 1
    assert any(signal.id == "usr-dark-3" for signal in agent.signals())
    assert any(signal.id == "usr-instrument" for signal in agent.signals())


def test_cli_demo_prints_pursue(tmp_path: Path, capsys):
    exit_code = main(["--home", str(tmp_path), "demo"])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Guided tracking plans" in captured.out
    assert "Pursue" in captured.out
