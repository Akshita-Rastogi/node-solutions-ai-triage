import json
from uuid import UUID

import asyncpg

from triage.models import ReviewRequest, TriageResult


class Database:
    """Async PostgreSQL repository; model output and human review remain immutable records."""

    def __init__(self, url: str):
        self.url = url
        self.pool: asyncpg.Pool | None = None

    async def connect(self) -> None:
        """Create the connection pool and idempotently initialise the small schema."""
        self.pool = await asyncpg.create_pool(self.url, min_size=1, max_size=8)
        async with self.pool.acquire() as connection:
            await connection.execute(
                """
                CREATE TABLE IF NOT EXISTS triage_requests (
                    request_id UUID PRIMARY KEY,
                    idempotency_key TEXT UNIQUE,
                    source TEXT NOT NULL,
                    original_request TEXT NOT NULL,
                    redacted_request TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    category TEXT NOT NULL,
                    priority TEXT NOT NULL,
                    priority_reason TEXT NOT NULL,
                    owner TEXT NOT NULL,
                    risk_flags JSONB NOT NULL,
                    confidence DOUBLE PRECISION NOT NULL,
                    draft_response TEXT NOT NULL,
                    requires_human_review BOOLEAN NOT NULL,
                    model_used TEXT NOT NULL,
                    decision_source TEXT NOT NULL,
                    warnings JSONB NOT NULL,
                    trace JSONB NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL
                );
                CREATE INDEX IF NOT EXISTS triage_created_at_idx
                    ON triage_requests (created_at DESC);
                CREATE TABLE IF NOT EXISTS triage_reviews (
                    request_id UUID PRIMARY KEY REFERENCES triage_requests(request_id),
                    outcome TEXT NOT NULL,
                    notes TEXT NOT NULL,
                    reviewed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                """
            )

    async def close(self) -> None:
        """Release database connections during graceful application shutdown."""
        if self.pool:
            await self.pool.close()

    async def healthy(self) -> bool:
        """Check a real database round trip, not only process availability."""
        try:
            if not self.pool:
                return False
            return await self.pool.fetchval("SELECT 1") == 1
        except (asyncpg.PostgresError, OSError):
            return False

    async def insert(self, result: TriageResult, redacted: str, key: str | None) -> None:
        """Persist the complete auditable inference without storing raw model prompts."""
        assert self.pool
        await self.pool.execute(
            """INSERT INTO triage_requests VALUES(
                $1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11::jsonb,$12,$13,$14,$15,$16,$17::jsonb,$18::jsonb,$19
            )""",
            result.request_id, key, result.source, result.original_request, redacted,
            result.summary, result.category.value, result.priority.value, result.priority_reason,
            result.owner.value, json.dumps(result.risk_flags), result.confidence,
            result.draft_response, result.requires_human_review, result.model_used,
            result.decision_source, json.dumps(result.warnings), json.dumps(result.trace),
            result.created_at,
        )

    async def by_idempotency_key(self, key: str) -> TriageResult | None:
        """Return a prior successful result so client retries cannot duplicate work."""
        assert self.pool
        row = await self.pool.fetchrow(
            "SELECT * FROM triage_requests WHERE idempotency_key=$1", key
        )
        return self._result(row) if row else None

    async def get(self, request_id: UUID) -> TriageResult | None:
        """Fetch one triage result by its stable identifier."""
        assert self.pool
        row = await self.pool.fetchrow(
            "SELECT * FROM triage_requests WHERE request_id=$1", request_id
        )
        return self._result(row) if row else None

    async def list(self, limit: int) -> list[TriageResult]:
        """Return the latest queue items in deterministic order."""
        assert self.pool
        rows = await self.pool.fetch(
            "SELECT * FROM triage_requests ORDER BY created_at DESC LIMIT $1", limit
        )
        return [self._result(row) for row in rows]

    async def add_review(self, request_id: UUID, review: ReviewRequest) -> bool:
        """Capture one human decision; return False when the item was already reviewed."""
        assert self.pool
        status = await self.pool.execute(
            """INSERT INTO triage_reviews(request_id,outcome,notes) VALUES($1,$2,$3)
               ON CONFLICT(request_id) DO NOTHING""",
            request_id, review.outcome, review.notes,
        )
        return status == "INSERT 0 1"

    @staticmethod
    def _result(row: asyncpg.Record) -> TriageResult:
        """Map a storage row back to the public schema."""
        values = dict(row)
        for field in ("risk_flags", "warnings", "trace"):
            if isinstance(values[field], str):
                values[field] = json.loads(values[field])
        return TriageResult.model_validate(values)
