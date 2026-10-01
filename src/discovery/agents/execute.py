"""Experiment execution and monitoring.

The agent prepares nine steps across the product systems. Configuring a
feature flag, starting the experiment, and stopping it change production, so
those steps wait for a person. The monitor compares each reading with the
control. The control is the behavioral baseline. A guardrail that leaves it
is an anomaly.
"""

from discovery.agents.results import analyze_results
from discovery.models import (
    ExecutionStep,
    ExperimentExecution,
    ExperimentMonitor,
    ExperimentSpec,
    MetricReading,
    MonitorLane,
)

SYSTEMS = (
    "Analytics",
    "Feature flags",
    "Product database",
    "Survey system",
    "A/B testing platform",
    "User feedback",
    "Experiment dashboard",
)

ACTIONS = (
    "Create experiment",
    "Configure audience",
    "Configure feature flag",
    "Start experiment",
    "Monitor metrics",
    "Detect anomalies",
    "Stop experiment",
    "Analyze results",
    "Generate experiment report",
)

HEALTHY = "Healthy"
WARNING = "Warning"
CRITICAL = "Critical"
WAITING = "No readings yet"

_FRICTION = "Variant appears effective but may be creating unexpected user friction."
_STOP = "A guardrail is far from the baseline. Stop is recommended."
_QUIET = "The variant is inside the baseline. No anomaly is open."
_BASELINE = "The control is the behavioral baseline. A move of more than 2% is an anomaly."

# A guardrail or quality signal past this band is a warning. Past the critical
# band, or a primary drop of 10%, the monitor asks for a stop.
_WARN = 0.02
_CRITICAL = 0.25
_PRIMARY_DROP = -0.10


def run_execution(
    specifications: list[ExperimentSpec],
    approved: bool,
    note: str = "",
    readings: list[MetricReading] | None = None,
    hypothesis: str = "",
    notes: list[tuple[str, str]] | None = None,
) -> ExperimentExecution:
    observed = list(readings or [])
    monitor = assess(observed)
    audience = specifications[0].target_audience if specifications else "The specification has no audience yet."
    claim = hypothesis or (specifications[0].hypothesis if specifications else "")
    analysis = analyze_results(claim, observed, notes)
    report = _report(monitor, observed)
    steps = [
        _step("Create experiment", "Experiment dashboard", "prepared", False, _create(specifications)),
        _step("Configure audience", "Product database", "prepared", False, f"Audience: {audience}"),
        _step(
            "Configure feature flag",
            "Feature flags",
            "approved" if approved else "waiting",
            True,
            _flag(approved),
        ),
        _step(
            "Start experiment",
            "A/B testing platform",
            "approved" if approved else "waiting",
            True,
            _start(approved, observed),
        ),
        _step("Monitor metrics", "Analytics", _watch_status(observed), False, _watch(observed, monitor)),
        _step("Detect anomalies", "Analytics", _watch_status(observed), False, _BASELINE),
        _step("Stop experiment", "Feature flags", _stop_status(monitor), True, _stop(monitor)),
        _step("Analyze results", "User feedback", _watch_status(observed), False, analysis.interpretation),
        _step("Generate experiment report", "Experiment dashboard", _watch_status(observed), False, report),
    ]
    return ExperimentExecution(
        steps=steps,
        approved=approved,
        approval_note=note,
        monitor=monitor,
        report=report,
        analysis=analysis,
    )


def assess(readings: list[MetricReading]) -> ExperimentMonitor:
    lanes = [
        MonitorLane(name="Primary", lines=_lane(readings, "primary")),
        MonitorLane(name="Guardrails", lines=_lane(readings, "guardrail")),
        MonitorLane(name="Quality", lines=_lane(readings, "quality")),
    ]
    if not readings:
        return ExperimentMonitor(
            status=WAITING,
            explanation="The monitor starts when analytics sends a reading.",
            lanes=lanes,
        )
    status, explanation, outcome = _judge(readings)
    return ExperimentMonitor(status=status, explanation=explanation, lanes=lanes, outcome=outcome)


def format_change(value: float) -> str:
    pct = round(value * 100, 1)
    number = f"{pct:.0f}" if pct == round(pct) else f"{pct:.1f}"
    if pct > 0:
        return f"+{number}%"
    return f"{number}%"


def _judge(readings: list[MetricReading]) -> tuple[str, str, str]:
    primary = [item.change for item in readings if item.lane == "primary"]
    guards = [item.change for item in readings if item.lane in {"guardrail", "quality"}]
    primary_up = any(change > 0 for change in primary)
    primary_drop = any(change <= _PRIMARY_DROP for change in primary)
    guard_critical = any(change >= _CRITICAL for change in guards)
    guard_warning = any(change > _WARN for change in guards)
    if primary_drop or guard_critical:
        return CRITICAL, _STOP, "Reject"
    if guard_warning and primary_up:
        return WARNING, _FRICTION, "Iterate"
    if guard_warning:
        return WARNING, "A guardrail has left the baseline.", "Iterate"
    return HEALTHY, _QUIET, "Continue" if primary_up else ""


def _lane(readings: list[MetricReading], lane: str) -> list[str]:
    lines = [f"{item.name} {format_change(item.change)}" for item in readings if item.lane == lane]
    if lines:
        return lines
    if lane == "quality":
        return ["No quality signal has left the baseline."]
    if not readings:
        return ["No reading yet."]
    return ["No reading in this lane."]


def _create(specifications: list[ExperimentSpec]) -> str:
    if not specifications:
        return "No specification is ready to create."
    names = ", ".join(item.name for item in specifications)
    return f"Created on the experiment dashboard: {names}."


def _flag(approved: bool) -> str:
    if not approved:
        return "Waiting for approval. The variant stays off."
    return (
        "Approved. The flag instruction is on the experiment dashboard. "
        "No flag service is connected, so the variant is not serving traffic."
    )


def _start(approved: bool, readings: list[MetricReading]) -> str:
    if not approved:
        return "Waiting for approval. The experiment has not started."
    if readings:
        return "Approved and running. Analytics has sent readings."
    return "Approved to start. Analytics has not sent a reading."


def _watch(readings: list[MetricReading], monitor: ExperimentMonitor) -> str:
    if not readings:
        return "Waiting until a reading arrives. The control is the behavioral baseline."
    return f"Experiment status: {monitor.status}. {monitor.explanation}"


def _watch_status(readings: list[MetricReading]) -> str:
    return "ready" if readings else "waiting"


def _stop(monitor: ExperimentMonitor) -> str:
    if monitor.status == CRITICAL:
        return "Stop is recommended. Approval is required before the variant is turned off."
    if monitor.status == WARNING:
        return "Stop is not required. The warning stays open."
    if monitor.status == WAITING:
        return "Not necessary. No reading is in."
    return "Not necessary. The variant is inside the baseline."


def _stop_status(monitor: ExperimentMonitor) -> str:
    if monitor.status == CRITICAL:
        return "hold"
    if monitor.status == WARNING:
        return "waiting"
    return "prepared"


def _report(monitor: ExperimentMonitor, readings: list[MetricReading]) -> str:
    if not readings:
        return "No experiment report yet. The report is written when readings arrive."
    outcome = f" Outcome: {monitor.outcome}." if monitor.outcome else ""
    return f"Experiment status: {monitor.status}. {monitor.explanation}{outcome}"


def _step(action: str, system: str, status: str, needs_approval: bool, summary: str) -> ExecutionStep:
    return ExecutionStep(
        action=action,
        system=system,
        summary=summary,
        status=status,
        needs_approval=needs_approval,
    )
