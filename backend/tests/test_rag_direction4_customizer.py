"""Unit tests for Direction 4: Interactive Roadmap Customizer API."""
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_customize_roadmap_resources_format_filtering():
    """Verify customize endpoint filters by video vs documentation format."""
    payload = {
        "missing_skills": ["docker", "fastapi"],
        "domain": "tech",
        "max_hours_per_week": 15,
        "preferred_format": "video",
        "free_only": True
    }
    response = client.post("/api/v1/advanced/roadmap/customize", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "customized_resources" in data
    assert data["total_matches"] >= 1
    # All returned resources must be video
    for item in data["customized_resources"]:
        assert item["type"] == "youtube_video"


def test_customize_roadmap_resources_pacing_filtering():
    """Verify customize endpoint enforces max hours pacing ceiling."""
    payload = {
        "missing_skills": ["kubernetes", "docker"],
        "domain": "tech",
        "max_hours_per_week": 2,  # Strict ceiling: max 4h total
        "preferred_format": "all",
        "free_only": False
    }
    response = client.post("/api/v1/advanced/roadmap/customize", json=payload)
    assert response.status_code == 200
    data = response.json()
    for item in data["customized_resources"]:
        if item.get("duration_hours"):
            assert item["duration_hours"] <= 4.0

