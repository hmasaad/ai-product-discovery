"""Closed product loop.

An approved opportunity leaves discovery as a brief the product manager can
accept. The PRD, the architect, the developer, QA, and review stay inside that
brief. Production is the experiment. Product analytics then re-enters discovery
as the measurement that experiment named.

A parked opportunity stays in discovery. A brief that is not approved stops
before the PRD. Contradicting evidence holds the review, so production waits.
"""

from discovery.models import (
    DevelopmentLoop,
    LoopArtifact,
    LoopStage,
    LoopStatus,
    Opportunity,
    ReturnSignal,
    ReviewStatus,
    Verdict,
)

_PARKED = "Parked opportunities stay in discovery."
_APPROVAL = "The PRD waits for approval."
_NO_BRIEF = "No product opportunity brief."
_HOLD = "Contradicting evidence is still open."


class DevelopmentLoopAgent:
    def write(self, opportunity: Opportunity, why: str = "") -> DevelopmentLoop:
        brief = opportunity.product_brief
        blocked = _block(opportunity)
        held = _held(opportunity, blocked)
        advance = blocked is None and held is None
        pm_brief = _pm_brief(opportunity, why) if brief is not None and opportunity.verdict is not Verdict.park else ""
        signals = _return_signals(opportunity) if advance else []
        stages = [
            _discovery(opportunity),
            _graph(why, brief is not None),
            _manager(opportunity, pm_brief, blocked),
            _prd(opportunity, blocked),
            _architect(opportunity, blocked, None),
            _developer(opportunity, blocked, None),
            _qa(opportunity, blocked, None),
            _review(opportunity, blocked),
            _production(opportunity, blocked, held),
            _analytics(opportunity, signals, blocked, held),
            _returned(signals, blocked, held),
        ]
        return DevelopmentLoop(
            opportunity_id=opportunity.id,
            title=opportunity.title,
            stages=stages,
            pm_brief=pm_brief,
            return_signals=signals,
        )


def _block(opportunity: Opportunity) -> str | None:
    if opportunity.product_brief is None:
        return _NO_BRIEF
    if opportunity.verdict is Verdict.park:
        return _PARKED
    if opportunity.status is not ReviewStatus.approved:
        return _APPROVAL
    return None


def _held(opportunity: Opportunity, blocked: str | None) -> str | None:
    if blocked is not None:
        return None
    challenge = opportunity.challenge
    if challenge is not None and challenge.contradicting:
        return f"{_HOLD} {challenge.contradicting[0].text}."
    return None


def _discovery(opportunity: Opportunity) -> LoopArtifact:
    brief = opportunity.product_brief
    if brief is None:
        return _artifact(
            LoopStage.discovery,
            "AI Product Discovery Agent",
            LoopStatus.waiting,
            _NO_BRIEF,
        )
    return _artifact(
        LoopStage.discovery,
        "AI Product Discovery Agent",
        LoopStatus.ready,
        brief.problem,
        [
            f"Target users: {brief.target_users}",
            f"Observed pain: {brief.observed_pain}",
            *brief.evidence,
            f"Recommended experiment: {brief.experiment}",
        ],
    )


def _graph(why: str, ready: bool) -> LoopArtifact:
    cleaned = " ".join(why.split())
    if not ready or not cleaned:
        return _artifact(
            LoopStage.graph,
            "Opportunity Graph",
            LoopStatus.waiting,
            "The opportunity graph is not attached.",
        )
    return _artifact(LoopStage.graph, "Opportunity Graph", LoopStatus.ready, cleaned)


def _manager(opportunity: Opportunity, pm_brief: str, blocked: str | None) -> LoopArtifact:
    if opportunity.verdict is Verdict.park or opportunity.product_brief is None:
        return _artifact(
            LoopStage.product_manager,
            "AI Product Manager",
            LoopStatus.waiting,
            blocked or _PARKED,
        )
    summary = "Intake is ready for the product manager."
    if blocked == _APPROVAL:
        summary = f"{summary} {_APPROVAL}"
    return _artifact(
        LoopStage.product_manager,
        "AI Product Manager",
        LoopStatus.ready,
        summary,
        pm_brief.splitlines(),
    )


def _prd(opportunity: Opportunity, blocked: str | None) -> LoopArtifact:
    brief = opportunity.product_brief
    if blocked is not None or brief is None:
        return _wait(LoopStage.prd, "PRD", blocked or _NO_BRIEF)
    return _artifact(
        LoopStage.prd,
        "PRD",
        LoopStatus.ready,
        "The PRD repeats the brief. Scope stops at the experiment.",
        [
            f"Overview: {brief.opportunity}",
            f"Problem: {brief.problem}",
            f"Users: {brief.target_users}",
            f"Goal: {brief.experiment}",
            "Non-goals: Scope stops at the recommended experiment.",
            *[f"Story: As {brief.target_users}, {item}." for item in brief.mvp],
            *[f"Requirement: {item}" for item in brief.mvp],
            *[f"Risk: {item}" for item in brief.risks],
            *[f"Open question: {item}" for item in brief.open_questions],
        ],
    )


def _architect(opportunity: Opportunity, blocked: str | None, held: str | None) -> LoopArtifact:
    brief = opportunity.product_brief
    if blocked is not None or held is not None or brief is None:
        return _wait(LoopStage.architect, "AI Software Architect", held or blocked or _NO_BRIEF)
    return _artifact(
        LoopStage.architect,
        "AI Software Architect",
        LoopStatus.ready,
        "Each MVP slice is a boundary. Nothing beyond the brief is in scope.",
        [
            *[f"Slice: {item}." for item in brief.mvp],
            "No capability beyond the MVP is in scope.",
            f"Release shape: {brief.experiment}",
        ],
    )


def _developer(opportunity: Opportunity, blocked: str | None, held: str | None) -> LoopArtifact:
    brief = opportunity.product_brief
    if blocked is not None or held is not None or brief is None:
        return _wait(LoopStage.developer, "AI Developer Agent", held or blocked or _NO_BRIEF)
    return _artifact(
        LoopStage.developer,
        "AI Developer Agent",
        LoopStatus.ready,
        "One task per MVP slice. Done means the experiment can run.",
        [
            *[f"Implement: {item}." for item in brief.mvp],
            f"Done when: {brief.experiment}",
        ],
    )


def _qa(opportunity: Opportunity, blocked: str | None, held: str | None) -> LoopArtifact:
    brief = opportunity.product_brief
    if blocked is not None or held is not None or brief is None:
        return _wait(LoopStage.qa, "AI QA Agent", held or blocked or _NO_BRIEF)
    return _artifact(
        LoopStage.qa,
        "AI QA Agent",
        LoopStatus.ready,
        "Cases are written. Results wait on the experiment.",
        [
            *[f"Open: {item}" for item in brief.open_questions],
            f"Measure: {brief.experiment}",
        ],
    )


def _review(opportunity: Opportunity, blocked: str | None) -> LoopArtifact:
    brief = opportunity.product_brief
    if blocked is not None or brief is None:
        return _wait(LoopStage.review, "AI Review Agent", blocked or _NO_BRIEF)
    challenge = opportunity.challenge
    if challenge is not None and challenge.contradicting:
        return _artifact(
            LoopStage.review,
            "AI Review Agent",
            LoopStatus.hold,
            f"{_HOLD} {challenge.contradicting[0].text}.",
            [f"Contradicts the brief: {point.text}" for point in challenge.contradicting],
        )
    return _artifact(
        LoopStage.review,
        "AI Review Agent",
        LoopStatus.ready,
        "The PRD matches the brief. Nothing was added.",
        [
            f"Problem matches: {brief.problem}",
            *[f"MVP matches: {item}" for item in brief.mvp],
        ],
    )


def _production(opportunity: Opportunity, blocked: str | None, held: str | None) -> LoopArtifact:
    brief = opportunity.product_brief
    if blocked is not None or held is not None or brief is None:
        return _wait(LoopStage.production, "Production", held or blocked or _NO_BRIEF)
    return _artifact(
        LoopStage.production,
        "Production",
        LoopStatus.ready,
        f"In the experiment. {brief.experiment}",
        [brief.experiment],
    )


def _analytics(
    opportunity: Opportunity,
    signals: list[ReturnSignal],
    blocked: str | None,
    held: str | None,
) -> LoopArtifact:
    if blocked is not None or held is not None or not signals:
        return _wait(LoopStage.analytics, "Product Analytics", held or blocked or _NO_BRIEF)
    return _artifact(
        LoopStage.analytics,
        "Product Analytics",
        LoopStatus.ready,
        "The experiment names what to measure. The result is not in yet.",
        [f"{signal.title}: {signal.body}" for signal in signals],
    )


def _returned(signals: list[ReturnSignal], blocked: str | None, held: str | None) -> LoopArtifact:
    if blocked is not None or held is not None or not signals:
        return _wait(LoopStage.discovery_return, "Product Discovery", held or blocked or _NO_BRIEF)
    return _artifact(
        LoopStage.discovery_return,
        "Product Discovery",
        LoopStatus.returned,
        "These measurements re-enter product discovery.",
        [signal.title for signal in signals],
    )


def _return_signals(opportunity: Opportunity) -> list[ReturnSignal]:
    brief = opportunity.product_brief
    if brief is None:
        return []
    return [
        ReturnSignal(
            title=f"{brief.opportunity} experiment",
            body=brief.experiment,
        )
    ]


def _pm_brief(opportunity: Opportunity, why: str) -> str:
    brief = opportunity.product_brief
    if brief is None:
        return ""
    lines = [
        f"Opportunity: {brief.opportunity}",
        f"Problem: {brief.problem}",
        f"Target users: {brief.target_users}",
        f"Observed pain: {brief.observed_pain}",
        "Existing solutions:",
        *brief.existing_solutions,
        f"Gap: {brief.gap}",
        "Potential MVP:",
        *[f"- {item}" for item in brief.mvp],
        "Evidence:",
        *brief.evidence,
        "Risks:",
        *[f"- {item}" for item in brief.risks],
        "Open questions:",
        *[f"- {item}" for item in brief.open_questions],
        f"Recommended experiment: {brief.experiment}",
    ]
    cleaned = " ".join(why.split())
    if cleaned:
        lines.append(f"Why this opportunity exists: {cleaned}")
    lines.append("Scope stops at the recommended experiment. Open questions stay open.")
    return "\n".join(lines)


def _wait(stage: LoopStage, title: str, summary: str) -> LoopArtifact:
    return _artifact(stage, title, LoopStatus.waiting, summary)


def _artifact(
    stage: LoopStage,
    title: str,
    status: LoopStatus,
    summary: str,
    lines: list[str] | None = None,
) -> LoopArtifact:
    return LoopArtifact(stage=stage, title=title, status=status, summary=summary, lines=lines or [])
