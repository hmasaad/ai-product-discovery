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


class EvidenceSide(str, Enum):
    support = "support"
    contradict = "contradict"


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
    solutions: list[str] = Field(default_factory=list)
    mvp: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    experiment: str = ""


class UserChannel(str, Enum):
    app_review = "app_review"
    support_ticket = "support_ticket"
    feature_request = "feature_request"
    survey = "survey"
    interview = "interview"
    community = "community"
    product_analytics = "product_analytics"
    user_feedback = "user_feedback"


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
    channel: UserChannel | None = None
    volume: int = Field(default=1, ge=1)
    stance: EvidenceSide | None = None

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


class ProblemCluster(BaseModel):
    """One complaint cluster from the user intelligence agent."""

    model_config = ConfigDict(extra="forbid")

    id: str
    theme: str
    label: str
    share: float = Field(ge=0, le=1)
    volume: int = Field(ge=0)
    channels: list[UserChannel]
    examples: list[str]
    corroborated_by: list[str] = Field(default_factory=list)
    unmet: bool
    unmet_need: str = ""


class UserIntelligence(BaseModel):
    """Clustered complaints and the unmet needs inside them."""

    model_config = ConfigDict(extra="forbid")

    feedback_count: int = 0
    other_volume: int = 0
    clusters: list[ProblemCluster] = Field(default_factory=list)
    unmet_needs: list[ProblemCluster] = Field(default_factory=list)


class CapabilityKind(str, Enum):
    feature = "feature"
    count = "count"
    price = "price"


class Capability(BaseModel):
    """One row in the competitor matrix."""

    model_config = ConfigDict(extra="forbid")

    id: str
    label: str
    kind: CapabilityKind
    direction: str = ""
    themes: list[str] = Field(default_factory=list)


class CatalogMove(BaseModel):
    """A dated observation of one capability on one competitor."""

    model_config = ConfigDict(extra="forbid")

    capability: str
    observed_at: date
    value: bool | int
    note: str = ""


class CompetitorProduct(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    moves: list[CatalogMove]


class CompetitorCatalog(BaseModel):
    """Structured competitor observations. The agent builds the matrix from this."""

    model_config = ConfigDict(extra="forbid")

    capabilities: list[Capability] = Field(default_factory=list)
    products: list[CompetitorProduct] = Field(default_factory=list)


class MatrixRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    capability_id: str
    label: str
    kind: CapabilityKind
    cells: list[str]


class CompetitorRead(BaseModel):
    """Behavior, trajectory, and direction for one competitor."""

    model_config = ConfigDict(extra="forbid")

    product_id: str
    name: str
    behavior: list[str]
    trajectory: str
    direction: str


class CompetitorGap(BaseModel):
    model_config = ConfigDict(extra="forbid")

    capability_id: str
    statement: str
    themes: list[str] = Field(default_factory=list)


class CompetitorIntelligence(BaseModel):
    """Matrix, then the chain from behavior to a market gap."""

    model_config = ConfigDict(extra="forbid")

    products: list[str] = Field(default_factory=list)
    product_ids: list[str] = Field(default_factory=list)
    rows: list[MatrixRow] = Field(default_factory=list)
    reads: list[CompetitorRead] = Field(default_factory=list)
    race: str = ""
    notes: list[str] = Field(default_factory=list)
    gaps: list[CompetitorGap] = Field(default_factory=list)


class CompetitorBrief(BaseModel):
    """The competitor read attached to a product opportunity."""

    model_config = ConfigDict(extra="forbid")

    race: str
    gap: str


class UserBrief(BaseModel):
    """The user-intelligence finding attached to a product opportunity."""

    model_config = ConfigDict(extra="forbid")

    label: str
    share: float
    volume: int
    feedback_count: int
    unmet: bool
    unmet_need: str = ""


class OpportunityChain(BaseModel):
    """Signal, problem, segment, pain, existing solutions, gap, opportunity."""

    model_config = ConfigDict(extra="forbid")

    signal: str
    problem: str
    segment: str
    pain: str
    existing_solutions: str
    gap: str
    opportunity: str


class ValidationPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    signal_id: str = ""


class ValidationQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    question: str
    answer: str
    status: str


class ValidationBrief(BaseModel):
    """Evidence for the opportunity, and the evidence that cuts against it."""

    model_config = ConfigDict(extra="forbid")

    supporting: list[ValidationPoint] = Field(default_factory=list)
    contradicting: list[ValidationPoint] = Field(default_factory=list)
    questions: list[ValidationQuestion] = Field(default_factory=list)
    challenge: str = ""


class ProductOpportunityBrief(BaseModel):
    """The handoff a product manager reads: evidence and an experiment."""

    model_config = ConfigDict(extra="forbid")

    problem: str
    target_users: str
    observed_pain: str
    existing_solutions: list[str]
    gap: str
    opportunity: str
    mvp: list[str]
    evidence: list[str]
    risks: list[str]
    open_questions: list[str]
    experiment: str


class LoopStage(str, Enum):
    discovery = "discovery"
    graph = "graph"
    product_manager = "product_manager"
    prd = "prd"
    architect = "architect"
    developer = "developer"
    qa = "qa"
    review = "review"
    production = "production"
    analytics = "analytics"
    discovery_return = "discovery_return"


class LoopStatus(str, Enum):
    ready = "ready"
    waiting = "waiting"
    hold = "hold"
    returned = "returned"


class LoopArtifact(BaseModel):
    """One hop in the closed product loop."""

    model_config = ConfigDict(extra="forbid")

    stage: LoopStage
    title: str
    status: LoopStatus
    summary: str
    lines: list[str] = Field(default_factory=list)


class ReturnSignal(BaseModel):
    """A measurement the experiment sends back into discovery."""

    model_config = ConfigDict(extra="forbid")

    title: str
    body: str


class DevelopmentLoop(BaseModel):
    """Discovery, the product manager, the build agents, and the return path."""

    model_config = ConfigDict(extra="forbid")

    opportunity_id: str
    title: str
    stages: list[LoopArtifact]
    pm_brief: str = ""
    return_signals: list[ReturnSignal] = Field(default_factory=list)


class MemoryKind(str, Enum):
    products = "products"
    features = "features"
    users = "users"
    problems = "problems"
    competitors = "competitors"
    experiments = "experiments"
    decisions = "decisions"
    metrics = "metrics"
    feedback = "feedback"
    rejected_ideas = "rejected_ideas"
    successful_ideas = "successful_ideas"
    failed_experiments = "failed_experiments"


class MemoryRecord(BaseModel):
    """One thing the product memory can cite later."""

    model_config = ConfigDict(extra="forbid")

    id: str
    kind: MemoryKind
    title: str
    detail: str = ""
    observed_at: date | None = None
    source: str = ""
    subject: str = ""
    count: int = Field(default=1, ge=1)
    verdict: str = ""


class ProductMemory(BaseModel):
    model_config = ConfigDict(extra="forbid")

    records: list[MemoryRecord] = Field(default_factory=list)

    def of_kind(self, kind: MemoryKind) -> list[MemoryRecord]:
        return [record for record in self.records if record.kind is kind]


class MemoryAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str
    answer: str
    records: list[MemoryRecord] = Field(default_factory=list)


class IntelligenceStage(BaseModel):
    """One capability of the opportunity intelligence engine."""

    model_config = ConfigDict(extra="forbid")

    capability: str
    summary: str
    lines: list[str] = Field(default_factory=list)
    href: str = ""


class OpportunityIntelligence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    opportunity_id: str
    title: str
    stages: list[IntelligenceStage]


class ExperimentStage(BaseModel):
    """One step from a hypothesis to a learning."""

    model_config = ConfigDict(extra="forbid")

    title: str
    summary: str
    lines: list[str] = Field(default_factory=list)
    status: str = "ready"


class TestHypothesis(BaseModel):
    """One claim the experiment can falsify before a build."""

    model_config = ConfigDict(extra="forbid")

    code: str
    statement: str
    target_segment: str
    expected_behavior: str
    metric: str
    threshold: str
    time_period: str
    confidence: str
    evidence: str


class ExperimentSpec(BaseModel):
    """One experiment, specified before it runs."""

    model_config = ConfigDict(extra="forbid")

    name: str
    objective: str
    hypothesis: str
    target_audience: str
    variant: str
    control: str
    primary_metric: str
    secondary_metric: str
    guardrails: list[str]
    sample_size: str
    duration: str
    decision_threshold: str
    risks: list[str]
    expected_learning: str
    outcomes: list[str]


class ExperimentChoice(BaseModel):
    """A candidate experiment, with what it costs and what it can teach."""

    model_config = ConfigDict(extra="forbid")

    code: str
    name: str
    cost: str
    information: str
    selected: bool = False


class MetricReading(BaseModel):
    """A change from the control, which is the behavioral baseline."""

    model_config = ConfigDict(extra="forbid")

    name: str
    lane: str
    change: float


class MonitorLane(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    lines: list[str] = Field(default_factory=list)


class ExperimentMonitor(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    explanation: str
    lanes: list[MonitorLane] = Field(default_factory=list)
    outcome: str = ""


class ExecutionStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: str
    system: str
    summary: str
    status: str
    needs_approval: bool = False


class ResultsAnalysis(BaseModel):
    """What the experiment taught, including the evidence that cuts against it."""

    model_config = ConfigDict(extra="forbid")

    hypothesis: str
    observed: str
    supporting: list[str] = Field(default_factory=list)
    contradicting: list[str] = Field(default_factory=list)
    interpretation: str
    uncertainty: str
    next_experiment: str


class ExperimentExecution(BaseModel):
    """The nine execution steps, gated before production changes."""

    model_config = ConfigDict(extra="forbid")

    steps: list[ExecutionStep]
    approved: bool = False
    approval_note: str = ""
    monitor: ExperimentMonitor
    report: str
    analysis: ResultsAnalysis | None = None


class ExperimentLearning(BaseModel):
    """One finished or in-progress experiment the next design can cite."""

    model_config = ConfigDict(extra="forbid")

    opportunity_id: str
    opportunity: str
    hypothesis: str
    experiment: str
    result: str
    learning: str
    decision: str


class PortfolioRow(BaseModel):
    """One experiment in the portfolio."""

    model_config = ConfigDict(extra="forbid")

    name: str
    status: str
    risk: str
    opportunity_id: str = ""
    audience: str = ""
    surface: str = ""
    information: str = ""
    cost: str = ""


class PortfolioNote(BaseModel):
    model_config = ConfigDict(extra="forbid")

    topic: str
    summary: str


class ExperimentValue(BaseModel):
    """One experiment scored by what it can teach, not by business value alone."""

    model_config = ConfigDict(extra="forbid")

    name: str
    opportunity_id: str = ""
    uncertainty: str
    information_gain: str
    decision_impact: str
    cost: str
    priority: str
    prioritize: bool = False


class ExperimentPortfolio(BaseModel):
    """Every experiment the agent is tracking, and what that set implies."""

    model_config = ConfigDict(extra="forbid")

    rows: list[PortfolioRow] = Field(default_factory=list)
    notes: list[PortfolioNote] = Field(default_factory=list)
    formula: str = ""
    chain: list[str] = Field(default_factory=list)
    values: list[ExperimentValue] = Field(default_factory=list)


class ExperimentPlan(BaseModel):
    """The cheapest experiment for one opportunity, and what it decided."""

    model_config = ConfigDict(extra="forbid")

    opportunity_id: str
    title: str
    stages: list[ExperimentStage]
    decision: str
    decision_summary: str
    pm_summary: str
    hypotheses: list[TestHypothesis] = Field(default_factory=list)
    unknown: str = ""
    choices: list[ExperimentChoice] = Field(default_factory=list)
    selected: str = ""
    catalog: list[str] = Field(default_factory=list)
    specifications: list[ExperimentSpec] = Field(default_factory=list)
    execution: ExperimentExecution | None = None
    memory_chain: ExperimentLearning | None = None
    prior_learning: ExperimentLearning | None = None
    informed_experiment: str = ""


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
    chain: OpportunityChain | None = None
    challenge: ValidationBrief | None = None
    product_brief: ProductOpportunityBrief | None = None
    market: MarketBrief | None = None
    user: UserBrief | None = None
    competitor: CompetitorBrief | None = None
    status: ReviewStatus = ReviewStatus.pending_review
    review_note: str = ""

    def evidence_by_pillar(self) -> list[tuple[str, list[Evidence]]]:
        order = [IntelPillar.market, IntelPillar.user, IntelPillar.product]
        grouped: dict[IntelPillar, list[Evidence]] = {pillar: [] for pillar in order}
        for item in self.evidence:
            grouped[item.pillar].append(item)
        return [(pillar.value, grouped[pillar]) for pillar in order]


class OpportunityCandidate(BaseModel):
    """One detected opportunity, including signals that are not ready to review."""

    model_config = ConfigDict(extra="forbid")

    id: str
    theme: str
    label: str
    signal_ids: list[str]
    chain: OpportunityChain
    review_id: str = ""


class NodeKind(str, Enum):
    market = "market"
    trend = "trend"
    users = "users"
    competitors = "competitors"
    problem = "problem"
    gap = "gap"
    opportunity = "opportunity"
    feature = "feature"
    product = "product"
    mvp = "mvp"
    business_case = "business_case"
    hypothesis = "hypothesis"
    experiment = "experiment"
    observation = "observation"
    learning = "learning"
    decision = "decision"
    product_change = "product_change"
    new_observation = "new_observation"
    new_hypothesis = "new_hypothesis"


class GraphSource(BaseModel):
    """A signal or agent finding a graph node is citing."""

    model_config = ConfigDict(extra="forbid")

    signal_id: str = ""
    title: str
    source: str
    observed_at: str = ""
    node_id: str = ""


class GraphNode(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    kind: NodeKind
    title: str
    detail: str = ""
    sources: list[GraphSource] = Field(default_factory=list)


class GraphEdge(BaseModel):
    model_config = ConfigDict(extra="forbid")

    origin: str
    target: str
    opportunity_id: str


class OpportunityGraph(BaseModel):
    """Market, trend, users, competitors, problems, gaps, and the bets they support."""

    model_config = ConfigDict(extra="forbid")

    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)

    def node(self, node_id: str) -> GraphNode | None:
        return next((item for item in self.nodes if item.id == node_id), None)


class OpportunityTrace(BaseModel):
    """Why one opportunity exists, and the sources along the path."""

    model_config = ConfigDict(extra="forbid")

    opportunity_id: str
    title: str
    why: str
    market: GraphNode | None = None
    trend: GraphNode | None = None
    users: GraphNode | None = None
    competitors: GraphNode | None = None
    problem: GraphNode | None = None
    gap: GraphNode | None = None
    opportunity: GraphNode | None = None
    feature: GraphNode | None = None
    product: GraphNode | None = None
    mvp: GraphNode | None = None
    business_case: GraphNode | None = None
    hypothesis: GraphNode | None = None
    experiment: GraphNode | None = None
    observation: GraphNode | None = None
    learning: GraphNode | None = None
    decision: GraphNode | None = None
    product_change: GraphNode | None = None
    new_observation: GraphNode | None = None
    new_hypothesis: GraphNode | None = None
    learning_path: list[str] = Field(default_factory=list)
    paths: list[list[str]] = Field(default_factory=list)
    sources: list[GraphSource] = Field(default_factory=list)


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
    user_intelligence: UserIntelligence | None = None
    competitor_intelligence: CompetitorIntelligence | None = None
    candidates: list[OpportunityCandidate] = Field(default_factory=list)
