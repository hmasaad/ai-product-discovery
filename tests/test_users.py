from datetime import date
from pathlib import Path

from discovery.agents.users import UserIntelligenceAgent, channel_for
from discovery.intel import load_signals, load_themes
from discovery.models import IntelPillar, Signal, SignalKind, Theme, UserChannel

SAMPLE = Path(__file__).resolve().parents[1] / "data" / "sample"


def _item(theme_id: str, label: str, volume: int) -> tuple[Theme, Signal]:
    keyword = label.lower()
    theme = Theme(
        id=theme_id,
        label=label,
        keywords=[keyword],
        problem=f"People cannot get {keyword} done.",
        idea_title=label,
        idea_summary=f"Fix {keyword}.",
    )
    signal = Signal(
        id=theme_id,
        pillar=IntelPillar.user,
        kind=SignalKind.review,
        title=f"{label} complaints",
        body=f"App reviews keep mentioning {keyword}.",
        source="App store",
        observed_at=date(2026, 9, 1),
        strength=0.8,
        polarity="pain",
        volume=volume,
    )
    return theme, signal


def test_clusters_complaints_by_share_of_feedback():
    specs = [
        ("authentication", "Authentication", 231),
        ("performance", "Performance", 180),
        ("reporting", "Reporting", 141),
        ("onboarding", "Onboarding", 116),
        ("notifications", "Notifications", 90),
    ]
    themes = []
    signals = []
    for theme_id, label, volume in specs:
        theme, signal = _item(theme_id, label, volume)
        themes.append(theme)
        signals.append(signal)
    signals.append(
        Signal(
            id="other",
            pillar=IntelPillar.user,
            kind=SignalKind.feedback,
            title="Miscellaneous praise",
            body="The export button is fine.",
            source="In-app feedback",
            observed_at=date(2026, 9, 2),
            strength=0.2,
            polarity="adoption",
            volume=526,
        )
    )
    report = UserIntelligenceAgent().analyze(signals, themes)
    assert report.feedback_count == 1284
    by_label = {cluster.label: cluster for cluster in report.clusters}
    assert [round(by_label[label].share * 100) for _, label, _ in specs] == [18, 14, 11, 9, 7]
    assert all(cluster.unmet for cluster in report.unmet_needs)
    assert by_label["Authentication"].unmet_need == "People cannot get authentication done."
    assert report.other_volume == 526


def test_northstar_separates_unmet_needs_from_weak_requests():
    report = UserIntelligenceAgent().analyze(
        load_signals(SAMPLE / "signals.json"),
        load_themes(SAMPLE / "themes.json"),
    )
    by_label = {cluster.label: cluster for cluster in report.clusters}
    assert report.feedback_count == 8
    assert round(by_label["Event instrumentation"].share * 100) == 25
    assert by_label["Event instrumentation"].unmet
    assert UserChannel.app_review in by_label["Event instrumentation"].channels
    assert UserChannel.community in by_label["Event instrumentation"].channels
    assert any("stall" in item.lower() for item in by_label["Event instrumentation"].corroborated_by)
    assert not by_label["Dark theme"].unmet
    assert "Session replay" not in by_label
    assert [cluster.label for cluster in report.unmet_needs] == [
        "Event instrumentation",
        "Self-serve analysis",
        "Grounded insights",
    ]


def test_channels_follow_the_source():
    review = Signal(
        id="review",
        pillar=IntelPillar.user,
        kind=SignalKind.review,
        title="Slow",
        body="The app is slow.",
        source="G2",
        observed_at=date(2026, 9, 1),
    )
    ticket = review.model_copy(update={"id": "ticket", "kind": SignalKind.feedback, "source": "Support"})
    interview = review.model_copy(update={"id": "interview", "kind": SignalKind.feedback, "source": "Customer interview"})
    forum = review.model_copy(update={"id": "forum", "kind": SignalKind.forum, "source": "r/ProductManagement"})
    analytics = review.model_copy(
        update={"id": "analytics", "pillar": IntelPillar.product, "kind": SignalKind.analytics, "source": "Warehouse"}
    )
    assert channel_for(review) is UserChannel.app_review
    assert channel_for(ticket) is UserChannel.support_ticket
    assert channel_for(interview) is UserChannel.interview
    assert channel_for(forum) is UserChannel.community
    assert channel_for(analytics) is UserChannel.product_analytics
