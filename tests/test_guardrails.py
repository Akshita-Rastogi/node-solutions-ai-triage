from triage.guardrails import enforce_business_rules, safe_fallback
from triage.models import AnalysisDecision, Category, Owner, Priority


def decision(category=Category.OTHER, priority=Priority.LOW, owner=Owner.SUCCESS):
    """Create a deliberately weak model decision for policy-correction tests."""
    return AnalysisDecision(summary="A customer has reported an important request.",
                            category=category, priority=priority,
                            priority_reason="No immediate impact was identified.", owner=owner,
                            confidence=0.8)


def test_wrong_workspace_is_always_an_urgent_engineering_incident():
    actual, warnings = enforce_business_rules(
        decision(), "Contacts were uploaded to the wrong workspace; remove access immediately."
    )
    assert (actual.category, actual.priority, actual.owner) == (
        Category.TECHNICAL, Priority.URGENT, Owner.ENGINEERING
    )
    assert warnings
    assert {"privacy", "access_control"} <= set(actual.risk_flags)


def test_billing_cannot_be_routed_away_from_finance():
    actual, _ = enforce_business_rules(
        decision(Category.BILLING, Priority.HIGH, Owner.ENGINEERING), "Duplicate invoice charge"
    )
    assert actual.owner == Owner.FINANCE


def test_commercial_follow_up_is_corrected_to_sales():
    actual, warnings = enforce_business_rules(
        decision(Category.OTHER, Priority.LOW, Owner.ENGINEERING),
        "Could this be automated? We would like to speak next week.",
    )
    assert (actual.category, actual.priority, actual.owner) == (
        Category.SALES, Priority.MEDIUM, Owner.SALES
    )
    assert warnings


def test_future_product_idea_is_routed_to_engineering():
    actual, warnings = enforce_business_rules(
        decision(Category.SALES, Priority.MEDIUM, Owner.SALES),
        "Can you add dark mode and change the dashboard font? No deadline; future update idea.",
    )
    assert (actual.category, actual.priority, actual.owner) == (
        Category.TECHNICAL, Priority.LOW, Owner.ENGINEERING
    )
    assert warnings


def test_deterministic_fallback_covers_outages():
    actual = safe_fallback("The portal is down and customer records are unavailable")
    assert actual.priority == Priority.URGENT
    assert actual.owner == Owner.ENGINEERING
