"""Validation agent.

A cluster becomes a bet only when the evidence can survive a fixed checklist:
a real user problem, enough independent signals, and a score that clears the
bar. Table-stakes adoption is parked even when the topic is popular.
"""

from discovery.models import Check, Gap, IntelPillar, Polarity, Signal, Verdict

PURSUE_SCORE = 0.55
INVESTIGATE_SCORE = 0.35
MIN_SIGNALS = 3

REMEDIES = {
    "user_evidence": "Interview users or pull reviews that describe this problem in their words.",
    "product_evidence": "Check analytics for a stall, drop-off, or adoption gap tied to this problem.",
    "market_context": "Scan competitor releases, category news, and trend reports for this theme.",
    "enough_evidence": "Gather at least three independent signals before treating this as a bet.",
    "measurable": "Attach a metric so the bet can be falsified.",
    "real_pain": "Separate unmet pain from table-stakes adoption before investing.",
}


def build_checks(signals: list[Signal]) -> list[Check]:
    user = sum(1 for signal in signals if signal.pillar is IntelPillar.user)
    product = sum(1 for signal in signals if signal.pillar is IntelPillar.product)
    market = sum(1 for signal in signals if signal.pillar is IntelPillar.market)
    measurable = sum(1 for signal in signals if signal.metrics)
    pain = sum(
        1
        for signal in signals
        if signal.resolved_polarity() in {Polarity.pain, Polarity.demand}
    )
    total = len(signals)
    return [
        Check(
            id="user_evidence",
            label="User evidence",
            passed=user > 0,
            detail=f"{_count(user, 'user signal')} in this cluster.",
        ),
        Check(
            id="product_evidence",
            label="Product evidence",
            passed=product > 0,
            detail=f"{_count(product, 'product signal')} in this cluster.",
        ),
        Check(
            id="market_context",
            label="Market context",
            passed=market > 0,
            detail=f"{_count(market, 'market signal')} in this cluster.",
        ),
        Check(
            id="enough_evidence",
            label="Enough evidence",
            passed=total >= MIN_SIGNALS,
            detail=f"{_count(total, 'independent signal')}; the bar is {MIN_SIGNALS}.",
        ),
        Check(
            id="measurable",
            label="Measurable",
            passed=measurable > 0,
            detail=_metric_detail(measurable),
        ),
        Check(
            id="real_pain",
            label="Unmet pain or demand",
            passed=pain > 0,
            detail=(
                f"{_count(pain, 'signal')} "
                f"{'describes' if pain == 1 else 'describe'} pain or an explicit ask."
            ),
        ),
    ]


def validation_score(checks: list[Check]) -> float:
    if not checks:
        return 0.0
    return sum(1 for check in checks if check.passed) / len(checks)


def choose_verdict(score: float, gap: Gap, checks: list[Check]) -> Verdict:
    passed = {check.id: check.passed for check in checks}
    if gap is Gap.table_stakes or not passed.get("real_pain", False):
        return Verdict.park
    ratio = validation_score(checks)
    if (
        passed.get("user_evidence", False)
        and passed.get("enough_evidence", False)
        and score >= PURSUE_SCORE
        and ratio >= 0.65
    ):
        return Verdict.pursue
    if score >= INVESTIGATE_SCORE:
        return Verdict.investigate
    return Verdict.park


def rationale(verdict: Verdict, gap: Gap, checks: list[Check]) -> str:
    failed = [check.label.lower() for check in checks if not check.passed]
    gap_label = {
        Gap.unserved: "whitespace",
        Gap.contested: "contested",
        Gap.internal: "internal",
        Gap.table_stakes: "table-stakes",
    }[gap]
    if verdict is Verdict.pursue:
        return (
            f"Pursue. User evidence and a {gap_label} gap clear the bar, "
            "and the other checks hold."
        )
    if verdict is Verdict.investigate:
        missing = ", ".join(failed) if failed else "a stronger opportunity score"
        return (
            "Investigate. The cluster is real, but it is not decision-ready. "
            f"Still open: {missing}."
        )
    if gap is Gap.table_stakes:
        return "Park. The evidence describes a capability the market already treats as table stakes."
    if failed:
        return f"Park. The case is too thin. Still open: {', '.join(failed)}."
    return "Park. The opportunity score does not clear the bar to spend more time on this."


def next_steps(checks: list[Check], experiments: list[str]) -> list[str]:
    steps = [REMEDIES[check.id] for check in checks if not check.passed and check.id in REMEDIES]
    steps.extend(experiments)
    return dedupe(steps, limit=4)


def _metric_detail(measurable: int) -> str:
    if measurable == 0:
        return "No signal in this cluster includes a metric."
    if measurable == 1:
        return "1 signal includes a metric."
    return f"{measurable} signals include a metric."


def _count(amount: int, noun: str) -> str:
    if amount == 1:
        return f"1 {noun}"
    if noun.endswith("y") and not noun.endswith("ay"):
        plural = noun[:-1] + "ies"
    else:
        plural = noun + "s"
    return f"{amount} {plural}"


def dedupe(items: list[str], limit: int) -> list[str]:
    chosen: list[str] = []
    seen: set[str] = set()
    for item in items:
        if not item or item in seen:
            continue
        seen.add(item)
        chosen.append(item)
        if len(chosen) == limit:
            break
    return chosen
