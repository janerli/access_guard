# AccessGuard — Система мониторинга и управления доступом

## Что это
Система из 4 модулей для управления доступом к информационным ресурсам организации (50–500 сотрудников). Дипломный проект, нужен рабочий прототип с тестами.

## Стек
- **Backend:** Python 3.11, FastAPI, SQLAlchemy 2.0, Pydantic 2, aiokafka, elasticsearch[async] 8.x, Celery 5 + Redis, ldap3
- **Frontend:** React 18 + TypeScript, Vite, shadcn/ui + Tailwind, recharts, Zustand
- **Infra:** PostgreSQL 15, Redis 7, OpenLDAP, Kafka 3.6 + Zookeeper, Elasticsearch 8.11, Logstash 8.11, Kibana 8.11, Docker Compose

## 4 модуля

1. **Identity** — управление учётными записями, жизненный цикл, LDAP, интеграция с HR-mock через Kafka
2. **Access** — RBAC, проверка полномочий (кэш Redis), матрица должность→роли, заявки на доступ
3. **Monitor** — audit_log (append-only PostgreSQL) + Elasticsearch через transactional outbox + Kafka + Logstash, 10 правил выявления (4 простых real-time + 6 сложных через ES aggregations), оповещения (email/webhook/log/kafka), Kibana-дашборды
4. **Reports** — 8 шаблонов, источники PG/ES/combined, форматы PDF/XLSX/CSV, асинхронная генерация через Celery, расписания

## Ключевые архитектурные решения
- Межмодульное взаимодействие через **Kafka** (8 топиков: hr.events, identity.users, identity.lifecycle, access.roles, access.requests, monitor.alerts, audit.events, reports.notifications)
- **Двухконтурный аудит:** PostgreSQL (источник истины, append-only триггер) + Elasticsearch (поиск, агрегации)
- **Transactional outbox:** запись в audit_log + outbox в одной транзакции, отдельный publisher → Kafka → Logstash → ES
- Все события имеют **correlation_id** для сквозной трассировки

## Структура проекта
```
accessguard/
├── docker-compose.yml
├── .env.example
├── docs/                    ← детальные спецификации модулей
│   ├── full-spec.md         ← ПОЛНОЕ ТЗ (читай при необходимости)
│   ├── events.md            ← каталог Kafka-событий
│   └── elasticsearch.md     ← схемы индексов
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── celery_app.py
│   │   ├── kafka/           ← producer, consumer, events, topics
│   │   ├── elastic/          ← client, indices, search
│   │   ├── core/             ← auth, deps, logging
│   │   └── modules/
│   │       ├── identity/
│   │       ├── access/
│   │       ├── monitor/
│   │       └── reports/
│   └── tests/
├── frontend/
├── hr-mock/
├── logstash/pipeline/audit.conf
├── kibana/dashboards/
└── scripts/seed.sh, reset.sh, elastic-init.sh, kibana-import.sh
```

## Порядок реализации
1. Фундамент (docker-compose, FastAPI, PostgreSQL, Alembic, JWT auth, frontend каркас)
2. Kafka + Elasticsearch инфраструктура (топики, index templates, Logstash pipeline)
3. Identity (модели, LDAP, HR-mock, Kafka consumer/producer, API, UI, тесты)
4. Access (RBAC, Kafka consumer identity.users, Redis cache, заявки, API, UI, тесты)
5. Monitor (audit_log + outbox, правила, оповещения, Kibana дашборды, API, UI, тесты)
6. Reports (генераторы, рендереры PDF/XLSX/CSV, Celery, расписания, API, UI, тесты)
7. Полировка (seed.sh, документация, CI, финальная проверка)

## Критерии готовности
- `docker-compose up -d && ./scripts/seed.sh` запускает всё с нуля
- Swagger на :8000/docs, UI на :5173, Kibana на :5601, MailHog на :8025
- pytest ≥ 70% покрытия
- 5 Kibana дашбордов с данными
- Полная цепочка: HR event → Identity → Access → audit_log → ES → Kibana

## Детальная спецификация
При необходимости **читай `docs/full-spec.md`** — там полное ТЗ с REST API, моделями данных, правилами выявления, шаблонами отчётов и переменными окружения.
