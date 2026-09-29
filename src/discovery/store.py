"""SQLite memory for signals, opportunities, and human review."""

import json
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from discovery.models import (
    CompetitorCatalog,
    CompetitorIntelligence,
    CycleReport,
    OpportunityCandidate,
    OpportunityGraph,
    MarketSignal,
    Opportunity,
    UserIntelligence,
    ProductContext,
    ReviewEntry,
    ReviewStatus,
    Signal,
    Theme,
)
from discovery.paths import home

DEFAULT_CONTEXT = ProductContext(
    name="Untitled product",
    category="Unspecified",
    audience="Unspecified",
    mission="Turn gathered evidence into product opportunities a person can review.",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@contextmanager
def open_db(root: Path | None = None) -> Iterator[object]:
    import sqlite3

    directory = root or home()
    directory.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(directory / "discovery.db")
    connection.row_factory = sqlite3.Row
    try:
        _migrate(connection)
        yield connection
        connection.commit()
    finally:
        connection.close()


def _migrate(connection: object) -> None:
    connection.executescript(
        """
        create table if not exists signals (
            id text primary key,
            payload text not null,
            updated_at text not null
        );
        create table if not exists opportunities (
            id text primary key,
            payload text not null,
            status text not null,
            review_note text not null default '',
            updated_at text not null
        );
        create table if not exists reviews (
            id integer primary key autoincrement,
            opportunity_id text not null,
            action text not null,
            note text not null,
            created_at text not null
        );
        create table if not exists cycles (
            id integer primary key autoincrement,
            ran_at text not null,
            signal_count integer not null,
            opportunity_count integer not null,
            summary text not null
        );
        create table if not exists market_signals (
            id text primary key,
            payload text not null,
            updated_at text not null
        );
        create table if not exists meta (
            key text primary key,
            value text not null
        );
        """
    )


def upsert_signals(connection: object, signals: list[Signal]) -> None:
    stamp = utc_now()
    for signal in signals:
        connection.execute(
            """
            insert into signals (id, payload, updated_at) values (?, ?, ?)
            on conflict(id) do update set payload = excluded.payload, updated_at = excluded.updated_at
            """,
            (signal.id, signal.model_dump_json(), stamp),
        )


def replace_signals(connection: object, signals: list[Signal]) -> None:
    connection.execute("delete from signals")
    upsert_signals(connection, signals)


def list_signals(connection: object) -> list[Signal]:
    rows = connection.execute("select payload from signals order by id")
    return [Signal.model_validate_json(row["payload"]) for row in rows]


def save_context(connection: object, context: ProductContext) -> None:
    _set_meta(connection, "context", context.model_dump_json())


def load_context(connection: object) -> ProductContext:
    raw = _get_meta(connection, "context")
    if raw is None:
        return DEFAULT_CONTEXT
    return ProductContext.model_validate_json(raw)


def save_themes(connection: object, themes: list[Theme]) -> None:
    payload = json.dumps([theme.model_dump(mode="json") for theme in themes])
    _set_meta(connection, "themes", payload)


def load_themes(connection: object) -> list[Theme]:
    raw = _get_meta(connection, "themes")
    if not raw:
        return []
    return [Theme.model_validate(item) for item in json.loads(raw)]


def replace_opportunities(connection: object, opportunities: list[Opportunity]) -> list[Opportunity]:
    existing = {
        row["id"]: row
        for row in connection.execute("select id, status, review_note from opportunities")
    }
    saved: list[Opportunity] = []
    for opportunity in opportunities:
        prior = existing.get(opportunity.id)
        if prior is not None:
            opportunity.status = ReviewStatus(prior["status"])
            opportunity.review_note = prior["review_note"]
        saved.append(opportunity)

    connection.execute("delete from opportunities")
    stamp = utc_now()
    for opportunity in saved:
        connection.execute(
            """
            insert into opportunities (id, payload, status, review_note, updated_at)
            values (?, ?, ?, ?, ?)
            """,
            (
                opportunity.id,
                opportunity.model_dump_json(),
                opportunity.status.value,
                opportunity.review_note,
                stamp,
            ),
        )
    return saved


def list_opportunities(connection: object) -> list[Opportunity]:
    rows = connection.execute("select payload, status, review_note from opportunities")
    opportunities = []
    for row in rows:
        opportunity = Opportunity.model_validate_json(row["payload"])
        opportunity.status = ReviewStatus(row["status"])
        opportunity.review_note = row["review_note"]
        opportunities.append(opportunity)
    order = {"pursue": 0, "investigate": 1, "park": 2}
    opportunities.sort(
        key=lambda item: (order[item.verdict.value], -item.scores.opportunity, item.id)
    )
    return opportunities


def get_opportunity(connection: object, opportunity_id: str) -> Opportunity | None:
    row = connection.execute(
        "select payload, status, review_note from opportunities where id = ?",
        (opportunity_id,),
    ).fetchone()
    if row is None:
        return None
    opportunity = Opportunity.model_validate_json(row["payload"])
    opportunity.status = ReviewStatus(row["status"])
    opportunity.review_note = row["review_note"]
    return opportunity


def apply_review(
    connection: object,
    opportunity_id: str,
    status: ReviewStatus,
    note: str,
) -> Opportunity | None:
    opportunity = get_opportunity(connection, opportunity_id)
    if opportunity is None:
        return None
    opportunity.status = status
    opportunity.review_note = note
    stamp = utc_now()
    connection.execute(
        """
        update opportunities
        set payload = ?, status = ?, review_note = ?, updated_at = ?
        where id = ?
        """,
        (opportunity.model_dump_json(), status.value, note, stamp, opportunity_id),
    )
    connection.execute(
        """
        insert into reviews (opportunity_id, action, note, created_at)
        values (?, ?, ?, ?)
        """,
        (opportunity_id, status.value, note, stamp),
    )
    return opportunity


def replace_market_signals(connection: object, signals: list[MarketSignal]) -> list[MarketSignal]:
    connection.execute("delete from market_signals")
    stamp = utc_now()
    for signal in signals:
        connection.execute(
            """
            insert into market_signals (id, payload, updated_at)
            values (?, ?, ?)
            """,
            (signal.id, signal.model_dump_json(), stamp),
        )
    return signals


def save_user_intelligence(connection: object, report: UserIntelligence) -> None:
    _set_meta(connection, "user_intelligence", report.model_dump_json())


def load_user_intelligence(connection: object) -> UserIntelligence | None:
    raw = _get_meta(connection, "user_intelligence")
    if not raw:
        return None
    return UserIntelligence.model_validate_json(raw)


def save_catalog(connection: object, catalog: CompetitorCatalog) -> None:
    _set_meta(connection, "competitor_catalog", catalog.model_dump_json())


def load_catalog(connection: object) -> CompetitorCatalog:
    raw = _get_meta(connection, "competitor_catalog")
    if not raw:
        return CompetitorCatalog()
    return CompetitorCatalog.model_validate_json(raw)


def save_candidates(connection: object, candidates: list[OpportunityCandidate]) -> None:
    payload = [candidate.model_dump(mode="json") for candidate in candidates]
    _set_meta(connection, "opportunity_candidates", json.dumps(payload))


def load_candidates(connection: object) -> list[OpportunityCandidate]:
    raw = _get_meta(connection, "opportunity_candidates")
    if not raw:
        return []
    return [OpportunityCandidate.model_validate(item) for item in json.loads(raw)]


def save_graph(connection: object, graph: OpportunityGraph) -> None:
    _set_meta(connection, "opportunity_graph", graph.model_dump_json())


def load_graph(connection: object) -> OpportunityGraph | None:
    raw = _get_meta(connection, "opportunity_graph")
    if not raw:
        return None
    return OpportunityGraph.model_validate_json(raw)


def save_competitor_intelligence(connection: object, report: CompetitorIntelligence) -> None:
    _set_meta(connection, "competitor_intelligence", report.model_dump_json())


def load_competitor_intelligence(connection: object) -> CompetitorIntelligence | None:
    raw = _get_meta(connection, "competitor_intelligence")
    if not raw:
        return None
    return CompetitorIntelligence.model_validate_json(raw)


def list_market_signals(connection: object) -> list[MarketSignal]:
    rows = connection.execute("select payload from market_signals")
    signals = [MarketSignal.model_validate_json(row["payload"]) for row in rows]
    signals.sort(key=lambda item: (-item.strength, item.id))
    return signals


def list_reviews(connection: object, opportunity_id: str) -> list[ReviewEntry]:
    rows = connection.execute(
        """
        select opportunity_id, action, note, created_at
        from reviews
        where opportunity_id = ?
        order by id
        """,
        (opportunity_id,),
    )
    return [
        ReviewEntry(
            opportunity_id=row["opportunity_id"],
            action=ReviewStatus(row["action"]),
            note=row["note"],
            created_at=row["created_at"],
        )
        for row in rows
    ]


def record_cycle(connection: object, report: CycleReport) -> None:
    connection.execute(
        """
        insert into cycles (ran_at, signal_count, opportunity_count, summary)
        values (?, ?, ?, ?)
        """,
        (
            report.ran_at,
            report.signal_count,
            report.opportunity_count,
            json.dumps(report.by_verdict),
        ),
    )


def latest_cycle(connection: object) -> dict[str, object] | None:
    row = connection.execute(
        """
        select ran_at, signal_count, opportunity_count, summary
        from cycles
        order by id desc
        limit 1
        """
    ).fetchone()
    if row is None:
        return None
    return {
        "ran_at": row["ran_at"],
        "signal_count": row["signal_count"],
        "opportunity_count": row["opportunity_count"],
        "by_verdict": json.loads(row["summary"]),
    }


def _set_meta(connection: object, key: str, value: str) -> None:
    connection.execute(
        """
        insert into meta (key, value) values (?, ?)
        on conflict(key) do update set value = excluded.value
        """,
        (key, value),
    )


def _get_meta(connection: object, key: str) -> str | None:
    row = connection.execute("select value from meta where key = ?", (key,)).fetchone()
    if row is None:
        return None
    return str(row["value"])
