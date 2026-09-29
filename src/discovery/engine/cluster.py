"""Cluster signals into problems.

Known workspace themes win when their keywords match. Everything left over is
grouped by shared language so unfamiliar evidence still surfaces.
"""

import re
from collections import defaultdict
from dataclasses import dataclass, field

from discovery.models import Signal, Theme

MIN_CLUSTER = 2

STOPWORDS = {
    "about",
    "after",
    "again",
    "against",
    "almost",
    "already",
    "always",
    "among",
    "another",
    "around",
    "because",
    "before",
    "being",
    "between",
    "build",
    "built",
    "could",
    "customer",
    "customers",
    "every",
    "evidence",
    "existing",
    "feature",
    "first",
    "found",
    "from",
    "have",
    "having",
    "into",
    "just",
    "more",
    "most",
    "much",
    "need",
    "needs",
    "only",
    "other",
    "people",
    "product",
    "really",
    "should",
    "still",
    "team",
    "teams",
    "their",
    "there",
    "these",
    "thing",
    "those",
    "through",
    "today",
    "using",
    "want",
    "where",
    "which",
    "while",
    "with",
    "without",
    "would",
    "workspace",
    "workspaces",
}


@dataclass
class Cluster:
    theme_id: str
    label: str
    problem: str
    idea_title: str
    idea_summary: str
    risks: list[str] = field(default_factory=list)
    experiments: list[str] = field(default_factory=list)
    signals: list[Signal] = field(default_factory=list)
    emergent: bool = False


def build_clusters(signals: list[Signal], themes: list[Theme]) -> list[Cluster]:
    assigned: dict[str, list[Signal]] = defaultdict(list)
    unmatched: list[Signal] = []
    themes_by_id = {theme.id: theme for theme in themes}

    for signal in signals:
        theme = match_theme(signal, themes)
        if theme is None:
            unmatched.append(signal)
        else:
            assigned[theme.id].append(signal)

    clusters: list[Cluster] = []
    for theme_id, grouped in assigned.items():
        if len(grouped) < MIN_CLUSTER:
            continue
        theme = themes_by_id[theme_id]
        clusters.append(
            Cluster(
                theme_id=theme.id,
                label=theme.label,
                problem=theme.problem,
                idea_title=theme.idea_title,
                idea_summary=theme.idea_summary,
                risks=list(theme.risks),
                experiments=list(theme.experiments),
                signals=_stable(grouped),
            )
        )

    clusters.extend(_emergent_clusters(unmatched))
    clusters.sort(key=lambda cluster: cluster.theme_id)
    return clusters


def match_theme(signal: Signal, themes: list[Theme]) -> Theme | None:
    text = signal.text()
    best: Theme | None = None
    best_score = 0
    for theme in themes:
        score = sum(1 for keyword in theme.keywords if keyword.lower() in text)
        if score > best_score:
            best = theme
            best_score = score
    return best


def _stable(signals: list[Signal]) -> list[Signal]:
    return sorted(signals, key=lambda signal: (signal.observed_at, signal.id))


def _tokens(signal: Signal) -> set[str]:
    words = re.findall(r"[a-z][a-z0-9-]{4,}", signal.text())
    return {word for word in words if word not in STOPWORDS}


def _emergent_clusters(signals: list[Signal]) -> list[Cluster]:
    if len(signals) < MIN_CLUSTER:
        return []

    docs = [(signal, _tokens(signal)) for signal in signals]
    parent = {signal.id: signal.id for signal, _ in docs}

    def find(node: str) -> str:
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    def union(left: str, right: str) -> None:
        root_left, root_right = find(left), find(right)
        if root_left != root_right:
            parent[root_right] = root_left

    for index, (left, left_tokens) in enumerate(docs):
        for right, right_tokens in docs[index + 1 :]:
            if len(left_tokens & right_tokens) >= 2:
                union(left.id, right.id)

    groups: dict[str, list[tuple[Signal, set[str]]]] = defaultdict(list)
    for signal, tokens in docs:
        groups[find(signal.id)].append((signal, tokens))

    clusters: list[Cluster] = []
    for items in groups.values():
        if len(items) < MIN_CLUSTER:
            continue
        label_tokens = _label_tokens(items)
        if not label_tokens:
            continue
        label = " ".join(label_tokens)
        theme_id = "emergent-" + "-".join(label_tokens)
        clusters.append(
            Cluster(
                theme_id=theme_id,
                label=label,
                problem=(
                    f"Independent signals keep returning to {label}, "
                    "and no workspace theme claims them yet."
                ),
                idea_title=f"Investigate {label}",
                idea_summary=(
                    f"Run a short discovery spike on {label} before promoting it "
                    "from a cluster of evidence to a roadmap bet."
                ),
                signals=_stable([signal for signal, _ in items]),
                emergent=True,
            )
        )
    return clusters


def _label_tokens(items: list[tuple[Signal, set[str]]]) -> list[str]:
    counts: dict[str, int] = defaultdict(int)
    for _, tokens in items:
        for token in tokens:
            counts[token] += 1
    shared = [token for token, count in counts.items() if count >= 2]
    shared.sort(key=lambda token: (-counts[token], token))
    return shared[:3]
