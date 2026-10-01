from discovery.agent import DiscoveryAgent
from discovery.agents.portfolio import assess
from discovery.models import PortfolioRow
from discovery.paths import sample_dir

EXAMPLE = [
    PortfolioRow(
        name="AI Spending Insight",
        status="Running",
        risk="Low",
        audience="Active users with ≥3 months transaction history.",
        surface="spending",
        information="Medium",
    ),
    PortfolioRow(
        name="Onboarding redesign",
        status="Running",
        risk="Medium",
        audience="New users in their first week.",
        surface="onboarding",
        information="Medium",
    ),
    PortfolioRow(
        name="Premium AI Coach",
        status="Planned",
        risk="High",
        audience="Active users with ≥3 months transaction history.",
        surface="spending",
        information="High",
    ),
    PortfolioRow(
        name="Notification test",
        status="Complete",
        risk="Low",
        audience="Active users with ≥3 months transaction history.",
        surface="notification",
        information="Low",
    ),
]


def test_the_example_portfolio_names_every_judgment():
    portfolio = assess(EXAMPLE)
    assert [(row.name, row.status, row.risk) for row in portfolio.rows] == [
        ("AI Spending Insight", "Running", "Low"),
        ("Onboarding redesign", "Running", "Medium"),
        ("Premium AI Coach", "Planned", "High"),
        ("Notification test", "Complete", "Low"),
    ]
    notes = {note.topic: note.summary for note in portfolio.notes}
    assert list(notes) == [
        "Experiment conflicts",
        "User overlap",
        "Resource consumption",
        "Statistical contamination",
        "Priority",
        "Expected information gain",
    ]
    assert notes["Experiment conflicts"] == (
        "AI Spending Insight and Onboarding redesign are both running. "
        "AI Spending Insight and Premium AI Coach share the spending surface."
    )
    assert notes["User overlap"] == (
        "AI Spending Insight and Premium AI Coach share one audience: "
        "Active users with ≥3 months transaction history. "
        "Onboarding redesign is the only experiment on New users in their first week."
    )
    assert notes["Resource consumption"] == (
        "AI Spending Insight (low risk) and Onboarding redesign (medium risk) are running. "
        "Premium AI Coach is high risk and planned, so it waits for a free slot."
    )
    assert notes["Statistical contamination"] == (
        "AI Spending Insight and Onboarding redesign are both running on different audiences, "
        "so one result does not explain the other. "
        "Starting Premium AI Coach while AI Spending Insight is running would contaminate the shared audience."
    )
    assert notes["Priority"] == (
        "Priority is AI Spending Insight, then Onboarding redesign. "
        "Hold Premium AI Coach. Notification test is complete."
    )
    assert notes["Expected information gain"] == (
        "Notification test has already delivered its learning. "
        "AI Spending Insight and Onboarding redesign are still producing information. "
        "Premium AI Coach has the highest expected information gain and stays planned because its risk is high."
    )


def test_northstar_portfolio_is_the_six_real_experiments(tmp_path):
    agent = DiscoveryAgent(tmp_path)
    agent.demo(sample_dir())
    portfolio = agent.portfolio()
    assert [row.name for row in portfolio.rows] == [
        "Guided tracking plans",
        "Analysis PMs can run themselves",
        "Insights that cite our events",
        "Natural language tied to the tracking plan",
        "Dark theme",
        "Bundled session replay",
    ]
    assert {row.status for row in portfolio.rows} == {"Planned"}
    assert {row.risk for row in portfolio.rows} == {"Low"}
    notes = {note.topic: note.summary for note in portfolio.notes}
    assert notes["Experiment conflicts"] == "No experiment is running."
    assert notes["User overlap"] == (
        "All six open experiments reach Product managers at B2B SaaS companies."
    )
    assert "AI Spending Insight" not in notes["Priority"]

    agent.approve_execution("opp-instrumentation", "Fake door only")
    running = agent.portfolio()
    guided = running.rows[0]
    assert guided.name == "Guided tracking plans"
    assert guided.status == "Running"
    assert guided.risk == "Low"
    assert all(row.status == "Planned" for row in running.rows[1:])
    approved_notes = {note.topic: note.summary for note in running.notes}
    assert approved_notes["Priority"] == (
        "Priority is Guided tracking plans. The five planned experiments wait. None are complete."
    )
    assert "Premium AI Coach" not in approved_notes["Experiment conflicts"]
