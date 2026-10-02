"""Experiment value engine.

Priority is what the experiment can still teach, times how much that would
move the decision, divided by what the experiment costs.

    Expected information gain × Decision impact ÷ Experiment cost

High uncertainty produces high information gain. A high-impact decision that
a low-cost experiment can settle is the one to run next.
"""

from discovery.models import ExperimentPortfolio, ExperimentValue, Opportunity, PortfolioRow, Verdict

FORMULA = "Expected information gain × Decision impact ÷ Experiment cost"
_LEVEL = {"Low": 1, "Medium": 2, "High": 3}
_HIGH_IMPACT = 0.75


def attach_value(portfolio: ExperimentPortfolio, opportunities: list[Opportunity]) -> ExperimentPortfolio:
    by_id = {row.opportunity_id: row for row in portfolio.rows}
    specs = []
    for opportunity in opportunities:
        row = by_id.get(opportunity.id)
        if row is None:
            continue
        specs.append(_spec(opportunity, row))
    values, chain = rank(specs)
    portfolio.formula = FORMULA
    portfolio.values = values
    portfolio.chain = chain
    return portfolio


def rank(specs: list[dict]) -> tuple[list[ExperimentValue], list[str]]:
    scored = [_value(item) for item in specs]
    scored.sort(key=lambda item: item[0], reverse=True)
    values = [item[1] for item in scored]
    if not values:
        return [], []
    winner = values[0]
    steps = _chain(winner)
    if steps[-1] == "PRIORITIZE":
        values[0] = winner.model_copy(update={"prioritize": True})
    return values, steps


def _spec(opportunity: Opportunity, row: PortfolioRow) -> dict:
    return {
        "name": row.name,
        "opportunity_id": row.opportunity_id,
        "uncertainty": "Low" if row.status == "Complete" else "High",
        "information": row.information or "Low",
        "impact": _impact(opportunity),
        "cost": row.cost or "Low",
        "weight": opportunity.scores.opportunity,
    }


def _value(spec: dict) -> tuple[tuple, ExperimentValue]:
    gain = _gain(spec["uncertainty"], spec["information"])
    impact = spec["impact"]
    cost = spec["cost"] if spec["cost"] in _LEVEL else "Low"
    priority = _LEVEL[gain] * _LEVEL[impact] / _LEVEL[cost]
    value = ExperimentValue(
        name=spec["name"],
        opportunity_id=spec.get("opportunity_id", ""),
        uncertainty=spec["uncertainty"],
        information_gain=gain,
        decision_impact=impact,
        cost=cost,
        priority=_format(priority),
    )
    return ((priority, _LEVEL[impact], -_LEVEL[cost], spec.get("weight", 0), _name_key(spec["name"])), value)


def _gain(uncertainty: str, information: str) -> str:
    if uncertainty == "Low":
        return "Low"
    if uncertainty == "High" and information in {"High", "Medium"}:
        return "High"
    if uncertainty == "High":
        return "Medium"
    if information == "High":
        return "High"
    return "Medium"


def _impact(opportunity: Opportunity) -> str:
    if opportunity.verdict is Verdict.park:
        return "Low"
    if opportunity.verdict is Verdict.investigate:
        return "Medium"
    if opportunity.scores.opportunity >= _HIGH_IMPACT:
        return "High"
    return "Medium"


def _chain(value: ExperimentValue) -> list[str]:
    cost = {
        "Low": "Low-cost experiment",
        "Medium": "Medium-cost experiment",
        "High": "High-cost experiment",
    }[value.cost]
    steps = [
        f"{value.uncertainty} uncertainty",
        f"{value.information_gain} information gain",
        f"{value.decision_impact} decision impact",
        cost,
    ]
    if (
        value.uncertainty == "High"
        and value.information_gain == "High"
        and value.decision_impact == "High"
        and value.cost == "Low"
    ):
        steps.append("PRIORITIZE")
    else:
        steps.append("Ranked first")
    return steps


def _format(priority: float) -> str:
    if priority == int(priority):
        return str(int(priority))
    return f"{priority:.1f}"


def _name_key(name: str) -> str:
    # rank() sorts with reverse=True. Invert the name so alphabetical order stays A to Z.
    return "".join(chr(0x10FFFF - ord(char)) for char in name)
