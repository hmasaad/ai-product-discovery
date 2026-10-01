from discovery.agent import DiscoveryAgent
from discovery.agents.results import analyze_results
from discovery.models import MetricReading
from discovery.paths import sample_dir

SPENDING_NOTES = [
    ("support", "Higher feature engagement"),
    ("support", "Repeat usage observed"),
    ("support", "Positive qualitative feedback"),
    ("contradict", "Some users ignored the feature"),
    ("contradict", "Usage declined after first interaction"),
]


def test_spending_results_are_a_learning_not_a_winner():
    analysis = analyze_results(
        "Users want AI spending explanations.",
        [MetricReading(name="Feature engagement", lane="primary", change=0.18)],
        SPENDING_NOTES,
    )
    assert analysis.hypothesis == "Users want AI spending explanations."
    assert analysis.observed == "Usage increased."
    assert analysis.supporting == [
        "Higher feature engagement",
        "Repeat usage observed",
        "Positive qualitative feedback",
    ]
    assert analysis.contradicting == [
        "Some users ignored the feature",
        "Usage declined after first interaction",
    ]
    assert analysis.interpretation == (
        "Initial demand exists, but sustained value is not yet established."
    )
    assert analysis.uncertainty == (
        "Whether users consider the feature valuable enough for repeated use."
    )
    assert analysis.next_experiment == "Improve explanation personalization and test retention."
    assert "Variant B won" not in analysis.interpretation


def test_metrics_alone_do_not_invent_qualitative_evidence():
    analysis = analyze_results(
        "Users want guided tracking plans.",
        [
            MetricReading(name="Primary metric", lane="primary", change=0.18),
            MetricReading(name="Support complaints", lane="guardrail", change=0.17),
        ],
    )
    assert analysis.observed == "Usage increased."
    assert analysis.supporting == ["Higher feature engagement"]
    assert "Repeat usage observed" not in analysis.supporting
    assert "Positive qualitative feedback" not in analysis.supporting
    assert analysis.contradicting == ["Support complaints rose"]
    assert analysis.interpretation == (
        "Initial demand exists, but sustained value is not yet established."
    )
    assert "Variant B won" not in analysis.interpretation


def test_a_waiting_experiment_does_not_declare_a_winner(tmp_path):
    agent = DiscoveryAgent(tmp_path)
    agent.demo(sample_dir())
    plan = agent.experiment("opp-instrumentation")
    assert plan is not None and plan.execution is not None and plan.execution.analysis is not None
    analysis = plan.execution.analysis
    assert analysis.hypothesis == "Users want guided tracking plans."
    assert analysis.observed == "No result is recorded."
    assert analysis.supporting == []
    assert analysis.contradicting == []
    assert analysis.interpretation == "There is no result to interpret."
    assert analysis.next_experiment == "Run the specified experiment before choosing a winner."
    assert plan.execution.steps[7].summary == analysis.interpretation
