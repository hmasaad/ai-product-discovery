"""Command line for ingesting evidence and running discovery cycles."""

import argparse
import os
import sys
import time
from pathlib import Path

from pydantic import ValidationError

from discovery.agent import DiscoveryAgent
from discovery.brief import render_product_brief
from discovery.models import CycleReport
from discovery.paths import inbox_dir
from discovery.engine.graph import trace
from discovery.present import NODE_LABELS, VERDICT_LABELS, percent


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
    commands.add_parser("users", help="Print clustered complaints and unmet needs")
    commands.add_parser("competitors", help="Print the competitor matrix and market gaps")
    commands.add_parser("detect", help="Print every signal as an opportunity candidate")
    validate = commands.add_parser("validate", help="Show evidence for and against an opportunity")
    validate.add_argument("opportunity_id", nargs="?")
    graph = commands.add_parser("graph", help="Explain why an opportunity exists")
    graph.add_argument("opportunity_id", nargs="?")

    brief = commands.add_parser("brief", help="Print the product opportunity brief")
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
    if args.command == "users":
        _print_users(agent.user_intelligence())
        return 0
    if args.command == "competitors":
        _print_competitors(agent.competitor_intelligence())
        return 0
    if args.command == "detect":
        _print_candidates(agent.candidates())
        return 0
    if args.command == "validate":
        _print_validation(agent, args.opportunity_id)
        return 0
    if args.command == "graph":
        _print_graph(agent, args.opportunity_id)
        return 0
    if args.command == "brief":
        opportunity = agent.opportunity(args.opportunity_id)
        if opportunity is None:
            raise ValueError(f"No opportunity named {args.opportunity_id}")
        if opportunity.product_brief is None:
            raise ValueError(f"{opportunity.id} has no product opportunity brief")
        print(render_product_brief(opportunity.product_brief), end="")
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
        if opportunity.chain is not None:
            _print_chain(opportunity.chain, indent="    ")
    if report.market_signals:
        print()
        _print_market(report.market_signals)
    if report.user_intelligence is not None and report.user_intelligence.feedback_count:
        print()
        _print_users(report.user_intelligence)
    if report.competitor_intelligence is not None and report.competitor_intelligence.rows:
        print()
        _print_competitors(report.competitor_intelligence)


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


def _print_users(report) -> None:
    if report is None or report.feedback_count == 0:
        print("No user feedback yet. Run `discovery demo` or `discovery run`.")
        return
    print(f"{report.feedback_count:,} user feedback items")
    print("\nClustered problems")
    for cluster in report.clusters:
        print(f"  {cluster.label:<28} {percent(cluster.share):>3}%")
    if report.other_volume:
        share = report.other_volume / report.feedback_count
        print(f"  {'Other':<28} {percent(share):>3}%")
    print("\nUnmet needs")
    if not report.unmet_needs:
        print("  None yet.")
        return
    for cluster in report.unmet_needs:
        print(f"  {cluster.label}: {cluster.unmet_need}")


def _print_candidates(candidates) -> None:
    if not candidates:
        print("No opportunity candidates yet. Run `discovery demo` or `discovery run`.")
        return
    print(f"{len(candidates)} opportunity candidates")
    for candidate in candidates:
        print(f"\n{candidate.label}")
        _print_chain(candidate.chain)
        if candidate.review_id:
            print(f"Review: {candidate.review_id}")
        else:
            print("Review: waiting for more evidence")


def _print_validation(agent: DiscoveryAgent, opportunity_id: str | None) -> None:
    opportunities = agent.opportunities()
    if opportunity_id:
        opportunities = [item for item in opportunities if item.id == opportunity_id]
        if not opportunities:
            raise ValueError(f"No opportunity named {opportunity_id}")
    if not opportunities:
        print("Nothing to challenge yet. Run `discovery demo` or `discovery run`.")
        return
    for opportunity in opportunities:
        brief = opportunity.challenge
        print(f"\nOpportunity: {opportunity.title}")
        if brief is None:
            print("No validation yet.")
            continue
        print("\nEvidence for")
        if not brief.supporting:
            print("- None")
        for point in brief.supporting:
            print(f"✓ {point.text}")
        print("\nEvidence against")
        if not brief.contradicting:
            print("- None")
        for point in brief.contradicting:
            print(f"⚠ {point.text}")
        print(f"\n{brief.challenge}")
        print()
        for item in brief.questions:
            print(f"{item.question} {item.answer}")


def _print_graph(agent: DiscoveryAgent, opportunity_id: str | None) -> None:
    stored = agent.opportunity_graph()
    if stored is None:
        print("No opportunity graph yet. Run `discovery demo` or `discovery run`.")
        return
    if opportunity_id:
        chosen = trace(stored, opportunity_id)
        if chosen is None:
            raise ValueError(f"No opportunity named {opportunity_id}")
        _print_trace(stored, chosen)
        return
    opportunities = [
        node for node in stored.nodes if node.kind.value == "opportunity"
    ]
    if not opportunities:
        print("No opportunity graph yet. Run `discovery demo` or `discovery run`.")
        return
    for node in opportunities:
        chosen = trace(stored, node.id)
        if chosen is not None:
            _print_trace(stored, chosen)
            print()


def _print_trace(graph, chosen) -> None:
    print(chosen.why)
    print()
    for path in chosen.paths:
        print(" → ".join(_node_label(graph, node_id) for node_id in path))
    print()
    slots = (
        ("market", chosen.market),
        ("trend", chosen.trend),
        ("users", chosen.users),
        ("competitors", chosen.competitors),
        ("problem", chosen.problem),
        ("gap", chosen.gap),
        ("opportunity", chosen.opportunity),
        ("feature", chosen.feature),
        ("product", chosen.product),
        ("mvp", chosen.mvp),
        ("business_case", chosen.business_case),
    )
    for kind, node in slots:
        if node is None:
            continue
        print(f"{NODE_LABELS[kind]}: {node.title}")
        if node.detail and node.detail != node.title:
            print(f"  {node.detail}")
    print("\nSources")
    if not chosen.sources:
        print("- None attached")
        return
    for source in chosen.sources:
        print(f"- {source.title} — {source.source}")


def _node_label(graph, node_id: str) -> str:
    node = graph.node(node_id)
    if node is None:
        return node_id
    return NODE_LABELS[node.kind.value]


def _print_chain(chain, indent: str = "") -> None:
    print(f"{indent}Signal: {chain.signal}")
    print(f"{indent}Problem: {chain.problem}")
    print(f"{indent}User segment: {chain.segment}")
    print(f"{indent}Pain: {chain.pain}")
    print(f"{indent}Existing solutions: {chain.existing_solutions}")
    print(f"{indent}Gap: {chain.gap}")
    print(f"{indent}Opportunity: {chain.opportunity}")


def _print_competitors(report) -> None:
    if report is None or not report.rows:
        print("No competitor matrix yet. Add competitors.json and run a cycle.")
        return
    headers = ["", *report.products]
    table = [[row.label, *row.cells] for row in report.rows]
    widths = [max(len(row[index]) for row in [headers, *table]) for index in range(len(headers))]

    def _line(row: list[str]) -> str:
        return "  ".join(cell.ljust(widths[index]) for index, cell in enumerate(row))

    print(_line(headers))
    print("  ".join("-" * width for width in widths))
    for row in table:
        print(_line(row))
    print("\nCompetitor behavior")
    for read in report.reads:
        print(f"\n{read.name}")
        for line in read.behavior:
            print(f"- {line}")
        print(f"Feature trajectory: {read.trajectory}")
        print(f"Strategic direction: {read.direction}")
    print(f"\nFeature trajectory\n{report.race}")
    for note in report.notes:
        print(note)
    print("\nPotential market gap")
    for gap in report.gaps:
        print(f"- {gap.statement}")


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
