from triage.models import AnalysisDecision, Category, Owner, Priority

SECURITY_TERMS = (
    "wrong workspace", "remove access", "customer contact information", "data leak",
    "breach", "exposed", "unauthorized access", "ransomware",
)
OUTAGE_TERMS = ("unavailable", "outage", "cannot access", "down", "not working")
BILLING_TERMS = ("invoice", "charged", "charge", "billing", "payment", "refund")
SALES_TERMS = ("pricing", "quote", "interested", "demo", "speak next week", "timeline")
LOW_TERMS = ("no deadline", "future update", "idea", "nice to have")
FEATURE_TERMS = (
    "dark mode", "dashboard font", "change the font", "export reports", "feature request",
    "future update", "enhancement", "nice to have",
)


def safe_fallback(text: str) -> AnalysisDecision:
    """Return a useful deterministic result when the local model is unavailable."""
    q = text.lower()
    if any(term in q for term in SECURITY_TERMS):
        values = (Category.TECHNICAL, Priority.URGENT, Owner.ENGINEERING,
                  "Potential confidentiality or access-control incident requires immediate containment.")
    elif any(term in q for term in OUTAGE_TERMS):
        values = (Category.TECHNICAL, Priority.URGENT, Owner.ENGINEERING,
                  "An active service outage is blocking access to customer records.")
    elif any(term in q for term in BILLING_TERMS):
        values = (Category.BILLING, Priority.HIGH, Owner.FINANCE,
                  "A possible billing error should be resolved before the stated payment deadline.")
    elif any(term in q for term in SALES_TERMS):
        values = (Category.SALES, Priority.MEDIUM, Owner.SALES,
                  "This is a commercial enquiry with a requested follow-up or buying intent.")
    elif any(term in q for term in LOW_TERMS):
        values = (Category.TECHNICAL, Priority.LOW, Owner.ENGINEERING,
                  "The enhancement request has no deadline or current service impact.")
    else:
        values = (Category.OTHER, Priority.MEDIUM, Owner.SUCCESS,
                  "The request needs human clarification before specialist routing.")
    category, priority, owner, reason = values
    return AnalysisDecision(
        summary=text[:217] + "..." if len(text) > 220 else text,
        category=category,
        priority=priority,
        priority_reason=reason,
        owner=owner,
        risk_flags=[],
        confidence=0.55,
    )


def enforce_business_rules(decision: AnalysisDecision, text: str) -> tuple[AnalysisDecision, list[str]]:
    """Override unsafe model decisions using deterministic business invariants."""
    q = text.lower()
    warnings: list[str] = []
    if any(term in q for term in SECURITY_TERMS):
        if (decision.category, decision.priority, decision.owner) != (
            Category.TECHNICAL, Priority.URGENT, Owner.ENGINEERING
        ):
            warnings.append("Security incident routing was elevated by policy.")
        decision.category = Category.TECHNICAL
        decision.priority = Priority.URGENT
        decision.owner = Owner.ENGINEERING
        decision.priority_reason = (
            "Potential exposure of customer information requires immediate access containment."
        )
        decision.risk_flags = sorted(set(decision.risk_flags + ["privacy", "access_control"]))
    elif any(term in q for term in OUTAGE_TERMS):
        decision.category = Category.TECHNICAL
        decision.priority = Priority.URGENT
        decision.owner = Owner.ENGINEERING
        decision.priority_reason = "An active customer-facing outage is blocking business operations."
    elif any(term in q for term in BILLING_TERMS):
        if (decision.category, decision.owner) != (Category.BILLING, Owner.FINANCE):
            warnings.append("Billing ownership was corrected by policy.")
        decision.category = Category.BILLING
        decision.owner = Owner.FINANCE
        if any(term in q for term in ("duplicate", "due tomorrow", "processed friday")):
            decision.priority = Priority.HIGH
            decision.priority_reason = (
                "A possible duplicate charge should be reviewed before the stated payment deadline."
            )
    elif any(term in q for term in FEATURE_TERMS):
        if (decision.category, decision.owner) != (Category.TECHNICAL, Owner.ENGINEERING):
            warnings.append("Product enhancement routing was corrected by policy.")
        decision.category = Category.TECHNICAL
        decision.priority = Priority.LOW
        decision.owner = Owner.ENGINEERING
        decision.priority_reason = (
            "This is a future product enhancement with no deadline or current service impact."
        )
    elif any(term in q for term in SALES_TERMS):
        if (decision.category, decision.owner) != (Category.SALES, Owner.SALES):
            warnings.append("Commercial enquiry routing was corrected by policy.")
        decision.category = Category.SALES
        decision.priority = Priority.MEDIUM
        decision.owner = Owner.SALES
        decision.priority_reason = (
            "This is a commercial enquiry with a requested follow-up or buying intent."
        )
    elif decision.category == Category.BILLING:
        decision.owner = Owner.FINANCE
    elif decision.category == Category.SALES:
        decision.owner = Owner.SALES
    elif decision.category == Category.SUPPORT and decision.owner == Owner.FINANCE:
        decision.owner = Owner.SUCCESS
        warnings.append("Unsupported Support-to-Finance route was corrected.")
    critical_signal = any(term in q for term in SECURITY_TERMS + OUTAGE_TERMS)
    if any(term in q for term in LOW_TERMS) and not decision.risk_flags and not critical_signal:
        decision.priority = Priority.LOW
    return decision, warnings
