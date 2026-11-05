from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .analysis import (
    aggregate_perturbation_profile,
    classify_evidence,
    inspect_metadata,
    parse_event_grounding,
    provenance,
)
from .models import Report, VerifyRequest, VerifyResponse

app = FastAPI(title="EventProof", version="0.1.0")
STATIC = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.get("/", include_in_schema=False)
async def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/v1/verify", response_model=VerifyResponse)
async def verify(request: VerifyRequest) -> VerifyResponse:
    category, confidence, rationale = classify_evidence(
        request.evidence,
        external_support=request.check_external_sources
        and request.evidence.metadata.get("supported") is True,
    )
    limitations = [
        "This MVP does not prove authenticity and never infers confidence without corroboration.",
        "External adapters are opt-in and network failures are treated as unavailable.",
    ]
    report = Report(
        category=category,
        confidence=confidence,
        rationale=rationale,
        event_grounding=parse_event_grounding(request.evidence),
        metadata_inspection=inspect_metadata(request.evidence),
        perturbation_profile=aggregate_perturbation_profile(request.evidence.perturbation_scores),
        provenance=provenance(request.evidence),
        limitations=limitations,
    )
    return VerifyResponse(report=report)
