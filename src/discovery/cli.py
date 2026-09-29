"""Command line for ingesting evidence and running discovery cycles."""

import argparse
import os
import sys
import time
from pathlib import Path

from pydantic import ValidationError

from discovery.agent import DiscoveryAgent
from discovery.brief import render_markdown
from discovery.models import CycleReport
from discovery.paths import inbox_dir
from discovery.present import VERDICT_LABELS, percent


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="discovery",
        description="Turn market, user, and product evidence into product opportunities.",
    )
    parser.add_argument(
        "--home",
        type=Path,
        help="Workspace directory. Defaults to .discovery in the current directory.",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("demo", help="Load the Northstar sample and run one cycle")

    ingest = commands.add_parser("ingest", help="Add signals from a JSON file or directory")
    ingest.add_argument("path", type=Path)

    commands.add_parser("run", help="Run the opportunity engine on stored signals")
    commands.add_parser("list", help="List the current opportunities")
    commands.add_parser("market", help="Print market signals from the latest cycle")

    brief = commands.add_parser("brief", help="Print a product-manager memo")
    brief.add_argument("opportunity_id")

    review = commands.add_parser("review", help="Record a human decision")
    review.add_argument("opportunity_id")
    review.add_argument("action", choices=["approved", "rejected", "needs_evidence"])
    review.add_argument("--note", default="")

    serve = commands.add_parser("serve", help="Open the review board")
    serve.add_argument("--port", type=int, default=8000)
    serve.add_argument("--host", default="127.0.0.1")

    watch = commands.add_parser("watch", help="Re-run when JSON files land in data/inbox")
    watch.add_argument("--interval", type=int, default=30)

    args = parser.parse_args(argv)
    if args.home is not None:
        os.environ["DISCOVERY_HOME"] = str(args.home)
    agent = DiscoveryAgent(args.home)
    try:
        return _dispatch(agent, args)
    except (ValueError, FileNotFoundError, ValidationError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


def _dispatch(agent: DiscoveryAgent, args: argparse.Namespace) -> int:
    if args.command == "demo":
        _print_report(agent.demo(), agent)
        return 0
    if args.command == "ingest":
        count = agent.ingest(args.path)
        print(f"Ingested {count} signals from {args.path}")
        return 0
    if args.command == "run":
        _print_report(agent.run_cycle(), agent)
        return 0
    if args.command == "list":
        _print_list(agent)
        return 0
    if args.command == "market":
        _print_market(agent.market_signals())
        return 0
    if args.command == "brief":
        opportunity = agent.opportunity(args.opportunity_id)
        if opportunity is None:
            raise ValueError(f"No opportunity named {args.opportunity_id}")
        print(render_markdown(opportunity, agent.context()))
        return 0
    if args.command == "review":
        opportunity = agent.apply_review(args.opportunity_id, args.action, args.note)
        if opportunity is None:
            raise ValueError(f"No opportunity named {args.opportunity_id}")
        print(f"{opportunity.id} is now {opportunity.status.value}")
        return 0
    if args.command == "serve":
        import uvicorn

        uvicorn.run(
            "discovery.web.app:app",
            host=args.host,
            port=args.port,
            factory=False,
        )
        return 0
    if args.command == "watch":
        return _watch(agent, args.interval)
    raise ValueError(f"Unknown command {args.command}")


def _print_report(report: CycleReport, agent: DiscoveryAgent) -> None:
    context = agent.context()
    counts = report.pillar_counts
    print(f"{context.name} discovery cycle")
    print(
        f"{report.signal_count} signals "
        f"(market {counts.get('market', 0)}, user {counts.get('user', 0)}, "
        f"product {counts.get('product', 0)}) "
        f"-> {report.opportunity_count} opportunities"
    )
    for opportunity in report.opportunities:
        print(
            f"  {VERDICT_LABELS[opportunity.verdict.value]:<12} "
            f"{percent(opportunity.scores.opportunity):>3}  "
            f"{opportunity.status.value:<16} {opportunity.title}"
        )
    if report.market_signals:
        print()
        _print_market(report.market_signals)


def _print_list(agent: DiscoveryAgent) -> None:
    opportunities = agent.opportunities()
    signals = agent.signals()
    if not opportunities:
        print("No opportunities yet. Run `discovery demo` or `discovery run`.")
        return
    _print_report(
        CycleReport(
            ran_at="",
            signal_count=len(signals),
            pillar_counts={
                pillar: sum(1 for signal in signals if signal.pillar.value == pillar)
                for pillar in ("market", "user", "product")
            },
            opportunity_count=len(opportunities),
            by_verdict={},
            opportunities=opportunities,
        ),
        agent,
    )


def _print_market(signals) -> None:
    if not signals:
        print("No market signals yet. Run `discovery demo` or `discovery run`.")
        return
    print(f"Market research ({len(signals)} signals)")
    for signal in signals:
        print(f"\nTrend: {signal.trend}")
        print("Evidence:")
        for item in signal.evidence:
            print(f"- {item.statement}")
        print(f"Potential implication:\n{signal.implication}")


def _watch(agent: DiscoveryAgent, interval: int) -> int:
    inbox = inbox_dir()
    inbox.mkdir(parents=True, exist_ok=True)
    print(f"Watching {inbox} every {interval}s. Stop with Ctrl-C.")
    previous: tuple[tuple[str, int], ...] | None = None
    while True:
        try:
            snapshot = tuple(
                sorted((path.name, path.stat().st_mtime_ns) for path in inbox.glob("*.json"))
            )
            if snapshot and snapshot != previous:
                try:
                    count = agent.ingest(inbox)
                    print(f"Ingested {count} signals")
                    _print_report(agent.run_cycle(), agent)
                except (ValueError, OSError, ValidationError) as exc:
                    print(f"error: {exc}", file=sys.stderr)
            previous = snapshot
            time.sleep(max(interval, 1))
        except KeyboardInterrupt:
            print("\nStopped.")
            return 0
