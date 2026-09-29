"""Product opportunity brief.

The handoff names the problem, the evidence, and one experiment. It does not
tell a product manager to build the idea.

Pain bands are explicit. A frequency or severity tag on a signal wins.
Otherwise frequency is read from a user complaint volume above 1, and severity
from a friction metric (stall, abandon, drop, dismiss, churn):

- frequency volume >= 20 is high, >= 8 is moderate, otherwise low
- severity >= 0.75 is high, >= 0.5 is moderate-high, >= 0.3 is moderate, otherwise low

Evidence lines sum signal volume, including zeros, so a missing pillar stays
visible: user complaints (pain or demand), competitor observations, other
market signals, and internal analytics or usage.
"""

from discovery.engine.cluster import Cluster
from discovery.models import (
    IntelPillar,
    OpportunityChain,
    Polarity,
    ProductOpportunityBrief,
    Signal,
    SignalKind,
    ValidationBrief,
)

_FRICTION = ("stall", "abandon", "drop", "dismiss", "churn")
_FREQUENCY = {"high": "High", "moderate": "Moderate", "low": "Low"}
_SEVERITY = ("high", "moderate-high", "moderate", "low")
_NO_SOLUTION = "No existing solution is in the evidence."
_NO_EXPERIMENT = "No experiment is proposed yet."
_NO_RISK = "No product risk is recorded."
_NO_QUESTION = "No open question is recorded."


class ProductBriefAgent:
    def write(
        self,
        cluster: Cluster,
        chain: OpportunityChain,
        challenge: ValidationBrief | None,
    ) -> ProductOpportunityBrief:
        return ProductOpportunityBrief(
            problem=chain.problem,
            target_users=chain.segment,
            observed_pain=_observed_pain(cluster.signals),
            existing_solutions=_solutions(cluster, chain),
            gap=chain.gap,
            opportunity=cluster.idea_title,
            mvp=_mvp(cluster),
            evidence=_evidence(cluster.signals),
            risks=list(cluster.risks) or [_NO_RISK],
            open_questions=_questions(cluster, challenge),
            experiment=_experiment(cluster),
        )


def _observed_pain(signals: list[Signal]) -> str:
    frequency = _frequency_tag(signals) or _frequency_volume(signals)
    severity = _severity_tag(signals) or _severity_metric(signals)
    frequency_label = (
        f"{_FREQUENCY[frequency]} frequency" if frequency else "Frequency is not measured"
    )
    severity_label = f"{severity} severity" if severity else "severity is not measured"
    return f"{frequency_label} / {severity_label}"


def _frequency_tag(signals: list[Signal]) -> str | None:
    return _tag(signals, "frequency", _FREQUENCY)


def _severity_tag(signals: list[Signal]) -> str | None:
    return _tag(signals, "severity", {name: name for name in _SEVERITY})


def _tag(signals: list[Signal], name: str, allowed: dict[str, str]) -> str | None:
    ranked = sorted(signals, key=lambda signal: (-signal.strength, signal.id))
    for signal in ranked:
        for tag in signal.tags:
            label, _, value = tag.partition(":")
            if label.lower() == name and value.lower() in allowed:
                return value.lower()
    return None


def _frequency_volume(signals: list[Signal]) -> str | None:
    volumes = [signal.volume for signal in signals if _is_complaint(signal)]
    peak = max(volumes) if volumes else 0
    if peak <= 1:
        return None
    if peak >= 20:
        return "high"
    if peak >= 8:
        return "moderate"
    return "low"


def _severity_metric(signals: list[Signal]) -> str | None:
    ranked = sorted(signals, key=lambda signal: (-signal.strength, signal.id))
    for signal in ranked:
        rates = [
            value
            for key, value in signal.metrics.items()
            if any(token in key for token in _FRICTION)
        ]
        if not rates:
            continue
        rate = max(rates)
        if rate >= 0.75:
            return "high"
        if rate >= 0.5:
            return "moderate-high"
        if rate >= 0.3:
            return "moderate"
        return "low"
    return None


def _solutions(cluster: Cluster, chain: OpportunityChain) -> list[str]:
    if cluster.solutions:
        return list(cluster.solutions)
    ranked = sorted(cluster.signals, key=lambda signal: (-signal.strength, signal.id))
    names = [signal.title for signal in ranked if signal.kind is SignalKind.competitor]
    if names:
        return names
    if chain.existing_solutions == _NO_SOLUTION or not chain.existing_solutions:
        return [_NO_SOLUTION]
    return [chain.existing_solutions]


def _mvp(cluster: Cluster) -> list[str]:
    if cluster.mvp:
        return list(cluster.mvp)
    if cluster.idea_summary:
        return [cluster.idea_summary]
    return ["No MVP is specified yet."]


def _evidence(signals: list[Signal]) -> list[str]:
    complaints = _volume(signals, _is_complaint)
    competitors = _volume(signals, lambda signal: signal.kind is SignalKind.competitor)
    market = _volume(
        signals,
        lambda signal: signal.pillar is IntelPillar.market and signal.kind is not SignalKind.competitor,
    )
    analytics = _volume(
        signals,
        lambda signal: signal.pillar is IntelPillar.product
        and signal.kind in {SignalKind.analytics, SignalKind.usage},
    )
    return [
        _count(complaints, "user complaint"),
        _count(competitors, "competitor observation"),
        _count(market, "market signal"),
        _count(analytics, "internal analytics signal"),
    ]


def _questions(cluster: Cluster, challenge: ValidationBrief | None) -> list[str]:
    if cluster.open_questions:
        return list(cluster.open_questions)
    if challenge is None:
        return [_NO_QUESTION]
    opened = [
        item.question
        for item in challenge.questions
        if item.status == "open" and item.id != "contradiction"
    ]
    return opened or [_NO_QUESTION]


def _experiment(cluster: Cluster) -> str:
    if cluster.experiment.strip():
        return cluster.experiment.strip()
    if cluster.experiments:
        return cluster.experiments[0]
    return _NO_EXPERIMENT


def _is_complaint(signal: Signal) -> bool:
    return signal.pillar is IntelPillar.user and signal.resolved_polarity() in {
        Polarity.pain,
        Polarity.demand,
    }


def _volume(signals: list[Signal], include) -> int:
    return sum(signal.volume for signal in signals if include(signal))


def _count(amount: int, singular: str) -> str:
    if amount == 1:
        return f"1 {singular}"
    return f"{amount} {_plural(singular)}"


def _plural(singular: str) -> str:
    if singular.endswith("y") and singular[-2] not in "aeiou":
        return singular[:-1] + "ies"
    return singular + "s"
