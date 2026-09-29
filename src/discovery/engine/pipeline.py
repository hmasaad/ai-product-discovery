"""Turn clusters into product opportunities."""

from discovery.agents.brief import ProductBriefAgent
from discovery.agents.validate import OpportunityValidationAgent
from discovery.engine.cluster import Cluster, build_clusters
from discovery.engine.detect import chain_for
from discovery.engine.scoring import (
    classify_gap,
    confidence_score,
    market_momentum,
    opportunity_score,
    problem_score,
)
from discovery.engine.validate import (
    build_checks,
    choose_verdict,
    dedupe,
    next_steps,
    rationale,
    validation_score,
)
from discovery.models import (
    Check,
    Evidence,
    Gap,
    IntelPillar,
    Opportunity,
    Polarity,
    Scores,
    Signal,
    SignalKind,
    Theme,
    Verdict,
)

MAPPING_NOTES = {
    Gap.unserved: "No competitor evidence is attached yet, so this is a whitespace bet.",
    Gap.contested: "Competitors are already moving, so a me-too launch is not enough.",
    Gap.internal: "The strongest evidence is inside our own product data.",
    Gap.table_stakes: "This looks like parity with the market, not a fresh pain.",
}


def run_engine(
    signals: list[Signal],
    themes: list[Theme],
    audience: str = "",
) -> list[Opportunity]:
    opportunities = [
        build_opportunity(cluster, audience) for cluster in build_clusters(signals, themes)
    ]
    order = {Verdict.pursue: 0, Verdict.investigate: 1, Verdict.park: 2}
    opportunities.sort(key=lambda item: (order[item.verdict], -item.scores.opportunity, item.id))
    return opportunities


def build_opportunity(cluster: Cluster, audience: str = "") -> Opportunity:
    gap = classify_gap(cluster.signals)
    checks = build_checks(cluster.signals)
    problem = problem_score(cluster.signals)
    validation = validation_score(checks)
    opportunity = opportunity_score(problem, market_momentum(cluster.signals), gap)
    verdict = choose_verdict(opportunity, gap, checks)
    chain = chain_for(cluster, audience)
    challenge = OpportunityValidationAgent().review(cluster.signals, gap, audience)
    return Opportunity(
        id=f"opp-{cluster.theme_id}",
        theme=cluster.theme_id,
        label=cluster.label,
        title=cluster.idea_title,
        problem=cluster.problem,
        gap=gap,
        why_now=_why_now(cluster.signals, gap),
        mapping_note=MAPPING_NOTES[gap],
        idea_summary=cluster.idea_summary,
        rationale=rationale(verdict, gap, checks),
        scores=Scores(
            problem=problem,
            opportunity=opportunity,
            validation=validation,
            confidence=confidence_score(validation, cluster.signals),
        ),
        verdict=verdict,
        checks=checks,
        risks=_risks(cluster, gap, checks),
        next_steps=next_steps(checks, cluster.experiments),
        evidence=[_evidence(signal) for signal in _by_strength(cluster.signals)],
        signal_ids=[signal.id for signal in _by_strength(cluster.signals)],
        chain=chain,
        challenge=challenge,
        product_brief=ProductBriefAgent().write(cluster, chain, challenge),
    )


def _by_strength(signals: list[Signal]) -> list[Signal]:
    return sorted(signals, key=lambda signal: (-signal.strength, signal.id))


def _evidence(signal: Signal) -> Evidence:
    return Evidence(
        signal_id=signal.id,
        pillar=signal.pillar,
        kind=signal.kind,
        title=signal.title,
        excerpt=_excerpt(signal.body),
        source=signal.source,
        observed_at=signal.observed_at,
        polarity=signal.resolved_polarity(),
        strength=signal.strength,
        metrics=dict(signal.metrics),
    )


def _excerpt(body: str, limit: int = 280) -> str:
    text = " ".join(body.split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _why_now(signals: list[Signal], gap: Gap) -> str:
    bits: list[str] = []
    news = next((signal for signal in signals if signal.kind is SignalKind.news), None)
    trend = next((signal for signal in signals if signal.kind is SignalKind.trend), None)
    competitors = [signal for signal in signals if signal.kind is SignalKind.competitor]
    if news is not None:
        bits.append(f"Market context shifted: {news.title}")
    elif trend is not None:
        bits.append(f"Demand is moving: {trend.title}")
    if competitors:
        sources = ", ".join(dict.fromkeys(signal.source for signal in competitors))
        bits.append(f"competitor activity shows up in {sources}")
    product = _by_strength(
        [signal for signal in signals if signal.pillar is IntelPillar.product]
    )
    if product:
        bits.append(f'product evidence includes "{product[0].title}"')
    users = _by_strength(
        [
            signal
            for signal in signals
            if signal.pillar is IntelPillar.user
            and signal.resolved_polarity() in {Polarity.pain, Polarity.demand}
        ]
    )
    if users:
        bits.append(f'users put it plainly: "{users[0].title}"')
    if gap is Gap.table_stakes:
        bits.append("the pattern matches adoption of an existing capability more than unmet demand")
    if not bits:
        return "Nothing in this cluster says why the timing is favorable."
    return " ".join(_sentence(bit) for bit in bits)


def _sentence(text: str) -> str:
    cleaned = text.strip().rstrip(".")
    return cleaned[0].upper() + cleaned[1:] + "."


def _risks(cluster: Cluster, gap: Gap, checks: list[Check]) -> list[str]:
    failed = {check.id for check in checks if not check.passed}
    pillars = {signal.pillar for signal in cluster.signals}
    items: list[str] = []
    if gap is Gap.table_stakes:
        items.append("Shipping this only matches a capability buyers already expect.")
    if gap is Gap.contested:
        items.append("Competitors are already shipping adjacent solutions.")
    if "product_evidence" in failed:
        items.append("No usage or analytics evidence yet.")
    if len(pillars) == 1:
        items.append("All of the evidence sits in one intel pillar.")
    if "enough_evidence" in failed:
        items.append("There are not enough independent signals to be confident.")
    items.extend(cluster.risks)
    return dedupe(items, limit=4)
