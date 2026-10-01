from datetime import date

from discovery.agent import DiscoveryAgent
from discovery.agents.experiment import REJECT, STAGES, VALIDATE, WAITING, design
from discovery.models import Evidence, IntelPillar, MemoryKind, MemoryRecord, Polarity, SignalKind, Verdict
from discovery.paths import sample_dir


def test_guided_tracking_plans_wait_for_a_result(tmp_path):
    agent = DiscoveryAgent(tmp_path)
    agent.demo(sample_dir())
    plan = agent.experiment("opp-instrumentation")
    assert plan is not None
    assert [stage.title for stage in plan.stages] == list(STAGES)
    assert [item.statement for item in plan.hypotheses] == [
        "Users want guided tracking plans.",
        "Users will regularly return to view guided tracking plans.",
        "Personalized guided tracking plans increase engagement.",
        "Users trust guided tracking plans.",
        "Users would pay for this capability.",
    ]
    assert plan.hypotheses[0].target_segment == "Product managers at B2B SaaS companies"
    assert plan.hypotheses[0].metric == "Interviews that describe the problem"
    assert plan.hypotheses[0].threshold == "At least 5 of 8 describe the problem unprompted."
    assert plan.hypotheses[0].time_period == "1 week"
    assert plan.hypotheses[0].confidence == "High"
    assert "Instrumentation took three weeks." in plan.hypotheses[0].evidence
    assert plan.hypotheses[4].confidence == "Low"
    assert plan.hypotheses[4].evidence == "No evidence is recorded for this hypothesis."
    assert plan.unknown == "Will users use guided tracking plans?"
    assert plan.selected == "Selected: C + targeted interviews."
    assert [choice.cost for choice in plan.choices] == ["Very High", "Medium", "Low", "Very Low"]
    assert [choice.information for choice in plan.choices] == ["High", "High", "Medium", "Medium"]
    assert [choice.selected for choice in plan.choices] == [False, False, True, True]
    assert plan.stages[1].summary == "Selected: C + targeted interviews."
    assert "This runs before engineering starts." in plan.stages[1].lines
    door = plan.specifications[0]
    assert door.name == "Guided tracking plans fake door"
    assert door.hypothesis == "Users want guided tracking plans."
    assert door.control == "The current instrumentation path."
    assert door.variant == '"Guided tracking plans" entry.'
    assert door.primary_metric == "Click-through rate."
    assert door.guardrails == ["Support complaints", "Session abandonment", "Incorrect-data reports"]
    assert door.sample_size == "Five workspaces."
    assert door.duration == "14 days"
    assert door.decision_threshold == "CTR ≥ 8%."
    assert door.outcomes == ["Continue", "Iterate", "Reject"]
    assert plan.specifications[1].name == "Guided tracking plans interviews"
    assert plan.specifications[1].sample_size == "8 interviews."
    assert plan.stages[2].summary.startswith("Guided tracking plans fake door")
    assert plan.stages[3].summary == "Success is a trusted funnel in days, not weeks"
    assert "Baseline: stall rate 62%." in plan.stages[3].lines
    assert plan.stages[4].summary == "Not run. Engineering has not started."
    assert plan.stages[5].summary == "No result is recorded."
    assert "Five teams opened replay" not in plan.stages[5].summary
    assert plan.decision == WAITING
    assert plan.pm_summary == "The product manager waits."


def test_parked_replay_is_not_the_old_pilot(tmp_path):
    agent = DiscoveryAgent(tmp_path)
    agent.demo(sample_dir())
    plan = agent.experiment("opp-session_replay")
    assert plan is not None
    assert plan.decision == REJECT
    assert plan.decision_summary == "Parked opportunities stay in discovery."
    assert plan.pm_summary == "The product manager does not take this opportunity."
    assert plan.selected == "Selected: D. Interview users."
    assert plan.unknown == "Do users have the problem?"
    assert plan.stages[1].summary == "Selected: D. Interview users."
    assert "A list, before any build." in plan.stages[1].lines
    assert plan.stages[4].summary == "Not run. The interviews have not been run."
    assert len(plan.specifications) == 1
    assert plan.specifications[0].name == "Bundled session replay interviews"
    assert "Fake door" not in plan.specifications[0].name
    assert "Five teams opened replay" not in " ".join(stage.summary for stage in plan.stages)


def test_a_recorded_failure_rejects_and_a_success_validates(tmp_path):
    agent = DiscoveryAgent(tmp_path)
    agent.demo(sample_dir())
    opportunity = agent.opportunity("opp-instrumentation")
    assert opportunity is not None
    failed = design(
        opportunity,
        [
            MemoryRecord(
                id="mem-fail",
                kind=MemoryKind.failed_experiments,
                title="Guided tracking plans",
                detail="The five workspaces did not reach a trusted funnel.",
                observed_at=date(2026, 9, 1),
                source="Experiment record",
                subject="opp-instrumentation",
            )
        ],
    )
    assert failed.decision == REJECT
    assert "The five workspaces did not reach a trusted funnel." in failed.decision_summary
    assert failed.stages[4].summary.startswith("Recorded on 1 Sep 2026.")
    succeeded = design(
        opportunity,
        [
            MemoryRecord(
                id="mem-ok",
                kind=MemoryKind.successful_ideas,
                title="Guided tracking plans",
                detail="A trusted funnel arrived in days.",
                observed_at=date(2026, 9, 2),
                source="Experiment record",
                subject="opp-instrumentation",
            )
        ],
    )
    assert succeeded.decision == VALIDATE
    assert succeeded.pm_summary == "The product manager can take the brief."


def test_an_unrelated_failure_does_not_decide_this_opportunity(tmp_path):
    agent = DiscoveryAgent(tmp_path)
    agent.demo(sample_dir())
    opportunity = agent.opportunity("opp-instrumentation")
    assert opportunity is not None
    plan = design(
        opportunity,
        [
            MemoryRecord(
                id="mem-replay-pilot",
                kind=MemoryKind.failed_experiments,
                title="Session replay pilot",
                detail="Five teams opened replay and did not change a roadmap decision.",
                observed_at=date(2026, 6, 2),
                source="Experiment record",
                subject="replay-pilot",
            )
        ],
    )
    assert plan.decision == WAITING


def test_spending_hypotheses_do_not_recommend_a_coach(tmp_path):
    agent = DiscoveryAgent(tmp_path)
    agent.demo(sample_dir())
    source = agent.opportunity("opp-instrumentation")
    assert source is not None and source.product_brief is not None and source.challenge is not None
    opportunity = source.model_copy(
        update={
            "id": "opp-spending",
            "theme": "spending",
            "title": "AI Financial Spending Analyst",
            "problem": "Users struggle to understand monthly spending.",
            "verdict": Verdict.pursue,
            "product_brief": source.product_brief.model_copy(
                update={
                    "problem": "Users struggle to understand monthly spending.",
                    "target_users": "Young professionals",
                    "opportunity": "AI Financial Spending Analyst",
                }
            ),
            "challenge": source.challenge.model_copy(update={"contradicting": []}),
            "evidence": [
                Evidence(
                    signal_id="usr-spend",
                    pillar=IntelPillar.user,
                    kind=SignalKind.feedback,
                    title="I cannot tell where my money goes each month",
                    excerpt="The month ends and the total is a surprise.",
                    source="Interview",
                    observed_at=date(2026, 9, 1),
                    polarity=Polarity.pain,
                    strength=0.8,
                )
            ],
        }
    )
    plan = design(opportunity, [])
    assert [item.statement for item in plan.hypotheses] == [
        "Users want automated explanations of their spending.",
        "Users will regularly return to view those explanations.",
        "Personalized explanations increase engagement.",
        "Users trust AI-generated financial explanations.",
        "Users would pay for this capability.",
    ]
    assert {item.target_segment for item in plan.hypotheses} == {"Young professionals"}
    assert plan.hypotheses[0].expected_behavior == (
        "They ask for an explanation of last month without a full financial coach."
    )
    assert plan.hypotheses[0].confidence == "Medium"
    assert plan.hypotheses[0].evidence == "I cannot tell where my money goes each month."
    assert plan.hypotheses[4].metric == "Users who name a price"
    assert plan.hypotheses[4].threshold == "At least 3 of 8 name a price they would pay."
    assert plan.hypotheses[4].confidence == "Low"
    assert plan.stages[0].lines == ["These hypotheses do not recommend building an AI financial coach."]
    assert plan.unknown == "Will users use AI spending explanations?"
    assert plan.selected == "Selected: C + targeted interviews."
    assert [(item.code, item.cost, item.information, item.selected) for item in plan.choices] == [
        ("A", "Very High", "High", False),
        ("B", "Medium", "High", False),
        ("C", "Low", "Medium", True),
        ("D", "Very Low", "Medium", True),
    ]
    assert "Will users click it? Fake-door test" in plan.catalog
    assert "The experiment does not build an AI financial coach." in plan.stages[1].lines
    door = plan.specifications[0]
    assert door.name == "AI Spending Insight Fake Door"
    assert door.hypothesis == "Users want automated explanations of their monthly spending."
    assert door.target_audience == "Active users with ≥3 months transaction history."
    assert door.control == "Existing spending dashboard."
    assert door.variant == '"Explain My Spending" button.'
    assert door.primary_metric == "Click-through rate."
    assert door.secondary_metric == "Feature activation."
    assert door.guardrails == ["Support complaints", "Session abandonment", "Incorrect-data reports"]
    assert door.duration == "14 days"
    assert door.decision_threshold == "CTR ≥ 8%."
    assert door.outcomes == ["Continue", "Iterate", "Reject"]
    assert "an AI financial coach" in door.expected_learning
    assert plan.specifications[1].name == "Spending explanation interviews"
