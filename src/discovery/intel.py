"""Market, user, and product intel.

Live connectors implement ``IntelSource``. This package ships a file source so
a cycle can run from evidence you already have: exports, interview notes,
review pulls, or analytics snapshots dropped in as JSON.
"""

import json
from pathlib import Path
from typing import Protocol

from pydantic import TypeAdapter, ValidationError

from discovery.models import IntelPillar, ProductContext, Signal, Theme

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

    ``context.json`` and ``themes.json`` are skipped so a workspace folder can
    be ingested as a directory without mixing configuration into evidence.
    """

    if path.is_dir():
        signals: list[Signal] = []
        for file in sorted(path.glob("*.json")):
            if file.name in {"context.json", "themes.json"}:
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


def _reject_duplicate_ids(signals: list[Signal]) -> None:
    seen: set[str] = set()
    for signal in signals:
        if signal.id in seen:
            raise ValueError(f"Duplicate signal id: {signal.id}")
        seen.add(signal.id)
