from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class KafkaEvent(BaseModel):
    event_id: UUID = Field(default_factory=uuid4)
    event_type: str
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    producer: str
    correlation_id: UUID = Field(default_factory=uuid4)
    version: str = "1.0"
    payload: dict[str, Any] = {}
