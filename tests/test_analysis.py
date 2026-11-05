from eventproof.analysis import (
    aggregate_perturbation_profile,
    classify_evidence,
    parse_event_grounding,
)
from eventproof.models import EvidenceCategory, EvidenceInput


def test_categories_do_not_fabricate_confidence():
    category, confidence, _ = classify_evidence(EvidenceInput(text="A claim"))
    assert category is EvidenceCategory.UNVERIFIABLE
    assert confidence is None


def test_recycled_and_conflicting_categories():
    recycled = EvidenceInput(text="old footage", metadata={"recycled": True})
    conflicting = EvidenceInput(text="claim", metadata={"conflicting_evidence": True})
    assert classify_evidence(recycled)[0] is EvidenceCategory.RECYCLED_OR_MISCONTEXTUALIZED
    assert classify_evidence(conflicting)[0] is EvidenceCategory.CONFLICTING_EVIDENCE
    assert (
        classify_evidence(EvidenceInput(text="corroborated", metadata={"supported": True}))[0]
        is EvidenceCategory.SUPPORTED
    )


def test_perturbation_aggregation():
    profile = aggregate_perturbation_profile({"jpeg": 0.2, "crop": 0.8})
    assert profile["score"] == 0.5
    assert profile["signals"] == ["crop"]


def test_event_grounding():
    grounding = parse_event_grounding(
        EvidenceInput(text="Earthquake in Quito 2025-02-03 at 0.1, -78.4")
    )
    assert "2025-02-03" in grounding["dates"]
    assert grounding["coordinates"] == ["0.1, -78.4"]
