"""User intelligence agent.

Reads app reviews, support tickets, feature requests, surveys, interviews,
community discussions, product analytics, and other user feedback.
Clusters the complaints, shows each cluster's share of feedback, and names
the unmet needs.
"""

from collections import defaultdict

from discovery.engine.cluster import Cluster, build_clusters, match_theme
from discovery.models import (
    IntelPillar,
    Polarity,
    ProblemCluster,
    Signal,
    SignalKind,
    Theme,
    UserChannel,
    UserIntelligence,
)

CHANNEL_ORDER = list(UserChannel)
_UNMET_INTENSITY = 0.5


class UserIntelligenceAgent:
    def analyze(self, signals: list[Signal], themes: list[Theme]) -> UserIntelligence:
        scoped = [signal for signal in signals if channel_for(signal) is not None]
        user_items = [signal for signal in scoped if signal.pillar is IntelPillar.user]
        feedback_count = sum(_volume(signal) for signal in user_items)
        if feedback_count == 0:
            return UserIntelligence()

        clusters: list[ProblemCluster] = []
        for cluster in _group(scoped, themes):
            user_signals = [signal for signal in cluster.signals if signal.pillar is IntelPillar.user]
            complaints = [signal for signal in user_signals if _is_complaint(signal)]
            volume = sum(_volume(signal) for signal in complaints)
            if volume < 2 and len(cluster.signals) < 2:
                continue
            if volume < 1:
                continue
            unmet = _unmet(complaints)
            problem = "" if cluster.emergent else cluster.problem
            clusters.append(
                ProblemCluster(
                    id=f"usr-{cluster.theme_id}",
                    theme=cluster.theme_id,
                    label=cluster.label,
                    share=volume / feedback_count,
                    volume=volume,
                    channels=_channels(complaints),
                    examples=_examples(complaints),
                    corroborated_by=_corroboration(cluster.signals),
                    unmet=unmet,
                    unmet_need=_unmet_need(cluster.label, problem, unmet),
                )
            )

        clusters.sort(key=lambda item: (-item.volume, item.label))
        named = sum(cluster.volume for cluster in clusters)
        return UserIntelligence(
            feedback_count=feedback_count,
            other_volume=max(feedback_count - named, 0),
            clusters=clusters,
            unmet_needs=[cluster for cluster in clusters if cluster.unmet],
        )


def _group(signals: list[Signal], themes: list[Theme]) -> list[Cluster]:
    """Group feedback by theme, including a theme that is one aggregated record.

    The opportunity engine ignores a lone signal. User intelligence keeps it
    when that record already carries a volume, such as 231 authentication complaints.
    """

    assigned: dict[str, list[Signal]] = defaultdict(list)
    unmatched: list[Signal] = []
    themes_by_id = {theme.id: theme for theme in themes}
    for signal in signals:
        theme = match_theme(signal, themes)
        if theme is None:
            unmatched.append(signal)
        else:
            assigned[theme.id].append(signal)

    grouped = []
    for theme_id, items in assigned.items():
        theme = themes_by_id[theme_id]
        grouped.append(
            Cluster(
                theme_id=theme.id,
                label=theme.label,
                problem=theme.problem,
                idea_title=theme.idea_title,
                idea_summary=theme.idea_summary,
                signals=sorted(items, key=lambda signal: (signal.observed_at, signal.id)),
            )
        )
    grouped.extend(cluster for cluster in build_clusters(unmatched, []) if cluster.emergent)
    return grouped


def channel_for(signal: Signal) -> UserChannel | None:
    """Which user-intelligence input an observation belongs to."""

    if signal.channel is not None:
        return signal.channel
    source = signal.source.lower()
    if signal.pillar is IntelPillar.product:
        if signal.kind in {SignalKind.analytics, SignalKind.usage, SignalKind.feature}:
            return UserChannel.product_analytics
        return None
    if signal.pillar is not IntelPillar.user:
        return None
    if "support" in source:
        return UserChannel.support_ticket
    if "interview" in source:
        return UserChannel.interview
    if "survey" in source:
        return UserChannel.survey
    if (
        signal.kind is SignalKind.forum
        or "reddit" in source
        or source.startswith("r/")
        or "community" in source
    ):
        return UserChannel.community
    if signal.kind is SignalKind.review or "app store" in source or source == "g2":
        return UserChannel.app_review
    if signal.resolved_polarity() is Polarity.demand or "feature request" in signal.text():
        return UserChannel.feature_request
    return UserChannel.user_feedback


def _is_complaint(signal: Signal) -> bool:
    return signal.resolved_polarity() in {Polarity.pain, Polarity.demand}


def _volume(signal: Signal) -> int:
    return signal.volume


def _unmet(complaints: list[Signal]) -> bool:
    if not complaints:
        return False
    total = sum(_volume(signal) for signal in complaints)
    if total < 1:
        return False
    intensity = sum(signal.strength * _volume(signal) for signal in complaints) / total
    return intensity >= _UNMET_INTENSITY


def _unmet_need(label: str, problem: str, unmet: bool) -> str:
    if not unmet:
        return ""
    if problem:
        return problem
    return f"{label} keeps showing up in feedback and is still unresolved."


def _channels(signals: list[Signal]) -> list[UserChannel]:
    found = {channel_for(signal) for signal in signals}
    found.discard(None)
    return [channel for channel in CHANNEL_ORDER if channel in found]


def _examples(signals: list[Signal]) -> list[str]:
    ordered = sorted(signals, key=lambda signal: (-signal.strength, signal.id))
    return [signal.title.strip().rstrip(".") for signal in ordered[:3]]


def _corroboration(signals: list[Signal]) -> list[str]:
    product = [
        signal
        for signal in signals
        if signal.pillar is IntelPillar.product and _is_complaint(signal)
    ]
    product.sort(key=lambda signal: (-signal.strength, signal.id))
    return [signal.title.strip().rstrip(".") for signal in product[:2]]
