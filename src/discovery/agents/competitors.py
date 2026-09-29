"""Competitor intelligence agent.

Builds a matrix from dated competitor observations, then reads the moves:

competitor behavior → feature trajectory → strategic direction → market gap.

A feature counts as a recent add when it turns on inside the window ending at
the newest observation. The window is 540 days, so a capability that has been
on for years stays a baseline rather than a launch.
"""

from dataclasses import dataclass
from datetime import date, timedelta

from discovery.models import (
    Capability,
    CapabilityKind,
    CatalogMove,
    CompetitorCatalog,
    CompetitorGap,
    CompetitorIntelligence,
    CompetitorProduct,
    CompetitorRead,
    MatrixRow,
    Signal,
    SignalKind,
)
from discovery.present import format_date

RECENT_DAYS = 540


@dataclass(frozen=True)
class _Change:
    capability_id: str
    observed_at: date
    order: int
    summary: str
    added: bool = False
    removed: bool = False
    price_down: bool = False
    count_up: bool = False


class CompetitorIntelligenceAgent:
    def analyze(
        self,
        catalog: CompetitorCatalog,
        signals: list[Signal] | None = None,
    ) -> CompetitorIntelligence:
        signals = signals or []
        if not catalog.products or not catalog.capabilities:
            return CompetitorIntelligence()

        newest = max(
            move.observed_at for product in catalog.products for move in product.moves
        )
        window_start = newest - timedelta(days=RECENT_DAYS)
        latest = {
            product.id: {
                capability.id: _latest(product.moves, capability.id)
                for capability in catalog.capabilities
            }
            for product in catalog.products
        }
        changes = {
            product.id: _changes(product, catalog.capabilities, window_start)
            for product in catalog.products
        }
        return CompetitorIntelligence(
            products=[product.name for product in catalog.products],
            product_ids=[product.id for product in catalog.products],
            rows=[_row(capability, catalog.products, latest) for capability in catalog.capabilities],
            reads=[
                _read(
                    product,
                    catalog.capabilities,
                    catalog.products,
                    latest,
                    changes[product.id],
                    signals,
                )
                for product in catalog.products
            ],
            race=_race(catalog, changes),
            notes=_notes(catalog, latest),
            gaps=_gaps(catalog, latest, changes),
        )


def _row(capability: Capability, products: list[CompetitorProduct], latest: dict) -> MatrixRow:
    return MatrixRow(
        capability_id=capability.id,
        label=capability.label,
        kind=capability.kind,
        cells=[_display(capability.kind, latest[product.id][capability.id]) for product in products],
    )


def _read(
    product: CompetitorProduct,
    capabilities: list[Capability],
    products: list[CompetitorProduct],
    latest: dict,
    changes: list[_Change],
    signals: list[Signal],
) -> CompetitorRead:
    added: list[str] = []
    removed: list[str] = []
    directions: list[str] = []
    missing: list[str] = []
    for capability in capabilities:
        if capability.kind is not CapabilityKind.feature:
            continue
        if any(change.capability_id == capability.id and change.added for change in changes):
            added.append(capability.label)
            directions.append(capability.direction or capability.label)
        if any(change.capability_id == capability.id and change.removed for change in changes):
            removed.append(capability.label)
        mine = latest[product.id][capability.id]
        others_have = any(
            _is_on(latest[other.id][capability.id])
            for other in products
            if other.id != product.id
        )
        if _is_off(mine) and others_have:
            missing.append(capability.label)

    parts: list[str] = []
    if added:
        parts.append(f"Added {_join(added)}.")
    if removed:
        parts.append(f"Removed {_join(removed)}.")
    if not added and not removed:
        parts.append("No capability was added in the recent window.")
    if missing:
        verb = "is" if len(missing) == 1 else "are"
        parts.append(f"{_join(missing)} {verb} still absent.")

    if directions:
        direction = f"Heading toward {_join(_unique(directions))}."
    else:
        direction = "No recent capability change."
    if any(change.price_down for change in changes):
        direction += " Competing on a lower price."
    if any(change.count_up for change in changes):
        direction += " Integration coverage is expanding."

    behavior = [change.summary for change in sorted(changes, key=lambda item: (item.observed_at, item.order))]
    behavior.extend(_observations(product, signals))
    if not behavior:
        behavior = ["No recorded move in the recent window."]
    return CompetitorRead(
        product_id=product.id,
        name=product.name,
        behavior=behavior,
        trajectory=" ".join(parts),
        direction=direction,
    )


def _race(catalog: CompetitorCatalog, changes: dict[str, list[_Change]]) -> str:
    directions: list[str] = []
    any_add = False
    for capability in catalog.capabilities:
        if capability.kind is not CapabilityKind.feature:
            continue
        adders = [
            product
            for product in catalog.products
            if any(
                change.capability_id == capability.id and change.added
                for change in changes[product.id]
            )
        ]
        if adders:
            any_add = True
        if len(adders) >= 2:
            directions.append(capability.direction or capability.label)
    shared = _unique(directions)
    if shared:
        return f"The field is moving toward {_join(shared)}."
    if any_add:
        return "Competitors are moving, but not toward the same capability."
    return "No recent capability change across the field."


def _notes(catalog: CompetitorCatalog, latest: dict) -> list[str]:
    notes: list[str] = []
    for capability in catalog.capabilities:
        if capability.kind is CapabilityKind.feature:
            continue
        numbers = [
            number
            for product in catalog.products
            if (number := _number(latest[product.id][capability.id])) is not None
        ]
        if len(numbers) < 2 or min(numbers) == max(numbers):
            continue
        lo, hi = min(numbers), max(numbers)
        verb = "run" if capability.label.endswith("s") else "runs"
        if capability.kind is CapabilityKind.price:
            notes.append(f"{capability.label} {verb} from ${lo} to ${hi}.")
        else:
            notes.append(f"{capability.label} {verb} from {lo} to {hi}.")
    return notes


def _gaps(
    catalog: CompetitorCatalog,
    latest: dict,
    changes: dict[str, list[_Change]],
) -> list[CompetitorGap]:
    features = [
        capability
        for capability in catalog.capabilities
        if capability.kind is CapabilityKind.feature
    ]
    gaps: list[CompetitorGap] = []
    for capability in features:
        states = [latest[product.id][capability.id] for product in catalog.products]
        if catalog.products and all(_is_off(move) for move in states):
            gaps.append(
                CompetitorGap(
                    capability_id=capability.id,
                    statement=f"{capability.label} {_verb(capability.label)} absent from every competitor.",
                    themes=list(capability.themes),
                )
            )
    for capability in features:
        holders = [
            product.name
            for product in catalog.products
            if _is_on(latest[product.id][capability.id])
        ]
        if len(holders) == 1:
            gaps.append(
                CompetitorGap(
                    capability_id=capability.id,
                    statement=f"{capability.label} {_verb(capability.label)} only on {holders[0]}.",
                    themes=list(capability.themes),
                )
            )
    for capability in features:
        adders = [
            product
            for product in catalog.products
            if any(
                change.capability_id == capability.id and change.added
                for change in changes[product.id]
            )
        ]
        if len(adders) < 2:
            continue
        missing = [
            product.name
            for product in catalog.products
            if not _is_on(latest[product.id][capability.id])
        ]
        if not missing:
            continue
        gaps.append(
            CompetitorGap(
                capability_id=capability.id,
                statement=f"{capability.label} {_verb(capability.label)} still missing from {_join(missing)}.",
                themes=list(capability.themes),
            )
        )

    recent = [
        capability
        for capability in features
        if any(
            any(
                change.capability_id == capability.id and change.added
                for change in changes[product.id]
            )
            for product in catalog.products
        )
    ]
    combinations = 0
    for index, left in enumerate(recent):
        for right in recent[index + 1 :]:
            if combinations >= 2:
                break
            combined = any(
                _is_on(latest[product.id][left.id]) and _is_on(latest[product.id][right.id])
                for product in catalog.products
            )
            if combined:
                continue
            gaps.append(
                CompetitorGap(
                    capability_id=left.id,
                    statement=f"No competitor combines {left.label} with {right.label}.",
                    themes=_unique([*left.themes, *right.themes]),
                )
            )
            combinations += 1
        if combinations >= 2:
            break
    return gaps


def _changes(
    product: CompetitorProduct,
    capabilities: list[Capability],
    window_start: date,
) -> list[_Change]:
    found: list[_Change] = []
    for order, capability in enumerate(capabilities):
        previous: bool | int | None = None
        seen = False
        for move in _ordered(product.moves, capability.id):
            if move.observed_at < window_start:
                previous = move.value
                seen = True
                continue
            change = _change(capability, move, previous, seen, order)
            if change is not None:
                found.append(change)
            previous = move.value
            seen = True
    return found


def _change(
    capability: Capability,
    move: CatalogMove,
    previous: bool | int | None,
    seen: bool,
    order: int,
) -> _Change | None:
    when = format_date(move.observed_at)
    if capability.kind is CapabilityKind.feature:
        if move.value is True and previous is not True:
            note = f" — {move.note}" if move.note else ""
            return _Change(
                capability_id=capability.id,
                observed_at=move.observed_at,
                order=order,
                summary=f"{when}: added {capability.label}{note}",
                added=True,
            )
        if move.value is False and previous is True:
            return _Change(
                capability_id=capability.id,
                observed_at=move.observed_at,
                order=order,
                summary=f"{when}: removed {capability.label}",
                removed=True,
            )
        return None

    current = _number(move)
    prior = previous if seen and _number_value(previous) is not None else None
    prior_number = _number_value(prior) if prior is not None else None
    if current is None or prior_number is None or current == prior_number:
        return None
    if capability.kind is CapabilityKind.price:
        return _Change(
            capability_id=capability.id,
            observed_at=move.observed_at,
            order=order,
            summary=f"{when}: {capability.label} ${prior_number} → ${current}",
            price_down=current < prior_number,
        )
    return _Change(
        capability_id=capability.id,
        observed_at=move.observed_at,
        order=order,
        summary=f"{when}: {capability.label} {prior_number} → {current}",
        count_up=current > prior_number,
    )


def _observations(product: CompetitorProduct, signals: list[Signal]) -> list[str]:
    name = product.name.casefold()
    matched = [
        signal
        for signal in signals
        if signal.kind is SignalKind.competitor
        and name in f"{signal.title} {signal.body} {signal.source}".casefold()
    ]
    matched.sort(key=lambda signal: (signal.observed_at, signal.title))
    return [
        f"{format_date(signal.observed_at)}: observed {signal.title}" for signal in matched
    ]


def _latest(moves: list[CatalogMove], capability_id: str) -> CatalogMove | None:
    chosen: CatalogMove | None = None
    chosen_index = -1
    for index, move in enumerate(moves):
        if move.capability != capability_id:
            continue
        if chosen is None or (move.observed_at, index) >= (chosen.observed_at, chosen_index):
            chosen = move
            chosen_index = index
    return chosen


def _ordered(moves: list[CatalogMove], capability_id: str) -> list[CatalogMove]:
    indexed = [
        (index, move)
        for index, move in enumerate(moves)
        if move.capability == capability_id
    ]
    indexed.sort(key=lambda pair: (pair[1].observed_at, pair[0]))
    return [move for _, move in indexed]


def _display(kind: CapabilityKind, move: CatalogMove | None) -> str:
    if move is None:
        return "—"
    if kind is CapabilityKind.feature:
        if move.value is True:
            return "✓"
        if move.value is False:
            return "✗"
        return "—"
    number = _number(move)
    if number is None:
        return "—"
    if kind is CapabilityKind.price:
        return f"${number}"
    return str(number)


def _number(move: CatalogMove | None) -> int | None:
    if move is None:
        return None
    return _number_value(move.value)


def _number_value(value: bool | int | None) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _is_on(move: CatalogMove | None) -> bool:
    return move is not None and move.value is True


def _is_off(move: CatalogMove | None) -> bool:
    return move is not None and move.value is False


def _verb(label: str) -> str:
    word = label.split()[-1].lower()
    if word.endswith("s") and not word.endswith(("ss", "ics", "analysis")):
        return "are"
    return "is"


def _join(items: list[str]) -> str:
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return ", ".join(items[:-1]) + f", and {items[-1]}"


def _unique(items: list[str]) -> list[str]:
    seen: list[str] = []
    for item in items:
        if item and item not in seen:
            seen.append(item)
    return seen
