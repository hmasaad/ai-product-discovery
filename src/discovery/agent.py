"""One discovery cycle: specialized agents, then the opportunity engine."""

from pathlib import Path

from discovery import intel, store
from discovery.agents.market import MarketResearchAgent
from discovery.engine import run_engine
from discovery.models import (
    CycleReport,
    MarketBrief,
    MarketSignal,
    Opportunity,
    ProductContext,
    ReviewStatus,
)
from discovery.paths import sample_dir
from discovery.store import utc_now


class DiscoveryAgent:
    def __init__(self, home: Path | None = None) -> None:
        self.home = home

    def load_workspace(self, directory: Path) -> int:
        context = intel.load_context(directory / "context.json")
        themes = intel.load_themes(directory / "themes.json")
        signals = intel.load_signals(directory / "signals.json")
        with store.open_db(self.home) as connection:
            store.save_context(connection, context)
            store.save_themes(connection, themes)
            store.replace_signals(connection, signals)
        return len(signals)

    def ingest(self, path: Path) -> int:
        signals = intel.load_signals(path)
        with store.open_db(self.home) as connection:
            store.upsert_signals(connection, signals)
        return len(signals)

    def demo(self, directory: Path | None = None) -> CycleReport:
        self.load_workspace(directory or sample_dir())
        return self.run_cycle()

    def run_cycle(self) -> CycleReport:
        with store.open_db(self.home) as connection:
            signals = store.list_signals(connection)
            themes = store.load_themes(connection)

        collected = intel.collect(intel.sources_for(signals))
        market_signals = MarketResearchAgent().analyze(collected, themes)
        drafted = run_engine(collected, themes)
        _attach_market(drafted, market_signals)
        pillar_counts = {
            "market": sum(1 for signal in collected if signal.pillar.value == "market"),
            "user": sum(1 for signal in collected if signal.pillar.value == "user"),
            "product": sum(1 for signal in collected if signal.pillar.value == "product"),
        }
        by_verdict = {"pursue": 0, "investigate": 0, "park": 0}
        for opportunity in drafted:
            by_verdict[opportunity.verdict.value] += 1

        report = CycleReport(
            ran_at=utc_now(),
            signal_count=len(collected),
            pillar_counts=pillar_counts,
            opportunity_count=len(drafted),
            by_verdict=by_verdict,
            opportunities=[],
            market_signals=market_signals,
        )
        with store.open_db(self.home) as connection:
            report.opportunities = store.replace_opportunities(connection, drafted)
            store.replace_market_signals(connection, market_signals)
            store.record_cycle(connection, report)
        return report

    def context(self) -> ProductContext:
        with store.open_db(self.home) as connection:
            return store.load_context(connection)

    def signals(self):
        with store.open_db(self.home) as connection:
            return store.list_signals(connection)

    def market_signals(self) -> list[MarketSignal]:
        with store.open_db(self.home) as connection:
            return store.list_market_signals(connection)

    def opportunities(self) -> list[Opportunity]:
        with store.open_db(self.home) as connection:
            return store.list_opportunities(connection)

    def opportunity(self, opportunity_id: str) -> Opportunity | None:
        with store.open_db(self.home) as connection:
            return store.get_opportunity(connection, opportunity_id)

    def reviews(self, opportunity_id: str):
        with store.open_db(self.home) as connection:
            return store.list_reviews(connection, opportunity_id)

    def latest_cycle(self):
        with store.open_db(self.home) as connection:
            return store.latest_cycle(connection)

    def apply_review(self, opportunity_id: str, action: str, note: str) -> Opportunity | None:
        try:
            status = ReviewStatus(action)
        except ValueError as exc:
            raise ValueError(f"Unknown review action: {action}") from exc
        if status is ReviewStatus.pending_review:
            raise ValueError("pending_review is the starting state, not a review decision")
        cleaned = " ".join(note.split())[:500]
        with store.open_db(self.home) as connection:
            return store.apply_review(connection, opportunity_id, status, cleaned)


def _attach_market(opportunities: list[Opportunity], market_signals: list[MarketSignal]) -> None:
    by_theme = {signal.theme: signal for signal in market_signals}
    for opportunity in opportunities:
        signal = by_theme.get(opportunity.theme)
        if signal is None:
            opportunity.market = None
            continue
        opportunity.market = MarketBrief(
            trend=signal.trend,
            evidence=[item.statement for item in signal.evidence],
            implication=signal.implication,
            facets=[facet.value for facet in signal.facets],
        )
