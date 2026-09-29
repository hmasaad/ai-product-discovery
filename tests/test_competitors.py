from datetime import date

from discovery.agents.competitors import CompetitorIntelligenceAgent
from discovery.intel import load_competitors, load_signals
from discovery.models import Capability, CapabilityKind, CatalogMove, CompetitorCatalog, CompetitorProduct
from discovery.paths import sample_dir


def _catalog() -> CompetitorCatalog:
    def feature(capability_id: str, label: str, direction: str) -> Capability:
        return Capability(
            id=capability_id,
            label=label,
            kind=CapabilityKind.feature,
            direction=direction,
        )

    def move(capability: str, observed_at: str, value: bool | int) -> CatalogMove:
        return CatalogMove(capability=capability, observed_at=date.fromisoformat(observed_at), value=value)

    return CompetitorCatalog(
        capabilities=[
            feature("ai_assistant", "AI Assistant", "AI assistance"),
            feature("offline", "Offline Mode", "offline use"),
            feature("automation", "Automation", "automation"),
            feature("analytics", "Analytics", "analytics"),
            Capability(id="integrations", label="Integrations", kind=CapabilityKind.count),
            Capability(id="pricing", label="Pricing", kind=CapabilityKind.price),
        ],
        products=[
            CompetitorProduct(
                id="product-a",
                name="Product A",
                moves=[
                    move("ai_assistant", "2024-01-01", False),
                    move("ai_assistant", "2026-01-15", True),
                    move("offline", "2026-09-01", False),
                    move("automation", "2025-01-01", False),
                    move("automation", "2026-06-01", True),
                    move("analytics", "2024-01-01", True),
                    move("integrations", "2026-09-01", 3),
                    move("pricing", "2026-09-01", 20),
                ],
            ),
            CompetitorProduct(
                id="product-b",
                name="Product B",
                moves=[
                    move("ai_assistant", "2024-06-01", False),
                    move("ai_assistant", "2026-02-01", True),
                    move("offline", "2024-06-01", True),
                    move("automation", "2026-09-01", False),
                    move("analytics", "2024-01-01", True),
                    move("integrations", "2026-09-01", 8),
                    move("pricing", "2026-09-01", 30),
                ],
            ),
            CompetitorProduct(
                id="product-c",
                name="Product C",
                moves=[
                    move("ai_assistant", "2026-09-01", False),
                    move("offline", "2024-01-01", True),
                    move("automation", "2026-09-01", False),
                    move("analytics", "2024-01-01", True),
                    move("integrations", "2026-09-01", 5),
                    move("pricing", "2026-09-01", 15),
                ],
            ),
        ],
    )


def test_matrix_matches_the_comparison():
    report = CompetitorIntelligenceAgent().analyze(_catalog())
    matrix = {row.label: row.cells for row in report.rows}
    assert report.products == ["Product A", "Product B", "Product C"]
    assert matrix["AI Assistant"] == ["✓", "✓", "✗"]
    assert matrix["Offline Mode"] == ["✗", "✓", "✓"]
    assert matrix["Automation"] == ["✓", "✗", "✗"]
    assert matrix["Analytics"] == ["✓", "✓", "✓"]
    assert matrix["Integrations"] == ["3", "8", "5"]
    assert matrix["Pricing"] == ["$20", "$30", "$15"]


def test_behavior_becomes_trajectory_direction_and_gap():
    report = CompetitorIntelligenceAgent().analyze(_catalog())
    product_a = next(read for read in report.reads if read.name == "Product A")
    product_c = next(read for read in report.reads if read.name == "Product C")

    assert "15 Jan 2026: added AI Assistant" in product_a.behavior
    assert "1 Jun 2026: added Automation" in product_a.behavior
    assert product_a.trajectory == "Added AI Assistant and Automation. Offline Mode is still absent."
    assert product_a.direction == "Heading toward AI assistance and automation."
    assert product_c.trajectory == (
        "No capability was added in the recent window. "
        "AI Assistant and Automation are still absent."
    )
    assert product_c.direction == "No recent capability change."
    assert report.race == "The field is moving toward AI assistance."
    assert "Integrations run from 3 to 8." in report.notes
    assert "Pricing runs from $15 to $30." in report.notes
    statements = [gap.statement for gap in report.gaps]
    assert "Automation is only on Product A." in statements
    assert "AI Assistant is still missing from Product C." in statements
    assert "Analytics is only on Product A." not in statements
    assert all("Analytics is absent" not in statement for statement in statements)


def test_northstar_gap_is_tracking_plans_and_signals_annotate_behavior():
    catalog = load_competitors(sample_dir() / "competitors.json")
    signals = load_signals(sample_dir() / "signals.json")
    report = CompetitorIntelligenceAgent().analyze(catalog, signals)

    tracking = next(row for row in report.rows if row.label == "Tracking plans")
    assert tracking.cells == ["✗", "✗", "✗", "✗"]
    assert any(
        gap.statement == "Tracking plans are absent from every competitor."
        and "instrumentation" in gap.themes
        for gap in report.gaps
    )
    amplitude = next(read for read in report.reads if read.name == "Amplitude")
    assert amplitude.direction == "Heading toward AI assistance."
    assert "Added AI Assistant." in amplitude.trajectory
    assert any("AI copilot" in line for line in amplitude.behavior)
    assert report.race == "Competitors are moving, but not toward the same capability."
    assert any("combines AI Assistant with Natural language." in gap.statement for gap in report.gaps)
    assert "Self-serve analysis is only on Canvas." in [gap.statement for gap in report.gaps]


def test_unknown_capability_is_rejected(tmp_path):
    path = tmp_path / "competitors.json"
    path.write_text(
        """
        {
          "capabilities": [{"id": "ai", "label": "AI Assistant", "kind": "feature"}],
          "products": [{
            "id": "a",
            "name": "Product A",
            "moves": [{"capability": "offline", "observed_at": "2026-09-01", "value": true}]
          }]
        }
        """,
        encoding="utf-8",
    )
    try:
        load_competitors(path)
    except ValueError as exc:
        assert "unknown capability offline" in str(exc)
    else:
        raise AssertionError("expected an unknown capability to be rejected")
