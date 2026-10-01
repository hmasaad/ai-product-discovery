"""Experiment portfolio.

The agent tracks every experiment together. Status is Planned until a start
is approved, Running once it is, and Complete once a result is stored.
Risk follows the cost of the selected experiment. The six notes are judgments
about the set, not a score for one row.
"""

from discovery.agents.experiment import design
from discovery.models import (
    ExperimentLearning,
    ExperimentPortfolio,
    MemoryRecord,
    Opportunity,
    PortfolioNote,
    PortfolioRow,
)

RUNNING = "Running"
PLANNED = "Planned"
COMPLETE = "Complete"
TOPICS = (
    "Experiment conflicts",
    "User overlap",
    "Resource consumption",
    "Statistical contamination",
    "Priority",
    "Expected information gain",
)
_RISK_RANK = {"Low": 0, "Medium": 1, "High": 2}
_INFO_RANK = {"Low": 0, "Medium": 1, "High": 2}
_COST_RISK = {"Very High": "High", "Medium": "Medium", "Low": "Low", "Very Low": "Low"}
_COUNT = {1: "One", 2: "Two", 3: "Three", 4: "Four", 5: "Five", 6: "Six"}


def build_portfolio(
    opportunities: list[Opportunity],
    records: list[MemoryRecord] | None = None,
    learnings: list[ExperimentLearning] | None = None,
    approvals: dict[str, str] | None = None,
) -> ExperimentPortfolio:
    stored = list(records or [])
    remembered = list(learnings or [])
    approved = approvals or {}
    rows = [
        _row(opportunity, stored, remembered, opportunity.id in approved)
        for opportunity in opportunities
    ]
    return assess(rows)


def assess(rows: list[PortfolioRow]) -> ExperimentPortfolio:
    summaries = (
        _conflicts(rows),
        _overlap(rows),
        _resources(rows),
        _contamination(rows),
        _priority(rows),
        _information(rows),
    )
    return ExperimentPortfolio(
        rows=list(rows),
        notes=[PortfolioNote(topic=topic, summary=summary) for topic, summary in zip(TOPICS, summaries, strict=True)],
    )


def _row(
    opportunity: Opportunity,
    records: list[MemoryRecord],
    learnings: list[ExperimentLearning],
    approved: bool,
) -> PortfolioRow:
    plan = design(opportunity, records, learnings)
    audience = plan.specifications[0].target_audience if plan.specifications else ""
    selected = [choice for choice in plan.choices if choice.selected]
    risk = "Low"
    information = "Low"
    for choice in selected:
        candidate = _COST_RISK.get(choice.cost, "Low")
        if _RISK_RANK[candidate] > _RISK_RANK[risk]:
            risk = candidate
        if _INFO_RANK.get(choice.information, 0) > _INFO_RANK.get(information, 0):
            information = choice.information
    return PortfolioRow(
        name=opportunity.title,
        status=_status(opportunity, learnings, approved),
        risk=risk,
        opportunity_id=opportunity.id,
        audience=audience,
        surface=opportunity.theme,
        information=information,
    )


def _status(
    opportunity: Opportunity,
    learnings: list[ExperimentLearning],
    approved: bool,
) -> str:
    keys = {opportunity.id, opportunity.title, opportunity.theme}
    for record in learnings:
        if record.opportunity_id in keys or record.opportunity in keys:
            if record.result != "No result is recorded.":
                return COMPLETE
    if approved:
        return RUNNING
    return PLANNED


def _conflicts(rows: list[PortfolioRow]) -> str:
    running = [row for row in rows if row.status == RUNNING]
    active = [row for row in rows if row.status != COMPLETE]
    sentences = []
    if not running:
        sentences.append("No experiment is running.")
    elif len(running) == 1:
        sentences.append(f"One experiment is running: {running[0].name}.")
    elif len(running) == 2:
        sentences.append(f"{running[0].name} and {running[1].name} are both running.")
    else:
        sentences.append(f"{_and([row.name for row in running])} are running at the same time.")
    shared = []
    for surface, group in _grouped(active, lambda row: row.surface).items():
        if surface and len(group) > 1:
            shared.append(f"{_and([row.name for row in group])} share the {surface} surface.")
    if shared:
        sentences.extend(shared)
    elif len(running) == 1:
        sentences.append("No other experiment uses that surface.")
    elif len(running) > 1 and len({row.surface for row in running}) == len(running):
        sentences.append("The running experiments use different surfaces.")
    return " ".join(sentences)


def _overlap(rows: list[PortfolioRow]) -> str:
    active = [row for row in rows if row.status != COMPLETE and row.audience]
    if not active:
        return "No open experiment has an audience."
    clusters = _clusters(active)
    if len(clusters) == 1:
        audience = _shared_audience(clusters[0]).rstrip(".")
        count = _COUNT.get(len(clusters[0]), str(len(clusters[0])))
        noun = "experiment" if len(clusters[0]) == 1 else "experiments"
        return f"All {count.lower()} open {noun} reach {audience}."
    sentences = []
    for cluster in clusters:
        names = _and([row.name for row in cluster])
        audience = _shared_audience(cluster).rstrip(".")
        if len(cluster) == 1:
            sentences.append(f"{names} is the only experiment on {audience}.")
        else:
            sentences.append(f"{names} share one audience: {audience}.")
    return " ".join(sentences)


def _resources(rows: list[PortfolioRow]) -> str:
    running = [row for row in rows if row.status == RUNNING]
    planned = [row for row in rows if row.status == PLANNED]
    high = [row for row in planned if row.risk == "High"]
    sentences = []
    if not running:
        sentences.append("No experiment is consuming a running slot.")
    elif len(running) == 1:
        sentences.append(f"One experiment is running: {running[0].name} ({running[0].risk.lower()} risk).")
    else:
        bits = [f"{row.name} ({row.risk.lower()} risk)" for row in running]
        sentences.append(f"{_and(bits)} are running.")
    if high:
        names = _and([row.name for row in high])
        verb = "is" if len(high) == 1 else "are"
        wait = "it waits" if len(high) == 1 else "they wait"
        sentences.append(f"{names} {verb} high risk and planned, so {wait} for a free slot.")
    elif planned:
        count = _COUNT.get(len(planned), str(len(planned)))
        if len(planned) == 1:
            sentences.append(f"{count} experiment is planned. It waits for a free slot.")
        else:
            sentences.append(f"{count} experiments are planned. They wait for a free slot.")
    return " ".join(sentences)


def _contamination(rows: list[PortfolioRow]) -> str:
    running = [row for row in rows if row.status == RUNNING]
    planned = [row for row in rows if row.status == PLANNED]
    if not running:
        return "No experiment is running, so there is no result to contaminate."
    sentences = []
    if len(running) == 1:
        sentences.append(f"{running[0].name} is the only running experiment.")
    elif _same_audience(running):
        sentences.append(
            f"{_and([row.name for row in running])} are both running on the same audience, "
            "so their metrics can move for reasons that belong to the other experiment."
            if len(running) == 2
            else f"{_and([row.name for row in running])} are running on the same audience, "
            "so their metrics can move for reasons that belong to another experiment."
        )
    else:
        joined = _and([row.name for row in running])
        verb = "are both running" if len(running) == 2 else "are running"
        sentences.append(
            f"{joined} {verb} on different audiences, so one result does not explain the other."
        )
    overlapping = [
        row
        for row in planned
        if any(_audiences_overlap(row.audience, live.audience) for live in running)
    ]
    if overlapping:
        live_names = []
        for row in overlapping:
            for live in running:
                if _audiences_overlap(row.audience, live.audience) and live.name not in live_names:
                    live_names.append(live.name)
        live = _and(live_names)
        verb = "is" if len(live_names) == 1 else "are"
        if len(overlapping) == len(planned) and len(planned) > 1:
            count = _COUNT.get(len(planned), str(len(planned))).lower()
            started = f"the {count} planned experiments"
        else:
            started = _and([row.name for row in overlapping])
        sentences.append(
            f"Starting {started} while {live} {verb} running would contaminate the shared audience."
        )
    return " ".join(sentences)


def _priority(rows: list[PortfolioRow]) -> str:
    running = sorted((row for row in rows if row.status == RUNNING), key=lambda row: _RISK_RANK[row.risk])
    planned = [row for row in rows if row.status == PLANNED]
    complete = [row for row in rows if row.status == COMPLETE]
    held = [row for row in planned if row.risk == "High"]
    sentences = []
    if len(running) == 1:
        sentences.append(f"Priority is {running[0].name}.")
    elif len(running) > 1:
        ordered = ", then ".join(row.name for row in running)
        sentences.append(f"Priority is {ordered}.")
    if held:
        names = _and([row.name for row in held])
        sentences.append(f"Hold {names}.")
    elif planned:
        count = _COUNT.get(len(planned), str(len(planned))).lower()
        noun = "experiment waits" if len(planned) == 1 else "experiments wait"
        sentences.append(f"The {count} planned {noun}.")
    if len(complete) == 1:
        sentences.append(f"{complete[0].name} is complete.")
    elif complete:
        sentences.append(f"{_and([row.name for row in complete])} are complete.")
    else:
        sentences.append("None are complete.")
    return " ".join(sentences)


def _information(rows: list[PortfolioRow]) -> str:
    complete = [row for row in rows if row.status == COMPLETE]
    running = [row for row in rows if row.status == RUNNING]
    planned = [row for row in rows if row.status == PLANNED]
    high = [row for row in planned if row.information == "High"]
    sentences = []
    if len(complete) == 1:
        sentences.append(f"{complete[0].name} has already delivered its learning.")
    elif complete:
        sentences.append(f"{_and([row.name for row in complete])} have already delivered their learning.")
    if len(running) == 1:
        sentences.append(f"{running[0].name} is still producing information.")
    elif running:
        sentences.append(f"{_and([row.name for row in running])} are still producing information.")
    if len(high) == 1:
        sentences.append(
            f"{high[0].name} has the highest expected information gain and stays planned "
            f"because its risk is {high[0].risk.lower()}."
        )
    elif high:
        sentences.append(
            f"{_and([row.name for row in high])} have the highest expected information gain and stay planned."
        )
    elif planned:
        sentences.append("The planned experiments have not started, so their information gain is still ahead.")
    return " ".join(sentences)


def _clusters(rows: list[PortfolioRow]) -> list[list[PortfolioRow]]:
    parent = list(range(len(rows)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    for left in range(len(rows)):
        for right in range(left + 1, len(rows)):
            if _audiences_overlap(rows[left].audience, rows[right].audience):
                parent[find(left)] = find(right)
    grouped: dict[int, list[PortfolioRow]] = {}
    for index, row in enumerate(rows):
        grouped.setdefault(find(index), []).append(row)
    return list(grouped.values())


def _audiences_overlap(left: str, right: str) -> bool:
    if not left or not right:
        return False
    return left in right or right in left


def _same_audience(rows: list[PortfolioRow]) -> bool:
    return len(_clusters(rows)) == 1


def _shared_audience(rows: list[PortfolioRow]) -> str:
    audiences = [row.audience for row in rows if row.audience]
    contained = [
        audience
        for audience in audiences
        if all(audience in other or other in audience for other in audiences)
    ]
    if contained:
        return min(contained, key=len)
    return audiences[0]


def _grouped(rows: list[PortfolioRow], key) -> dict[str, list[PortfolioRow]]:
    grouped: dict[str, list[PortfolioRow]] = {}
    for row in rows:
        grouped.setdefault(key(row), []).append(row)
    return grouped


def _and(names: list[str]) -> str:
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f"{names[0]} and {names[1]}"
    return f"{', '.join(names[:-1])}, and {names[-1]}"
