"""Tests for GET /api/monitor/health."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_requires_auth(client: AsyncClient):
    resp = await client.get("/api/monitor/health")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_health_ok_all_services_mocked(client: AsyncClient, admin_token: str):
    """Health endpoint returns 200 with all services mocked as reachable."""
    mock_redis = AsyncMock()
    mock_redis.ping = AsyncMock(return_value=True)
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.aclose = AsyncMock()

    mock_es_instance = AsyncMock()
    mock_es_instance.cluster.health = AsyncMock(return_value={"status": "green"})
    mock_es_instance.close = AsyncMock()

    mock_producer = MagicMock()

    with (
        patch("app.modules.monitor.health.aioredis.from_url", return_value=mock_redis),
        patch("app.modules.monitor.health.AsyncElasticsearch", return_value=mock_es_instance),
        patch("app.modules.monitor.health.get_producer", new_callable=AsyncMock, return_value=mock_producer),
    ):
        resp = await client.get(
            "/api/monitor/health",
            headers={"Authorization": f"Bearer {admin_token}"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["postgres"]["status"] == "ok"
    assert data["redis"]["status"] == "ok"
    assert data["elasticsearch"]["status"] == "ok"
    assert data["kafka"]["status"] == "ok"
    assert "checked_at" in data
    assert "outbox_pending" in data
    assert "outbox_failed" in data


@pytest.mark.asyncio
async def test_health_es_yellow(client: AsyncClient, admin_token: str):
    """ES cluster yellow → ok (single-node setup, replica shards always unassigned)."""
    mock_redis = AsyncMock()
    mock_redis.ping = AsyncMock(return_value=True)
    mock_redis.get = AsyncMock(return_value="2026-06-01T00:00:00")
    mock_redis.aclose = AsyncMock()

    mock_es_instance = AsyncMock()
    mock_es_instance.cluster.health = AsyncMock(return_value={"status": "yellow"})
    mock_es_instance.close = AsyncMock()

    mock_producer = MagicMock()

    with (
        patch("app.modules.monitor.health.aioredis.from_url", return_value=mock_redis),
        patch("app.modules.monitor.health.AsyncElasticsearch", return_value=mock_es_instance),
        patch("app.modules.monitor.health.get_producer", new_callable=AsyncMock, return_value=mock_producer),
    ):
        resp = await client.get(
            "/api/monitor/health",
            headers={"Authorization": f"Bearer {admin_token}"},
        )

    assert resp.status_code == 200
    data = resp.json()
    # yellow is treated as ok for single-node ES (no replica placement possible)
    assert data["elasticsearch"]["status"] == "ok"
    assert data["last_celery_beat"] == "2026-06-01T00:00:00"


@pytest.mark.asyncio
async def test_health_es_red(client: AsyncClient, admin_token: str):
    """ES cluster red → down."""
    mock_redis = AsyncMock()
    mock_redis.ping = AsyncMock(return_value=True)
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.aclose = AsyncMock()

    mock_es_instance = AsyncMock()
    mock_es_instance.cluster.health = AsyncMock(return_value={"status": "red"})
    mock_es_instance.close = AsyncMock()

    with (
        patch("app.modules.monitor.health.aioredis.from_url", return_value=mock_redis),
        patch("app.modules.monitor.health.AsyncElasticsearch", return_value=mock_es_instance),
        patch("app.modules.monitor.health.get_producer", new_callable=AsyncMock, return_value=None),
    ):
        resp = await client.get(
            "/api/monitor/health",
            headers={"Authorization": f"Bearer {admin_token}"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["elasticsearch"]["status"] == "down"
    assert data["kafka"]["status"] == "down"  # producer=None


@pytest.mark.asyncio
async def test_health_all_services_down(client: AsyncClient, admin_token: str):
    """When Redis/ES/Kafka all raise — endpoint still returns 200 with 'down' statuses."""
    with (
        patch("app.modules.monitor.health.aioredis.from_url", side_effect=Exception("conn refused")),
        patch("app.modules.monitor.health.AsyncElasticsearch", side_effect=Exception("no es")),
        patch("app.modules.monitor.health.get_producer", side_effect=Exception("no kafka")),
    ):
        resp = await client.get(
            "/api/monitor/health",
            headers={"Authorization": f"Bearer {admin_token}"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["redis"]["status"] == "down"
    assert data["elasticsearch"]["status"] == "down"
    assert data["kafka"]["status"] == "down"
    # postgres should still be ok (real DB in test)
    assert data["postgres"]["status"] == "ok"


@pytest.mark.asyncio
async def test_health_response_structure(client: AsyncClient, admin_token: str):
    """Response has all required fields."""
    with (
        patch("app.modules.monitor.health.aioredis.from_url", side_effect=Exception("x")),
        patch("app.modules.monitor.health.AsyncElasticsearch", side_effect=Exception("x")),
        patch("app.modules.monitor.health.get_producer", side_effect=Exception("x")),
    ):
        resp = await client.get(
            "/api/monitor/health",
            headers={"Authorization": f"Bearer {admin_token}"},
        )

    assert resp.status_code == 200
    data = resp.json()
    required_keys = {
        "postgres", "redis", "elasticsearch", "kafka",
        "outbox_pending", "outbox_failed", "last_celery_beat", "checked_at",
    }
    assert required_keys.issubset(data.keys())
    assert isinstance(data["outbox_pending"], int)
    assert isinstance(data["outbox_failed"], int)
