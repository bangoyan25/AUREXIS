"""
Tests for the /health endpoint.

Uses FastAPI TestClient — no real DB or Redis required for unit tests.
Integration tests (marked 'integration') require live services.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """FastAPI test client with mocked infrastructure."""
    from backend.main import create_app
    app = create_app()
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


@pytest.mark.unit
class TestHealthEndpoint:

    def test_health_returns_200(self, client: TestClient) -> None:
        with (
            patch("backend.api.v1.health._check_postgres", new_callable=AsyncMock) as mock_pg,
            patch("backend.api.v1.health.check_redis_health", new_callable=AsyncMock) as mock_redis,
        ):
            mock_pg.return_value = {"status": "healthy"}
            mock_redis.return_value = {"status": "healthy", "ping": True}
            response = client.get("/api/v1/health")
            assert response.status_code == 200

    def test_health_structure(self, client: TestClient) -> None:
        with (
            patch("backend.api.v1.health._check_postgres", new_callable=AsyncMock) as mock_pg,
            patch("backend.api.v1.health.check_redis_health", new_callable=AsyncMock) as mock_redis,
        ):
            mock_pg.return_value = {"status": "healthy"}
            mock_redis.return_value = {"status": "healthy"}
            response = client.get("/api/v1/health")
            data = response.json()
            assert "status" in data
            assert "version" in data
            assert "environment" in data
            assert "components" in data
            for comp in ["backend", "database", "redis", "brain", "risk_engine", "market_data", "news", "mt5"]:
                assert comp in data["components"], f"Missing component: {comp}"

    def test_risk_engine_not_configured_by_default(self, client: TestClient) -> None:
        with (
            patch("backend.api.v1.health._check_postgres", new_callable=AsyncMock) as mock_pg,
            patch("backend.api.v1.health.check_redis_health", new_callable=AsyncMock) as mock_redis,
        ):
            mock_pg.return_value = {"status": "healthy"}
            mock_redis.return_value = {"status": "healthy"}
            response = client.get("/api/v1/health")
            risk = response.json()["components"]["risk_engine"]
            assert risk["status"] == "NOT_CONFIGURED"
            assert "missing_parameters" in risk

    def test_brain_not_configured_by_default(self, client: TestClient) -> None:
        with (
            patch("backend.api.v1.health._check_postgres", new_callable=AsyncMock) as mock_pg,
            patch("backend.api.v1.health.check_redis_health", new_callable=AsyncMock) as mock_redis,
        ):
            mock_pg.return_value = {"status": "healthy"}
            mock_redis.return_value = {"status": "healthy"}
            response = client.get("/api/v1/health")
            brain = response.json()["components"]["brain"]
            assert brain["status"] == "NOT_CONFIGURED"

    def test_liveness_probe(self, client: TestClient) -> None:
        response = client.get("/api/v1/health/live")
        assert response.status_code == 200
        assert response.json()["status"] == "alive"

    def test_readiness_probe_503_when_db_down(self, client: TestClient) -> None:
        with (
            patch("backend.api.v1.health._check_postgres", new_callable=AsyncMock) as mock_pg,
            patch("backend.api.v1.health.check_redis_health", new_callable=AsyncMock) as mock_redis,
        ):
            mock_pg.return_value = {"status": "unhealthy", "error": "connection refused"}
            mock_redis.return_value = {"status": "healthy"}
            response = client.get("/api/v1/health/ready")
            assert response.status_code == 503

    def test_health_degraded_when_redis_down(self, client: TestClient) -> None:
        with (
            patch("backend.api.v1.health._check_postgres", new_callable=AsyncMock) as mock_pg,
            patch("backend.api.v1.health.check_redis_health", new_callable=AsyncMock) as mock_redis,
        ):
            mock_pg.return_value = {"status": "healthy"}
            mock_redis.return_value = {"status": "unhealthy", "error": "ECONNREFUSED"}
            response = client.get("/api/v1/health")
            assert response.json()["status"] == "degraded"

    def test_correlation_id_header_echoed(self, client: TestClient) -> None:
        with (
            patch("backend.api.v1.health._check_postgres", new_callable=AsyncMock) as mock_pg,
            patch("backend.api.v1.health.check_redis_health", new_callable=AsyncMock) as mock_redis,
        ):
            mock_pg.return_value = {"status": "healthy"}
            mock_redis.return_value = {"status": "healthy"}
            test_id = "test-correlation-abc-123"
            response = client.get("/api/v1/health", headers={"X-Correlation-ID": test_id})
            assert response.headers["X-Correlation-ID"] == test_id
