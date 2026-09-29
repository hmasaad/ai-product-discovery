"""Decision memos handed to a product manager after review."""

from discovery.models import Opportunity, ProductContext, ProductOpportunityBrief
from discovery.present import (
    GAP_LABELS,
    KIND_LABELS,
    PILLAR_LABELS,
    STATUS_LABELS,
    VERDICT_LABELS,
    format_date,
    format_metric,
    percent,
)


RULE = "━" * 30
_WIDTH = 42


def render_product_brief(brief: ProductOpportunityBrief) -> str:
    """The boxed handoff: evidence and one experiment."""

    sections = [
        ("Problem", _wrap(brief.problem)),
        ("Target users", _wrap(brief.target_users)),
        ("Observed pain", _wrap(brief.observed_pain)),
        ("Existing solutions", _lines(brief.existing_solutions)),
        ("Gap", _wrap(brief.gap)),
        ("Opportunity", _wrap(brief.opportunity)),
        ("Potential MVP", _bullets(brief.mvp)),
        ("Evidence", _lines(brief.evidence)),
        ("Risks", _bullets(brief.risks)),
        ("Open questions", _bullets(brief.open_questions)),
        ("Recommended experiment", _wrap(brief.experiment)),
    ]
    lines = [RULE, "PRODUCT OPPORTUNITY", RULE, ""]
    for label, body in sections:
        lines.extend([label, body, ""])
    lines.append(RULE)
    return "\n".join(lines) + "\n"


def _wrap(text: str) -> str:
    words = text.split()
    if not words:
        return ""
    rows: list[str] = []
    current = words[0]
    for word in words[1:]:
        if len(current) + 1 + len(word) <= _WIDTH:
            current = f"{current} {word}"
        else:
            rows.append(current)
            current = word
    rows.append(current)
    return "\n".join(rows)


def _lines(items: list[str]) -> str:
    return "\n".join(items)


def _bullets(items: list[str]) -> str:
    return "\n".join(f"• {item}" for item in items)


def render_markdown(opportunity: Opportunity, context: ProductContext) -> str:
    scores = opportunity.scores
    lines = [
        f"# {opportunity.title}",
        "",
        f"{context.name} · {context.category}",
        (
            f"{VERDICT_LABELS[opportunity.verdict.value]} · "
            f"{GAP_LABELS[opportunity.gap.value]} · "
            f"opportunity {percent(scores.opportunity)} · "
            f"confidence {percent(scores.confidence)}"
        ),
        f"Review: {STATUS_LABELS[opportunity.status.value]}",
        "",
    ]
    if opportunity.product_brief is not None:
        lines.extend([render_product_brief(opportunity.product_brief).rstrip(), ""])
    lines.extend(
        [
            "## Validation",
            "",
            opportunity.rationale,
            "",
        ]
    )
    if opportunity.chain is not None:
        lines.extend(
            [
                "## Signal",
                "",
                opportunity.chain.signal,
                "",
                "## Problem",
                "",
                opportunity.chain.problem,
                "",
                "## User segment",
                "",
                opportunity.chain.segment,
                "",
                "## Pain",
                "",
                opportunity.chain.pain,
                "",
                "## Existing solutions",
                "",
                opportunity.chain.existing_solutions,
                "",
                "## Gap",
                "",
                opportunity.chain.gap,
                "",
                "## Opportunity",
                "",
                opportunity.chain.opportunity,
                "",
            ]
        )
    else:
        lines.extend(["## Problem", "", opportunity.problem, ""])
    lines.extend(
        [
            "## Why now",
            "",
            opportunity.why_now,
            "",
            opportunity.mapping_note,
            "",
        ]
    )
    if opportunity.market is not None:
        lines.extend(
            [
                "## Market signal",
                "",
                f"Trend: {opportunity.market.trend}",
                "",
                "Evidence:",
                "",
            ]
        )
        lines.extend(f"- {item}" for item in opportunity.market.evidence)
        lines.extend(["", "Potential implication:", "", opportunity.market.implication, ""])
    if opportunity.user is not None:
        lines.extend(
            [
                "## User intelligence",
                "",
                (
                    f"{round(opportunity.user.share * 100)}% of "
                    f"{opportunity.user.feedback_count:,} feedback items are about {opportunity.user.label}."
                ),
                "",
            ]
        )
        if opportunity.user.unmet:
            lines.extend(["Unmet need:", "", opportunity.user.unmet_need, ""])
    if opportunity.competitor is not None:
        lines.extend(
            [
                "## Competitor intelligence",
                "",
                opportunity.competitor.race,
                "",
                "Potential market gap:",
                "",
                opportunity.competitor.gap,
                "",
            ]
        )
    lines.extend(
        [
            "## The bet",
            "",
            opportunity.idea_summary,
            "",
            "## Evidence",
            "",
        ]
    )
    for item in opportunity.evidence:
        metrics = ", ".join(format_metric(key, value) for key, value in item.metrics.items())
        metric_note = f" ({metrics})" if metrics else ""
        lines.append(
            f"- **{PILLAR_LABELS[item.pillar.value]} · {KIND_LABELS[item.kind.value]}** "
            f"{item.title} — {item.source}, {format_date(item.observed_at)}{metric_note}"
        )
        lines.append(f"  {item.excerpt}")
    lines.extend(["", "## Checks", ""])
    for check in opportunity.checks:
        mark = "pass" if check.passed else "fail"
        lines.append(f"- {mark} · {check.label}: {check.detail}")
    lines.extend(["", "## Risks", ""])
    lines.extend(f"- {risk}" for risk in opportunity.risks)
    lines.extend(["", "## Next", ""])
    lines.extend(f"- {step}" for step in opportunity.next_steps)
    if opportunity.review_note:
        lines.extend(["", "## Review note", "", opportunity.review_note])
    lines.append("")
    return "\n".join(lines)
