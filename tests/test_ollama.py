from triage.ollama import OllamaClient


def test_customer_draft_rejects_exposed_reasoning():
    assert not OllamaClient._safe_customer_draft(
        "Okay, the user is asking for automation. I need to acknowledge the request."
    )


def test_customer_draft_accept_accepts_polished_response():
    assert OllamaClient._safe_customer_draft(
        "Thank you for reaching out. Our Sales Team will review your requirements and contact you."
    )


def test_customer_draft_rejects_redaction_placeholder_leakage():
    assert not OllamaClient._safe_customer_draft(
        "Please contact [ email_address_redacted] so Finance can investigate.", "High"
    )


def test_customer_draft_rejects_urgent_language_for_high_priority():
    assert not OllamaClient._safe_customer_draft(
        "Immediate action is needed. Finance will review the reported duplicate charge.", "High"
    )
