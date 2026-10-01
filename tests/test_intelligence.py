from discovery.agent import DiscoveryAgent
from discovery.engine.intelligence import CAPABILITIES
from discovery.paths import sample_dir


def test_engine_runs_the_six_capabilities(tmp_path):
    agent = DiscoveryAgent(tmp_path)
    agent.demo(sample_dir())
    agent.apply_review("opp-instrumentation", "approved", "Pilot with five stalled workspaces")
    report = agent.intelligence("opp-instrumentation")
    assert report is not None
    assert [stage.capability for stage in report.stages] == list(CAPABILITIES)
    assert report.stages[0].summary == "20 signals ingested."
    assert report.stages[1].summary == "Event instrumentation is 25% of the feedback."
    assert report.stages[2].summary == "Guided tracking plans"
    assert report.stages[3].summary.startswith("Guided tracking plans exists because")
    assert "unchallenged" in report.stages[4].summary
    assert any(
        line.startswith("Problem: Teams stall before the product is trustworthy")
        for line in report.stages[5].lines
    )
    assert "The PRD repeats the brief." in report.stages[5].summary


def test_parked_handoff_stays_in_discovery(tmp_path):
    agent = DiscoveryAgent(tmp_path)
    agent.demo(sample_dir())
    report = agent.intelligence("opp-session_replay")
    assert report is not None
    assert report.stages[5].capability == "Opportunity → PRD handoff"
    assert report.stages[5].summary == "Parked opportunities stay in discovery."


def test_pending_handoff_waits_for_approval(tmp_path):
    agent = DiscoveryAgent(tmp_path)
    agent.demo(sample_dir())
    report = agent.intelligence("opp-instrumentation")
    assert report is not None
    assert report.stages[3].summary.startswith("Guided tracking plans exists because")
    assert report.stages[5].summary == "The PRD waits for approval."
