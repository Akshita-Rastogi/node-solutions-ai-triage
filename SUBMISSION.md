# Submission Note — AI Request Triage Assistant

## Problem statement

Professional-services teams receive sales enquiries, support requests, billing concerns, technical
incidents, and ambiguous messages. Manual triage is slow and inconsistent, but fully automated responses
are risky: an incorrect priority can delay an outage or privacy incident, while generated text can invent
commitments. This project assists—not replaces—the operator by producing a structured routing decision
and a first-response draft that always requires human review.

## Assessment coverage

| Requested capability | Implementation |
|---|---|
| Accept written requests | Streamlit form and typed FastAPI endpoint |
| Short summary | Schema-constrained local analysis agent |
| One of five categories | Pydantic enum validation |
| Four priorities and reason | Structured decision plus visible rationale |
| One allowed owner | Enum plus deterministic routing invariants |
| Professional draft | Separate Ollama response agent; review-only output |
| Six examples and new input | Exact supplied fixtures plus custom mock input |
| Demonstrate at least three | UI includes all six, especially critical request 05 |
| Explain decisions and limitations | README, trace panel, and this note |
| No confidential data | Supplied mock data only; PII redaction before inference |

## Complexity added with purpose

The complexity is concentrated around trustworthy failure handling rather than feature count. A LangGraph
state machine makes sanitation, analysis, validation, and drafting individually visible. Ollama provides
fully local inference with strict structured output. Invalid output receives one bounded repair attempt;
model unavailability falls back to deterministic classification and a safe response template.

The highest-cost cases do not depend solely on model judgment. Wrong-workspace exposure is always elevated
to Technical / Urgent / Engineering with privacy and access-control flags. Active outages receive the same
urgent engineering route. Billing and commercial ownership are also policy constrained.

The operational path adds three submission differentiators:

1. Contact and payment identifiers are redacted before inference, and prompt-injection language remains
   untrusted request content.
2. PostgreSQL provides durable, immutable AI decisions plus separate human reviews; Redis supplies shared
   rate limiting; idempotency makes retries safe.
3. Health checks, correct HTTP semantics, correlation logs, Prometheus metrics, evaluation evidence, and
   regression tests expose quality and reliability.

## Technology judgment

LangGraph fits because the task has ordered state transitions and guardrail boundaries. Ollama keeps the
mock workflow local. PostgreSQL is preferable to a document database because uniqueness, foreign keys,
review relationships, and audit integrity dominate. A vector database is deliberately absent because this
is a classification-and-drafting task with no knowledge-retrieval requirement.

## Evaluation and honest limitations

The executable golden set uses all six supplied requests and checks category, priority, and owner. Unit
tests adversarially inject wrong decisions into the critical rule layer. For a real rollout, six examples
are insufficient: the next dataset would be versioned, multilingual, class-balanced, paraphrase-heavy,
and labelled by multiple reviewers. Release gates would include critical-incident false-negative rate,
macro F1, schema validity, human draft-edit distance, and p50/p95/p99 latency.

This is production-aware, not production-ready. Authentication is a demo API key; policy vocabulary is
English and finite; confidence is not calibrated; and no draft is sent to a customer system. Those limits
are intentional and documented rather than hidden.
