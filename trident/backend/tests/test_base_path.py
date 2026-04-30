from fastapi.testclient import TestClient

from app.config.settings import Settings
from app.main import build_app


def test_health_under_trident_base_path():
    app = build_app(Settings(base_path="/trident"))
    client = TestClient(app)
    r = client.get("/trident/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_ready_under_trident_base_path():
    app = build_app(Settings(base_path="/trident"))
    client = TestClient(app)
    r = client.get("/trident/api/ready")
    assert r.status_code == 200


def test_root_lists_base_path():
    app = build_app(Settings(base_path="/trident"))
    client = TestClient(app)
    r = client.get("/trident/")
    assert r.status_code == 200
    assert r.json()["base_path"] == "/trident"
