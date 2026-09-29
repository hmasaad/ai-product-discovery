"""Decision memos handed to a product manager after review."""

from discovery.models import Opportunity, ProductContext
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
        "## Validation",
        "",
        opportunity.rationale,
        "",
        "## Problem",
        "",
        opportunity.problem,
        "",
        "## Why now",
        "",
        opportunity.why_now,
        "",
        opportunity.mapping_note,
        "",
    ]
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
