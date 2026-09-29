"""Explicit scoring rubric for a cluster of evidence.

Problem score combines how strong the signals are, how many there are, and
how many intel pillars they cover. Five signals saturate volume. Opportunity
score then discounts that problem for weak market timing and for gaps that
are already crowded or merely table stakes.

The numbers are a review aid. The verdict rules in validation.py decide
whether a person should spend time on the bet.
"""

from discovery.models import Gap, IntelPillar, Signal, SignalKind

GAP_FACTOR = {
    Gap.unserved: 1.0,
    Gap.contested: 0.85,
    Gap.internal: 0.7,
    Gap.table_stakes: 0.35,
}


def clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def problem_score(signals: list[Signal]) -> float:
    intensity = sum(signal.strength for signal in signals) / len(signals)
    volume = min(len(signals) / 5, 1.0)
    coverage = len({signal.pillar for signal in signals}) / 3
    return clamp(0.5 * intensity + 0.3 * volume + 0.2 * coverage)


def market_momentum(signals: list[Signal]) -> float:
    kinds = {signal.kind for signal in signals}
    if SignalKind.news in kinds or SignalKind.trend in kinds:
        return 1.0
    if SignalKind.competitor in kinds:
        return 0.6
    return 0.25


def opportunity_score(problem: float, momentum: float, gap: Gap) -> float:
    timing = 0.65 + 0.35 * momentum
    return clamp(problem * timing * GAP_FACTOR[gap])


def confidence_score(validation: float, signals: list[Signal]) -> float:
    coverage = len({signal.pillar for signal in signals}) / 3
    volume = min(len(signals) / 5, 1.0)
    return clamp(0.45 * validation + 0.25 * coverage + 0.30 * volume)


def classify_gap(signals: list[Signal]) -> Gap:
    pain = sum(1 for signal in signals if signal.resolved_polarity().value in {"pain", "demand"})
    adoption = sum(1 for signal in signals if signal.resolved_polarity().value == "adoption")
    competitors = any(signal.kind is SignalKind.competitor for signal in signals)
    market = sum(1 for signal in signals if signal.pillar is IntelPillar.market)
    product = sum(1 for signal in signals if signal.pillar is IntelPillar.product)

    if pain == 0 and competitors and adoption > 0:
        return Gap.table_stakes
    if pain > 0 and competitors:
        return Gap.contested
    if pain > 0 and market == 0 and product > 0:
        return Gap.internal
    if pain > 0:
        return Gap.unserved
    if product > 0:
        return Gap.internal
    return Gap.unserved
