"""Experiment learning memory.

A result is kept as a chain the next experiment can read:

opportunity, hypothesis, experiment, result, learning, decision.

When an earlier experiment drew clicks and then lost follow-through, the next
experiment tests the action instead of another informational variant.
"""

from discovery.models import (
    ExperimentLearning,
    ExperimentPlan,
    GraphEdge,
    GraphNode,
    NodeKind,
    Opportunity,
    OpportunityGraph,
)

NEW_EXPERIMENT = "Test actionable recommendations instead of informational recommendations."
_NO_RESULT = "No result is recorded."
_NO_OBSERVATION = "No observation is recorded."
_NO_LEARNING = "No learning is recorded yet."
_NO_CHANGE = "No product change follows until a learning is recorded."
_NEXT_OBSERVATION = "The next observation arrives after the product change."
_NEXT_HYPOTHESIS = "The next hypothesis waits for that observation."
_VALIDATE = "Validate opportunity"
_TAKES_BRIEF = "The product manager can take the brief."

_KINDS = (
    "hypothesis",
    "experiment",
    "observation",
    "learning",
    "decision",
    "product_change",
    "new_observation",
    "new_hypothesis",
)


def advise(record: ExperimentLearning) -> str:
    text = f"{record.opportunity} {record.experiment} {record.learning}".lower()
    clicked = "click" in text
    low_follow = "follow-through" in text and "low" in text
    if not (clicked and low_follow):
        return ""
    if "recommendation" in text:
        return NEW_EXPERIMENT
    noun = record.opportunity.strip() or "this capability"
    if noun[0].isupper() and not noun[:2].isupper():
        noun = f"{noun[0].lower()}{noun[1:]}"
    return f"Test actionable {noun} instead of informational {noun}."


def match_learning(
    opportunity: Opportunity,
    learnings: list[ExperimentLearning],
) -> ExperimentLearning | None:
    keys = {opportunity.id, opportunity.title, opportunity.theme}
    for record in learnings:
        if record.opportunity_id not in keys and record.opportunity not in keys:
            continue
        if advise(record):
            return record
    return None


def chain_for(plan: ExperimentPlan) -> ExperimentLearning:
    rows = dict(step_text(plan))
    result = rows["observation"]
    if result == _NO_OBSERVATION:
        result = _NO_RESULT
    return ExperimentLearning(
        opportunity_id=plan.opportunity_id,
        opportunity=plan.title,
        hypothesis=rows["hypothesis"],
        experiment=rows["experiment"],
        result=result,
        learning=rows["learning"],
        decision=rows["decision"],
    )


def step_text(plan: ExperimentPlan) -> list[tuple[str, str]]:
    hypothesis = plan.hypotheses[0].statement if plan.hypotheses else plan.title
    experiment = plan.specifications[0].name if plan.specifications else plan.selected
    analysis = plan.execution.analysis if plan.execution is not None else None
    observed = analysis.observed if analysis is not None else _NO_RESULT
    if observed == _NO_RESULT:
        observation = _NO_OBSERVATION
        learning = _NO_LEARNING
    else:
        observation = observed
        learning = analysis.interpretation if analysis is not None else _NO_LEARNING
    product_change = _TAKES_BRIEF if plan.decision == _VALIDATE else _NO_CHANGE
    new_hypothesis = plan.informed_experiment or _NEXT_HYPOTHESIS
    return [
        ("hypothesis", hypothesis),
        ("experiment", experiment),
        ("observation", observation),
        ("learning", learning),
        ("decision", plan.decision),
        ("product_change", product_change),
        ("new_observation", _NEXT_OBSERVATION),
        ("new_hypothesis", new_hypothesis),
    ]


def attach_learning(
    graph: OpportunityGraph,
    opportunity: Opportunity,
    plan: ExperimentPlan,
) -> OpportunityGraph:
    graph = graph.model_copy(deep=True)
    ids = [f"{kind}-{opportunity.id}" for kind in _KINDS]
    id_set = set(ids)
    graph.nodes = [node for node in graph.nodes if node.id not in id_set]
    graph.edges = [
        edge
        for edge in graph.edges
        if edge.origin not in id_set and edge.target not in id_set
    ]
    titles = dict(step_text(plan))
    for kind in _KINDS:
        graph.nodes.append(
            GraphNode(
                id=f"{kind}-{opportunity.id}",
                kind=NodeKind(kind),
                title=titles[kind],
            )
        )
    previous = opportunity.id
    for kind in _KINDS:
        current = f"{kind}-{opportunity.id}"
        graph.edges.append(
            GraphEdge(origin=previous, target=current, opportunity_id=opportunity.id)
        )
        previous = current
    return graph


def learning_ids(opportunity_id: str) -> list[str]:
    return [f"{kind}-{opportunity_id}" for kind in _KINDS]
