"""Opportunity validation agent.

Challenges a candidate before it is handed to a product manager. Supporting
evidence and contradicting evidence are listed separately. A question with no
evidence stays open. An empty "against" column is reported as unchallenged,
not as confirmation.
"""

import re

from discovery.models import (
    EvidenceSide,
    Gap,
    IntelPillar,
    Polarity,
    Signal,
    SignalKind,
    ValidationBrief,
    ValidationPoint,
    ValidationQuestion,
)
from discovery.present import format_metric

_CONTRADICT = re.compile(
    r"\b(low engagement|prefer humans?|human advisors?|high trust|do not trust|"
    r"won't pay|would not pay|too expensive|contradict\w*)\b",
    re.IGNORECASE,
)
_ALTERNATIVE = re.compile(
    r"\b(prefer|advisor|alternative|instead|competitor)\b",
    re.IGNORECASE,
)
_SIZE_KEYS = ("tam", "sam", "som", "market_size")
_PAY_KEYS = ("wtp", "willingness", "price")
_FRICTION = ("stall", "abandon", "drop", "dismiss", "churn")


class OpportunityValidationAgent:
    def review(
        self,
        signals: list[Signal],
        gap: Gap,
        segment: str,
    ) -> ValidationBrief:
        ranked = sorted(signals, key=lambda signal: (-signal.strength, signal.observed_at, signal.id))
        supporting = [
            ValidationPoint(text=signal.title, signal_id=signal.id)
            for signal in ranked
            if _side(signal, gap) is EvidenceSide.support
        ]
        contradicting = [
            ValidationPoint(text=signal.title, signal_id=signal.id)
            for signal in ranked
            if _side(signal, gap) is EvidenceSide.contradict
        ]
        questions = _questions(ranked, supporting, contradicting, gap, segment)
        if contradicting:
            challenge = (
                f"Contradicting evidence: {contradicting[0].text}. "
                "The supporting list is not confirmation."
            )
        else:
            challenge = "No contradicting evidence is in the cluster. The case is unchallenged."
        return ValidationBrief(
            supporting=supporting,
            contradicting=contradicting,
            questions=questions,
            challenge=challenge,
        )


def _side(signal: Signal, gap: Gap) -> EvidenceSide | None:
    if signal.stance is EvidenceSide.contradict:
        return EvidenceSide.contradict
    if signal.stance is EvidenceSide.support:
        return EvidenceSide.support
    if "contradict" in signal.tags or "against" in signal.tags:
        return EvidenceSide.contradict
    if _CONTRADICT.search(f"{signal.title} {signal.body}"):
        return EvidenceSide.contradict
    if gap is Gap.table_stakes and signal.resolved_polarity() is Polarity.adoption:
        return EvidenceSide.contradict
    polarity = signal.resolved_polarity()
    if polarity in {Polarity.pain, Polarity.demand}:
        return EvidenceSide.support
    if signal.kind is SignalKind.competitor or polarity is Polarity.movement:
        return EvidenceSide.support
    if polarity is Polarity.adoption:
        return EvidenceSide.support
    return None


def _questions(
    signals: list[Signal],
    supporting: list[ValidationPoint],
    contradicting: list[ValidationPoint],
    gap: Gap,
    segment: str,
) -> list[ValidationQuestion]:
    by_id = {signal.id: signal for signal in signals}
    support_signals = [by_id[point.signal_id] for point in supporting if point.signal_id in by_id]
    return [
        _real(support_signals),
        _who(segment),
        _frequency(support_signals),
        _painful(signals),
        _alternatives(support_signals, contradicting),
        _market_size(signals),
        _feasible(signals),
        _pay(signals),
        _contradiction(contradicting),
    ]


def _real(support_signals: list[Signal]) -> ValidationQuestion:
    pains = [
        signal
        for signal in support_signals
        if signal.pillar is IntelPillar.user
        and signal.resolved_polarity() in {Polarity.pain, Polarity.demand}
    ]
    if pains:
        return _question(
            "real",
            "Is the problem real?",
            "supported",
            "Yes. " + " ".join(_sentence(signal.title) for signal in pains),
        )
    return _question(
        "real",
        "Is the problem real?",
        "open",
        "Not established. No user described the problem.",
    )


def _who(segment: str) -> ValidationQuestion:
    cleaned = segment.strip()
    if cleaned and cleaned.lower() != "unspecified":
        return _question("who", "Who experiences it?", "supported", _sentence(cleaned))
    return _question("who", "Who experiences it?", "open", "No user segment is attached.")


def _frequency(support_signals: list[Signal]) -> ValidationQuestion:
    noted = [
        signal.title
        for signal in support_signals
        if signal.pillar is IntelPillar.user
        and (signal.volume > 1 or "recurring" in signal.text())
    ]
    if noted:
        return _question(
            "frequency",
            "How frequently?",
            "supported",
            " ".join(_sentence(title) for title in noted),
        )
    return _question("frequency", "How frequently?", "open", "Frequency is not measured.")


def _painful(signals: list[Signal]) -> ValidationQuestion:
    readings = [
        format_metric(key, value)
        for signal in signals
        for key, value in signal.metrics.items()
        if any(token in key for token in _FRICTION)
    ]
    if readings:
        return _question(
            "painful",
            "How painful?",
            "supported",
            " ".join(_sentence(reading) for reading in readings),
        )
    return _question("painful", "How painful?", "open", "Severity is not measured.")


def _alternatives(
    support_signals: list[Signal],
    contradicting: list[ValidationPoint],
) -> ValidationQuestion:
    names = [signal.title for signal in support_signals if signal.kind is SignalKind.competitor]
    names.extend(point.text for point in contradicting if _ALTERNATIVE.search(point.text))
    if names:
        return _question(
            "alternatives",
            "What alternatives exist?",
            "supported",
            " ".join(_sentence(name) for name in names),
        )
    return _question(
        "alternatives",
        "What alternatives exist?",
        "open",
        "No alternative is in the evidence.",
    )


def _market_size(signals: list[Signal]) -> ValidationQuestion:
    readings = _metric_readings(signals, _SIZE_KEYS)
    if readings:
        return _question(
            "market_size",
            "Is the market large enough?",
            "supported",
            " ".join(_sentence(reading) for reading in readings),
        )
    return _question(
        "market_size",
        "Is the market large enough?",
        "open",
        "No market-size evidence.",
    )


def _feasible(signals: list[Signal]) -> ValidationQuestion:
    noted = [
        signal.title
        for signal in signals
        if "feasible" in signal.tags or "feasibility" in signal.text()
    ]
    if noted:
        return _question(
            "feasible",
            "Is this technically feasible?",
            "supported",
            " ".join(_sentence(title) for title in noted),
        )
    return _question(
        "feasible",
        "Is this technically feasible?",
        "open",
        "No feasibility evidence.",
    )


def _pay(signals: list[Signal]) -> ValidationQuestion:
    readings = _metric_readings(signals, _PAY_KEYS)
    titled = [
        signal.title
        for signal in signals
        if "would pay" in signal.text() or "willingness to pay" in signal.text()
    ]
    if readings or titled:
        return _question(
            "pay",
            "What would users pay?",
            "supported",
            " ".join(_sentence(item) for item in [*titled, *readings]),
        )
    return _question("pay", "What would users pay?", "open", "No willingness-to-pay evidence.")


def _contradiction(contradicting: list[ValidationPoint]) -> ValidationQuestion:
    if contradicting:
        return _question(
            "contradiction",
            "What evidence contradicts it?",
            "contradicted",
            " ".join(_sentence(point.text) for point in contradicting),
        )
    return _question(
        "contradiction",
        "What evidence contradicts it?",
        "open",
        "Nothing in the evidence contradicts this yet.",
    )


def _metric_readings(signals: list[Signal], keys: tuple[str, ...]) -> list[str]:
    return [
        format_metric(key, value)
        for signal in signals
        for key, value in signal.metrics.items()
        if any(token in key for token in keys)
    ]


def _question(question_id: str, question: str, status: str, answer: str) -> ValidationQuestion:
    return ValidationQuestion(id=question_id, question=question, answer=answer, status=status)


def _sentence(text: str) -> str:
    cleaned = " ".join(text.split()).strip()
    if not cleaned:
        return ""
    if cleaned[-1] not in ".!?":
        cleaned += "."
    return cleaned[0].upper() + cleaned[1:]
