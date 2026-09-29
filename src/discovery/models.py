"""Shared records for evidence, themes, and product opportunities."""

from datetime import date
from enum import Enum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class IntelPillar(str, Enum):
    market = "market"
    user = "user"
    product = "product"


class SignalKind(str, Enum):
    competitor = "competitor"
    trend = "trend"
    news = "news"
    review = "review"
    feedback = "feedback"
    forum = "forum"
    analytics = "analytics"
    feature = "feature"
    usage = "usage"


class Polarity(str, Enum):
    pain = "pain"
    demand = "demand"
    adoption = "adoption"
    movement = "movement"
    neutral = "neutral"


class Gap(str, Enum):
    unserved = "unserved"
    contested = "contested"
    internal = "internal"
    table_stakes = "table_stakes"


class Verdict(str, Enum):
    pursue = "pursue"
    investigate = "investigate"
    park = "park"


class ReviewStatus(str, Enum):
    pending_review = "pending_review"
    approved = "approved"
    rejected = "rejected"
    needs_evidence = "needs_evidence"


PILLAR_KINDS: dict[IntelPillar, set[SignalKind]] = {
    IntelPillar.market: {SignalKind.competitor, SignalKind.trend, SignalKind.news},
    IntelPillar.user: {SignalKind.review, SignalKind.feedback, SignalKind.forum},
    IntelPillar.product: {SignalKind.analytics, SignalKind.feature, SignalKind.usage},
}

FRICTION_METRIC_KEYS = ("stall", "abandon", "drop", "dismiss", "churn")


class ProductContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    category: str
    audience: str
    mission: str


class Theme(BaseModel):
    """A named problem space the engine knows how to talk about.

    Themes live in the workspace, not in code, so a different product can
    bring its own vocabulary. Unmatched signals still cluster on their own.
    """

    model_config = ConfigDict(extra="forbid")

    id: str
    label: str
    keywords: list[str] = Field(min_length=1)
    problem: str
    idea_title: str
    idea_summary: str
    risks: list[str] = Field(default_factory=list)
    experiments: list[str] = Field(default_factory=list)


class Signal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    pillar: IntelPillar
    kind: SignalKind
    title: str
    body: str
    source: str
    observed_at: date
    strength: float = Field(default=0.5, ge=0, le=1)
    polarity: Polarity | None = None
    metrics: dict[str, float] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    url: str | None = None

    @model_validator(mode="after")
    def kind_matches_pillar(self) -> Self:
        allowed = PILLAR_KINDS[self.pillar]
        if self.kind not in allowed:
            names = ", ".join(kind.value for kind in allowed)
            raise ValueError(
                f"Signal {self.id}: {self.kind.value} does not belong to "
                f"{self.pillar.value} intel ({names})"
            )
        return self

    def text(self) -> str:
        return " ".join([self.title, self.body, " ".join(self.tags)]).lower()

    def resolved_polarity(self) -> Polarity:
        if self.polarity is not None:
            return self.polarity
        for key, value in self.metrics.items():
            if any(token in key for token in FRICTION_METRIC_KEYS) and value >= 0.3:
                return Polarity.pain
        if self.kind in {SignalKind.competitor, SignalKind.trend, SignalKind.news}:
            return Polarity.movement
        if self.kind in {SignalKind.review, SignalKind.feedback, SignalKind.forum}:
            return Polarity.pain
        return Polarity.neutral


class Evidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    signal_id: str
    pillar: IntelPillar
    kind: SignalKind
    title: str
    excerpt: str
    source: str
    observed_at: date
    polarity: Polarity
    strength: float
    metrics: dict[str, float] = Field(default_factory=dict)


class MarketFacet(str, Enum):
    trend = "trend"
    technology = "technology"
    competitor_launch = "competitor_launch"
    pricing = "pricing"
    market_gap = "market_gap"
    complaint = "complaint"
    startup = "startup"
    product_launch = "product_launch"
    regulatory = "regulatory"


class MarketEvidenceItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    signal_id: str
    facet: MarketFacet
    statement: str
    source: str
    observed_at: date


class MarketSignal(BaseModel):
    """What the market research agent publishes for one trend."""

    model_config = ConfigDict(extra="forbid")

    id: str
    theme: str
    trend: str
    evidence: list[MarketEvidenceItem]
    implication: str
    facets: list[MarketFacet]
    strength: float = Field(ge=0, le=1)
    signal_ids: list[str]


class MarketBrief(BaseModel):
    """The market signal attached to a product opportunity."""

    model_config = ConfigDict(extra="forbid")

    trend: str
    evidence: list[str]
    implication: str
    facets: list[str]


class Check(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    label: str
    passed: bool
    detail: str


class Scores(BaseModel):
    model_config = ConfigDict(extra="forbid")

    problem: float
    opportunity: float
    validation: float
    confidence: float


class Opportunity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    theme: str
    label: str
    title: str
    problem: str
    gap: Gap
    why_now: str
    mapping_note: str
    idea_summary: str
    rationale: str
    scores: Scores
    verdict: Verdict
    checks: list[Check]
    risks: list[str]
    next_steps: list[str]
    evidence: list[Evidence]
    signal_ids: list[str]
    market: MarketBrief | None = None
    status: ReviewStatus = ReviewStatus.pending_review
    review_note: str = ""

    def evidence_by_pillar(self) -> list[tuple[str, list[Evidence]]]:
        order = [IntelPillar.market, IntelPillar.user, IntelPillar.product]
        grouped: dict[IntelPillar, list[Evidence]] = {pillar: [] for pillar in order}
        for item in self.evidence:
            grouped[item.pillar].append(item)
        return [(pillar.value, grouped[pillar]) for pillar in order]


class ReviewEntry(BaseModel):
    opportunity_id: str
    action: ReviewStatus
    note: str
    created_at: str


class CycleReport(BaseModel):
    ran_at: str
    signal_count: int
    pillar_counts: dict[str, int]
    opportunity_count: int
    by_verdict: dict[str, int]
    opportunities: list[Opportunity]
    market_signals: list[MarketSignal] = Field(default_factory=list)
