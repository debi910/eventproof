from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, HttpUrl, field_validator


class EvidenceCategory(str, Enum):
    SUPPORTED = "SUPPORTED"
    MANIPULATED = "MANIPULATED"
    RECYCLED_OR_MISCONTEXTUALIZED = "RECYCLED_OR_MISCONTEXTUALIZED"
    CONFLICTING_EVIDENCE = "CONFLICTING_EVIDENCE"
    UNVERIFIABLE = "UNVERIFIABLE"


class EvidenceInput(BaseModel):
    text: str = Field("", max_length=20_000)
    source_url: HttpUrl | None = None
    observed_at: str | None = Field(None, max_length=100)
    claimed_location: str | None = Field(None, max_length=200)
    claimed_event: str | None = Field(None, max_length=500)
    metadata: dict[str, Any] = Field(default_factory=dict)
    perturbation_scores: dict[str, float] = Field(default_factory=dict)

    @field_validator("text")
    @classmethod
    def non_empty_payload(cls, value: str) -> str:
        return value.strip()

    @field_validator("perturbation_scores")
    @classmethod
    def score_range(cls, value: dict[str, float]) -> dict[str, float]:
        if any(not 0 <= score <= 1 for score in value.values()):
            raise ValueError("perturbation scores must be between 0 and 1")
        return value


class VerifyRequest(BaseModel):
    evidence: EvidenceInput
    check_external_sources: bool = False


class Report(BaseModel):
    category: EvidenceCategory
    confidence: float | None = None
    rationale: list[str]
    event_grounding: dict[str, Any]
    metadata_inspection: dict[str, Any]
    perturbation_profile: dict[str, Any]
    provenance: dict[str, Any]
    media_inspection: dict[str, Any]
    external_evidence: dict[str, Any]
    limitations: list[str]


class VerifyResponse(BaseModel):
    report: Report
