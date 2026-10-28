import os
import sys
from pathlib import Path
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.main import app

client = TestClient(app)


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "operational"


def test_scenarios_list_or_default():
    # Try to get a known scenario
    r = client.get("/api/scenario/scenario_wakashio_validation")
    assert r.status_code == 200
    data = r.json()
    assert data["id"] == "scenario_wakashio_validation"


def test_dossier_markdown_includes_sections():
    r = client.get("/api/dossier/scenario_wakashio_validation/markdown")
    assert r.status_code == 200
    text = r.text
    assert "DATA SOURCES" in text or "DATA SOURCES" in text.upper()
    assert "UNCERTAINTY" in text.upper()
    assert "TIMESTAMP" in text.upper() or "GENERATED" in text.upper()


def test_real_data_rejects_unapproved_source_and_path_traversal():
    crop = client.post("/api/real-data/sentinel/crop", json={
        "asset_url": "https://example.com/not-a-sentinel-scene.tif",
        "bbox": [-95.05, 28.83, -94.69, 29.81],
    })
    assert crop.status_code == 400
    assert "approved" in crop.json()["detail"].lower()

    analysis = client.post("/api/real-data/analyze-crop", json={"filename": "../../.env"})
    assert analysis.status_code == 400
    assert "invalid filename" in analysis.json()["detail"].lower()


def test_real_data_search_uses_cache_and_audit(monkeypatch):
    import backend.main as main
    from backend.cache_manager import CACHE_DIR

    # Avoid a network dependency while testing that the secured route records
    # a source and turns its second equivalent request into a cache hit.
    monkeypatch.setattr(main, "search_sentinel_scenes", lambda *args: [{"id": "test-scene"}])
    query = {
        "bbox": [-95.05, 28.83, -94.69, 29.81],
        "start": "2020-01-10T00:26:30Z",
        "end": "2020-01-10T00:27:00Z",
        "limit": 1,
    }
    first = client.post("/api/real-data/sentinel/search", json=query)
    second = client.post("/api/real-data/sentinel/search", json=query)
    assert first.status_code == second.status_code == 200
    assert second.json().get("from_cache") is True
    assert list(Path("audit_logs").glob("audit_*.jsonl"))
    # The request must not create an arbitrary cache filename.
    assert all(path.name.startswith("sentinel_search_") for path in CACHE_DIR.glob("sentinel_search_*.json"))
