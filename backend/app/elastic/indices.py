import structlog

logger = structlog.get_logger()

AUDIT_INDEX_TEMPLATE_NAME = "audit-events-template"

AUDIT_INDEX_TEMPLATE = {
    "index_patterns": ["audit-events-*"],
    "template": {
        "settings": {
            "number_of_shards": 1,
            "number_of_replicas": 0,
            "refresh_interval": "5s",
        },
        "mappings": {
            "properties": {
                "event_id": {"type": "keyword"},
                "audit_log_id": {"type": "long"},
                "timestamp": {"type": "date"},
                "actor_id": {"type": "keyword"},
                "actor_username": {"type": "keyword"},
                "target_type": {"type": "keyword"},
                "target_id": {"type": "keyword"},
                "operation": {"type": "keyword"},
                "module": {"type": "keyword"},
                "result": {"type": "keyword"},
                "ip_address": {"type": "ip"},
                "user_agent": {"type": "text"},
                "details": {"type": "object", "enabled": True},
                "correlation_id": {"type": "keyword"},
                "department_code": {"type": "keyword"},
                "position_code": {"type": "keyword"},
            }
        },
    },
}


async def ensure_index_template() -> None:
    from app.elastic.client import get_elastic_client

    client = get_elastic_client()
    try:
        await client.indices.put_index_template(
            name=AUDIT_INDEX_TEMPLATE_NAME,
            body=AUDIT_INDEX_TEMPLATE,
        )
        logger.info("elastic_template_created", name=AUDIT_INDEX_TEMPLATE_NAME)
    except Exception as exc:
        logger.error("elastic_template_failed", error=str(exc))
        raise
