"""Display helpers shared by the CLI, memos, and review board."""

from datetime import date, datetime

GAP_LABELS = {
    "unserved": "Whitespace",
    "contested": "Contested",
    "internal": "Internal",
    "table_stakes": "Table stakes",
}

NODE_LABELS = {
    "market": "Market",
    "trend": "Trend",
    "users": "Users",
    "competitors": "Competitors",
    "problem": "Problem",
    "gap": "Gap",
    "opportunity": "Opportunity",
    "feature": "Feature",
    "product": "Product",
    "mvp": "MVP",
    "business_case": "Business case",
}

VERDICT_LABELS = {
    "pursue": "Pursue",
    "investigate": "Investigate",
    "park": "Park",
}

STATUS_LABELS = {
    "pending_review": "Pending review",
    "approved": "Approved",
    "rejected": "Rejected",
    "needs_evidence": "Needs evidence",
}

PILLAR_LABELS = {
    "market": "Market",
    "user": "User",
    "product": "Product",
}

KIND_LABELS = {
    "competitor": "Competitor",
    "trend": "Trend",
    "news": "News",
    "review": "Review",
    "feedback": "Feedback",
    "forum": "Forum",
    "analytics": "Analytics",
    "feature": "Feature",
    "usage": "Usage",
}

CHANNEL_LABELS = {
    "app_review": "App review",
    "support_ticket": "Support ticket",
    "feature_request": "Feature request",
    "survey": "Survey",
    "interview": "Interview",
    "community": "Community",
    "product_analytics": "Product analytics",
    "user_feedback": "User feedback",
}

FACET_LABELS = {
    "trend": "Industry trend",
    "technology": "Emerging technology",
    "competitor_launch": "Competitor launch",
    "pricing": "Pricing change",
    "market_gap": "Market gap",
    "complaint": "Customer complaint",
    "startup": "New startup",
    "product_launch": "Product launch",
    "regulatory": "Regulatory change",
}

POLARITY_LABELS = {
    "pain": "Pain",
    "demand": "Demand",
    "adoption": "Adoption",
    "movement": "Movement",
    "neutral": "Neutral",
}


def format_metric(key: str, value: float) -> str:
    label = key.replace("_", " ")
    if key.endswith(("rate", "share")) and 0 <= value <= 1:
        return f"{label} {round(value * 100)}%"
    if "lift" in key:
        return f"{label} {value:g}x"
    return f"{label} {value:g}"


def format_date(value: date | str) -> str:
    if isinstance(value, str):
        value = date.fromisoformat(value[:10])
    return f"{value.day} {value.strftime('%b %Y')}"


def format_timestamp(value: str) -> str:
    parsed = datetime.fromisoformat(value)
    return f"{parsed.day} {parsed.strftime('%b %Y, %H:%M UTC')}"


def percent(value: float) -> int:
    return round(float(value) * 100)
