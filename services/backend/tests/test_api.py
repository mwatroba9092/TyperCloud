from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_is_public_and_ok():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_matches_requires_auth():
    resp = client.get("/api/matches")
    assert resp.status_code in (401, 403)


def test_metrics_exposed():
    resp = client.get("/metrics")
    assert resp.status_code == 200
    assert "typercloud_predictions_created_total" in resp.text
