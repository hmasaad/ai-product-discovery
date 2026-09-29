"""Local review board."""

from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from discovery.agent import DiscoveryAgent
from discovery.models import Opportunity, ReviewStatus
from discovery.present import (
    CHANNEL_LABELS,
    FACET_LABELS,
    GAP_LABELS,
    KIND_LABELS,
    PILLAR_LABELS,
    NODE_LABELS,
    POLARITY_LABELS,
    STATUS_LABELS,
    VERDICT_LABELS,
    format_date,
    format_metric,
    format_timestamp,
    percent,
)

WEB_ROOT = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(WEB_ROOT / "templates"))
templates.env.filters["pct"] = percent
templates.env.filters["commas"] = lambda value: f"{int(value):,}"
templates.env.filters["metric"] = lambda value, key: format_metric(key, value)
templates.env.filters["pretty_date"] = format_date
templates.env.filters["pretty_time"] = format_timestamp

LABELS = {
    "gap": GAP_LABELS,
    "verdict": VERDICT_LABELS,
    "status": STATUS_LABELS,
    "pillar": PILLAR_LABELS,
    "kind": KIND_LABELS,
    "polarity": POLARITY_LABELS,
    "facet": FACET_LABELS,
    "channel": CHANNEL_LABELS,
    "node": NODE_LABELS,
}


def create_app() -> FastAPI:
    app = FastAPI(title="AI Product Discovery")
    app.mount("/static", StaticFiles(directory=str(WEB_ROOT / "static")), name="static")

    @app.get("/favicon.ico")
    def favicon() -> Response:
        return Response(status_code=204)

    @app.get("/", response_class=HTMLResponse)
    def board(
        request: Request,
        verdict: str | None = None,
        status: str | None = None,
    ) -> HTMLResponse:
        return _board(request, verdict=verdict, status=status, queue=False)

    @app.get("/market", response_class=HTMLResponse)
    def market(request: Request) -> HTMLResponse:
        agent = DiscoveryAgent()
        return _render(
            request,
            "market.html",
            {
                "context": agent.context(),
                "signals": agent.market_signals(),
                "signal_count": len(agent.signals()),
                "labels": LABELS,
                "market": True,
                "queue": False,
            },
        )

    @app.post("/cycle")
    def cycle(request: Request) -> RedirectResponse:
        DiscoveryAgent().run_cycle()
        from urllib.parse import urlparse

        path = urlparse(request.headers.get("referer", "")).path
        if path in {"/market", "/users", "/competitors", "/detect", "/validate", "/graph"}:
            return RedirectResponse(path, status_code=303)
        return RedirectResponse("/", status_code=303)

    @app.get("/users", response_class=HTMLResponse)
    def users(request: Request) -> HTMLResponse:
        agent = DiscoveryAgent()
        return _render(
            request,
            "users.html",
            {
                "context": agent.context(),
                "report": agent.user_intelligence(),
                "signal_count": len(agent.signals()),
                "labels": LABELS,
                "users": True,
                "market": False,
                "queue": False,
            },
        )

    @app.get("/competitors", response_class=HTMLResponse)
    def competitors(request: Request) -> HTMLResponse:
        agent = DiscoveryAgent()
        return _render(
            request,
            "competitors.html",
            {
                "context": agent.context(),
                "report": agent.competitor_intelligence(),
                "signal_count": len(agent.signals()),
                "labels": LABELS,
                "competitors": True,
                "market": False,
                "users": False,
                "queue": False,
            },
        )

    @app.get("/detect", response_class=HTMLResponse)
    def detect(request: Request) -> HTMLResponse:
        agent = DiscoveryAgent()
        return _render(
            request,
            "detect.html",
            {
                "context": agent.context(),
                "candidates": agent.candidates(),
                "signal_count": len(agent.signals()),
                "labels": LABELS,
                "detect": True,
                "market": False,
                "users": False,
                "competitors": False,
                "queue": False,
            },
        )

    @app.get("/validate", response_class=HTMLResponse)
    def validate(request: Request) -> HTMLResponse:
        agent = DiscoveryAgent()
        return _render(
            request,
            "validate.html",
            {
                "context": agent.context(),
                "opportunities": agent.opportunities(),
                "signal_count": len(agent.signals()),
                "labels": LABELS,
                "validate": True,
                "market": False,
                "users": False,
                "competitors": False,
                "detect": False,
                "queue": False,
            },
        )

    @app.get("/graph", response_class=HTMLResponse)
    def graph_page(request: Request, opportunity: str | None = None) -> HTMLResponse:
        from discovery.engine.graph import trace

        agent = DiscoveryAgent()
        opportunities = agent.opportunities()
        selected = opportunity or _default_opportunity(opportunities)
        stored = agent.opportunity_graph()
        traced = trace(stored, selected) if stored is not None and selected else None
        return _render(
            request,
            "graph.html",
            {
                "context": agent.context(),
                "opportunities": opportunities,
                "selected": selected,
                "trace": traced,
                "signal_count": len(agent.signals()),
                "labels": LABELS,
                "graph": True,
                "market": False,
                "users": False,
                "competitors": False,
                "detect": False,
                "queue": False,
            },
        )

    @app.get("/queue", response_class=HTMLResponse)
    def queue(request: Request) -> HTMLResponse:
        return _board(request, verdict=None, status=ReviewStatus.approved.value, queue=True)

    @app.get("/opportunities/{opportunity_id}", response_class=HTMLResponse)
    def brief(request: Request, opportunity_id: str) -> HTMLResponse:
        agent = DiscoveryAgent()
        opportunity = agent.opportunity(opportunity_id)
        if opportunity is None:
            return HTMLResponse("Opportunity not found", status_code=404)
        return _render(
            request,
            "brief.html",
            {
                "context": agent.context(),
                "opportunity": opportunity,
                "reviews": agent.reviews(opportunity_id),
                "labels": LABELS,
                "trace": _trace_for(agent, opportunity_id),
                "next_url": f"/opportunities/{opportunity_id}",
            },
        )

    @app.post("/demo")
    def demo() -> RedirectResponse:
        DiscoveryAgent().demo()
        return RedirectResponse("/", status_code=303)

    @app.post("/opportunities/{opportunity_id}/review")
    def review(
        opportunity_id: str,
        action: str = Form(...),
        note: str = Form(""),
        next_url: str = Form("/"),
    ) -> RedirectResponse:
        if action not in {
            ReviewStatus.approved.value,
            ReviewStatus.rejected.value,
            ReviewStatus.needs_evidence.value,
        }:
            raise HTTPException(status_code=400, detail="Unknown review action")
        updated = DiscoveryAgent().apply_review(opportunity_id, action, note)
        if updated is None:
            raise HTTPException(status_code=404, detail="Opportunity not found")
        return RedirectResponse(_safe_next(next_url), status_code=303)

    return app


def _board(
    request: Request,
    verdict: str | None,
    status: str | None,
    queue: bool,
) -> HTMLResponse:
    agent = DiscoveryAgent()
    signals = agent.signals()
    opportunities = agent.opportunities()
    pillar_counts = {
        "market": sum(1 for signal in signals if signal.pillar.value == "market"),
        "user": sum(1 for signal in signals if signal.pillar.value == "user"),
        "product": sum(1 for signal in signals if signal.pillar.value == "product"),
    }
    verdict_counts = {name: 0 for name in VERDICT_LABELS}
    status_counts = {name: 0 for name in STATUS_LABELS}
    for opportunity in opportunities:
        verdict_counts[opportunity.verdict.value] += 1
        status_counts[opportunity.status.value] += 1

    visible = _filter_opportunities(opportunities, verdict, status, hide_rejected=not queue and status is None)
    return _render(
        request,
        "board.html",
        {
            "context": agent.context(),
            "opportunities": visible,
            "signal_count": len(signals),
            "pillar_counts": pillar_counts,
            "verdict_counts": verdict_counts,
            "status_counts": status_counts,
            "opportunity_count": len(opportunities),
            "last_cycle": agent.latest_cycle(),
            "labels": LABELS,
            "queue": queue,
            "active_verdict": verdict,
            "active_status": status,
            "pursue_count": verdict_counts["pursue"],
        },
    )


def _default_opportunity(opportunities: list[Opportunity]) -> str:
    pursue = next((item for item in opportunities if item.verdict.value == "pursue"), None)
    if pursue is not None:
        return pursue.id
    return opportunities[0].id if opportunities else ""


def _trace_for(agent: DiscoveryAgent, opportunity_id: str):
    from discovery.engine.graph import trace

    stored = agent.opportunity_graph()
    if stored is None:
        return None
    return trace(stored, opportunity_id)


def _filter_opportunities(
    opportunities: list[Opportunity],
    verdict: str | None,
    status: str | None,
    hide_rejected: bool,
) -> list[Opportunity]:
    rows = opportunities
    if status:
        rows = [item for item in rows if item.status.value == status]
    elif hide_rejected:
        rows = [item for item in rows if item.status is not ReviewStatus.rejected]
    if verdict:
        rows = [item for item in rows if item.verdict.value == verdict]
    return rows


def _safe_next(target: str) -> str:
    if not target.startswith("/") or target.startswith("//"):
        return "/"
    return target


def _render(request: Request, name: str, context: dict) -> HTMLResponse:
    payload = {"request": request, **context}
    return templates.TemplateResponse(request, name, payload)


app = create_app()
