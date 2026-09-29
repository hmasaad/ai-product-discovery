"""Market, user, and product intel.

Live connectors implement ``IntelSource``. This package ships a file source so
a cycle can run from evidence you already have: exports, interview notes,
review pulls, or analytics snapshots dropped in as JSON.
"""

import json
from pathlib import Path
from typing import Protocol

from pydantic import TypeAdapter, ValidationError

from discovery.models import CompetitorCatalog, IntelPillar, ProductContext, Signal, Theme

_SIGNAL_LIST = TypeAdapter(list[Signal])
_THEME_LIST = TypeAdapter(list[Theme])


class IntelSource(Protocol):
    name: str
    pillar: IntelPillar

    def fetch(self) -> list[Signal]:
        """Return signals for one pillar. Implementations own their I/O."""


class StaticIntelSource:
    """An in-memory source used after signals have been loaded from files."""

    def __init__(self, name: str, pillar: IntelPillar, signals: list[Signal]) -> None:
        self.name = name
        self.pillar = pillar
        self._signals = signals

    def fetch(self) -> list[Signal]:
        return [signal for signal in self._signals if signal.pillar is self.pillar]


def sources_for(signals: list[Signal]) -> list[StaticIntelSource]:
    return [
        StaticIntelSource("market", IntelPillar.market, signals),
        StaticIntelSource("user", IntelPillar.user, signals),
        StaticIntelSource("product", IntelPillar.product, signals),
    ]


def collect(sources: list[IntelSource]) -> list[Signal]:
    collected: list[Signal] = []
    for source in sources:
        for signal in source.fetch():
            if signal.pillar is not source.pillar:
                raise ValueError(
                    f"{source.name} returned {signal.id}, which is {signal.pillar.value} intel"
                )
            collected.append(signal)
    return collected


def load_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path} is not valid JSON: {exc}") from exc


def load_context(path: Path) -> ProductContext:
    payload = load_json(path)
    try:
        return ProductContext.model_validate(payload)
    except ValidationError as exc:
        raise ValueError(f"{path} is not a product context:\n{exc}") from exc


def load_themes(path: Path) -> list[Theme]:
    if not path.exists():
        return []
    payload = load_json(path)
    try:
        return _THEME_LIST.validate_python(payload)
    except ValidationError as exc:
        raise ValueError(f"{path} is not a theme list:\n{exc}") from exc


def load_signals(path: Path) -> list[Signal]:
    """Load signals from a JSON file or from every ``*.json`` file in a directory.

    ``context.json``, ``themes.json``, and ``competitors.json`` are skipped so a
    workspace folder can be ingested as a directory without mixing configuration
    into evidence.
    """

    if path.is_dir():
        signals: list[Signal] = []
        for file in sorted(path.glob("*.json")):
            if file.name in {"context.json", "themes.json", "competitors.json"}:
                continue
            signals.extend(load_signals(file))
        _reject_duplicate_ids(signals)
        return signals

    payload = load_json(path)
    if isinstance(payload, dict) and "signals" in payload:
        payload = payload["signals"]
    try:
        signals = _SIGNAL_LIST.validate_python(payload)
    except ValidationError as exc:
        raise ValueError(f"{path} is not a signal list:\n{exc}") from exc
    _reject_duplicate_ids(signals)
    return signals


def load_competitors(path: Path) -> CompetitorCatalog:
    if not path.exists():
        return CompetitorCatalog()
    payload = load_json(path)
    try:
        catalog = CompetitorCatalog.model_validate(payload)
    except ValidationError as exc:
        raise ValueError(f"{path} is not a competitor catalog:\n{exc}") from exc
    _validate_catalog(catalog, path)
    return catalog


def _validate_catalog(catalog: CompetitorCatalog, path: Path) -> None:
    capability_ids = [capability.id for capability in catalog.capabilities]
    if len(capability_ids) != len(set(capability_ids)):
        raise ValueError(f"{path} repeats a capability id")
    product_ids = [product.id for product in catalog.products]
    if len(product_ids) != len(set(product_ids)):
        raise ValueError(f"{path} repeats a competitor id")
    names = [product.name for product in catalog.products]
    if len(names) != len(set(names)):
        raise ValueError(f"{path} repeats a competitor name")
    kinds = {capability.id: capability.kind for capability in catalog.capabilities}
    for product in catalog.products:
        for move in product.moves:
            kind = kinds.get(move.capability)
            if kind is None:
                raise ValueError(
                    f"{path}: {product.name} references unknown capability {move.capability}"
                )
            if kind.value == "feature" and not isinstance(move.value, bool):
                raise ValueError(
                    f"{path}: {product.name} {move.capability} must be true or false"
                )
            if kind.value != "feature" and (isinstance(move.value, bool) or not isinstance(move.value, int)):
                raise ValueError(
                    f"{path}: {product.name} {move.capability} must be a number"
                )


def _reject_duplicate_ids(signals: list[Signal]) -> None:
    seen: set[str] = set()
    for signal in signals:
        if signal.id in seen:
            raise ValueError(f"Duplicate signal id: {signal.id}")
        seen.add(signal.id)
