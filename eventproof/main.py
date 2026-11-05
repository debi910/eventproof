import json
import uuid
from datetime import datetime, timezone
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
        report_id=f"EP-{uuid.uuid4().hex[:10].upper()}",
        generated_at=datetime.now(timezone.utc).isoformat(),
        category=category,
        confidence=confidence,
        rationale=rationale,
        event_grounding=parse_event_grounding(evidence),
        metadata_inspection=inspect_metadata(evidence),
        perturbation_profile=aggregate_perturbation_profile(evidence.perturbation_scores),
        provenance=provenance(evidence),
        media_inspection=inspect_media(*media),
        external_evidence=external_evidence,
        evidence_ledger=build_evidence_ledger(
            evidence, category.value, external_evidence
        ),
        review_recommendation=build_review_recommendation(
            evidence, category.value, external_evidence
        ),
        limitations=limitations,
    )
    return VerifyResponse(report=report)


def build_evidence_ledger(
    evidence: EvidenceInput, category: str, external_evidence: dict[str, Any]
) -> list[dict[str, Any]]:
    ledger = [
        {
            "status": "unknown",
            "signal": "Media model analysis",
            "finding": "Heavyweight pixel, waveform, and temporal detectors are not bundled.",
        },
        {
            "status": "unknown" if not evidence.metadata else "observed",
            "signal": "Metadata / provenance",
            "finding": (
                "No metadata supplied."
                if not evidence.metadata
                else f"Inspected keys: {', '.join(sorted(evidence.metadata))}."
            ),
        },
        {
            "status": (
                "observed"
                if evidence.claimed_event or evidence.claimed_location
                else "unknown"
            ),
            "signal": "Claim grounding",
            "finding": (
                "Event or location fields were supplied."
                if evidence.claimed_event or evidence.claimed_location
                else "No structured event or location claim was supplied."
            ),
        },
    ]
    if evidence.perturbation_scores:
        score = sum(evidence.perturbation_scores.values()) / len(evidence.perturbation_scores)
        ledger.append(
            {
                "status": "contradicts" if score >= 0.8 else "observed",
                "signal": "Perturbation profile",
                "finding": f"Mean score {score:.0%}; this is a manipulation signal, not proof.",
            }
        )
    ledger.append(
        {
            "status": "unknown"
            if not external_evidence["requested"]
            else ("observed" if external_evidence["status"] == "available" else "unknown"),
            "signal": "External grounding",
            "finding": (
                "Not requested."
                if not external_evidence["requested"]
                else (
                    "At least one source responded; response availability is not claim support."
                    if external_evidence["status"] == "available"
                    else "Requested sources were unavailable."
                )
            ),
        }
    )
    if category == "CONFLICTING_EVIDENCE":
        ledger.append(
            {
                "status": "contradicts",
                "signal": "Aggregation",
                "finding": "Conflicting evidence takes precedence over a simple positive signal.",
            }
        )
    return ledger


def build_review_recommendation(
    evidence: EvidenceInput, category: str, external_evidence: dict[str, Any]
) -> dict[str, Any]:
    next_checks = ["Have a human reviewer inspect the original file and source context."]
    if not evidence.metadata:
        next_checks.append("Request original metadata or a chain-of-custody record.")
    if not evidence.perturbation_scores:
        next_checks.append("Run an enabled media detector before making a high-stakes decision.")
    if external_evidence["requested"] and external_evidence["status"] == "unavailable":
        next_checks.append("Retry external grounding when the source APIs are reachable.")
    return {
        "priority": "high" if category != "SUPPORTED" else "medium",
        "decision": "human_review_required",
        "next_checks": next_checks,
    }


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
