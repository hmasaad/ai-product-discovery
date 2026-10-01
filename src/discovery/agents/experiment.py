"""AI experimentation agent.

Writes testable hypotheses, then picks the least expensive experiment that
can still reduce the unknown. A full build is not that experiment. A result
counts only when memory recorded it against this opportunity.
"""

import re
from dataclasses import dataclass

from discovery.agents.learning import advise, match_learning
from discovery.models import (
    ExperimentChoice,
    ExperimentLearning,
    ExperimentPlan,
    ExperimentSpec,
    ExperimentStage,
    IntelPillar,
    MemoryKind,
    MemoryRecord,
    Opportunity,
    Polarity,
    TestHypothesis,
    Verdict,
)
from discovery.present import format_date, format_metric

STAGES = (
    "Hypothesis Generator",
    "Experiment Designer",
    "Experiment Specification",
    "Success Metric Designer",
    "Experiment Executor",
    "Results Analyzer",
    "Learning Engine",
)

OUTCOMES = ("Continue", "Iterate", "Reject")
_FAKE_DOOR_GUARDRAILS = (
    "Support complaints",
    "Session abandonment",
    "Incorrect-data reports",
)

VALIDATE = "Validate opportunity"
REJECT = "Reject/Iterate"
WAITING = "Waiting for a result"

_PM_WAITS = "The product manager waits."
_PM_TAKES = "The product manager can take the brief."
_PM_DOES_NOT = "The product manager does not take this opportunity."
_PARKED = "Parked opportunities stay in discovery."
_NOT_RUN = "Not run. Engineering has not started."
_NO_RESULT = "No result is recorded."
_NO_EXPERIMENT = "No experiment is proposed yet."
_NO_EVIDENCE = "No evidence is recorded for this hypothesis."
_SELECTED_USE = "Selected: C + targeted interviews."
_SELECTED_INTERVIEWS = "Selected: D. Interview users."

# Decision bars for experiments that have not run. They are not observed results.
_THRESHOLD_PROBLEM = "At least 5 of 8 describe the problem unprompted."
_THRESHOLD_RETURN = "At least 40% return within 14 days."
_THRESHOLD_ENGAGEMENT = "Engagement is higher than the current baseline."
_THRESHOLD_TRUST = "At least 5 of 8 say they would rely on the answer."
_THRESHOLD_PAY = "At least 3 of 8 name a price they would pay."
_THRESHOLD_CLICK = "At least 8% click."

CATALOG = (
    "Do users have the problem? User interviews",
    "Do users understand the concept? Prototype test",
    "Will users click it? Fake-door test",
    "Will they use it repeatedly? Beta",
    "Will they pay? Pricing experiment",
    "Which version works better? A/B test",
    "Is the technology feasible? Technical spike",
)

_CHOICE_ROWS = (
    ("A", "Build full feature", "Very High", "High"),
    ("B", "Build prototype", "Medium", "High"),
    ("C", "Fake-door test", "Low", "Medium"),
    ("D", "Interview users", "Very Low", "Medium"),
)

_SAMPLE = re.compile(
    r"\b(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s+"
    r"((?:[a-z]+\s+){0,2}?[a-z]+)"
    r"(?=\s*(?:stalled|who|that|and|with|on|against|for|in|at|,|\.|$))",
    re.IGNORECASE,
)
_BOUNDARY = re.compile(r"(?<=[.])\s+")
_PAY = re.compile(r"\b(pay|price|pricing|wtp|willingness)\b", re.IGNORECASE)
_TRUST = re.compile(r"\btrust\b", re.IGNORECASE)
_PERSONAL = re.compile(r"\bpersonal", re.IGNORECASE)
_RETURN = re.compile(r"\b(return|retention|repeat|weekly active)\b", re.IGNORECASE)


@dataclass(frozen=True)
class _Subject:
    want: str
    view: str
    personalized: str
    trust: str
    unknown: str
    avoid: str


def design(
    opportunity: Opportunity,
    records: list[MemoryRecord] | None = None,
    learnings: list[ExperimentLearning] | None = None,
) -> ExperimentPlan:
    experiment = _experiment_text(opportunity)
    failed, succeeded = _results(opportunity, records or [])
    hypotheses = _hypotheses(opportunity)
    unknown, selected, codes = _choose(opportunity, experiment)
    choices = _choices(codes)
    specifications = _specifications(opportunity, experiment, hypotheses, codes)
    prior = match_learning(opportunity, learnings or [])
    informed = advise(prior) if prior is not None else ""
    hypothesis = _hypothesis_stage(hypotheses, _subject(opportunity))
    designer = _designer_stage(opportunity, experiment, unknown, selected, codes, prior, informed)
    specified = _specification_stage(specifications)
    metric = _metric(opportunity, experiment, codes)
    executor = _executor(experiment, failed or succeeded, codes)
    analyzer = _analyzer(failed, succeeded)
    decision, reason, pm = _decision(opportunity, experiment, failed, succeeded)
    learning = ExperimentStage(
        title=STAGES[6],
        summary=reason,
        lines=[f"Decision: {decision}", pm],
        status=_learning_status(decision),
    )
    return ExperimentPlan(
        opportunity_id=opportunity.id,
        title=opportunity.title,
        stages=[hypothesis, designer, specified, metric, executor, analyzer, learning],
        decision=decision,
        decision_summary=reason,
        pm_summary=pm,
        hypotheses=hypotheses,
        unknown=unknown,
        choices=choices,
        selected=selected,
        catalog=list(CATALOG),
        specifications=specifications,
        prior_learning=prior,
        informed_experiment=informed,
    )


def _experiment_text(opportunity: Opportunity) -> str:
    brief = opportunity.product_brief
    if brief is not None and brief.experiment.strip():
        return brief.experiment.strip()
    if opportunity.next_steps:
        return opportunity.next_steps[0].strip()
    return _NO_EXPERIMENT


def _hypotheses(opportunity: Opportunity) -> list[TestHypothesis]:
    subject = _subject(opportunity)
    segment = _segment(opportunity)
    buckets = _evidence_buckets(opportunity)
    rows = (
        (
            "H1",
            f"Users want {subject.want}.",
            "They describe the problem and ask for it without a full build.",
            "Interviews that describe the problem",
            _THRESHOLD_PROBLEM,
            "1 week",
            buckets["problem"],
        ),
        (
            "H2",
            f"Users will regularly return to view {subject.view}.",
            "They come back to look at the next result.",
            "Return rate",
            _THRESHOLD_RETURN,
            "14 days",
            buckets["return"],
        ),
        (
            "H3",
            f"Personalized {subject.personalized} {_verb(subject.personalized)} engagement.",
            "They engage more when the result uses their own history.",
            "Engagement",
            _THRESHOLD_ENGAGEMENT,
            "14 days",
            buckets["personal"],
        ),
        (
            "H4",
            f"Users trust {subject.trust}.",
            "They rely on the answer for a decision.",
            "Users who say they trust the answer",
            _THRESHOLD_TRUST,
            "1 week",
            buckets["trust"],
        ),
        (
            "H5",
            "Users would pay for this capability.",
            "They name a price they would pay.",
            "Users who name a price",
            _THRESHOLD_PAY,
            "1 week",
            buckets["pay"],
        ),
    )
    hypotheses = []
    for code, statement, behavior, metric, threshold, period, evidence in rows:
        titles = [item for item in evidence]
        hypotheses.append(
            TestHypothesis(
                code=code,
                statement=statement,
                target_segment=segment,
                expected_behavior=behavior,
                metric=metric,
                threshold=threshold,
                time_period=period,
                confidence=_confidence(len(titles)),
                evidence=_evidence_text(titles),
            )
        )
    if subject.avoid:
        hypotheses[0] = hypotheses[0].model_copy(
            update={
                "expected_behavior": "They ask for an explanation of last month without a full financial coach.",
            }
        )
        hypotheses[1] = hypotheses[1].model_copy(
            update={"expected_behavior": "They come back to read the next explanation."}
        )
        hypotheses[2] = hypotheses[2].model_copy(
            update={"expected_behavior": "They engage more when the explanation uses their own spending."}
        )
        hypotheses[3] = hypotheses[3].model_copy(
            update={"expected_behavior": "They rely on the explanation for a money decision."}
        )
    return hypotheses


def _hypothesis_stage(hypotheses: list[TestHypothesis], subject: _Subject) -> ExperimentStage:
    lines = []
    if subject.avoid:
        lines.append(f"These hypotheses do not recommend building {subject.avoid}.")
    return ExperimentStage(
        title=STAGES[0],
        summary="Five testable hypotheses.",
        lines=lines,
    )


def _designer_stage(
    opportunity: Opportunity,
    experiment: str,
    unknown: str,
    selected: str,
    codes: set[str],
    prior: ExperimentLearning | None = None,
    informed: str = "",
) -> ExperimentStage:
    lines = ["This runs before engineering starts."]
    subject = _subject(opportunity)
    if subject.avoid:
        lines.append(f"The experiment does not build {subject.avoid}.")
    if _before_building(experiment):
        lines.append("A list, before any build.")
    if _do_not_schedule(experiment):
        lines.append("No experiment is scheduled. The named evidence has to arrive first.")
    sample = _sample(experiment)
    if sample and codes == {"D"}:
        lines.append(f"Sample: {sample}.")
    if prior is not None and informed:
        lines.append(f"Past experiment: {prior.experiment}")
        lines.append(f"Past learning: {prior.learning}")
        lines.append(f"New experiment: {informed}")
    return ExperimentStage(title=STAGES[1], summary=selected, lines=lines)


def _choose(opportunity: Opportunity, experiment: str) -> tuple[str, str, set[str]]:
    subject = _subject(opportunity)
    if opportunity.verdict is Verdict.park or _do_not_schedule(experiment):
        return "Do users have the problem?", _SELECTED_INTERVIEWS, {"D"}
    return subject.unknown, _SELECTED_USE, {"C", "D"}


def _choices(codes: set[str]) -> list[ExperimentChoice]:
    return [
        ExperimentChoice(
            code=code,
            name=name,
            cost=cost,
            information=information,
            selected=code in codes,
        )
        for code, name, cost, information in _CHOICE_ROWS
    ]


def _specifications(
    opportunity: Opportunity,
    experiment: str,
    hypotheses: list[TestHypothesis],
    codes: set[str],
) -> list[ExperimentSpec]:
    specs = []
    if "C" in codes:
        specs.append(_fake_door(opportunity, hypotheses))
    if "D" in codes:
        specs.append(_interviews(opportunity, experiment, hypotheses))
    return specs


def _specification_stage(specifications: list[ExperimentSpec]) -> ExperimentStage:
    if not specifications:
        return ExperimentStage(
            title=STAGES[2],
            summary="No experiment is specified.",
            status="waiting",
        )
    names = ", ".join(item.name for item in specifications)
    return ExperimentStage(
        title=STAGES[2],
        summary=names,
        lines=[
            "Continue: the threshold is met.",
            "Iterate: change the variant and run again.",
            "Reject: the threshold is missed.",
        ],
    )


def _fake_door(opportunity: Opportunity, hypotheses: list[TestHypothesis]) -> ExperimentSpec:
    subject = _subject(opportunity)
    hypothesis = hypotheses[0].statement
    segment = _segment(opportunity)
    if subject.avoid:
        return ExperimentSpec(
            name="AI Spending Insight Fake Door",
            objective="Learn whether users click an explanation of monthly spending before any explanation is built.",
            hypothesis="Users want automated explanations of their monthly spending.",
            target_audience="Active users with ≥3 months transaction history.",
            variant='"Explain My Spending" button.',
            control="Existing spending dashboard.",
            primary_metric="Click-through rate.",
            secondary_metric="Feature activation.",
            guardrails=list(_FAKE_DOOR_GUARDRAILS),
            sample_size="Every active user with at least 3 months of transaction history who sees the dashboard.",
            duration="14 days",
            decision_threshold="CTR ≥ 8%.",
            risks=[
                "A click is not trust in the explanation.",
                "Incorrect spending figures would show up as support complaints.",
            ],
            expected_learning="Whether users click Explain My Spending often enough to continue. The click does not justify building an AI financial coach.",
            outcomes=list(OUTCOMES),
        )
    sample = _sample(_experiment_text(opportunity))
    audience = segment
    if "stalled" in _experiment_text(opportunity).lower():
        audience = f"{segment} with a workspace stalled at instrumentation."
    control = "The current path, with no new feature."
    if "instrumentation" in opportunity.problem.lower() or "tracking" in opportunity.title.lower():
        control = "The current instrumentation path."
    return ExperimentSpec(
        name=f"{_title_case(opportunity.title)} fake door",
        objective=f"Learn whether {segment} will click the {opportunity.title} entry before it is built.",
        hypothesis=hypothesis,
        target_audience=audience,
        variant=f'"{opportunity.title}" entry.',
        control=control,
        primary_metric="Click-through rate.",
        secondary_metric="Feature activation.",
        guardrails=list(_FAKE_DOOR_GUARDRAILS),
        sample_size=f"{sample[:1].upper()}{sample[1:]}." if sample else "Every eligible user during the 14 days.",
        duration="14 days",
        decision_threshold="CTR ≥ 8%.",
        risks=list(opportunity.risks) or ["A click is not repeated use."],
        expected_learning=f"Whether {segment} click before the feature is built.",
        outcomes=list(OUTCOMES),
    )


def _interviews(
    opportunity: Opportunity,
    experiment: str,
    hypotheses: list[TestHypothesis],
) -> ExperimentSpec:
    segment = _segment(opportunity)
    subject = _subject(opportunity)
    if subject.avoid:
        name = "Spending explanation interviews"
        variant = "An interview about last month's spending, with no product pitch."
        objective = "Learn whether young professionals describe the spending problem in their own words."
    elif _before_building(experiment):
        name = f"{_title_case(opportunity.title)} interviews"
        variant = "An interview that asks which questions current analytics cannot answer."
        objective = "Learn which questions current analytics cannot answer, before any build."
    else:
        name = f"{_title_case(opportunity.title)} interviews"
        variant = "An interview about the problem, with no product pitch."
        objective = f"Learn whether {segment} describe the problem in their own words."
    return ExperimentSpec(
        name=name,
        objective=objective,
        hypothesis=hypotheses[0].statement,
        target_audience=segment,
        variant=variant,
        control="No product is shown.",
        primary_metric="Interviews that describe the problem.",
        secondary_metric="Users who ask for the capability unprompted.",
        guardrails=["Leading questions", "A pitch before the answer", "Fewer than 8 interviews"],
        sample_size="8 interviews.",
        duration="1 week",
        decision_threshold=_THRESHOLD_PROBLEM,
        risks=["Stated interest is not a click."],
        expected_learning="Whether the problem shows up in their own words.",
        outcomes=list(OUTCOMES),
    )


def _title_case(title: str) -> str:
    text = title.strip()
    if not text:
        return "Opportunity"
    return f"{text[0].upper()}{text[1:]}"


def _metric(opportunity: Opportunity, experiment: str, codes: set[str]) -> ExperimentStage:
    success = _success_sentence(experiment)
    if _do_not_schedule(experiment):
        summary = "No success metric is set until the named evidence arrives."
        status = "waiting"
    elif success:
        summary = success
        status = "ready"
    elif _before_building(experiment):
        summary = "Done when the list exists."
        status = "ready"
    else:
        summary = experiment
        status = "ready"
    lines = []
    if "C" in codes:
        lines.append(
            f"Fake-door test: click-through. Threshold: {_THRESHOLD_CLICK} Time period: 14 days."
        )
    if "D" in codes:
        lines.append(
            "User interviews: interviews that describe the problem. "
            f"Threshold: {_THRESHOLD_PROBLEM} Time period: 1 week."
        )
    seen: set[str] = set()
    for item in opportunity.evidence:
        for key, value in item.metrics.items():
            rendered = f"Baseline: {format_metric(key, value)}."
            if rendered not in seen:
                seen.add(rendered)
                lines.append(rendered)
    return ExperimentStage(title=STAGES[3], summary=summary, lines=lines, status=status)


def _executor(experiment: str, recorded: MemoryRecord | None, codes: set[str]) -> ExperimentStage:
    if recorded is not None:
        when = format_date(recorded.observed_at) if recorded.observed_at else "an unstated date"
        return ExperimentStage(
            title=STAGES[4],
            summary=f"Recorded on {when}. {recorded.title}.",
            lines=[line for line in (recorded.detail, recorded.source) if line],
        )
    if _do_not_schedule(experiment):
        return ExperimentStage(
            title=STAGES[4],
            summary="Not run. No experiment is scheduled.",
            status="waiting",
        )
    if codes == {"D"}:
        return ExperimentStage(
            title=STAGES[4],
            summary="Not run. The interviews have not been run.",
            status="waiting",
        )
    return ExperimentStage(title=STAGES[4], summary=_NOT_RUN, status="waiting")


def _analyzer(failed: MemoryRecord | None, succeeded: MemoryRecord | None) -> ExperimentStage:
    if failed is not None:
        return ExperimentStage(
            title=STAGES[5],
            summary=f"Failed. {failed.detail}".rstrip(),
            lines=[failed.title],
        )
    if succeeded is not None:
        return ExperimentStage(
            title=STAGES[5],
            summary=f"Succeeded. {succeeded.detail}".rstrip(),
            lines=[succeeded.title],
        )
    return ExperimentStage(title=STAGES[5], summary=_NO_RESULT, status="waiting")


def _decision(
    opportunity: Opportunity,
    experiment: str,
    failed: MemoryRecord | None,
    succeeded: MemoryRecord | None,
) -> tuple[str, str, str]:
    if opportunity.product_brief is None:
        return WAITING, "No product opportunity brief.", _PM_WAITS
    if opportunity.verdict is Verdict.park:
        return REJECT, _PARKED, _PM_DOES_NOT
    if _do_not_schedule(experiment):
        return REJECT, experiment, _PM_DOES_NOT
    if failed is not None:
        detail = failed.detail or failed.title
        return REJECT, f"The experiment failed. {detail}", _PM_DOES_NOT
    if succeeded is not None:
        detail = succeeded.detail or succeeded.title
        return VALIDATE, f"The experiment succeeded. {detail}", _PM_TAKES
    challenge = opportunity.challenge
    if challenge is not None and challenge.contradicting:
        return (
            REJECT,
            f"Contradicting evidence is still open. {challenge.contradicting[0].text}.",
            _PM_DOES_NOT,
        )
    return WAITING, f"{_NO_RESULT} The product manager waits for the experiment.", _PM_WAITS


def _results(
    opportunity: Opportunity,
    records: list[MemoryRecord],
) -> tuple[MemoryRecord | None, MemoryRecord | None]:
    keys = {opportunity.id, opportunity.title, opportunity.theme}
    failed = None
    succeeded = None
    for record in records:
        if record.subject not in keys and record.title not in keys:
            continue
        if record.kind is MemoryKind.failed_experiments and failed is None:
            failed = record
        elif record.kind is MemoryKind.successful_ideas and succeeded is None:
            succeeded = record
    return failed, succeeded


def _learning_status(decision: str) -> str:
    if decision == VALIDATE:
        return "ready"
    if decision == REJECT:
        return "hold"
    return "waiting"


def _subject(opportunity: Opportunity) -> _Subject:
    problem = opportunity.problem.lower()
    if "spending" in problem or "where their money" in problem or "money is going" in problem:
        return _Subject(
            want="automated explanations of their spending",
            view="those explanations",
            personalized="explanations",
            trust="AI-generated financial explanations",
            unknown="Will users use AI spending explanations?",
            avoid="an AI financial coach",
        )
    noun = _noun(opportunity.title)
    return _Subject(
        want=noun,
        view=noun,
        personalized=noun,
        trust=noun,
        unknown=f"Will users use {noun}?",
        avoid="",
    )


def _noun(title: str) -> str:
    text = title.strip() or "this capability"
    if text[0].isupper() and not text[:2].isupper():
        return f"{text[0].lower()}{text[1:]}"
    return text


def _verb(noun: str) -> str:
    last = noun.split()[-1].lower()
    if last.endswith("s") and not last.endswith(("ss", "ics", "analysis")):
        return "increase"
    return "increases"


def _segment(opportunity: Opportunity) -> str:
    brief = opportunity.product_brief
    if brief is not None and brief.target_users.strip():
        return brief.target_users.strip()
    return "Users"


def _evidence_buckets(opportunity: Opportunity) -> dict[str, list[str]]:
    buckets = {"problem": [], "return": [], "personal": [], "trust": [], "pay": []}
    ranked = sorted(opportunity.evidence, key=lambda item: (-item.strength, item.signal_id))
    for item in ranked:
        text = f"{item.title} {item.excerpt}"
        if _PAY.search(text):
            buckets["pay"].append(item.title)
        elif _TRUST.search(text):
            buckets["trust"].append(item.title)
        elif _PERSONAL.search(text):
            buckets["personal"].append(item.title)
        elif _RETURN.search(text):
            buckets["return"].append(item.title)
        elif item.polarity in {Polarity.pain, Polarity.demand} and item.pillar in {
            IntelPillar.user,
            IntelPillar.product,
        }:
            buckets["problem"].append(item.title)
    return buckets


def _confidence(count: int) -> str:
    if count >= 2:
        return "High"
    if count == 1:
        return "Medium"
    return "Low"


def _evidence_text(titles: list[str]) -> str:
    if not titles:
        return _NO_EVIDENCE
    return " ".join(f"{title}." if not title.endswith(".") else title for title in titles)


def _success_sentence(experiment: str) -> str:
    for sentence in _BOUNDARY.split(experiment.strip()):
        cleaned = sentence.strip().rstrip(".")
        if cleaned.lower().startswith("success is "):
            return cleaned
    return ""


def _sample(experiment: str) -> str:
    match = _SAMPLE.search(experiment)
    if match is None:
        return ""
    return f"{match.group(1)} {match.group(2)}"


def _do_not_schedule(experiment: str) -> bool:
    return experiment.lower().startswith("do not schedule")


def _before_building(experiment: str) -> bool:
    return experiment.lower().startswith("before building")
