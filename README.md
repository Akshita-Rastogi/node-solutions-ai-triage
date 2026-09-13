# Node Solutions — AI Request Triage Assistant

This submission turns the six supplied mock requests into a local, review-first triage workflow. It
summarises each request, selects exactly one allowed category and owner, assigns a priority with a
reason, and drafts a professional acknowledgement. It does **not** automatically send that draft:
an operator must approve, correct, or reject it.

The assessment asks for thoughtful judgment rather than unnecessary infrastructure. The solution is
therefore production-aware but intentionally compact: one FastAPI service, one Streamlit interface,
an explicit LangGraph workflow, local Ollama inference, PostgreSQL persistence, and Redis operational
controls. There are no TOML files, vector database, cloud services, or hidden customer data.

Supporting documents:

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md): system and state diagrams, node design, failure paths,
  and the framework decision.
- [`docs/architecture.drawio`](docs/architecture.drawio): editable diagrams.net architecture source for
  submission or export to PNG/PDF.
- [`docs/CODE_WALKTHROUGH.md`](docs/CODE_WALKTHROUGH.md): every file and main method, the complete call
  flow, extension steps, and operational inspection commands.
- [`SUBMISSION.md`](SUBMISSION.md): concise reviewer-facing problem statement and coverage mapping.

## Run it locally

Prerequisites: Docker Desktop and Ollama. The default local model is `qwen3:4b`, a practical balance
between classification quality, structured-output behavior, memory use, and laptop latency.

```bash
cd node-solutions-ai-triage
ollama pull qwen3:4b
cp .env.example .env
docker compose up -d --build
docker compose ps
curl -s http://localhost:8100/health/ready | python -m json.tool
```

Open:

- Streamlit UI: http://localhost:8601
- FastAPI documentation: http://localhost:8100/docs
- PostgreSQL: `postgresql://triage:triage@localhost:5433/triage`
- Redis host port: `localhost:6380`
- Redis CLI: `docker compose exec redis redis-cli`

The Ollama process remains on the host so its models and acceleration work normally. Containers reach
it at `host.docker.internal:11434`. All application data remains on the machine.

Stop containers without deleting records:

```bash
docker compose down
```

Delete the local database and Redis volumes only when an intentional clean reset is needed:

```bash
docker compose down -v
```

## What to demonstrate

Use the selector in the UI for at least these three paths:

1. Request 01: commercial automation enquiry → Sales / Medium / Sales Team.
2. Request 02: active client-portal outage → Technical / Urgent / Engineering.
3. Request 05: wrong-workspace customer data → Technical / Urgent / Engineering, with privacy and
   access-control risk flags.

Then submit a human review, open the durable Review Queue, and show the decision trace. New mock text
can be pasted into the same input. Do not enter real confidential or private client data.

The selector also exposes six additional cases from `data/edge_case_requests.json`: ambiguity, prompt
injection, sensitive identifiers, conflicting urgency, mixed intent, and a novel support request. They
demonstrate that the supplied six messages are examples rather than hardcoded response branches.

## Architecture and end-to-end flow

```text
Browser / Streamlit
        │
        ▼
FastAPI validation ── API key ── Redis rate limit ── idempotency check
        │
        ▼
LangGraph workflow
  1. sanitize: redact contact/payment identifiers; detect prompt injection
  2. analyse: Ollama returns schema-constrained summary/category/priority/owner
  3. validate: deterministic business invariants correct unsafe routes
  4. draft: a second Ollama role creates a cautious first response
        │
        ├── inference failure → deterministic classification/template fallback
        ▼
PostgreSQL immutable decision record
        │
        ▼
Human approve / correct / reject record (original inference is retained)
```

LangGraph is used because this is genuinely a multi-stage decision workflow. Each node owns one
responsibility and passes typed state to the next stage. The graph makes future conditional branches,
specialist agents, and approval interrupts possible without hiding logic in a monolithic prompt.
Parallel agents are not used here because analysis must precede policy validation and drafting; adding
parallelism to four short sequential dependencies would increase complexity without reducing the
critical path.

LangChain is useful for composing model and retrieval components, but LangGraph is the stronger fit here
because state transitions, reducers, failure branches, and future human interrupts are first-class and
visible. A free-form ReAct, CrewAI, or AutoGen workflow would grant unnecessary autonomy for a known safe
sequence and make latency and deterministic incident rules harder to reason about. A plain Python chain
would work today but provides a less explicit extension path. See the full
[framework comparison](docs/ARCHITECTURE.md#why-langgraph-rather-than-langchain-or-another-agent-framework).

The two AI roles are deliberately separated:

- The **analysis agent** uses temperature 0 and a Pydantic JSON schema. It must return one value from
  each assessment enum plus a concise rationale, risk flags, and confidence.
- The **response agent** uses temperature 0.1. It receives the validated decision, drafts only an
  acknowledgement, and is prohibited from inventing prices, deadlines, completed actions, or copying
  sensitive identifiers.

## Why these infrastructure choices

**Ollama instead of a hosted model:** the supplied examples can remain local, setup needs no API key,
and structured JSON output is supported. `qwen3:4b` is the default for laptop-friendly latency. A larger
local model can be selected by changing `OLLAMA_MODEL`; the typed output and guardrails remain the same.

**PostgreSQL instead of MongoDB:** request, decision, and one-to-one review data have stable relations,
strong uniqueness requirements, and audit semantics. Transactions, UUID keys, unique idempotency keys,
foreign keys, and ordered queue queries fit a relational database well. JSONB is used only for flexible
risk flags and traces. MongoDB would work, but is not the better default for these invariants.

**Redis:** rate-limit counters must be shared if the API gains replicas. Redis also provides predictable
expiry and avoids unsafe in-process counters. Durable idempotency is ultimately enforced by PostgreSQL,
so a Redis restart cannot create duplicate successful requests.

**No vector database or RAG:** the challenge supplies individual requests and asks for classification,
not knowledge retrieval. Embedding six messages in Qdrant would add operational surface without helping
the result. If policy documents became part of the task, retrieval with citations would be a separate,
justified capability.

## Guardrails and failure handling

- Input is limited to 5–5,000 characters, meaningful text only, and known sources.
- Email addresses, phone numbers, and card-like numbers are redacted before inference.
- The drafting agent receives only the validated PII-free summary and routing decision, not the original
  request or literal redaction placeholders. This second-stage minimization prevents placeholder leakage.
- Client content is wrapped and explicitly treated as untrusted data. Common prompt-injection language
  is flagged; it never replaces the system policy. A detected injection is normalised to Other / Low /
  Client Success and receives a guarded clarification template without a response-agent call.
- Pydantic constrains category, priority, owner, lengths, and confidence. Invalid model JSON receives one
  repair attempt, then the workflow degrades to deterministic routing.
- Security/privacy exposure and active outages are always elevated to Technical / Urgent / Engineering.
  Billing always routes to Finance and commercial enquiries to Sales Team.
- Privacy and access-control incidents use a deterministic response template after routing. It gives safe
  containment guidance but never claims that access was removed or remediation was performed.
- Generated text is always labelled a draft for human review. A generation failure uses a safe generic
  acknowledgement instead of returning an error or fabricated content.
- API keys are compared without logging them; logs use hashed identities and correlation IDs.
- Every successful result records the model, decision source, warnings, token/duration metadata, and
  policy trace. Human review is a separate immutable record.
- Idempotency keys make retried submissions return HTTP 200 with `Idempotent-Replayed: true`; new work
  returns HTTP 201.
- Redis limits authenticated callers. Readiness becomes HTTP 503 if PostgreSQL, Redis, or Ollama is not
  ready, while liveness still distinguishes a running process from a capable service.

### Correct API status codes

| Situation | Status |
|---|---:|
| New triage or new human review | 201 |
| Read/list or idempotent replay | 200 |
| Missing/invalid API key | 401 |
| Unknown request ID | 404 |
| Duplicate review or idempotency race | 409 |
| Invalid body, enum, UUID, or limit | 422 |
| Rate limit exceeded | 429 |
| Dependency not ready | 503 |
| Unexpected server failure | 500 |

## Evaluation strategy

`data/evaluation.json` is a golden set built from all six supplied requests. It checks the three most
important deterministic decision dimensions independently: category, priority, and owner. Request 05 is
also unit-tested against a deliberately wrong model answer, proving that the policy layer—not optimistic
prompting—enforces escalation.

Run unit tests and static checks:

```bash
docker compose exec api pytest -q
docker compose exec api ruff check --line-length 100 src tests scripts ui
```

Run the six-case evaluation through the actual HTTP boundary after the services are ready:

```bash
docker compose exec api python scripts/evaluate.py
cat output/evaluation-results.json
```

The report contains expected and actual outputs, per-field checks, and an overall pass count. In a larger
system I would add a hand-labelled, versioned dataset with class balance and hard negatives; macro F1 and
per-class recall for classification; exact-match owner accuracy; critical-incident false-negative rate;
schema-validity rate; human edit distance for drafts; and p50/p95/p99 latency. The security false-negative
rate is the release-blocking metric because aggregate accuracy can hide rare but costly failures.

## Brownie-point features beyond the minimum

These reflect experience with the places where AI workflows usually fail:

1. **Explicit multi-stage agent state:** separate analysis and drafting roles use a typed LangGraph;
   additive reducers preserve warnings and traces from every node.
2. **Schema-constrained local inference:** Ollama receives the Pydantic JSON schema, repairs malformed
   output once, and exposes whether local inference or fallback produced the decision.
3. **Policy-backed guardrails:** privacy exposure and outages cannot be under-prioritised even when the
   model makes a poor decision. Ownership invariants protect Billing and Sales routes.
4. **Privacy and adversarial boundary:** contact and payment identifiers are redacted before inference;
   prompt-injection language is detected and remains untrusted request data.
5. **Graceful degradation:** model timeout or invalid output produces visible warnings plus a conservative
   classification and safe draft instead of fabrication or an unexplained failure.
6. **Human-in-the-loop audit design:** output is always a draft. Review is stored separately, so the
   original AI inference is never overwritten.
7. **Safe retry and concurrency semantics:** durable idempotency avoids duplicate work; PostgreSQL handles
   uniqueness races; Redis shares limits across future replicas.
8. **Observable behavior:** correlation IDs, JSON logs, low-cardinality Prometheus metrics, dependency
   readiness, node traces, token counts, and inference durations make failures diagnosable.
9. **Regression-first evaluation:** all supplied cases have field-level golden expectations, and tests
   deliberately feed incorrect decisions into the critical safety layer.
10. **Generalisation demonstration:** six extra edge cases exercise unseen and adversarial inputs without
    hardcoded final responses.

These additions make the problem meaningfully harder while staying relevant to the assessment. They do
not claim that a local demo is fully production-ready.

## Project structure

```text
node-solutions-ai-triage/
├── data/                 supplied, edge-case, and golden evaluation requests
├── docs/                 architecture diagrams and detailed code walkthrough
├── output/               generated evaluation evidence (ignored except placeholder)
├── scripts/evaluate.py   real-API evaluation runner
├── src/triage/
│   ├── main.py           FastAPI routes, lifecycle, status codes and request logging
│   ├── graph.py          LangGraph workflow and node transitions
│   ├── ollama.py         structured local inference, repair and timeout boundary
│   ├── guardrails.py     deterministic routing invariants and fallback
│   ├── security.py       authentication, redaction and injection detection
│   ├── service.py        idempotency, graph execution and persistence orchestration
│   ├── database.py       PostgreSQL schema and repository
│   ├── rate_limit.py     Redis operational control
│   ├── models.py         external and internal Pydantic contracts
│   ├── config.py         environment configuration
│   ├── logging.py        structured JSON logs
│   └── metrics.py        Prometheus counters and latency histogram
├── tests/                security and business-invariant regression tests
├── ui/app.py             Streamlit triage and review interface
├── Dockerfile
├── docker-compose.yml
├── requirements.txt      one simple unpinned dependency file
└── .env.example
```

## Design decisions, limitations, and next improvements

Prompt wording is intentionally short and policy-oriented. Schemas enforce syntax; deterministic rules
enforce high-cost safety decisions. Confidence is model-reported diagnostic metadata, not a calibrated
probability, so the UI never treats it as permission to auto-send.

Current limitations:

1. Keyword-backed invariants cover the supplied incident patterns, not every paraphrase or language.
2. The golden set is only six examples, so it cannot estimate real generalisation or class imbalance.
3. The app has one API-key role and no tenant-level row security or secrets manager.
4. Draft quality is evaluated by human review, not yet by a rubric-based automated judge.
5. A fixed-window rate limiter permits bursts near a minute boundary.

With another day I would add multilingual adversarial examples, reviewer corrections as a versioned
offline dataset, calibrated critical-risk scoring, role-based access, Alembic-style migrations (without
changing the requested simple dependency format), OpenTelemetry spans, a sliding-window limiter, and CI
latency/quality regression gates. Feedback would improve prompts or training/evaluation datasets only
after offline review; merely storing approvals is not reinforcement learning or RLHF.

## Direct API example

```bash
curl -i http://localhost:8100/v1/triage \
  -H 'Content-Type: application/json' \
  -H 'X-API-Key: demo-key' \
  -d '{
    "request_text":"A user can see contacts from the wrong workspace. Remove access immediately.",
    "source":"email",
    "idempotency_key":"demo-security-0001"
  }'
```

The draft is for internal review. No endpoint sends email or changes a customer system.
