"""One discovery cycle: specialized agents, then the opportunity engine."""

from pathlib import Path

from discovery import intel, store
from discovery.agents.competitors import CompetitorIntelligenceAgent
from discovery.agents.market import MarketResearchAgent
from discovery.agents.users import UserIntelligenceAgent
from discovery.engine import detect_candidates, run_engine
from discovery.engine.graph import build_opportunity_graph
from discovery.models import (
    CompetitorBrief,
    CompetitorIntelligence,
    CycleReport,
    OpportunityCandidate,
    OpportunityGraph,
    MarketBrief,
    MarketSignal,
    Opportunity,
    ProblemCluster,
    UserBrief,
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
        catalog = intel.load_competitors(directory / "competitors.json")
        with store.open_db(self.home) as connection:
            store.save_context(connection, context)
            store.save_themes(connection, themes)
            store.replace_signals(connection, signals)
            store.save_catalog(connection, catalog)
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
            catalog = store.load_catalog(connection)
            context = store.load_context(connection)

        collected = intel.collect(intel.sources_for(signals))
        market_signals = MarketResearchAgent().analyze(collected, themes)
        user_intelligence = UserIntelligenceAgent().analyze(collected, themes)
        competitor_intelligence = CompetitorIntelligenceAgent().analyze(catalog, collected)
        candidates = detect_candidates(collected, themes, context.audience)
        drafted = run_engine(collected, themes, context.audience)
        _link_candidates(candidates, drafted)
        _attach_market(drafted, market_signals)
        _attach_users(drafted, user_intelligence)
        _attach_competitors(drafted, competitor_intelligence)
        graph = build_opportunity_graph(
            context,
            drafted,
            market_signals,
            user_intelligence,
            competitor_intelligence,
        )
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
            user_intelligence=user_intelligence,
            competitor_intelligence=competitor_intelligence,
            candidates=candidates,
        )
        with store.open_db(self.home) as connection:
            report.opportunities = store.replace_opportunities(connection, drafted)
            store.replace_market_signals(connection, market_signals)
            store.save_user_intelligence(connection, user_intelligence)
            store.save_competitor_intelligence(connection, competitor_intelligence)
            store.save_candidates(connection, candidates)
            store.save_graph(connection, graph)
            store.record_cycle(connection, report)
        return report

    def context(self) -> ProductContext:
        with store.open_db(self.home) as connection:
            return store.load_context(connection)

    def signals(self):
        with store.open_db(self.home) as connection:
            return store.list_signals(connection)

    def user_intelligence(self):
        with store.open_db(self.home) as connection:
            return store.load_user_intelligence(connection)

    def opportunity_graph(self) -> OpportunityGraph | None:
        with store.open_db(self.home) as connection:
            return store.load_graph(connection)

    def candidates(self) -> list[OpportunityCandidate]:
        with store.open_db(self.home) as connection:
            return store.load_candidates(connection)

    def competitor_intelligence(self) -> CompetitorIntelligence | None:
        with store.open_db(self.home) as connection:
            return store.load_competitor_intelligence(connection)

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


def _attach_users(opportunities: list[Opportunity], report) -> None:
    if report is None:
        return
    by_theme = {cluster.theme: cluster for cluster in report.clusters}
    for opportunity in opportunities:
        cluster = by_theme.get(opportunity.theme)
        if cluster is None:
            opportunity.user = None
            continue
        opportunity.user = _user_brief(cluster, report.feedback_count)


def _link_candidates(candidates: list[OpportunityCandidate], opportunities: list[Opportunity]) -> None:
    by_theme = {opportunity.theme: opportunity.id for opportunity in opportunities}
    for candidate in candidates:
        candidate.review_id = by_theme.get(candidate.theme, "")


def _attach_competitors(
    opportunities: list[Opportunity],
    report: CompetitorIntelligence | None,
) -> None:
    if report is None:
        return
    for opportunity in opportunities:
        match = next(
            (gap for gap in report.gaps if opportunity.theme in gap.themes),
            None,
        )
        if match is None:
            opportunity.competitor = None
            continue
        opportunity.competitor = CompetitorBrief(race=report.race, gap=match.statement)


def _user_brief(cluster: ProblemCluster, feedback_count: int) -> UserBrief:
    return UserBrief(
        label=cluster.label,
        share=cluster.share,
        volume=cluster.volume,
        feedback_count=feedback_count,
        unmet=cluster.unmet,
        unmet_need=cluster.unmet_need,
    )
