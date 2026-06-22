"""Test failure analysis API endpoint."""

from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def test_failure_analysis_endpoint():
    """Test GET /failures endpoint."""
    response = client.get("/failures")
    assert response.status_code == 200
    data = response.json()
    assert "total_queries" in data
    assert "total_failures" in data
    assert "failure_rate" in data
    assert "top_categories" in data
    assert "failures" in data


def test_failure_trends_endpoint():
    """Test GET /failures/trends endpoint."""
    response = client.get("/failures/trends")
    assert response.status_code == 200
    data = response.json()
    assert "trends" in data
    assert "latest_run" in data
    assert "previous_run" in data


def test_failures_page():
    """Test GET /app/failures page."""
    response = client.get("/app/failures")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]