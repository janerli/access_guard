from typing import Optional

from elasticsearch import AsyncElasticsearch

from app.config import settings

_client: Optional[AsyncElasticsearch] = None


def get_elastic_client() -> AsyncElasticsearch:
    global _client
    if _client is None:
        _client = AsyncElasticsearch(
            hosts=[settings.ELASTICSEARCH_URL],
            retry_on_timeout=True,
            max_retries=3,
        )
    return _client


async def close_elastic_client() -> None:
    global _client
    if _client:
        await _client.close()
        _client = None
