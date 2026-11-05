"""Deterministic evidence analysis. It deliberately refuses to invent certainty."""

from __future__ import annotations

import hashlib
import re
from typing import Any

from .models import EvidenceCategory, EvidenceInput


def parse_event_grounding(evidence: EvidenceInput) -> dict[str, Any]:
    text = evidence.text
    dates = re.findall(r"\b(?:20\d{2}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}[-/]\d{1,2}[-/]20\d{2})\b", text)
    coordinates = re.findall(r"[-+]?\d{1,3}\.\d+\s*,\s*[-+]?\d{1,3}\.\d+", text)
    locations = [x for x in (evidence.claimed_location,) if x]
    event = evidence.claimed_event or next(
        (line.strip() for line in text.splitlines() if line.strip()), None
    )
    return {
        "event": event,
        "locations": locations,
        "dates": dates,
        "coordinates": coordinates,
        "has_claim": bool(event or locations or dates or coordinates),
    }


def aggregate_perturbation_profile(scores: dict[str, float]) -> dict[str, Any]:
    if not scores:
        return {"available": False, "score": None, "signals": [], "interpretation": "not provided"}
    score = sum(scores.values()) / len(scores)
    signals = [name for name, value in scores.items() if value >= 0.6]
    interpretation = (
        "strong manipulation signal"
        if score >= 0.7
        else "some manipulation signal"
        if score >= 0.4
        else "weak manipulation signal"
    )
    return {
        "available": True,
        "score": round(score, 4),
        "signals": signals,
        "interpretation": interpretation,
        "sample_count": len(scores),
    }


def inspect_metadata(evidence: EvidenceInput) -> dict[str, Any]:
    metadata = evidence.metadata
    asserted_flags = [
        key
        for key in (
            "supported",
            "conflicting_evidence",
            "recycled",
            "miscontextualized",
            "synthetic",
        )
        if metadata.get(key) is True
    ]
    suspicious = [
        key for key in ("software", "editing_software", "history", "synthetic") if key in metadata
    ]
    return {
        "provided": bool(metadata),
        "keys": sorted(metadata),
        "suspicious_keys": suspicious,
        "has_timestamp": bool(metadata.get("timestamp") or evidence.observed_at),
        "has_hash": bool(metadata.get("sha256") or metadata.get("hash")),
        "asserted_flags": asserted_flags,
        "assertions_are_verified": False,
    }


def inspect_media(filename: str | None, content_type: str | None, data: bytes) -> dict[str, Any]:
    if not filename:
        return {
            "provided": False,
            "status": "not_provided",
            "sha256": None,
            "size_bytes": 0,
            "content_type": None,
        }
    return {
        "provided": True,
        "status": "signature_validated",
        "filename": filename,
        "content_type": content_type,
        "size_bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "analysis_status": "metadata_only",
        "note": (
            "File signature is validated; pixel, waveform, and temporal model analysis "
            "are not enabled in this MVP."
        ),
    }


def validate_media(filename: str | None, content_type: str | None, data: bytes) -> str | None:
    if not filename:
        return None
    allowed_prefixes = ("image/", "video/", "audio/")
    if not content_type or not content_type.startswith(allowed_prefixes):
        return "Only image, video, and audio uploads are accepted."
    if not data:
        return "The uploaded media file is empty."
    if len(data) > 25 * 1024 * 1024:
        return "Media uploads must be 25 MB or smaller."
    detected_type = sniff_media_type(data)
    if detected_type is None:
        return "The uploaded file does not match a supported image, video, or audio signature."
    if not media_types_compatible(content_type, detected_type):
        return f"Uploaded content is {detected_type}, not {content_type}."
    return None


def sniff_media_type(data: bytes) -> str | None:
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "image/webp"
    if data.startswith(b"\x1aE\xdf\xa3"):
        return "video/webm"
    if len(data) >= 12 and data[4:8] == b"ftyp":
        return "video/mp4"
    if data.startswith((b"ID3", b"\xff\xfb", b"\xff\xf3", b"\xff\xf2")):
        return "audio/mpeg"
    if data.startswith(b"RIFF") and data[8:12] == b"WAVE":
        return "audio/wav"
    if data.startswith(b"OggS"):
        return "audio/ogg"
    return None


def media_types_compatible(declared: str, detected: str) -> bool:
    return declared == detected


def classify_evidence(
    evidence: EvidenceInput,
    *,
    external_conflict: bool = False,
    external_support: bool = False,
) -> tuple[EvidenceCategory, float | None, list[str]]:
    profile = aggregate_perturbation_profile(evidence.perturbation_scores)
    metadata = inspect_metadata(evidence)
    reasons: list[str] = []
    if external_conflict:
        return (
            EvidenceCategory.CONFLICTING_EVIDENCE,
            None,
            ["An external source conflicts with the claim."],
        )
    if external_support and evidence.source_url:
        return (
            EvidenceCategory.SUPPORTED,
            None,
            ["A supplied external source supports the claim; confidence is not fabricated."],
        )
    if not evidence.text and not evidence.source_url:
        return (
            EvidenceCategory.UNVERIFIABLE,
            None,
            ["No evidence content or source URL was supplied."],
        )
    if evidence.source_url and evidence.claimed_event:
        return (
            EvidenceCategory.UNVERIFIABLE,
            None,
            ["A source and claim were supplied, but no live verification was requested."],
        )
    assertion_reasons = []
    if metadata["asserted_flags"] or profile["available"]:
        assertion_reasons.append(
            "Submitter-provided metadata or perturbation scores are unverified assertions and "
            "cannot establish a verdict."
        )
    return (
        EvidenceCategory.UNVERIFIABLE,
        None,
        reasons
        or assertion_reasons
        or ["Available inputs are insufficient to establish authenticity."],
    )


def provenance(
    evidence: EvidenceInput,
    external_evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    external_evidence = external_evidence or {}
    return {
        "source_url": str(evidence.source_url) if evidence.source_url else None,
        "observed_at": evidence.observed_at,
        "input_type": "text" if evidence.text else "metadata-only",
        "external_check_requested": bool(external_evidence.get("requested")),
        "external_check_performed": bool(external_evidence.get("performed")),
        "external_check_status": external_evidence.get("status", "not_requested"),
        "provenance_verification": "not_performed",
    }
