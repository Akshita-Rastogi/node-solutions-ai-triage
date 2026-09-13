# Video 2 — Redis and PostgreSQL Evidence Walkthrough

**Suggested duration:** 4–6 minutes  
**Screens:** Streamlit → RedisInsight → Terminal → DBeaver → FastAPI metrics

## 00:00–00:45 — Storage responsibilities

**Screen:** Streamlit with one completed request.

**Say:**

“This video explains the two persistence-related components and why they have different responsibilities.
PostgreSQL is the durable system of record for request decisions and human reviews. Redis is not a second
request database. It stores only short-lived distributed rate-limit counters. This avoids duplicating
sensitive request text and ensures a Redis restart cannot remove completed triage history.”

## 00:45–01:50 — Generate and inspect a Redis key

**Screen:** Submit a new request in Streamlit. Immediately move to RedisInsight, open `127.0.0.1:6380`,
select database `db0`, open **Browse**, refresh, and search for:

```text
rate:*
```

Also keep this Terminal command ready:

```bash
docker compose exec redis redis-cli --scan --pattern 'rate:*'
```

Copy a returned key and run:

```bash
docker compose exec redis redis-cli GET 'PASTE_THE_KEY_HERE'
docker compose exec redis redis-cli TTL 'PASTE_THE_KEY_HERE'
```

**Say:**

“Submitting through the UI calls the same public FastAPI endpoint as any other client. Authentication returns
only a hashed API-key identity to the rate limiter. Redis increments a `rate:` counter and assigns a sixty-second
expiry. The value is the number of calls in the current fixed window, and TTL shows how many seconds remain.
The key may disappear quickly by design, so I refresh immediately after submission.

The full request is intentionally not visible in RedisInsight. That is correct architecture: Redis contains
ephemeral operational state, not durable or sensitive business content. A shared Redis counter also works if
the API is later replicated, unlike an in-process Python dictionary.”

## 01:50–03:40 — Inspect PostgreSQL in DBeaver

**Screen:** DBeaver connection using:

```text
Host: localhost
Port: 5433
Database: triage
Username: triage
Password: triage
```

Run:

```sql
SELECT
    request_id,
    original_request,
    redacted_request,
    summary,
    category,
    priority,
    owner,
    confidence,
    decision_source,
    risk_flags,
    created_at
FROM triage_requests
ORDER BY created_at DESC;
```

Then run:

```sql
SELECT
    t.request_id,
    t.category,
    t.priority,
    t.owner,
    t.decision_source,
    r.outcome,
    r.notes,
    r.reviewed_at
FROM triage_requests AS t
LEFT JOIN triage_reviews AS r ON r.request_id = t.request_id
ORDER BY t.created_at DESC;
```

**Say:**

“PostgreSQL contains the original request for authorised audit, the redacted form sent to analysis, the
validated decision, draft, warnings, trace, model source, and creation time. Stable relations and audit
requirements are why I chose PostgreSQL over MongoDB. UUID primary keys, a unique idempotency key, a foreign
key from review to request, and transactions express the invariants directly. JSONB is reserved for flexible
risk flags and node traces.

The join shows the original AI decision beside the later human outcome. Review does not update or erase the
AI record. It creates one separate immutable review row. A second review attempt returns HTTP 409, which
protects review history from accidental resubmission.”

## 03:40–04:35 — Idempotency and durability

**Screen:** FastAPI docs or Terminal. Re-run one API call with the same idempotency key.

**Say:**

“A new triage request returns HTTP 201. Repeating the same idempotency key returns the existing durable result
with HTTP 200 and the `Idempotent-Replayed` header. PostgreSQL is the final concurrency authority, so duplicate
work remains protected even if Redis is cleared. `docker compose down` preserves both named volumes; only an
intentional `docker compose down -v` deletes local data.”

## 04:35–05:20 — Observability evidence

**Screen:** Terminal:

```bash
docker compose logs --tail=50 api
curl -s http://localhost:8100/metrics | grep '^triage_'
```

**Say:**

“Structured logs contain correlation ID, route, status code, and latency, but not request bodies or raw API
keys. Prometheus metrics use low-cardinality labels for request counts, status, decision class, and latency.
This gives operational evidence without leaking client content into logs or metric labels. In summary:
PostgreSQL answers what decision was made and reviewed; Redis answers whether this authenticated caller may
make another request in the current time window.”

