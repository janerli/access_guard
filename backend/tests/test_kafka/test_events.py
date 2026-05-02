"""Юнит-тесты для KafkaEvent и функций публикации."""
import json
from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest

from app.kafka.events import KafkaEvent
from app.kafka.topics import TOPIC_AUDIT_EVENTS, TOPIC_IDENTITY_USERS


def test_kafka_event_defaults():
    event = KafkaEvent(event_type="user.created", producer="identity", payload={"user_id": "abc"})
    assert isinstance(event.event_id, UUID)
    assert isinstance(event.correlation_id, UUID)
    assert event.version == "1.0"
    assert event.event_type == "user.created"
    assert event.payload == {"user_id": "abc"}


def test_kafka_event_serialization():
    event = KafkaEvent(event_type="audit.logged", producer="monitor", payload={"op": "create"})
    data = event.model_dump(mode="json")
    assert data["event_type"] == "audit.logged"
    assert data["producer"] == "monitor"
    assert "event_id" in data
    assert "occurred_at" in data
    # Verify it's JSON-serializable
    json_str = json.dumps(data, default=str)
    parsed = json.loads(json_str)
    assert parsed["event_type"] == "audit.logged"


def test_kafka_event_custom_correlation_id():
    from uuid import uuid4
    corr = uuid4()
    event = KafkaEvent(event_type="role.assigned", producer="access", correlation_id=corr)
    assert event.correlation_id == corr


def test_topic_constants():
    assert TOPIC_AUDIT_EVENTS == "audit.events"
    assert TOPIC_IDENTITY_USERS == "identity.users"


@pytest.mark.asyncio
async def test_publish_event_calls_producer():
    """publish_event должен вызывать producer.send с правильными аргументами."""
    event = KafkaEvent(event_type="user.created", producer="identity", payload={"user_id": "u1"})

    mock_producer = AsyncMock()
    mock_producer.send = AsyncMock()

    with patch("app.kafka.producer.get_producer", return_value=mock_producer):
        from app.kafka.producer import publish_event
        await publish_event(TOPIC_IDENTITY_USERS, event, key="u1")

    mock_producer.send.assert_called_once()
    call_args = mock_producer.send.call_args
    assert call_args[0][0] == TOPIC_IDENTITY_USERS
