from pathlib import Path

from fastapi.testclient import TestClient

from discovery.web.app import create_app


def test_board_review_and_queue(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("DISCOVERY_HOME", str(tmp_path))
    client = TestClient(create_app())

    empty = client.get("/")
    assert empty.status_code == 200
    assert "No opportunities on the board" in empty.text

    loaded = client.post("/demo", follow_redirects=True)
    assert loaded.status_code == 200
    assert "Guided tracking plans" in loaded.text
    assert "Market signal" in loaded.text

    market = client.get("/market")
    assert market.status_code == 200
    assert "Potential implication" in market.text
    assert "Self-serve analysis" in market.text

    users = client.get("/users")
    assert users.status_code == 200
    assert "Clustered problems" in users.text
    assert "Unmet needs" in users.text
    assert "Event instrumentation" in users.text
    assert "25%" in users.text

    competitors = client.get("/competitors")
    assert competitors.status_code == 200
    assert "Competitor matrix" in competitors.text
    assert "Potential market gap" in competitors.text
    assert "Tracking plans are absent from every competitor." in competitors.text
    assert "Amplitude" in competitors.text
    assert "absent from every competitor." in loaded.text
    assert "From signal to opportunity" in loaded.text
    assert "User segment" in loaded.text

    detected = client.get("/detect")
    assert detected.status_code == 200
    assert "Opportunity detection engine" in detected.text
    assert "Guided tracking plans" in detected.text
    assert "Product managers at B2B SaaS companies" in detected.text
    assert "On the review board" in detected.text

    graph = client.get("/graph")
    assert graph.status_code == 200
    assert "Why does this opportunity exist?" in graph.text
    assert "Guided tracking plans exists because" in graph.text
    assert "Instrumentation took three weeks" in graph.text
    assert "No observation is recorded." in graph.text
    assert "The next hypothesis waits for that observation." in graph.text
    assert "A new observation starts the next hypothesis." in graph.text

    memo = client.get("/opportunities/opp-instrumentation")
    assert "Trace it on the opportunity graph" in memo.text
    assert "Product opportunity" in memo.text
    assert "Observed pain" in memo.text
    assert "Recommended experiment" in memo.text
    assert "2 user complaints" in memo.text
    assert "Pilot guided tracking plans" in memo.text
    assert "Draft the event spec" in memo.text

    validated = client.get("/validate")
    assert validated.status_code == 200
    assert "Evidence for" in validated.text
    assert "Evidence against" in validated.text
    assert "What evidence contradicts it?" in validated.text
    assert "unchallenged" in validated.text
    assert "Bundled session replay" in loaded.text
    assert "Market intel" in loaded.text
    assert "stall rate 62%" in loaded.text

    remembered = client.get("/memory")
    assert remembered.status_code == 200
    assert "Have we seen this problem before?" in remembered.text
    assert "Event instrumentation appears in 2 feedback items." in remembered.text
    assert "Export to PDF was rejected on 29 Mar 2026." in remembered.text
    assert "Finance team already had a spreadsheet." in remembered.text
    assert "These opportunities have a pursue verdict and no recorded experiment result:" in remembered.text
    assert "Guided tracking plans" in remembered.text
    assert "Rejected ideas" in remembered.text
    assert "Failed experiments" in remembered.text
    assert "Workspace invite email" in remembered.text

    approved = client.post(
        "/opportunities/opp-instrumentation/review",
        data={
            "action": "approved",
            "note": "Pilot with five stalled workspaces",
            "next_url": "/opportunities/opp-instrumentation",
        },
        follow_redirects=True,
    )
    assert approved.status_code == 200
    assert "Pilot with five stalled workspaces" in approved.text
    assert "Approved" in approved.text

    queue = client.get("/queue")
    assert "Guided tracking plans" in queue.text
    assert "Handoff to the product manager" in queue.text

    client.post(
        "/opportunities/opp-dark_mode/review",
        data={"action": "rejected", "note": "Not a roadmap bet", "next_url": "/"},
        follow_redirects=True,
    )
    board = client.get("/")
    assert "Dark theme" not in board.text
    rejected = client.get("/?status=rejected")
    assert "Dark theme" in rejected.text
    remembered = client.get("/memory")
    assert "Not a roadmap bet" in remembered.text

    rerun = client.post("/cycle", follow_redirects=True)
    assert rerun.status_code == 200
    memo = client.get("/opportunities/opp-instrumentation")
    assert "Approved" in memo.text
    assert "Pilot with five stalled workspaces" in memo.text
    assert "Follow it through the product loop" in memo.text

    loop = client.get("/loop?opportunity=opp-instrumentation")
    assert loop.status_code == 200
    assert "AI Product Manager" in loop.text
    assert "PRD" in loop.text
    assert "In the experiment." in loop.text
    assert "These measurements re-enter product discovery." in loop.text
    assert "Guided tracking plans experiment" in loop.text

    engine = client.get("/engine")
    assert engine.status_code == 200
    for capability in (
        "Signal ingestion",
        "Problem clustering",
        "Opportunity detection",
        "Evidence graph",
        "Opportunity validation",
        "Opportunity → PRD handoff",
    ):
        assert capability in engine.text
    assert "20 signals ingested." in engine.text
    assert "Event instrumentation is 25% of the feedback." in engine.text
    assert "Guided tracking plans exists because" in engine.text
    assert "The PRD repeats the brief." in engine.text

    parked = client.get("/loop?opportunity=opp-session_replay")
    assert "Parked opportunities stay in discovery." in parked.text
    parked_engine = client.get("/engine?opportunity=opp-session_replay")
    assert "Parked opportunities stay in discovery." in parked_engine.text

    experiment = client.get("/experiment")
    assert experiment.status_code == 200
    for stage in (
        "Hypothesis Generator",
        "Experiment Designer",
        "Experiment Specification",
        "Success Metric Designer",
        "Experiment Executor",
        "Results Analyzer",
        "Learning Engine",
    ):
        assert stage in experiment.text
    assert "Experiment portfolio" in experiment.text
    assert "Every experiment in flight" in experiment.text
    assert "User overlap" in experiment.text
    assert "Statistical contamination" in experiment.text
    assert "Expected information gain" in experiment.text
    assert "No experiment is running." in experiment.text
    assert "Expected information gain × Decision impact ÷ Experiment cost" in experiment.text
    assert "PRIORITIZE" in experiment.text
    assert "Prioritize Guided tracking plans." in experiment.text
    assert "AI Spending Insight" not in experiment.text
    assert "Users want guided tracking plans." in experiment.text
    assert "Target segment" in experiment.text
    assert "Selected: C + targeted interviews." in experiment.text
    assert "Fake-door test" in experiment.text
    assert "Guided tracking plans fake door" in experiment.text
    assert "CTR ≥ 8%." in experiment.text
    assert "Continue → Iterate → Reject" in experiment.text
    assert "Very Low" in experiment.text
    assert "Not run. Engineering has not started." in experiment.text
    assert "Waiting for a result" in experiment.text
    assert "The product manager waits." in experiment.text
    assert "Configure feature flag" in experiment.text
    assert "Waiting for approval. The variant stays off." in experiment.text
    assert "No readings yet" in experiment.text
    assert "There is no result to interpret." in experiment.text
    assert "Variant B won" not in experiment.text
    assert "No learning is recorded yet." in experiment.text
    assert "No earlier experiment is stored for this opportunity." in experiment.text
    assert "Test actionable recommendations" not in experiment.text
    approved = client.post(
        "/experiment/approve",
        data={"opportunity_id": "opp-instrumentation", "note": "Fake door only"},
        follow_redirects=True,
    )
    assert approved.status_code == 200
    assert "not serving traffic" in approved.text
    assert "One experiment is running: Guided tracking plans." in approved.text
    assert "Fake door only" in approved.text
    assert "No readings yet" in approved.text
    assert "+18%" not in approved.text
    parked_experiment = client.get("/experiment?opportunity=opp-session_replay")
    assert "Reject/Iterate" in parked_experiment.text
    assert "Parked opportunities stay in discovery." in parked_experiment.text
    assert "Five teams opened replay" not in parked_experiment.text

    blocked = client.post(
        "/opportunities/opp-instrumentation/review",
        data={"action": "pending_review", "note": "", "next_url": "/"},
    )
    assert blocked.status_code == 400

    external = client.post(
        "/opportunities/opp-instrumentation/review",
        data={"action": "approved", "note": "stay", "next_url": "https://example.com"},
        follow_redirects=False,
    )
    assert external.headers["location"] == "/"
