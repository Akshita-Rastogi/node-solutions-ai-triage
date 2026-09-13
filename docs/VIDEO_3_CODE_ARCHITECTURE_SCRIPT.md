# Video 3 — Code Structure, Graph Flow, and Engineering Decisions

**Suggested duration:** 8–10 minutes  
**Screens:** VS Code Explorer → source files → graph diagram → tests → data/output → Docker files

## 00:00–00:45 — Repository structure

**Screen:** VS Code Explorer at the repository root.

**Say:**

“This video walks through the code and the engineering decisions behind the service. I kept the repository
compact: one requirements file, no TOML files, one FastAPI microservice, one Streamlit client, focused tests,
three data fixtures, Docker configuration, and generated submission artifacts. The UI communicates only
through HTTP and does not import backend internals, so it exercises the same contract as a real external
client.”

## 00:45–01:35 — Container and startup flow

**Screen:** `docker-compose.yml`, `Dockerfile`, `.env.example`, then `src/triage/main.py`.

**Say:**

“Docker Compose runs API, UI, PostgreSQL, and Redis on ports that do not conflict with my other project:
8100, 8601, 5433, and 6380. Ollama stays on the Mac host for normal model storage and acceleration, and the
containers reach it through `host.docker.internal`.

Uvicorn starts `triage.main:app`. FastAPI’s lifespan opens the PostgreSQL pool, creates the Redis limiter and
Ollama client, compiles the LangGraph once, and builds the application service. Shared clients are closed on
shutdown. Liveness checks only the process; readiness checks all required dependencies and returns 503 when
the service is running but not fully capable.”

## 01:35–02:30 — HTTP contracts and status handling

**Screen:** `src/triage/main.py`, then `src/triage/models.py`.

**Say:**

“The middleware creates or propagates an `X-Request-ID`, times every request, records Prometheus metrics, and
writes structured logs. The POST endpoint authenticates, applies the Redis limit, invokes the service, and
returns 201 for new work or 200 for an idempotent replay. Other explicit contracts are 401 for authentication,
404 for an unknown UUID, 409 for duplicate review or an idempotency race, 422 for invalid input, 429 for rate
limits, and 503 for failed readiness.

Pydantic models are the source of truth for input length, allowed source values, category, priority, owner,
confidence, risk flags, and response shape. Normalisation collapses whitespace and rejects meaningless text.
This prevents invalid states from moving deeper into the graph.”

## 02:30–04:10 — LangGraph nodes and conditional paths

**Screen:** `src/triage/graph.py` side by side with `artifacts/Node_Solutions_AI_Triage_Technical_Conditional_Flow.png`.

**Say:**

“`TriageState` explicitly carries original and redacted text, the decision, draft, decision source, injection
flag, warnings, and trace. Warnings and traces use additive reducers, so evidence from earlier nodes is not
overwritten.

The sanitize node redacts contact and payment identifiers and detects prompt-injection phrases. The first
conditional edge is important: detected injection skips the analysis agent and goes directly to deterministic
validation. Otherwise, analyse calls Ollama. Model or validation failure produces a conservative fallback.

Validate is the safety authority. It isolates prompt injection and applies business invariants to normal
model output. The draft node then has three runtime behaviors: a guarded injection template, a deterministic
privacy/access incident template, or a normal response-agent call. Ollama failure uses a cautious owner-based
acknowledgement. Every path converges before PostgreSQL persistence.

I chose LangGraph rather than a free-form ReAct, CrewAI, or AutoGen loop because the safe sequence is known
and bounded. State transitions, reducers, and conditional branches are explicit. LangChain is useful for
component composition, but the graph—not retrieval—is the central abstraction here. The stages are sequential
because validation depends on analysis and drafting depends on the validated decision; artificial parallelism
would not shorten this critical path.”

## 04:10–05:15 — Ollama and structured inference

**Screen:** `src/triage/ollama.py` and `src/triage/models.py`.

**Say:**

“The Ollama boundary has two narrowly scoped AI roles. The analysis role receives untrusted redacted text and
the Pydantic JSON schema as its required output format. Temperature zero reduces variance. Pydantic validates
the actual response. If JSON is malformed, the client appends one repair instruction and retries; repeated
failure raises a controlled `OllamaError` for deterministic degradation.

The response role receives only the validated PII-free summary and routing decision—not raw text and not
literal redaction placeholders. Its schema and content checks reject reasoning leakage, fabricated completion,
inappropriate urgency, copied placeholders, and incomplete prose. `qwen3:4b` was selected as a laptop-friendly
balance of local privacy, structured-output behavior, memory demand, and latency. The model can be changed by
environment variable without changing graph contracts or policy.”

## 05:15–06:05 — Deterministic safety and security boundary

**Screen:** `src/triage/guardrails.py` and `src/triage/security.py`.

**Say:**

“Prompting is not treated as the security boundary. `guardrails.py` contains deterministic escalation and
ownership invariants: outages and privacy exposure are urgent Engineering work, Billing belongs to Finance,
commercial intent belongs to Sales, and product enhancements belong to Engineering. It also provides a safe
fallback for inference failure.

`security.py` performs constant-time API-key comparison, hashes caller identity for operational keys, redacts
email, phone, and card-like values, and detects common injection patterns. Request bodies and raw secrets are
not placed in logs or metric labels.”

## 06:05–07:05 — Service, PostgreSQL, and Redis

**Screen:** `src/triage/service.py`, `database.py`, and `rate_limit.py`.

**Say:**

“`TriageService` is the application-use-case boundary. It checks durable idempotency, invokes the compiled
graph, converts final state to the API result, and persists it. Keeping orchestration outside the HTTP route
makes the use case testable.

`Database` owns schema creation and repository methods. PostgreSQL was chosen because request, decision, and
review have stable relations, uniqueness constraints, transaction needs, and audit semantics. JSONB handles
only variable flags and traces. Redis owns expiring, replica-safe rate counters. It intentionally stores no
request text and is not the authority for completed work.”

## 07:05–07:45 — UI and review flow

**Screen:** `ui/app.py`.

**Say:**

“The Streamlit app loads the six supplied and six edge-case fixtures dynamically. It supports custom input,
shows loading state, appends results as conversation-like turns, automatically brings the latest result into
view, displays warnings and traces, and provides one review form per request using unique component keys.
After review, controls are disabled and the durable outcome is shown. The Review Queue reads records back
through the API rather than relying on browser session state.”

## 07:45–08:40 — Tests and evaluation

**Screen:** `tests/`, `data/evaluation.json`, `scripts/evaluate.py`, and `output/evaluation-results.json`.

**Say:**

“The test suite contains eleven focused tests covering guardrail corrections, structured-output repair and
fallback, redaction, injection detection, and authentication. The golden evaluation runs all six supplied
requests through the real HTTP boundary and checks category, priority, and owner separately—eighteen field
checks in total. Expected and actual values are written to a JSON artifact.

For production-scale evaluation I would add a versioned, class-balanced set with hard negatives and multiple
languages. I would report macro F1, per-class recall, owner exact match, schema-validity rate, draft edit
distance, and p50/p95/p99 latency. Security and outage false negatives would block release even if aggregate
accuracy remained high.”

## 08:40–09:30 — Documentation, boundaries, and close

**Screen:** `README.md`, `SUBMISSION.md`, `docs/`, `artifacts/`.

**Say:**

“The README explains setup, architecture, model choice, infrastructure trade-offs, status codes, guardrails,
evaluation, limitations, and future work. The technical report, code walkthrough, submission summary,
high-resolution PNGs, and editable Draw.io diagrams are included in the artifacts and docs folders.

I did not add RAG, a vector store, Kafka, or autonomous tools because the assessment input is one request and
the required output is a bounded classification and draft. Those components would increase failure surface
without improving correctness. The design is microservice-based where the boundary is useful—UI versus API
and external stores—but it avoids splitting four dependent graph nodes into network services. That gives a
production-aware, explainable submission without claiming unnecessary production scale.”

