import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.datastructures import UploadFile as StarletteUploadFile

from .adapters import gdacs_events, open_meteo_weather
from .analysis import (
    aggregate_perturbation_profile,
    classify_evidence,
    inspect_media,
    inspect_metadata,
    parse_event_grounding,
    provenance,
    validate_media,
)
from .models import EvidenceInput, Report, VerifyRequest, VerifyResponse

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
async def verify(request: Request) -> VerifyResponse:
    evidence, check_external_sources, media = await parse_request(request)
    external_evidence: dict[str, Any] = {
        "requested": check_external_sources,
        "status": "not_requested",
        "sources": [],
    }
    external_support = False
    external_conflict = False
    if check_external_sources:
        external_evidence = await collect_external_evidence(evidence)
        external_support = external_evidence["status"] == "available"
    category, confidence, rationale = classify_evidence(
        evidence,
        external_conflict=external_conflict,
        external_support=external_support,
    )
    limitations = [
        "This MVP does not prove authenticity and never infers confidence without corroboration.",
        "External adapters are opt-in; network failures are reported as unavailable evidence.",
        "Heavyweight deepfake, temporal localization, and C2PA model adapters are not bundled.",
    ]
    report = Report(
        category=category,
        confidence=confidence,
        rationale=rationale,
        event_grounding=parse_event_grounding(evidence),
        metadata_inspection=inspect_metadata(evidence),
        perturbation_profile=aggregate_perturbation_profile(evidence.perturbation_scores),
        provenance=provenance(evidence),
        media_inspection=inspect_media(*media),
        external_evidence=external_evidence,
        limitations=limitations,
    )
    return VerifyResponse(report=report)


async def parse_request(
    request: Request,
) -> tuple[EvidenceInput, bool, tuple[str | None, str | None, bytes]]:
    content_type = request.headers.get("content-type", "")
    if content_type.startswith("application/json"):
        try:
            payload = VerifyRequest.model_validate(await request.json())
        except Exception as exc:
            raise HTTPException(status_code=422, detail=f"Invalid JSON request: {exc}") from exc
        return payload.evidence, payload.check_external_sources, (None, None, b"")
    if content_type.startswith("multipart/form-data"):
        form = await request.form()
        upload = form.get("media")
        is_upload = isinstance(upload, (UploadFile, StarletteUploadFile))
        filename = upload.filename if is_upload else None
        upload_type = upload.content_type if is_upload else None
        data = await upload.read() if is_upload else b""
        error = validate_media(filename, upload_type, data)
        if error:
            raise HTTPException(status_code=422, detail=error)
        try:
            metadata = json.loads(str(form.get("metadata") or "{}"))
            perturbation_scores = json.loads(str(form.get("perturbation_scores") or "{}"))
            evidence = EvidenceInput(
                text=str(form.get("text") or ""),
                source_url=str(form.get("source_url") or "") or None,
                observed_at=str(form.get("observed_at") or "") or None,
                claimed_location=str(form.get("claimed_location") or "") or None,
                claimed_event=str(form.get("claimed_event") or "") or None,
                metadata=metadata,
                perturbation_scores=perturbation_scores,
            )
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid multipart evidence fields: {exc}",
            ) from exc
        return evidence, str(form.get("check_external_sources")).lower() == "true", (
            filename,
            upload_type,
            data,
        )
    raise HTTPException(status_code=415, detail="Use application/json or multipart/form-data.")


async def collect_external_evidence(evidence: EvidenceInput) -> dict[str, Any]:
    sources: list[dict[str, Any]] = []
    grounding = parse_event_grounding(evidence)
    coordinates = grounding["coordinates"]
    dates = grounding["dates"]
    if coordinates and dates:
        latitude, longitude = (float(value.strip()) for value in coordinates[0].split(","))
        try:
            sources.append(
                await open_meteo_weather(latitude, longitude, dates[0].replace("/", "-"))
            )
        except Exception as exc:
            sources.append({"provider": "Open-Meteo", "available": False, "error": str(exc)})
    try:
        sources.append(await gdacs_events())
    except Exception as exc:
        sources.append({"provider": "GDACS", "available": False, "error": str(exc)})
    available = any(source.get("available") is True for source in sources)
    return {
        "requested": True,
        "status": "available" if available else "unavailable",
        "sources": sources,
        "note": (
            "Availability is not proof of claim support; inspect source data before "
            "relying on it."
        ),
    }
