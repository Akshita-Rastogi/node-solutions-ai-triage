from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Category(StrEnum):
    SALES = "Sales"
    SUPPORT = "Support"
    BILLING = "Billing"
    TECHNICAL = "Technical"
    OTHER = "Other"


class Priority(StrEnum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    URGENT = "Urgent"


class Owner(StrEnum):
    SALES = "Sales Team"
    SUCCESS = "Client Success"
    FINANCE = "Finance"
    ENGINEERING = "Engineering"


class TriageRequest(BaseModel):
    """Validated external request accepted by the API."""

    request_text: str = Field(min_length=5, max_length=5000)
    source: str = Field(default="web", pattern=r"^(email|web|chat)$")
    idempotency_key: str | None = Field(default=None, min_length=8, max_length=100)

    @field_validator("request_text")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        """Collapse whitespace and reject control-only input."""
        normalized = " ".join(value.split())
        if not any(character.isalnum() for character in normalized):
            raise ValueError("request_text must contain meaningful text")
        return normalized


class AnalysisDecision(BaseModel):
    """Schema-constrained output expected from the analysis agent."""

    summary: str = Field(min_length=10, max_length=220)
    category: Category
    priority: Priority
    priority_reason: str = Field(min_length=8, max_length=240)
    owner: Owner
    risk_flags: list[str] = Field(default_factory=list, max_length=5)
    confidence: float = Field(ge=0, le=1)


class DraftOutput(BaseModel):
    """Schema-constrained customer-facing content returned by the response agent."""

    message: str = Field(min_length=20, max_length=800)


class TriageResult(AnalysisDecision):
    """Stable response contract returned to the UI and stored for audit."""

    model_config = ConfigDict(from_attributes=True)

    request_id: UUID = Field(default_factory=uuid4)
    source: str
    original_request: str
    draft_response: str = Field(min_length=20, max_length=1200)
    requires_human_review: bool = True
    model_used: str
    decision_source: str
    warnings: list[str] = Field(default_factory=list)
    trace: list[dict] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ReviewRequest(BaseModel):
    """Human review decision captured without changing the original inference."""

    outcome: str = Field(pattern=r"^(approved|corrected|rejected)$")
    notes: str = Field(default="", max_length=1000)


class EvaluationCase(BaseModel):
    id: str
    request_text: str
    expected_category: Category
    expected_priority: Priority
    expected_owner: Owner
