from datetime import datetime
from typing import Any, Optional

from app.config import settings
from app.elastic.client import get_elastic_client


async def search_audit_events(
    query: Optional[str] = None,
    actor_id: Optional[str] = None,
    operation: Optional[str] = None,
    module: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    page: int = 1,
    size: int = 100,
) -> dict[str, Any]:
    client = get_elastic_client()
    must: list[dict] = []

    if query:
        must.append({
            "multi_match": {
                "query": query,
                "fields": ["actor_username", "operation", "target_id", "details.*"],
            }
        })
    if actor_id:
        must.append({"term": {"actor_id": actor_id}})
    if operation:
        must.append({"term": {"operation": operation}})
    if module:
        must.append({"term": {"module": module}})
    if date_from or date_to:
        range_q: dict[str, str] = {}
        if date_from:
            range_q["gte"] = date_from.isoformat()
        if date_to:
            range_q["lte"] = date_to.isoformat()
        must.append({"range": {"timestamp": range_q}})

    body: dict[str, Any] = {
        "query": {"bool": {"must": must}} if must else {"match_all": {}},
        "sort": [{"timestamp": {"order": "desc"}}],
        "from": (page - 1) * size,
        "size": min(size, 1000),
    }

    index = f"{settings.ELASTICSEARCH_AUDIT_INDEX_PREFIX}-*"
    return await client.search(index=index, body=body)
