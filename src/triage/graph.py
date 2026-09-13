import operator
from typing import Annotated, TypedDict

from langgraph.graph import END, START, StateGraph

from triage.guardrails import enforce_business_rules, safe_fallback
from triage.models import AnalysisDecision, Category, Owner, Priority
from triage.ollama import OllamaClient, OllamaError
from triage.security import detect_prompt_injection, redact_sensitive_values


class TriageState(TypedDict, total=False):
    """Explicit state passed between independently testable workflow stages."""

    original_text: str
    redacted_text: str
    decision: AnalysisDecision
    draft: str
    decision_source: str
    injection_detected: bool
    warnings: Annotated[list[str], operator.add]
    trace: Annotated[list[dict], operator.add]


def build_graph(ollama: OllamaClient):
    """Compile the deterministic Plan-Analyse-Validate-Draft workflow once at startup."""

    async def sanitize(state: TriageState) -> dict:
        redacted, sensitive = redact_sensitive_values(state["original_text"])
        injection_detected = detect_prompt_injection(redacted)
        warnings = [f"Redacted before inference: {kind}." for kind in sensitive]
        if injection_detected:
            warnings.append("Prompt-injection language detected; request remained untrusted data.")
        return {
            "redacted_text": redacted,
            "injection_detected": injection_detected,
            "warnings": warnings,
            "trace": [{"node": "sanitize", "redactions": sensitive}],
        }

    async def analyse(state: TriageState) -> dict:
        try:
            decision, trace = await ollama.analyse(state["redacted_text"])
            return {"decision": decision, "decision_source": "ollama", "trace": [trace]}
        except OllamaError as exc:
            return {
                "decision": safe_fallback(state["redacted_text"]),
                "decision_source": "deterministic_fallback",
                "warnings": [str(exc)],
                "trace": [{"node": "analysis_agent", "status": "fallback"}],
            }

    async def validate(state: TriageState) -> dict:
        if state.get("injection_detected"):
            decision = AnalysisDecision(
                summary="The message contains instructions unrelated to supported business triage.",
                category=Category.OTHER,
                priority=Priority.LOW,
                priority_reason=(
                    "Embedded prompt instructions are not a business incident and require clarification."
                ),
                owner=Owner.SUCCESS,
                risk_flags=["prompt_injection"],
                confidence=1.0,
            )
            return {
                "decision": decision,
                "decision_source": "deterministic_guardrail",
                "trace": [{"node": "policy_guardrail", "action": "injection_isolated"}],
            }
        decision, warnings = enforce_business_rules(state["decision"], state["redacted_text"])
        return {
            "decision": decision,
            "warnings": warnings,
            "trace": [{"node": "policy_guardrail", "corrections": len(warnings)}],
        }

    async def draft(state: TriageState) -> dict:
        if state.get("injection_detected"):
            return {
                "draft": (
                    "We could not identify a supported business request in this message. Please resend "
                    "the sales, support, billing, or technical issue you would like our team to review."
                ),
                "trace": [{"node": "response_guardrail", "status": "guarded_template"}],
            }
        if {"privacy", "access_control"} & set(state["decision"].risk_flags):
            return {
                "draft": (
                    "Thank you for reporting this potential data-access incident. The request has been "
                    "routed to Engineering for immediate human review; please avoid sharing additional "
                    "customer data and use an approved secure channel for workspace identifiers. This "
                    "message acknowledges escalation and does not confirm that access has been removed."
                ),
                "trace": [{
                    "node": "response_guardrail",
                    "status": "security_incident_template",
                }],
            }
        try:
            # The response agent receives the validated summary, not raw text or redaction tokens.
            # This is data minimization and prevents placeholders from leaking into customer drafts.
            answer, trace = await ollama.draft(state["decision"].summary, state["decision"])
            return {"draft": answer, "trace": [trace]}
        except OllamaError as exc:
            answer = (
                "Thank you for contacting us. We have recorded your request and routed it to "
                f"{state['decision'].owner.value} for review. A team member will verify the details "
                "and respond with the appropriate next step."
            )
            return {
                "draft": answer,
                "warnings": [str(exc)],
                "trace": [{"node": "response_agent", "status": "fallback"}],
            }

    graph = StateGraph(TriageState)
    graph.add_node("sanitize", sanitize)
    graph.add_node("analyse", analyse)
    graph.add_node("validate", validate)
    graph.add_node("draft", draft)
    graph.add_edge(START, "sanitize")
    graph.add_conditional_edges(
        "sanitize",
        lambda state: "validate" if state.get("injection_detected") else "analyse",
        {"validate": "validate", "analyse": "analyse"},
    )
    graph.add_edge("analyse", "validate")
    graph.add_edge("validate", "draft")
    graph.add_edge("draft", END)
    return graph.compile()
