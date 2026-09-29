"""Market research agent.

Reads industry trends, emerging technology, competitor and startup launches,
pricing, gaps, customer complaints, product launches, and regulatory changes.
Publishes one market signal per trend: the evidence, then a potential implication.
"""

import re

from discovery.engine.cluster import build_clusters
from discovery.engine.scoring import clamp
from discovery.models import (
    IntelPillar,
    MarketEvidenceItem,
    MarketFacet,
    MarketSignal,
    Polarity,
    Signal,
    SignalKind,
    Theme,
)

# Most specific facet wins when one observation fits several lenses.
FACET_PRIORITY = (
    MarketFacet.pricing,
    MarketFacet.regulatory,
    MarketFacet.startup,
    MarketFacet.competitor_launch,
    MarketFacet.product_launch,
    MarketFacet.technology,
    MarketFacet.complaint,
    MarketFacet.market_gap,
    MarketFacet.trend,
)

_REGULATORY = ("regulat", "privacy", "compliance", "gdpr", "lawsuit")
_PRICING = ("pricing", "price cut", "price increase", "discount", "raised prices", "cheaper")
_GAP = ("market gap", "nobody offers", "still no ", "lack of", "unserved")
_LAUNCH = ("launch", "shipped", "released", "announced", "added")


class MarketResearchAgent:
    def analyze(self, signals: list[Signal], themes: list[Theme]) -> list[MarketSignal]:
        facets_by_id = {signal.id: classify_market(signal) for signal in signals}
        relevant = [signal for signal in signals if facets_by_id[signal.id]]
        published: list[MarketSignal] = []
        for cluster in build_clusters(relevant, themes):
            facets = _union(facets_by_id[signal.id] for signal in cluster.signals)
            if not facets:
                continue
            evidence = [
                _evidence_item(signal, _primary(facets_by_id[signal.id]))
                for signal in sorted(cluster.signals, key=lambda item: (-item.strength, item.id))
            ]
            published.append(
                MarketSignal(
                    id=f"mkt-{cluster.theme_id}",
                    theme=cluster.theme_id,
                    trend=cluster.label,
                    evidence=evidence[:6],
                    implication=_implication(
                        cluster.label,
                        facets,
                        "" if cluster.emergent else cluster.idea_title,
                    ),
                    facets=_ordered(facets),
                    strength=_strength(cluster.signals, facets),
                    signal_ids=[item.signal_id for item in evidence],
                )
            )
        published.sort(key=lambda item: (-item.strength, item.id))
        return published


def classify_market(signal: Signal) -> list[MarketFacet]:
    """Which market lenses an observation belongs to. Product usage stays out."""

    if signal.pillar is IntelPillar.product:
        return []

    text = f" {signal.text()} "
    if signal.pillar is IntelPillar.user:
        if signal.resolved_polarity() in {Polarity.pain, Polarity.demand}:
            return [MarketFacet.complaint]
        return []

    found: list[MarketFacet] = []
    if any(token in text for token in _REGULATORY):
        found.append(MarketFacet.regulatory)
    if any(token in text for token in _PRICING):
        found.append(MarketFacet.pricing)
    if re.search(r"\bai\b", text) or "copilot" in text or "machine learning" in text:
        found.append(MarketFacet.technology)
    if "startup" in text or "start-up" in text:
        found.append(MarketFacet.startup)
    if signal.kind is SignalKind.competitor and any(token in text for token in _LAUNCH):
        found.append(MarketFacet.competitor_launch)
    elif signal.kind is SignalKind.competitor and MarketFacet.startup not in found:
        found.append(MarketFacet.product_launch)
    if any(token in text for token in _GAP):
        found.append(MarketFacet.market_gap)
    if signal.kind is SignalKind.trend or "search interest" in text or "increasingly" in text:
        found.append(MarketFacet.trend)
    if signal.kind is SignalKind.news and MarketFacet.regulatory not in found and not found:
        found.append(MarketFacet.trend)
    if not found and signal.pillar is IntelPillar.market:
        found.append(MarketFacet.trend)
    return _ordered(set(found))


def _primary(facets: list[MarketFacet]) -> MarketFacet:
    return _ordered(facets)[0]


def _ordered(facets: set[MarketFacet] | list[MarketFacet]) -> list[MarketFacet]:
    present = set(facets)
    return [facet for facet in FACET_PRIORITY if facet in present]


def _union(groups) -> set[MarketFacet]:
    found: set[MarketFacet] = set()
    for group in groups:
        found.update(group)
    return found


def _evidence_item(signal: Signal, facet: MarketFacet) -> MarketEvidenceItem:
    return MarketEvidenceItem(
        signal_id=signal.id,
        facet=facet,
        statement=_statement(signal, facet),
        source=signal.source,
        observed_at=signal.observed_at,
    )


def _statement(signal: Signal, facet: MarketFacet) -> str:
    title = signal.title.strip().rstrip(".")
    lowered = title.lower()
    if "search interest" in signal.text():
        if lowered.startswith("search interest"):
            return title
        return f"Search interest increased: {title}"
    if facet is MarketFacet.complaint:
        if lowered.startswith("users "):
            return title
        return f"Users report: {title}"
    if facet is MarketFacet.startup:
        if "startup" in lowered:
            return title
        return f"Startups entering: {title}"
    if facet is MarketFacet.competitor_launch:
        if any(word in lowered for word in ("launch", "shipped", "released", "added")):
            return title
        return f"{signal.source} launched: {title}"
    if facet is MarketFacet.product_launch:
        return f"Product launch: {title}"
    if facet is MarketFacet.pricing:
        return title if "pric" in lowered else f"Pricing change: {title}"
    if facet is MarketFacet.regulatory:
        return title
    if facet is MarketFacet.technology:
        return f"Emerging technology: {title}"
    if facet is MarketFacet.market_gap:
        return f"Market gap: {title}"
    return title


_MOVEMENT = {
    MarketFacet.trend,
    MarketFacet.technology,
    MarketFacet.competitor_launch,
    MarketFacet.pricing,
    MarketFacet.market_gap,
    MarketFacet.startup,
    MarketFacet.product_launch,
    MarketFacet.regulatory,
}


def _implication(label: str, facets: set[MarketFacet], idea_title: str) -> str:
    moving = bool(facets & _MOVEMENT)
    if idea_title and moving and " can " not in idea_title.lower():
        phrase = idea_title[0].lower() + idea_title[1:]
        return f"Opportunity for {phrase.rstrip('.')}."
    if MarketFacet.complaint in facets and (
        MarketFacet.competitor_launch in facets or MarketFacet.startup in facets
    ):
        return (
            f"Opportunity around {label}: customers are asking, "
            "and the market is already shipping answers."
        )
    if MarketFacet.regulatory in facets:
        return f"Opportunity to move on {label} before the regulatory shift becomes the default."
    if MarketFacet.technology in facets:
        return f"Opportunity to apply emerging technology to {label} more specifically than a generic launch."
    if MarketFacet.pricing in facets:
        return f"Pricing movement in {label} may open a gap in packaging or willingness to pay."
    if MarketFacet.startup in facets:
        return f"New startups are entering {label}; the category is still being defined."
    if MarketFacet.complaint in facets:
        return f"Customer complaints keep returning to {label}."
    if MarketFacet.competitor_launch in facets or MarketFacet.product_launch in facets:
        return f"Competitors are staking out {label}; a copy of the launch is a weak response."
    return f"Demand is building around {label}."


def _strength(signals: list[Signal], facets: set[MarketFacet]) -> float:
    intensity = sum(signal.strength for signal in signals) / len(signals)
    diversity = min(len(facets) / 4, 1)
    return clamp(intensity * (0.75 + 0.25 * diversity))
