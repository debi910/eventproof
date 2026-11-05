from fastapi.testclient import TestClient

from eventproof.main import app

client = TestClient(app)


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_verify_endpoint():
    response = client.post("/api/v1/verify", json={"evidence": {"text": "No corroboration"}})
    assert response.status_code == 200
    assert response.json()["report"]["category"] == "UNVERIFIABLE"


def test_validation_rejects_bad_scores():
    response = client.post("/api/v1/verify", json={"evidence": {"perturbation_scores": {"x": 2}}})
    assert response.status_code == 422


def test_multipart_media_report():
    response = client.post(
        "/api/v1/verify",
        data={"text": "Synthetic demo image", "claimed_event": "Demo"},
        files={"media": ("demo.jpg", b"fake-image-bytes", "image/jpeg")},
    )
    assert response.status_code == 200
    report = response.json()["report"]
    assert report["media_inspection"]["provided"] is True
    assert report["media_inspection"]["analysis_status"] == "metadata_only"


def test_invalid_media_type_rejected():
    response = client.post(
        "/api/v1/verify",
        data={"text": "not media"},
        files={"media": ("notes.txt", b"hello", "text/plain")},
    )
    assert response.status_code == 422


def test_report_is_reproducible_and_requires_review():
    response = client.post(
        "/api/v1/verify",
        json={
            "evidence": {
                "text": "Demo claim",
                "metadata": {"synthetic": True},
                "perturbation_scores": {"jpeg": 0.82, "crop": 0.76},
            }
        },
    )
    assert response.status_code == 200
    report = response.json()["report"]
    assert report["report_id"].startswith("EP-")
    assert report["generated_at"].endswith("+00:00")
    assert report["review_recommendation"]["decision"] == "human_review_required"
    assert any(row["signal"] == "Perturbation profile" for row in report["evidence_ledger"])
