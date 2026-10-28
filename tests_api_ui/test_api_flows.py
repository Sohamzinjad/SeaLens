import os
import sys
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
