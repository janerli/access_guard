from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://accessguard:secret@postgres:5432/accessguard"

    # Redis
    REDIS_URL: str = "redis://redis:6379/0"

    # LDAP
    LDAP_URI: str = "ldap://ldap:389"
    LDAP_BASE_DN: str = "dc=accessguard,dc=local"
    LDAP_BIND_DN: str = "cn=admin,dc=accessguard,dc=local"
    LDAP_BIND_PASSWORD: str = "admin"

    # HR Mock
    HR_MOCK_URL: str = "http://hr-mock:8001"

    # Kafka
    KAFKA_BOOTSTRAP_SERVERS: str = "kafka:9092"
    KAFKA_CONSUMER_GROUP_PREFIX: str = "accessguard"
    KAFKA_PRODUCER_ACKS: str = "all"
    KAFKA_PRODUCER_IDEMPOTENCE: bool = True

    # Elasticsearch
    ELASTICSEARCH_URL: str = "http://elasticsearch:9200"
    ELASTICSEARCH_AUDIT_INDEX_PREFIX: str = "audit-events"

    # Kibana
    KIBANA_URL: str = "http://kibana:5601"
    KIBANA_EMBED_URL: str = "http://localhost:5601/app/dashboards#/view"

    # JWT
    JWT_SECRET: str = "change-me-in-production"
    JWT_ACCESS_TTL_MIN: int = 15
    JWT_REFRESH_TTL_DAYS: int = 7

    # SMTP
    SMTP_HOST: str = "mailhog"
    SMTP_PORT: int = 1025
    SMTP_FROM: str = "noreply@accessguard.local"

    # App
    CORS_ORIGINS: str = "http://localhost:5173"
    LOG_LEVEL: str = "INFO"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",")]


settings = Settings()
