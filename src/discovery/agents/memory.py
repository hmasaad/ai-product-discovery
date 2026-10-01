"""Product intelligence memory.

Remembers products, features, users, problems, competitors, experiments,
decisions, metrics, feedback, rejected ideas, successful ideas, and failed
experiments. Answers are retrieved from those records.

A problem has been seen before when the same theme has two or more feedback
items, counting each signal's volume. A rejection "six months ago" is a
rejected idea dated 150 to 210 days before the day of the question. Strong
evidence that has not been tested is a pursue opportunity with no successful
idea and no failed experiment recorded against it.
"""

from collections import defaultdict
from datetime import date

from discovery.engine.cluster import match_theme
from discovery.models import (
    CompetitorCatalog,
    MemoryAnswer,
    MemoryKind,
    MemoryRecord,
    Opportunity,
    ProductContext,
    ProductMemory,
    ReviewEntry,
    ReviewStatus,
    Signal,
    Theme,
    Verdict,
)
from discovery.present import format_date, format_metric

QUESTIONS = (
    "Have we seen this problem before?",
    "Why did we reject this feature six months ago?",
    "Which customer problems are repeatedly appearing?",
    "Which opportunities have strong evidence but haven't been tested?",
)

_SIX_MONTHS = (150, 210)
_OUTCOME_KINDS = {
    MemoryKind.rejected_ideas,
    MemoryKind.successful_ideas,
    MemoryKind.failed_experiments,
}


class ProductMemoryAgent:
    def remember(
        self,
        context: ProductContext,
        signals: list[Signal],
        opportunities: list[Opportunity],
        reviews: list[ReviewEntry],
        catalog: CompetitorCatalog,
        themes: list[Theme],
        outcomes: list[MemoryRecord] | None = None,
    ) -> ProductMemory:
        titles = {item.id: item.title for item in opportunities}
        records: list[MemoryRecord] = []
        records.extend(_products(context))
        records.extend(_features(opportunities))
        records.extend(_users(context))
        records.extend(_problems(signals, themes))
        records.extend(_competitors(catalog))
        records.extend(_experiments(opportunities))
        records.extend(_decisions(reviews, titles))
        records.extend(_metrics(signals))
        records.extend(_feedback(signals))
        records.extend(_rejections(reviews, titles))
        for outcome in outcomes or []:
            records.append(outcome)
            if outcome.kind in _OUTCOME_KINDS:
                records.append(_decision_from_outcome(outcome))
        return ProductMemory(records=_dedupe(records))

    def ask(self, memory: ProductMemory, question: str, today: date) -> MemoryAnswer:
        cleaned = " ".join(question.split())
        lowered = cleaned.lower()
        if lowered.startswith("have we seen"):
            return _seen(memory, cleaned)
        if "reject" in lowered:
            return _rejected(memory, cleaned, today)
        if "repeat" in lowered:
            return _repeated(memory, cleaned)
        if "tested" in lowered or "strong evidence" in lowered:
            return _untested(memory, cleaned)
        return MemoryAnswer(
            question=cleaned,
            answer="The memory answers four questions: seen before, rejected six months ago, repeated problems, and untested opportunities.",
        )


def _products(context: ProductContext) -> list[MemoryRecord]:
    return [
        MemoryRecord(
            id="product",
            kind=MemoryKind.products,
            title=context.name,
            detail=f"{context.category}. {context.mission}",
            source="Product context",
        )
    ]


def _features(opportunities: list[Opportunity]) -> list[MemoryRecord]:
    return [
        MemoryRecord(
            id=f"feature-{item.id}",
            kind=MemoryKind.features,
            title=item.title,
            detail=item.idea_summary,
            source="Opportunity",
            subject=item.id,
            verdict=item.verdict.value,
        )
        for item in opportunities
    ]


def _users(context: ProductContext) -> list[MemoryRecord]:
    if not context.audience.strip():
        return []
    return [
        MemoryRecord(
            id="users",
            kind=MemoryKind.users,
            title=context.audience,
            detail=context.name,
            source="Product context",
        )
    ]


def _problems(signals: list[Signal], themes: list[Theme]) -> list[MemoryRecord]:
    records: list[MemoryRecord] = []
    for signal in signals:
        if signal.pillar.value != "user":
            continue
        if signal.resolved_polarity().value not in {"pain", "demand"}:
            continue
        theme = match_theme(signal, themes)
        records.append(
            MemoryRecord(
                id=f"problem-{signal.id}",
                kind=MemoryKind.problems,
                title=theme.label if theme is not None else signal.title,
                detail=signal.title,
                observed_at=signal.observed_at,
                source=signal.source,
                subject=theme.id if theme is not None else signal.id,
                count=signal.volume,
            )
        )
    return records


def _competitors(catalog: CompetitorCatalog) -> list[MemoryRecord]:
    return [
        MemoryRecord(
            id=f"competitor-{product.id}",
            kind=MemoryKind.competitors,
            title=product.name,
            source="Competitor catalog",
            subject=product.id,
        )
        for product in catalog.products
    ]


def _experiments(opportunities: list[Opportunity]) -> list[MemoryRecord]:
    records: list[MemoryRecord] = []
    for item in opportunities:
        experiment = ""
        if item.product_brief is not None and item.product_brief.experiment.strip():
            experiment = item.product_brief.experiment.strip()
        elif item.next_steps:
            experiment = item.next_steps[0]
        if not experiment:
            continue
        records.append(
            MemoryRecord(
                id=f"experiment-{item.id}",
                kind=MemoryKind.experiments,
                title=item.title,
                detail=experiment,
                source="Opportunity brief",
                subject=item.id,
            )
        )
    return records


def _decisions(reviews: list[ReviewEntry], titles: dict[str, str]) -> list[MemoryRecord]:
    records: list[MemoryRecord] = []
    for review in reviews:
        title = titles.get(review.opportunity_id, review.opportunity_id)
        records.append(
            MemoryRecord(
                id=f"decision-{review.opportunity_id}-{review.created_at}",
                kind=MemoryKind.decisions,
                title=f"{title} — {review.action.value}",
                detail=review.note,
                observed_at=_day(review.created_at),
                source="Review",
                subject=review.opportunity_id,
            )
        )
    return records


def _metrics(signals: list[Signal]) -> list[MemoryRecord]:
    records: list[MemoryRecord] = []
    for signal in signals:
        for key, value in signal.metrics.items():
            records.append(
                MemoryRecord(
                    id=f"metric-{signal.id}-{key}",
                    kind=MemoryKind.metrics,
                    title=format_metric(key, value),
                    detail=signal.title,
                    observed_at=signal.observed_at,
                    source=signal.source,
                    subject=signal.id,
                )
            )
    return records


def _feedback(signals: list[Signal]) -> list[MemoryRecord]:
    return [
        MemoryRecord(
            id=f"feedback-{signal.id}",
            kind=MemoryKind.feedback,
            title=signal.title,
            detail=signal.body,
            observed_at=signal.observed_at,
            source=signal.source,
            subject=signal.id,
            count=signal.volume,
        )
        for signal in signals
        if signal.pillar.value == "user"
    ]


def _rejections(reviews: list[ReviewEntry], titles: dict[str, str]) -> list[MemoryRecord]:
    records: list[MemoryRecord] = []
    for review in reviews:
        if review.action is not ReviewStatus.rejected:
            continue
        title = titles.get(review.opportunity_id, review.opportunity_id)
        records.append(
            MemoryRecord(
                id=f"rejected-{review.opportunity_id}-{review.created_at}",
                kind=MemoryKind.rejected_ideas,
                title=title,
                detail=review.note or "No note was recorded.",
                observed_at=_day(review.created_at),
                source="Review",
                subject=review.opportunity_id,
            )
        )
    return records


def _decision_from_outcome(outcome: MemoryRecord) -> MemoryRecord:
    return MemoryRecord(
        id=f"decision-{outcome.id}",
        kind=MemoryKind.decisions,
        title=outcome.title,
        detail=outcome.detail,
        observed_at=outcome.observed_at,
        source=outcome.source or "Decision record",
        subject=outcome.subject,
    )


def _seen(memory: ProductMemory, question: str) -> MemoryAnswer:
    groups = _problem_groups(memory)
    phrase = _phrase(question, "have we seen ")
    if phrase:
        groups = [group for group in groups if phrase in group["text"]]
        if not groups:
            return MemoryAnswer(question=question, answer="No. That problem is not in memory.")
    repeated = [group for group in groups if group["count"] >= 2]
    chosen = repeated or groups
    if not chosen:
        return MemoryAnswer(question=question, answer="No. No customer problem is in memory.")
    lines = [_appears(group) for group in chosen]
    if repeated or (phrase and chosen):
        prefix = "Yes."
    else:
        prefix = "Once."
    return MemoryAnswer(question=question, answer=f"{prefix} {' '.join(lines)}", records=_group_records(chosen))


def _rejected(memory: ProductMemory, question: str, today: date) -> MemoryAnswer:
    records = memory.of_kind(MemoryKind.rejected_ideas)
    phrase = _phrase(question, "why did we reject ")
    if phrase:
        records = [record for record in records if phrase in _blob(record)]
    if "six months" in question.lower():
        records = [record for record in records if _six_months(record.observed_at, today)]
        empty = "No rejection from six months ago is in memory."
    else:
        empty = "No rejection is in memory."
    records = sorted(records, key=lambda record: (record.observed_at or date.min, record.title))
    if not records:
        return MemoryAnswer(question=question, answer=empty)
    sentences = []
    for record in records:
        when = format_date(record.observed_at) if record.observed_at else "an unknown date"
        reason = record.detail.strip() or "No note was recorded."
        sentences.append(f"{record.title} was rejected on {when}. {reason}")
    return MemoryAnswer(question=question, answer=" ".join(sentences), records=records)


def _repeated(memory: ProductMemory, question: str) -> MemoryAnswer:
    groups = [group for group in _problem_groups(memory) if group["count"] >= 2]
    phrase = _phrase(question, "which customer problems are repeatedly appearing")
    if phrase:
        groups = [group for group in groups if phrase in group["text"]]
    if not groups:
        return MemoryAnswer(question=question, answer="No customer problem appears more than once.")
    lines = [_appears(group) for group in groups]
    return MemoryAnswer(question=question, answer=" ".join(lines), records=_group_records(groups))


def _untested(memory: ProductMemory, question: str) -> MemoryAnswer:
    tested = {
        record.subject
        for record in memory.records
        if record.kind in {MemoryKind.successful_ideas, MemoryKind.failed_experiments} and record.subject
    }
    tested_titles = {
        record.title.casefold()
        for record in memory.records
        if record.kind in {MemoryKind.successful_ideas, MemoryKind.failed_experiments}
    }
    waiting = []
    for record in memory.of_kind(MemoryKind.features):
        if record.subject in tested or record.title.casefold() in tested_titles:
            continue
        opportunity_id = record.subject
        if not _is_pursue(memory, opportunity_id):
            continue
        waiting.append(record)
    phrase = _phrase(question, "which opportunities have strong evidence but haven't been tested")
    if phrase:
        waiting = [record for record in waiting if phrase in record.title.casefold()]
    if not waiting:
        return MemoryAnswer(
            question=question,
            answer="No pursue opportunity is waiting on a test.",
        )
    names = "; ".join(record.title for record in waiting)
    return MemoryAnswer(
        question=question,
        answer=f"These opportunities have a pursue verdict and no recorded experiment result: {names}.",
        records=waiting,
    )


def _is_pursue(memory: ProductMemory, opportunity_id: str) -> bool:
    return any(
        record.subject == opportunity_id and record.verdict == Verdict.pursue.value
        for record in memory.of_kind(MemoryKind.features)
    )


def _problem_groups(memory: ProductMemory) -> list[dict]:
    grouped: dict[str, dict] = defaultdict(lambda: {"title": "", "count": 0, "records": [], "text": ""})
    for record in memory.of_kind(MemoryKind.problems):
        bucket = grouped[record.subject or record.id]
        bucket["title"] = record.title
        bucket["count"] += record.count
        bucket["records"].append(record)
        bucket["text"] = f"{bucket['text']} {record.title} {record.detail}".casefold()
    groups = list(grouped.values())
    groups.sort(key=lambda group: (-group["count"], group["title"]))
    return groups


def _appears(group: dict) -> str:
    count = group["count"]
    noun = "feedback item" if count == 1 else "feedback items"
    return f"{group['title']} appears in {count} {noun}."


def _group_records(groups: list[dict]) -> list[MemoryRecord]:
    records: list[MemoryRecord] = []
    for group in groups:
        records.extend(group["records"])
    return records


def _phrase(question: str, prefix: str) -> str:
    text = question.strip().rstrip("?").casefold()
    if text.startswith(prefix):
        text = text[len(prefix) :]
    for token in ("this problem before", "this feature", "six months ago", "before"):
        text = text.replace(token, " ")
    return " ".join(text.split())


def _blob(record: MemoryRecord) -> str:
    return f"{record.title} {record.detail}".casefold()


def _six_months(observed: date | None, today: date) -> bool:
    if observed is None:
        return False
    delta = (today - observed).days
    return _SIX_MONTHS[0] <= delta <= _SIX_MONTHS[1]


def _day(value: str) -> date | None:
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _dedupe(records: list[MemoryRecord]) -> list[MemoryRecord]:
    chosen: list[MemoryRecord] = []
    seen: set[str] = set()
    for record in records:
        if record.id in seen:
            continue
        seen.add(record.id)
        chosen.append(record)
    return chosen
