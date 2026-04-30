from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_ready_endpoint():
    response = client.get("/api/ready")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"


def test_version_endpoint():
    response = client.get("/api/version")
    assert response.status_code == 200
    body = response.json()
    assert "version" in body
    assert body["service"] == "trident-api"
