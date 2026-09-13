from triage.database import Database
from triage.models import TriageRequest, TriageResult


class TriageService:
    """Application service coordinating idempotency, the agent graph, and persistence."""

    def __init__(self, graph, database: Database, model: str):
        self.graph = graph
        self.database = database
        self.model = model

    async def triage(self, request: TriageRequest) -> tuple[TriageResult, bool]:
        """Run one request or replay its prior durable result when the key already exists."""
        if request.idempotency_key:
            existing = await self.database.by_idempotency_key(request.idempotency_key)
            if existing:
                return existing, True
        state = await self.graph.ainvoke({"original_text": request.request_text})
        decision = state["decision"]
        result = TriageResult(
            **decision.model_dump(),
            source=request.source,
            original_request=request.request_text,
            draft_response=state["draft"],
            model_used=self.model,
            decision_source=state["decision_source"],
            warnings=state.get("warnings", []),
            trace=state.get("trace", []),
        )
        await self.database.insert(result, state["redacted_text"], request.idempotency_key)
        return result, False

