"""Opportunity intelligence engine.

Six capabilities, in order: ingest signals, cluster problems, detect the
opportunity, trace the evidence graph, validate it, and hand an approved
brief to a PRD. Each stage cites the artifact that capability already produced.
"""

from discovery.agents.loop import DevelopmentLoopAgent
from discovery.models import (
    IntelligenceStage,
    Opportunity,
    OpportunityIntelligence,
    OpportunityTrace,
    ProblemCluster,
    Signal,
)
from discovery.present import percent

CAPABILITIES = (
    "Signal ingestion",
    "Problem clustering",
    "Opportunity detection",
    "Evidence graph",
    "Opportunity validation",
    "Opportunity → PRD handoff",
)


def compose(
    signals: list[Signal],
    opportunity: Opportunity,
    cluster: ProblemCluster | None,
    trace: OpportunityTrace | None,
) -> OpportunityIntelligence:
    why = trace.why if trace is not None else ""
    stages = [
        _ingestion(signals, opportunity),
        _clustering(cluster, opportunity),
        _detection(opportunity),
        _graph(trace, opportunity),
        _validation(opportunity),
        _handoff(opportunity, why),
    ]
    return OpportunityIntelligence(
        opportunity_id=opportunity.id,
        title=opportunity.title,
        stages=stages,
    )


def _ingestion(signals: list[Signal], opportunity: Opportunity) -> IntelligenceStage:
    counts = {"market": 0, "user": 0, "product": 0}
    for signal in signals:
        counts[signal.pillar.value] = counts.get(signal.pillar.value, 0) + 1
    lines = [
        f"{len(signals)} signals ingested.",
        f"market {counts['market']}, user {counts['user']}, product {counts['product']}.",
        f"{len(opportunity.evidence)} are attached to {opportunity.title}.",
    ]
    lines.extend(item.title for item in opportunity.evidence)
    return IntelligenceStage(
        capability=CAPABILITIES[0],
        summary=f"{len(signals)} signals ingested.",
        lines=lines,
        href="/",
    )


def _clustering(cluster: ProblemCluster | None, opportunity: Opportunity) -> IntelligenceStage:
    if cluster is None:
        return IntelligenceStage(
            capability=CAPABILITIES[1],
            summary=opportunity.problem,
            href="/users",
        )
    summary = f"{cluster.label} is {percent(cluster.share)}% of the feedback."
    lines = [summary]
    if cluster.unmet_need:
        lines.append(cluster.unmet_need)
    lines.extend(cluster.examples)
    return IntelligenceStage(
        capability=CAPABILITIES[1],
        summary=summary,
        lines=lines,
        href="/users",
    )


def _detection(opportunity: Opportunity) -> IntelligenceStage:
    chain = opportunity.chain
    if chain is None:
        return IntelligenceStage(
            capability=CAPABILITIES[2],
            summary=opportunity.title,
            lines=[opportunity.problem],
            href="/detect",
        )
    lines = [
        f"Signal: {chain.signal}",
        f"Problem: {chain.problem}",
        f"User segment: {chain.segment}",
        f"Pain: {chain.pain}",
        f"Existing solutions: {chain.existing_solutions}",
        f"Gap: {chain.gap}",
        f"Opportunity: {chain.opportunity}",
    ]
    return IntelligenceStage(
        capability=CAPABILITIES[2],
        summary=chain.opportunity,
        lines=lines,
        href="/detect",
    )


def _graph(trace: OpportunityTrace | None, opportunity: Opportunity) -> IntelligenceStage:
    if trace is None or not trace.why:
        return IntelligenceStage(
            capability=CAPABILITIES[3],
            summary="The opportunity graph is not attached.",
            href=f"/graph?opportunity={opportunity.id}",
        )
    lines = [f"{source.title} — {source.source}" for source in trace.sources]
    return IntelligenceStage(
        capability=CAPABILITIES[3],
        summary=trace.why,
        lines=lines,
        href=f"/graph?opportunity={opportunity.id}",
    )


def _validation(opportunity: Opportunity) -> IntelligenceStage:
    challenge = opportunity.challenge
    if challenge is None:
        return IntelligenceStage(
            capability=CAPABILITIES[4],
            summary="No validation brief is attached.",
            href="/validate",
        )
    lines = [f"For: {point.text}" for point in challenge.supporting]
    if challenge.contradicting:
        lines.extend(f"Against: {point.text}" for point in challenge.contradicting)
    else:
        lines.append("Against: none")
    return IntelligenceStage(
        capability=CAPABILITIES[4],
        summary=challenge.challenge,
        lines=lines,
        href="/validate",
    )


def _handoff(opportunity: Opportunity, why: str) -> IntelligenceStage:
    loop = DevelopmentLoopAgent().write(opportunity, why)
    prd = next(stage for stage in loop.stages if stage.title == "PRD")
    return IntelligenceStage(
        capability=CAPABILITIES[5],
        summary=prd.summary,
        lines=prd.lines,
        href=f"/loop?opportunity={opportunity.id}",
    )
