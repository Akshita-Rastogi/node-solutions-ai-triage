# Video 1 — Product Demo and All 12 Scenarios

**Suggested duration:** 8–10 minutes  
**Screens:** Terminal → Streamlit Triage → Review Queue → Evaluation → How it works  
**Recording note:** Keep the browser at 80–90% zoom. Run the containers and Ollama before recording.

## 00:00–00:50 — Introduction and deployment

**Screen:** Terminal in the project folder.

**Run before or during the recording:**

```bash
docker compose ps
curl -s http://localhost:8100/health/ready | python -m json.tool
```

**Say:**

“Hi, this is my Node Solutions AI Request Triage submission. I treated the task as a small but
production-aware decision service, rather than a single prompt demonstration. The complete application
runs locally through Docker Compose. It includes a FastAPI microservice, a Streamlit operator interface,
PostgreSQL for durable request and review records, Redis for distributed rate limiting, and Ollama with
the local `qwen3:4b` model. The readiness endpoint verifies PostgreSQL, Redis, and Ollama separately.
All inference stays local, and no cloud model or external customer-data service is required.”

## 00:50–01:35 — Problem and architecture

**Screen:** Open the technical conditional flow PNG, then briefly return to Streamlit.

**Say:**

“The system converts an unstructured client request into a concise summary, exactly one category,
priority, owner, rationale, risk flags, confidence, and a first-response draft. The draft is never sent
automatically; it remains subject to human approval. The LangGraph flow has four explicit stages:
sanitize, analyse, validate, and draft. Conditional branches isolate prompt injection, apply deterministic
security templates, repair malformed model output once, and degrade safely if local inference fails.
This separation makes each decision visible and testable.”

## 01:35–04:50 — Demonstrate the six supplied scenarios

**Screen:** Streamlit → **Triage**. Select each request and press **Analyse request**. While each result
appears, point to category, priority, owner, rationale, draft, warnings, and the decision trace.

### Request 01 — Automation enquiry

**Say:**

“Request 01 is a commercial automation enquiry from a forty-person team. It routes to Sales, Medium
priority, and Sales Team. The deterministic commercial rule can correct an unsuitable model route, while
the draft avoids inventing price, delivery dates, or implementation commitments.”

### Request 02 — Active portal outage

**Say:**

“Request 02 describes an active client-portal outage. Business impact overrides vague language, so the
policy layer enforces Technical, Urgent, and Engineering. This is an important guardrail because a model
confidence score alone must never under-prioritise a production outage.”

### Request 03 — Duplicate invoice charge

**Say:**

“Request 03 is a possible duplicate invoice charge before a payment deadline. It becomes Billing, High,
and Finance. Ownership is an invariant: billing requests cannot accidentally remain assigned to Sales or
Engineering.”

### Request 04 — Future dark-mode idea

**Say:**

“Request 04 asks for dark mode and a font change with no deadline. It is a product or technical enhancement,
so the corrected result is Technical, Low, and Engineering—not Sales. The absence of urgency is retained.”

### Request 05 — Customer data in the wrong workspace

**Say:**

“Request 05 is the critical safety case. Customer information was uploaded to the wrong workspace. The
policy layer elevates it to Technical, Urgent, and Engineering and adds privacy and access-control flags.
Instead of allowing a generative response to claim remediation is complete, the system uses a deterministic
incident template. It advises containment and a secure channel without repeating private data or claiming
that access has already been removed.”

### Request 06 — Pricing enquiry

**Say:**

“Request 06 asks about pricing and timeline for a custom AI system. It is Sales, Medium, and Sales Team.
The draft acknowledges buying intent but does not fabricate a quote or promise a schedule.”

## 04:50–06:45 — Demonstrate the six additional edge cases

**Screen:** Continue in the Triage selector under **Edge cases**. These can be shown more quickly—submit
each and point to the key behavior.

**Say for E01:**

“E01 is ambiguous ownership. The system preserves uncertainty and routes conservatively rather than
inventing specialist context.”

**Say for E02:**

“E02 embeds instructions to ignore policy and reveal the system prompt. The request remains untrusted
data. The sanitize node detects it, skips the analysis model path, assigns Other and Low with a
prompt-injection flag, and returns a guarded clarification template.”

**Say for E03:**

“E03 contains an email address and phone number with a billing issue. Both identifiers are redacted before
Ollama sees the request, but the billing meaning and deadline remain available for correct routing.”

**Say for E04:**

“E04 says ‘not urgent’ while describing a production outage. The deterministic impact rule overrides the
self-reported urgency and escalates it to Engineering.”

**Say for E05:**

“E05 mixes a duplicate invoice with a pricing enquiry. The schema requires exactly one primary category,
and the payment issue receives precedence for safe ownership.”

**Say for E06:**

“E06 is a new account-administration question that was not in the supplied set. It demonstrates that the
workflow accepts new requests and is not a lookup table of twelve hardcoded answers.”

## 06:45–07:35 — Custom request and human review

**Screen:** Select custom input and paste:

```text
Our staging dashboard is slow for one internal tester, but production is working. Please investigate when convenient.
```

Press **Analyse request**, choose **Corrected** or **Approved**, enter a short note, and submit. Then open
**Review queue**.

**Say:**

“A custom request enters the same contracts and graph. This example should not be escalated like a production
outage because impact and environment matter. Every result exposes its decision trace and is presented as a
draft. I can approve, correct, or reject it once. Human review is stored separately, so it does not overwrite
the original AI decision. This creates an auditable comparison between model output and human judgment.”

## 07:35–08:35 — Evaluation and why the model was chosen

**Screen:** Streamlit → **Evaluation**, then Terminal if needed:

```bash
docker compose exec api python scripts/evaluate.py
cat output/evaluation-results.json
docker compose exec api pytest -q
```

**Say:**

“The evaluation set contains all six supplied requests. Each is scored independently on category, priority,
and owner, giving eighteen deterministic field checks. The screen shows expected versus actual output and
the current pass total, so I report the measured result rather than a memorised claim. The repository also
contains eleven focused tests for business guardrails, malformed structured output, redaction, injection,
and authentication.

I chose `qwen3:4b` because it offers a practical laptop balance: local privacy, manageable memory usage,
schema-following ability, and acceptable latency. Temperature zero reduces classification variance. Model
confidence is displayed only as diagnostic metadata; it is not calibrated and never bypasses policy or
human review. For a larger dataset I would track macro F1, per-class recall, owner exact match, schema-validity
rate, human draft-edit distance, and p50, p95, and p99 latency. The release-blocking metric would be the
false-negative rate for security and outage cases.”

## 08:35–09:30 — Brownie features and close

**Screen:** Streamlit → **How it works**, slowly scroll.

**Say:**

“The additions beyond the minimum are typed multi-stage LangGraph state, two separated AI roles, strict
schema output with a repair retry, deterministic business guardrails, PII redaction before inference,
prompt-injection isolation, local-model failure fallback, idempotent requests, shared Redis rate limiting,
correct HTTP status contracts, structured logs, Prometheus metrics, request correlation IDs, immutable
human review, and a regression-first evaluation pack with six additional edge cases.

I deliberately did not add RAG or a vector database because this task is request classification, not
knowledge retrieval. PostgreSQL is the correct system of record for relational decision and review
invariants, while Redis holds only expiring operational counters. A separate infrastructure video shows
both stores in detail, and a separate code video walks through every file and conditional graph. The README,
technical report, editable Draw.io diagram, tests, and generated evaluation evidence are included with the
submission.”

