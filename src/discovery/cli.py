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
from discovery.agents.memory import QUESTIONS
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
    loop = commands.add_parser("loop", help="Follow an opportunity through the product loop")
    loop.add_argument("opportunity_id", nargs="?")
    engine = commands.add_parser("engine", help="Run the opportunity intelligence engine")
    engine.add_argument("opportunity_id", nargs="?")
    experiment = commands.add_parser("experiment", help="Design the cheapest experiment for an opportunity")
    experiment.add_argument("opportunity_id", nargs="?")
    commands.add_parser("memory", help="Show what the product memory remembers")
    ask = commands.add_parser("ask", help="Ask the product memory a question")
    ask.add_argument("question")

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
    if args.command == "loop":
        _print_loop(agent, args.opportunity_id)
        return 0
    if args.command == "engine":
        _print_engine(agent, args.opportunity_id)
        return 0
    if args.command == "experiment":
        _print_experiment(agent, args.opportunity_id)
        return 0
    if args.command == "memory":
        _print_memory(agent)
        return 0
    if args.command == "ask":
        answer = agent.ask(args.question)
        print(answer.question)
        print(answer.answer)
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


def _print_engine(agent: DiscoveryAgent, opportunity_id: str | None) -> None:
    opportunities = agent.opportunities()
    if opportunity_id:
        opportunities = [item for item in opportunities if item.id == opportunity_id]
        if not opportunities:
            raise ValueError(f"No opportunity named {opportunity_id}")
    elif opportunities:
        approved = next((item for item in opportunities if item.status.value == "approved"), None)
        pursue = next((item for item in opportunities if item.verdict.value == "pursue"), None)
        opportunities = [approved or pursue or opportunities[0]]
    if not opportunities:
        print("No opportunity intelligence yet. Run `discovery demo` or `discovery run`.")
        return
    report = agent.intelligence(opportunities[0].id)
    if report is None:
        return
    print(report.title)
    for index, stage in enumerate(report.stages, start=1):
        print(f"\n{index}. {stage.capability}")
        print(stage.summary)
        for line in stage.lines:
            print(f"  {line}")


def _print_experiment(agent: DiscoveryAgent, opportunity_id: str | None) -> None:
    opportunities = agent.opportunities()
    if opportunity_id:
        opportunities = [item for item in opportunities if item.id == opportunity_id]
        if not opportunities:
            raise ValueError(f"No opportunity named {opportunity_id}")
    elif opportunities:
        approved = next((item for item in opportunities if item.status.value == "approved"), None)
        pursue = next((item for item in opportunities if item.verdict.value == "pursue"), None)
        opportunities = [approved or pursue or opportunities[0]]
    if not opportunities:
        print("No experiment yet. Run `discovery demo` or `discovery run`.")
        return
    portfolio = agent.portfolio()
    if portfolio.rows:
        print("Experiment portfolio")
        for row in portfolio.rows:
            print(f"  {row.name} — {row.status} — {row.risk}")
        for note in portfolio.notes:
            print(f"\n{note.topic}")
            print(note.summary)
        print()
    plan = agent.experiment(opportunities[0].id)
    if plan is None:
        return
    print(plan.title)
    for index, stage in enumerate(plan.stages, start=1):
        print(f"\n{index}. {stage.title}")
        print(stage.summary)
        if stage.title == "Hypothesis Generator":
            for item in plan.hypotheses:
                print(f"  {item.code}: {item.statement}")
                print(f"  Target segment: {item.target_segment}")
                print(f"  Expected behavior: {item.expected_behavior}")
                print(f"  Metric: {item.metric}")
                print(f"  Threshold: {item.threshold}")
                print(f"  Time period: {item.time_period}")
                print(f"  Confidence: {item.confidence}")
                print(f"  Evidence: {item.evidence}")
        if stage.title == "Experiment Specification":
            for spec in plan.specifications:
                print(f"  Experiment: {spec.name}")
                print(f"  Objective: {spec.objective}")
                print(f"  Hypothesis: {spec.hypothesis}")
                print(f"  Target audience: {spec.target_audience}")
                print(f"  Variant: {spec.variant}")
                print(f"  Control: {spec.control}")
                print(f"  Primary metric: {spec.primary_metric}")
                print(f"  Secondary metric: {spec.secondary_metric}")
                print(f"  Guardrails: {', '.join(spec.guardrails)}")
                print(f"  Sample size: {spec.sample_size}")
                print(f"  Duration: {spec.duration}")
                print(f"  Decision threshold: {spec.decision_threshold}")
                print(f"  Risks: {'; '.join(spec.risks)}")
                print(f"  Expected learning: {spec.expected_learning}")
                print(f"  Possible outcomes: {' → '.join(spec.outcomes)}")
        if stage.title == "Experiment Designer":
            print(f"  Unknown: {plan.unknown}")
            for choice in plan.choices:
                mark = "selected" if choice.selected else "not selected"
                print(f"  {choice.code}. {choice.name}. Cost: {choice.cost}. Information: {choice.information}. {mark}.")
            for row in plan.catalog:
                print(f"  {row}")
        for line in stage.lines:
            print(f"  {line}")
    if plan.execution is not None:
        print("\nExperiment execution")
        for index, step in enumerate(plan.execution.steps, start=1):
            gate = " approval" if step.needs_approval else ""
            print(f"{index}. {step.action} — {step.system} ({step.status}{gate})")
            print(f"  {step.summary}")
        print(f"\nMonitor: {plan.execution.monitor.status}")
        print(plan.execution.monitor.explanation)
        print(plan.execution.report)
        if plan.execution.analysis is not None:
            item = plan.execution.analysis
            print("\nResults")
            print(f"Hypothesis: {item.hypothesis}")
            print(f"Observed: {item.observed}")
            print("Evidence:")
            for line in item.supporting or ["No supporting evidence is recorded."]:
                print(f"  {line}")
            print("Contradicting evidence:")
            for line in item.contradicting or ["No contradicting evidence is recorded."]:
                print(f"  {line}")
            print(f"Interpretation: {item.interpretation}")
            print(f"Remaining uncertainty: {item.uncertainty}")
            print(f"Next experiment: {item.next_experiment}")
    if plan.memory_chain is not None:
        item = plan.memory_chain
        print("\nLearning memory")
        print(f"Opportunity: {item.opportunity}")
        print(f"Hypothesis: {item.hypothesis}")
        print(f"Experiment: {item.experiment}")
        print(f"Result: {item.result}")
        print(f"Learning: {item.learning}")
        print(f"Decision: {item.decision}")
        if plan.prior_learning is not None and plan.informed_experiment:
            print(f"Past experiment: {plan.prior_learning.experiment}")
            print(f"Past learning: {plan.prior_learning.learning}")
            print(f"New experiment: {plan.informed_experiment}")
    print(f"\n{plan.decision}")
    print(plan.pm_summary)


def _print_memory(agent: DiscoveryAgent) -> None:
    from discovery.models import MemoryKind
    from discovery.present import MEMORY_LABELS

    memory = agent.memory()
    if not memory.records:
        print("No product memory yet. Run `discovery demo` or `discovery run`.")
        return
    for kind in MemoryKind:
        records = memory.of_kind(kind)
        print(f"\n{MEMORY_LABELS[kind.value]} ({len(records)})")
        if not records:
            print("  None recorded.")
            continue
        for record in records:
            print(f"  {record.title}")
    print()
    for question in QUESTIONS:
        answer = agent.ask(question)
        print(question)
        print(answer.answer)
        print()


def _print_loop(agent: DiscoveryAgent, opportunity_id: str | None) -> None:
    opportunities = agent.opportunities()
    if opportunity_id:
        opportunities = [item for item in opportunities if item.id == opportunity_id]
        if not opportunities:
            raise ValueError(f"No opportunity named {opportunity_id}")
    elif opportunities:
        approved = next((item for item in opportunities if item.status.value == "approved"), None)
        pursue = next((item for item in opportunities if item.verdict.value == "pursue"), None)
        chosen = approved or pursue or opportunities[0]
        opportunities = [chosen]
    if not opportunities:
        print("No product loop yet. Run `discovery demo` or `discovery run`.")
        return
    for opportunity in opportunities:
        loop = agent.development_loop(opportunity.id)
        if loop is None:
            continue
        print(loop.title)
        for stage in loop.stages:
            print(f"\n{stage.title}  {stage.status.value}")
            print(stage.summary)
            for line in stage.lines:
                print(f"  {line}")
            if stage.stage.value != "discovery_return":
                print("↓")


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
        ("hypothesis", chosen.hypothesis),
        ("experiment", chosen.experiment),
        ("observation", chosen.observation),
        ("learning", chosen.learning),
        ("decision", chosen.decision),
        ("product_change", chosen.product_change),
        ("new_observation", chosen.new_observation),
        ("new_hypothesis", chosen.new_hypothesis),
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
