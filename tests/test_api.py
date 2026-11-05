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
