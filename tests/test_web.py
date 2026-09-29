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
    assert "Bundled session replay" in loaded.text
    assert "Market intel" in loaded.text
    assert "stall rate 62%" in loaded.text

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

    rerun = client.post("/cycle", follow_redirects=True)
    assert rerun.status_code == 200
    memo = client.get("/opportunities/opp-instrumentation")
    assert "Approved" in memo.text
    assert "Pilot with five stalled workspaces" in memo.text

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
