"""Turn every signal into an opportunity candidate.

Signal → problem → user segment → pain → existing solutions → gap → opportunity.

Signals that share a workspace theme become one candidate, so a complaint and
the solutions already in market can sit on the same chain. A signal that
matches nothing still becomes its own candidate. Scoring and review stay with
the opportunity engine, which still requires more than one signal.
"""

import re

from discovery.engine.cluster import MIN_CLUSTER, Cluster, build_clusters, match_theme, themed_cluster
from discovery.models import (
    IntelPillar,
    OpportunityCandidate,
    OpportunityChain,
    Polarity,
    Signal,
    SignalKind,
    Theme,
)

_COMPLAINT_PREFIXES = (
    "users repeatedly complain about ",
    "users repeatedly complain that ",
    "users complain about ",
    "users complain that ",
    "customers complain about ",
    "customers complain that ",
    "people complain about ",
    "people complain that ",
)
_SHORTFALL = re.compile(
    r"\b(but|however|still|requires?|manual\w*|missing|without)\b",
    re.IGNORECASE,
)
def detect_candidates(
    signals: list[Signal],
    themes: list[Theme],
    audience: str = "",
) -> list[OpportunityCandidate]:
    """Convert every signal into a candidate. Related signals share one chain."""

    groups = _groups(signals, themes)
    return [candidate_for(group, audience) for group in groups]


def chain_for(cluster: Cluster, audience: str = "") -> OpportunityChain:
    complaint = _complaint(cluster.signals)
    pain_signal = _felt_pain(cluster.signals)
    pain = (
        _pain(pain_signal)
        if pain_signal is not None
        else "No direct user pain is in the evidence yet."
    )
    solutions = _solution_texts(cluster.signals)
    return OpportunityChain(
        signal=_sentence(complaint.body or complaint.title) if complaint else "No signal is attached.",
        problem=cluster.problem,
        segment=audience.strip() or "Unspecified",
        pain=pain,
        existing_solutions=_solutions_line(solutions),
        gap=_gap(solutions, pain, pain_signal is not None),
        opportunity=cluster.idea_title,
    )


def candidate_for(cluster: Cluster, audience: str = "") -> OpportunityCandidate:
    return OpportunityCandidate(
        id=f"cand-{cluster.theme_id}",
        theme=cluster.theme_id,
        label=cluster.label,
        signal_ids=[signal.id for signal in cluster.signals],
        chain=chain_for(cluster, audience),
    )


def _groups(signals: list[Signal], themes: list[Theme]) -> list[Cluster]:
    clustered = build_clusters(signals, themes)
    covered = {signal.id for cluster in clustered for signal in cluster.signals}
    groups = list(clustered)
    themes_by_id = {theme.id: theme for theme in themes}
    assigned: dict[str, list[Signal]] = {}
    for signal in signals:
        if signal.id in covered:
            continue
        theme = match_theme(signal, themes)
        if theme is None:
            groups.append(_solo(signal))
            continue
        assigned.setdefault(theme.id, []).append(signal)
    for theme_id, grouped in assigned.items():
        theme = themes_by_id[theme_id]
        groups.append(
            themed_cluster(
                theme,
                sorted(grouped, key=lambda item: (item.observed_at, item.id)),
            )
        )
    groups.sort(key=lambda cluster: (len(cluster.signals) < MIN_CLUSTER, cluster.theme_id))
    return groups


def _solo(signal: Signal) -> Cluster:
    pain = _pain(signal)
    return Cluster(
        theme_id=f"signal-{signal.id}",
        label=signal.title,
        problem=pain,
        idea_title=f"Investigate {signal.title}",
        idea_summary=f"One signal points at {signal.title}. It needs a second source before review.",
        signals=[signal],
        emergent=True,
    )


def _complaint(signals: list[Signal]) -> Signal | None:
    felt = _felt_pain(signals)
    pool = [felt] if felt is not None else list(signals)
    if not pool or pool == [None]:
        return None
    return max(pool, key=lambda signal: (signal.strength, signal.id))


def _felt_pain(signals: list[Signal]) -> Signal | None:
    user = [signal for signal in signals if _is_pain(signal)]
    if user:
        return max(user, key=lambda signal: (signal.strength, signal.id))
    product = [
        signal
        for signal in signals
        if signal.pillar is IntelPillar.product
        and signal.resolved_polarity() in {Polarity.pain, Polarity.demand}
    ]
    if product:
        return max(product, key=lambda signal: (signal.strength, signal.id))
    return None


def _is_pain(signal: Signal | None) -> bool:
    if signal is None or signal.pillar is not IntelPillar.user:
        return False
    return signal.resolved_polarity() in {Polarity.pain, Polarity.demand}


def _pain(signal: Signal) -> str:
    source = signal.body.strip() or signal.title.strip()
    lowered = source.lower()
    for prefix in _COMPLAINT_PREFIXES:
        if lowered.startswith(prefix):
            return _sentence(source[len(prefix) :])
    return _sentence(source)


def _solution_texts(signals: list[Signal]) -> list[str]:
    texts: list[str] = []
    for signal in sorted(signals, key=lambda item: (-item.strength, item.id)):
        if not _is_solution(signal):
            continue
        text = (signal.body or signal.title).strip()
        if text:
            texts.append(text)
    return texts


def _is_solution(signal: Signal) -> bool:
    if signal.kind is SignalKind.competitor:
        return True
    return signal.resolved_polarity() is Polarity.adoption


def _solutions_line(solutions: list[str]) -> str:
    if not solutions:
        return "No existing solution is in the evidence."
    return " ".join(_sentence(text) for text in solutions)


def _gap(solutions: list[str], pain: str, has_pain: bool) -> str:
    for text in solutions:
        sentence = _sentence(text)
        if _SHORTFALL.search(sentence):
            return sentence
    if solutions and has_pain:
        return f"The pain is still open. {pain}"
    if solutions:
        return "Existing solutions already cover this, and the evidence does not show unmet pain."
    if has_pain:
        return "No existing solution is in the evidence, so the pain is unserved."
    return "No existing solution or unmet pain is in the evidence."


def _sentence(text: str) -> str:
    cleaned = " ".join(text.split()).strip()
    if not cleaned:
        return ""
    if cleaned[-1] not in ".!?":
        cleaned += "."
    return cleaned[0].upper() + cleaned[1:]
