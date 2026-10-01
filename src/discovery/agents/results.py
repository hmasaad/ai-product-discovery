"""Results analysis.

A result is a learning. Support and contradiction stay in separate lists.
The write-up does not declare a winner.
"""

from discovery.models import MetricReading, ResultsAnalysis

_NO_RESULT = "No result is recorded."
_NO_INTERPRETATION = "There is no result to interpret."
_DEMAND = "Initial demand exists, but sustained value is not yet established."
_REPEAT = "Whether users consider the feature valuable enough for repeated use."
_NEXT_SPENDING = "Improve explanation personalization and test retention."
_USAGE_UP = "Usage increased."
_USAGE_DOWN = "Usage decreased."


def analyze_results(
    hypothesis: str,
    readings: list[MetricReading] | None = None,
    notes: list[tuple[str, str]] | None = None,
) -> ResultsAnalysis:
    observed_readings = list(readings or [])
    recorded = list(notes or [])
    observed = _observed(observed_readings, recorded)
    supporting, contradicting = _evidence(observed_readings, recorded)
    if observed == _NO_RESULT:
        return ResultsAnalysis(
            hypothesis=hypothesis,
            observed=observed,
            supporting=supporting,
            contradicting=contradicting,
            interpretation=_NO_INTERPRETATION,
            uncertainty="Whether the hypothesis holds.",
            next_experiment="Run the specified experiment before choosing a winner.",
        )
    if supporting and contradicting and observed == _USAGE_UP:
        return ResultsAnalysis(
            hypothesis=hypothesis,
            observed=observed,
            supporting=supporting,
            contradicting=contradicting,
            interpretation=_DEMAND,
            uncertainty=_REPEAT,
            next_experiment=_next(hypothesis),
        )
    if observed == _USAGE_DOWN or contradicting:
        return ResultsAnalysis(
            hypothesis=hypothesis,
            observed=observed,
            supporting=supporting,
            contradicting=contradicting,
            interpretation="The result cuts against sustained use.",
            uncertainty=_REPEAT,
            next_experiment=_next(hypothesis),
        )
    return ResultsAnalysis(
        hypothesis=hypothesis,
        observed=observed,
        supporting=supporting,
        contradicting=contradicting,
        interpretation="Initial demand exists. Sustained value is still untested.",
        uncertainty=_REPEAT,
        next_experiment=_next(hypothesis),
    )


def _observed(readings: list[MetricReading], notes: list[tuple[str, str]]) -> str:
    primary = [item.change for item in readings if item.lane == "primary"]
    if any(change <= -0.10 for change in primary):
        return _USAGE_DOWN
    if any(change > 0 for change in primary):
        return _USAGE_UP
    if notes and not primary:
        return _USAGE_UP if any(side == "support" for side, _text in notes) else _NO_RESULT
    return _NO_RESULT


def _evidence(
    readings: list[MetricReading],
    notes: list[tuple[str, str]],
) -> tuple[list[str], list[str]]:
    if notes:
        supporting = [text for side, text in notes if side == "support"]
        contradicting = [text for side, text in notes if side == "contradict"]
        return supporting, contradicting
    supporting: list[str] = []
    contradicting: list[str] = []
    if any(item.lane == "primary" and item.change > 0 for item in readings):
        supporting.append("Higher feature engagement")
    for item in readings:
        if item.lane != "primary" and item.change > 0.02:
            contradicting.append(f"{item.name} rose")
        if item.change < 0 and "repeat" in item.name.lower():
            contradicting.append("Usage declined after first interaction")
    return supporting, contradicting


def _next(hypothesis: str) -> str:
    text = hypothesis.lower()
    if "spend" in text or "explanation" in text:
        return _NEXT_SPENDING
    return "Improve personalization and test retention."
