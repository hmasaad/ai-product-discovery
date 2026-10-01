from discovery.agent import DiscoveryAgent
from discovery.agents.execute import ACTIONS, CRITICAL, WARNING, assess, format_change, run_execution
from discovery.models import MetricReading
from discovery.paths import sample_dir


def _reading(name: str, lane: str, change: float) -> MetricReading:
    return MetricReading(name=name, lane=lane, change=change)


def test_execution_waits_for_approval_before_production_changes(tmp_path):
    agent = DiscoveryAgent(tmp_path)
    agent.demo(sample_dir())
    plan = agent.experiment("opp-instrumentation")
    assert plan is not None and plan.execution is not None
    execution = plan.execution
    assert [step.action for step in execution.steps] == list(ACTIONS)
    flag = execution.steps[2]
    start = execution.steps[3]
    assert flag.system == "Feature flags"
    assert flag.needs_approval
    assert flag.summary == "Waiting for approval. The variant stays off."
    assert start.summary == "Waiting for approval. The experiment has not started."
    assert execution.monitor.status == "No readings yet"
    assert "+18%" not in execution.report
    assert "The control is the behavioral baseline." in execution.steps[5].summary


def test_warning_pattern_keeps_the_experiment_open(tmp_path):
    agent = DiscoveryAgent(tmp_path)
    agent.demo(sample_dir())
    plan = agent.experiment("opp-instrumentation")
    assert plan is not None
    readings = [
        _reading("Primary metric", "primary", 0.18),
        _reading("Conversion", "primary", 0.11),
        _reading("Error rate", "guardrail", 0.042),
        _reading("Support complaints", "guardrail", 0.17),
    ]
    monitor = assess(readings)
    assert monitor.status == WARNING
    assert format_change(0.18) == "+18%"
    assert format_change(0.042) == "+4.2%"
    assert format_change(0.17) == "+17%"
    assert monitor.explanation == (
        "Variant appears effective but may be creating unexpected user friction."
    )
    assert monitor.lanes[0].lines == ["Primary metric +18%", "Conversion +11%"]
    assert monitor.lanes[1].lines == ["Error rate +4.2%", "Support complaints +17%"]
    execution = run_execution(plan.specifications, approved=True, readings=readings)
    assert execution.steps[6].summary == "Stop is not required. The warning stays open."
    assert execution.report == (
        "Experiment status: Warning. "
        "Variant appears effective but may be creating unexpected user friction. "
        "Outcome: Iterate."
    )
    assert "not serving traffic" in execution.steps[2].summary


def test_a_critical_guardrail_recommends_a_stop_that_still_needs_approval():
    readings = [
        _reading("Primary metric", "primary", 0.18),
        _reading("Support complaints", "guardrail", 0.30),
    ]
    monitor = assess(readings)
    assert monitor.status == CRITICAL
    assert monitor.outcome == "Reject"
    execution = run_execution([], approved=True, readings=readings)
    assert execution.steps[6].status == "hold"
    assert execution.steps[6].summary.startswith("Stop is recommended.")


def test_approval_records_the_instruction_and_does_not_invent_readings(tmp_path):
    agent = DiscoveryAgent(tmp_path)
    agent.demo(sample_dir())
    assert agent.approve_execution("opp-instrumentation", "Fake door only")
    plan = agent.experiment("opp-instrumentation")
    assert plan is not None and plan.execution is not None
    assert plan.execution.approved
    assert plan.execution.approval_note == "Fake door only"
    assert "not serving traffic" in plan.execution.steps[2].summary
    assert plan.execution.monitor.status == "No readings yet"
    assert plan.execution.report.startswith("No experiment report yet.")
