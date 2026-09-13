# Code Walkthrough and Extension Guide

## Where execution starts

Docker starts `uvicorn triage.main:app`. FastAPI executes `lifespan()` in `src/triage/main.py`, which opens
the PostgreSQL pool, creates the Redis limiter, creates the Ollama boundary, compiles the LangGraph once,
and constructs `TriageService`. Compiling once avoids rebuilding the workflow for every request.

Streamlit starts separately with `ui/app.py`. It never imports backend internals; it calls the public HTTP
API exactly as another client would. That separation catches contract and networking problems during the
demo rather than creating a UI that only works in-process.

## One request, method by method

1. The Streamlit form calls `api()` and sends `POST /v1/triage` with a unique idempotency key.
2. `request_context()` attaches `X-Request-ID`, records latency and status metrics, and writes a structured
   completion log without the request body or API key.
3. `TriageRequest.normalize_text()` collapses whitespace and rejects meaningless input. Pydantic also
   enforces length and source constraints.
4. `require_api_key()` authenticates the caller and returns only a hash fingerprint for operational keys.
5. `RateLimiter.allow()` increments a Redis minute bucket shared across possible API replicas.
6. `TriageService.triage()` first calls `Database.by_idempotency_key()`. A retry returns the existing result
   instead of spending another inference call or creating another queue item.
7. The compiled graph runs `sanitize`: `redact_sensitive_values()` removes email, phone, and card-like
   identifiers; `detect_prompt_injection()` records suspicious phrases as warnings.
8. The `analyse` node calls `OllamaClient.analyse()`. Ollama receives `AnalysisDecision.model_json_schema()`
   as its output format. Pydantic validates the returned summary, enum values, rationale, flags, and bounded
   confidence. Malformed output gets one explicit repair instruction; repeated failure calls `safe_fallback()`.
9. `enforce_business_rules()` corrects unsafe combinations. Privacy/access exposure and active outages are
   Urgent Engineering cases; Billing belongs to Finance; Sales belongs to Sales Team.
10. The `draft` node calls `OllamaClient.draft()` with only the validated, PII-free summary and decision—not
    the raw request or literal redaction tokens. The prompt prohibits invented pricing, timelines, completed
    actions, and copied PII. On failure, a cautious deterministic template is used.
11. The service builds `TriageResult` and `Database.insert()` writes the complete decision atomically.
12. Streamlit `show_result()` renders the decision, rationale, draft, warnings, and trace. Its review form
    calls `POST /v1/triage/{id}/review`; `Database.add_review()` accepts one immutable human outcome.

## File-by-file responsibility

| File | Important symbols | Reason it exists |
|---|---|---|
| `src/triage/main.py` | `lifespan`, middleware, route methods | HTTP lifecycle and status-code boundary |
| `src/triage/models.py` | enums, request/decision/result schemas | one source of truth for contracts |
| `src/triage/graph.py` | `TriageState`, `build_graph`, four nodes | explicit agent orchestration |
| `src/triage/ollama.py` | `health`, `analyse`, `draft` | isolate inference, timeout, schema and repair logic |
| `src/triage/guardrails.py` | `safe_fallback`, `enforce_business_rules` | model-independent business safety |
| `src/triage/security.py` | redaction, injection detection, API key | untrusted-input boundary |
| `src/triage/service.py` | `TriageService.triage` | application use case and idempotency |
| `src/triage/database.py` | schema and repository methods | durable decision/review audit history |
| `src/triage/rate_limit.py` | `allow`, `healthy` | replica-safe abuse control |
| `src/triage/metrics.py` | counters and histogram | low-cardinality operational measurement |
| `src/triage/config.py` | `Settings` | environment-only deployment differences |
| `src/triage/logging.py` | `configure_logging` | searchable JSON logs |
| `ui/app.py` | `api`, `show_result`, four tabs | operator workflow and explainability |
| `scripts/evaluate.py` | `main` | run golden cases through the real API |
| `data/mock_requests.json` | six supplied inputs | faithful assessment dataset |
| `data/edge_case_requests.json` | six additional inputs | demonstrate generalisation and guardrails |
| `data/evaluation.json` | expected decisions | reproducible regression evidence |

## Requests beyond the supplied six

The six assessment examples are fixtures, not hardcoded response branches. Any 5–5,000 character mock
request can enter the same schema-constrained workflow. The UI now includes an additional edge-case pack:

- ambiguous ownership, which should request human clarification rather than fabricate certainty;
- prompt injection embedded in a customer message;
- email and phone identifiers requiring pre-inference redaction;
- text saying “not urgent” while describing a real production outage;
- a mixed billing-and-sales message requiring one primary category;
- a new account-administration support question not present in the original six.

This does not imply universal coverage. Novel languages, subtle legal requests, and unseen security
paraphrases require more labelled evaluation data and policy review. The human-review requirement remains
the safety boundary.

## Adding a new request versus adding a new rule

To **process a new request**, no code or ingestion is needed: paste mock text in the UI or call the API.

To **add a reusable demo example**, append `{id, name, text, purpose}` to
`data/edge_case_requests.json`. Streamlit loads the file dynamically at startup.

To **add a new supported category or owner**, update the enums in `models.py`, the analysis system prompt,
the deterministic ownership rules, the UI/evaluation expectations, and regression tests. Changing only the
prompt would leave contracts and safety policy inconsistent.

To **add a policy-document capability**, create a retrieval node that returns excerpts and citations before
analysis. Add a vector database only after measuring that semantic retrieval is needed; retain PostgreSQL
for requests and reviews. Unsupported evidence should lead to refusal or clarification.

To **add a specialist tool**, define a typed input/output schema, add a conditional graph edge after
analysis, enforce timeouts and bounded retries, persist the tool trace, and never expose unrestricted tool
execution to the model.

## Operational inspection

```bash
# API health and dependency state
curl -s http://localhost:8100/health/ready | python -m json.tool

# Generated OpenAPI contract
open http://localhost:8100/docs

# PostgreSQL decisions
docker compose exec postgres psql -U triage -d triage \
  -c 'select request_id, category, priority, owner, decision_source from triage_requests;'

# Human review audit records
docker compose exec postgres psql -U triage -d triage \
  -c 'select * from triage_reviews order by reviewed_at desc;'

# Redis limiter keys
docker compose exec redis redis-cli --scan --pattern 'rate:*'

# Structured service logs
docker compose logs --tail=100 api

# Prometheus-formatted metrics
curl -s http://localhost:8100/metrics | grep '^triage_'
```

The code uses no request-text metric labels, avoiding high-cardinality and privacy leakage. Logs likewise
record operational context, not client bodies or raw API keys.
