"""Opportunity graph.

Ideas are not a flat list. Each opportunity sits on a path:

market → trend → users and competitors → problems and gaps → opportunity
→ feature and product → MVP and business case.

The trace answers why the opportunity exists and cites the signals on that path.
"""

from discovery.models import (
    CompetitorIntelligence,
    Evidence,
    GraphEdge,
    GraphNode,
    GraphSource,
    MarketSignal,
    NodeKind,
    Opportunity,
    OpportunityGraph,
    OpportunityTrace,
    ProductContext,
    SignalKind,
    UserIntelligence,
)
from discovery.present import GAP_LABELS, VERDICT_LABELS, percent


def build_opportunity_graph(
    context: ProductContext,
    opportunities: list[Opportunity],
    market_signals: list[MarketSignal] | None = None,
    user_intelligence: UserIntelligence | None = None,
    competitor_intelligence: CompetitorIntelligence | None = None,
    learnings: list | None = None,
) -> OpportunityGraph:
    nodes: dict[str, GraphNode] = {
        "market": GraphNode(
            id="market",
            kind=NodeKind.market,
            title=context.category,
            detail=context.mission,
        ),
        "product": GraphNode(
            id="product",
            kind=NodeKind.product,
            title=context.name,
            detail=f"{context.category} for {context.audience}",
        ),
    }
    edges: list[GraphEdge] = []
    trends = {signal.theme: signal for signal in market_signals or []}
    clusters = {
        cluster.theme: cluster
        for cluster in (user_intelligence.clusters if user_intelligence else [])
    }
    for opportunity in opportunities:
        _branch(
            opportunity,
            nodes,
            edges,
            trends.get(opportunity.theme),
            clusters.get(opportunity.theme),
            competitor_intelligence,
        )
    graph = OpportunityGraph(nodes=list(nodes.values()), edges=edges)
    from discovery.agents.experiment import design
    from discovery.agents.learning import attach_learning

    for opportunity in opportunities:
        plan = design(opportunity, learnings=learnings)
        graph = attach_learning(graph, opportunity, plan)
    return graph


def trace(graph: OpportunityGraph, opportunity_id: str) -> OpportunityTrace | None:
    opportunity = graph.node(opportunity_id)
    if opportunity is None or opportunity.kind is not NodeKind.opportunity:
        return None
    by_kind = {
        kind: None
        for kind in NodeKind
    }
    relevant = _relevant_nodes(graph, opportunity_id)
    for node in relevant:
        by_kind[node.kind] = node
    paths = _paths(graph, "market", opportunity_id, opportunity_id)
    sources = _sources(relevant)
    return OpportunityTrace(
        opportunity_id=opportunity_id,
        title=opportunity.title,
        why=_why(by_kind),
        market=by_kind[NodeKind.market],
        trend=by_kind[NodeKind.trend],
        users=by_kind[NodeKind.users],
        competitors=by_kind[NodeKind.competitors],
        problem=by_kind[NodeKind.problem],
        gap=by_kind[NodeKind.gap],
        opportunity=opportunity,
        feature=by_kind[NodeKind.feature],
        product=by_kind[NodeKind.product],
        mvp=by_kind[NodeKind.mvp],
        business_case=by_kind[NodeKind.business_case],
        paths=paths,
        sources=sources,
        hypothesis=by_kind[NodeKind.hypothesis],
        experiment=by_kind[NodeKind.experiment],
        observation=by_kind[NodeKind.observation],
        learning=by_kind[NodeKind.learning],
        decision=by_kind[NodeKind.decision],
        product_change=by_kind[NodeKind.product_change],
        new_observation=by_kind[NodeKind.new_observation],
        new_hypothesis=by_kind[NodeKind.new_hypothesis],
        learning_path=_learning_path(graph, opportunity_id),
    )


def _branch(
    opportunity: Opportunity,
    nodes: dict[str, GraphNode],
    edges: list[GraphEdge],
    market: MarketSignal | None,
    cluster,
    competitors: CompetitorIntelligence | None,
) -> None:
    theme = opportunity.theme
    chain = opportunity.chain
    opportunity_id = opportunity.id

    trend_id = f"trend-{theme}"
    if market is not None:
        nodes[trend_id] = GraphNode(
            id=trend_id,
            kind=NodeKind.trend,
            title=market.trend,
            detail=market.implication,
            sources=[_market_source(item, trend_id) for item in market.evidence],
        )
        _link(edges, "market", trend_id, opportunity_id)
        parent = trend_id
    else:
        parent = "market"

    users_id = f"users-{theme}"
    segment = chain.segment if chain else "Users"
    unmet = ""
    if cluster is not None and cluster.unmet_need:
        unmet = cluster.unmet_need
    elif chain is not None:
        unmet = chain.pain
    share = ""
    if cluster is not None and cluster.share:
        share = f"{percent(cluster.share)}% of the feedback. "
    nodes[users_id] = GraphNode(
        id=users_id,
        kind=NodeKind.users,
        title=segment,
        detail=f"{share}{unmet}".strip(),
        sources=_evidence_sources(
            opportunity.evidence,
            users_id,
            lambda item: item.pillar.value == "user",
        ),
    )
    _link(edges, parent, users_id, opportunity_id)

    problem_id = f"problem-{theme}"
    nodes[problem_id] = GraphNode(
        id=problem_id,
        kind=NodeKind.problem,
        title=opportunity.label,
        detail=opportunity.problem,
        sources=_evidence_sources(
            opportunity.evidence,
            problem_id,
            lambda item: item.pillar.value == "product",
        ),
    )
    _link(edges, users_id, problem_id, opportunity_id)

    competitor_gap = _competitor_gap(opportunity, competitors)
    competitor_sources = _evidence_sources(
        opportunity.evidence,
        f"competitors-{theme}",
        lambda item: item.kind is SignalKind.competitor,
    )
    competitors_id = ""
    if competitor_gap or competitor_sources:
        competitors_id = f"competitors-{theme}"
        nodes[competitors_id] = GraphNode(
            id=competitors_id,
            kind=NodeKind.competitors,
            title="Competitors",
            detail=competitor_gap or "Competitor evidence is attached.",
            sources=competitor_sources,
        )
        _link(edges, parent, competitors_id, opportunity_id)

    gap_id = f"gap-{theme}"
    gap_detail = chain.gap if chain else opportunity.mapping_note
    gap_sources: list[GraphSource] = []
    if competitor_gap:
        gap_sources.append(
            GraphSource(
                title=competitor_gap,
                source="Competitor intelligence",
                node_id=gap_id,
            )
        )
    nodes[gap_id] = GraphNode(
        id=gap_id,
        kind=NodeKind.gap,
        title=GAP_LABELS[opportunity.gap.value],
        detail=gap_detail,
        sources=gap_sources,
    )
    _link(edges, competitors_id or parent, gap_id, opportunity_id)

    nodes[opportunity_id] = GraphNode(
        id=opportunity_id,
        kind=NodeKind.opportunity,
        title=opportunity.title,
        detail=opportunity.rationale,
    )
    _link(edges, problem_id, opportunity_id, opportunity_id)
    _link(edges, gap_id, opportunity_id, opportunity_id)

    feature_id = f"feature-{theme}"
    feature = _first_sentence(opportunity.idea_summary)
    nodes[feature_id] = GraphNode(
        id=feature_id,
        kind=NodeKind.feature,
        title=feature or opportunity.title,
        detail=opportunity.idea_summary if opportunity.idea_summary != feature else "",
    )
    _link(edges, opportunity_id, feature_id, opportunity_id)
    if opportunity.next_steps:
        mvp_id = f"mvp-{theme}"
        nodes[mvp_id] = GraphNode(
            id=mvp_id,
            kind=NodeKind.mvp,
            title="MVP",
            detail=opportunity.next_steps[0],
        )
        _link(edges, feature_id, mvp_id, opportunity_id)

    _link(edges, opportunity_id, "product", opportunity_id)
    case_id = f"case-{theme}"
    nodes[case_id] = GraphNode(
        id=case_id,
        kind=NodeKind.business_case,
        title=VERDICT_LABELS[opportunity.verdict.value],
        detail=(
            f"Opportunity score {percent(opportunity.scores.opportunity)}. "
            f"{opportunity.why_now}"
        ),
    )
    _link(edges, "product", case_id, opportunity_id)


def _learning_path(graph: OpportunityGraph, opportunity_id: str) -> list[str]:
    from discovery.agents.learning import learning_ids

    return [node_id for node_id in learning_ids(opportunity_id) if graph.node(node_id)]


def trace_kinds(graph: OpportunityGraph, path: list[str]) -> list[str]:
    return [node.kind.value for node_id in path if (node := graph.node(node_id))]


def _link(edges: list[GraphEdge], origin: str, target: str, opportunity_id: str) -> None:
    edges.append(GraphEdge(origin=origin, target=target, opportunity_id=opportunity_id))


def _competitor_gap(
    opportunity: Opportunity,
    competitors: CompetitorIntelligence | None,
) -> str:
    if competitors is not None:
        for gap in competitors.gaps:
            if opportunity.theme in gap.themes:
                return gap.statement
    if opportunity.competitor is not None:
        return opportunity.competitor.gap
    return ""


def _market_source(item, node_id: str) -> GraphSource:
    return GraphSource(
        signal_id=item.signal_id,
        title=item.statement,
        source=item.source,
        observed_at=item.observed_at.isoformat(),
        node_id=node_id,
    )


def _evidence_sources(evidence: list[Evidence], node_id: str, include) -> list[GraphSource]:
    sources: list[GraphSource] = []
    for item in evidence:
        if not include(item):
            continue
        sources.append(
            GraphSource(
                signal_id=item.signal_id,
                title=item.title,
                source=item.source,
                observed_at=item.observed_at.isoformat(),
                node_id=node_id,
            )
        )
    return sources


def _relevant_nodes(graph: OpportunityGraph, opportunity_id: str) -> list[GraphNode]:
    seen = {opportunity_id}
    stack = [opportunity_id]
    while stack:
        current = stack.pop()
        linked = [
            edge.origin
            for edge in graph.edges
            if edge.target == current and edge.opportunity_id == opportunity_id
        ]
        linked.extend(
            edge.target
            for edge in graph.edges
            if edge.origin == current and edge.opportunity_id == opportunity_id
        )
        for node_id in linked:
            if node_id not in seen:
                seen.add(node_id)
                stack.append(node_id)
    return [node for node in graph.nodes if node.id in seen]


def _paths(
    graph: OpportunityGraph,
    origin: str,
    dest: str,
    opportunity_id: str,
) -> list[list[str]]:
    paths: list[list[str]] = []

    def walk(node_id: str, trail: list[str]) -> None:
        if node_id in trail:
            return
        trail = [*trail, node_id]
        if node_id == dest:
            paths.append(trail)
            return
        children = [
            edge.target
            for edge in graph.edges
            if edge.origin == node_id and edge.opportunity_id == opportunity_id
        ]
        for child in children:
            walk(child, trail)

    walk(origin, [])
    return paths


def _sources(nodes: list[GraphNode]) -> list[GraphSource]:
    """One line per signal. A later citation replaces an earlier paraphrase of it."""

    found: dict[str, GraphSource] = {}
    order: list[str] = []
    for node in nodes:
        for source in node.sources:
            key = source.signal_id or source.title
            if key not in found:
                order.append(key)
            found[key] = source
    return [found[key] for key in order]


def _first_sentence(text: str) -> str:
    cleaned = " ".join(text.split())
    for mark in ".!?":
        index = cleaned.find(mark)
        if index != -1:
            return cleaned[: index + 1]
    return cleaned


def _why(nodes: dict[NodeKind, GraphNode | None]) -> str:
    opportunity = nodes[NodeKind.opportunity]
    if opportunity is None:
        return ""
    users = nodes[NodeKind.users]
    problem = nodes[NodeKind.problem]
    trend = nodes[NodeKind.trend]
    gap = nodes[NodeKind.gap]
    segment = users.title if users else "The audience"
    problem_text = problem.detail if problem and problem.detail else opportunity.title
    if problem_text[-1:] not in ".!?":
        problem_text += "."
    bits = [f"{opportunity.title} exists because {segment} run into this problem: {problem_text}"]
    if trend is not None:
        bits.append(f"The market trend is {trend.title}.")
    if gap is not None and gap.detail:
        detail = gap.detail if gap.detail[-1:] in ".!?" else f"{gap.detail}."
        bits.append(f"The gap: {detail}")
    return " ".join(bits)
