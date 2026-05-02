# AccessGuard — Система мониторинга и управления доступом

Прототип корпоративной системы управления доступом к информационным ресурсам
для организаций численностью 50–500 сотрудников.

## Быстрый старт

```bash
# 1. Скопировать конфиг (при необходимости изменить JWT_SECRET)
cp .env.example .env

# 2. Запустить все сервисы
docker compose up -d

# 3. Дождаться готовности (30–60 секунд) и заполнить демо-данными
bash scripts/seed.sh
```

После этого открыть:

| Сервис      | Адрес                      | Назначение                       |
|-------------|----------------------------|----------------------------------|
| Frontend    | http://localhost:5173      | Основной интерфейс               |
| API Swagger | http://localhost:8000/docs | Документация REST API            |
| Kibana      | http://localhost:5601      | Дашборды событий безопасности    |
| MailHog     | http://localhost:8025      | Перехват email-оповещений        |
| HR-mock     | http://localhost:8001/docs | Симулятор кадровой системы       |

## Учётные записи (после seed.sh)

| Логин          | Пароль         | Роль                    |
|----------------|----------------|-------------------------|
| admin          | Admin123456789 | Системный администратор |
| security_admin | Security123456 | Офицер безопасности     |
| hr_admin       | HrAdmin123456  | HR-оператор             |
| auditor        | Auditor123456  | Аудитор                 |

## Архитектура

```
HR-mock ──Kafka(hr.events)──► Identity Module ──Kafka(identity.users)──► Access Module
                                    │                                           │
                                    └──────────────► Monitor Module ◄──────────┘
                                                          │
                                                    audit_log (PG)
                                                    outbox_events
                                                          │
                                                    Kafka(audit.events)
                                                          │
                                                       Logstash
                                                          │
                                                    Elasticsearch
                                                          │
                                                       Kibana
                                                          │
                                                   Reports Module
```

Подробная архитектурная документация: [`docs/architecture.md`](docs/architecture.md)

## Модули

### Identity — управление учётными записями
- Жизненный цикл сотрудника: найм → изменения → увольнение
- Автоматическая синхронизация с HR-системой через Kafka
- Provisioning/deprovisioning в OpenLDAP
- REST API: `/api/identity/users`, `/events`, `/sync`, `/positions`, `/departments`

### Access — контроль доступа (RBAC)
- 7 ролей, 14 разрешений, матрица должность→роли
- Проверка полномочий с кэшом Redis (TTL 60 сек)
- Заявки на доступ с процессом согласования
- REST API: `/api/access/roles`, `/permissions`, `/requests`, `/matrix`, `/check`

### Monitor — мониторинг и аудит
- Двухконтурный аудит: PostgreSQL (источник истины) + Elasticsearch (поиск)
- Transactional outbox: гарантированная доставка событий в Kafka
- 10 правил выявления: 4 real-time (PostgreSQL) + 6 сложных (Elasticsearch aggregations)
- Оповещения: email (MailHog), webhook, log, Kafka
- REST API: `/api/monitor/dashboard`, `/audit`, `/rules`, `/alerts`, `/channels`

### Reports — отчётность
- 8 шаблонов: пользователи, роли, заявки, аудит, инциденты и др.
- Форматы: CSV, XLSX (openpyxl), PDF (WeasyPrint)
- Асинхронная генерация через Celery, статус по WebSocket
- REST API: `/api/reports/templates`, `/reports`, `/schedules`

## Стек технологий

**Backend:** Python 3.11, FastAPI, SQLAlchemy 2.0 async, Alembic, Pydantic 2,
aiokafka, elasticsearch[async] 8.x, Celery 5 + Redis, ldap3, openpyxl, WeasyPrint

**Frontend:** React 18, TypeScript, Vite, shadcn/ui, Tailwind CSS, recharts, Zustand,
react-router-dom, axios

**Инфраструктура:** PostgreSQL 15, Redis 7, OpenLDAP, Apache Kafka 3.6 + Zookeeper,
Elasticsearch 8.11, Logstash 8.11, Kibana 8.11, Docker Compose

## Kafka-топики

| Топик                  | Продюсер     | Консьюмер          |
|------------------------|--------------|--------------------|
| `hr.events`            | HR-mock      | Identity           |
| `identity.users`       | Identity     | Access, Monitor    |
| `identity.lifecycle`   | Identity     | Monitor            |
| `access.roles`         | Access       | Monitor            |
| `access.requests`      | Access       | Monitor            |
| `monitor.alerts`       | Monitor      | Notification svc   |
| `audit.events`         | Outbox pub.  | Logstash → ES      |
| `reports.notifications`| Reports      | —                  |

## Разработка

```bash
# Запустить только базовые сервисы (без Kafka/ES)
docker compose up -d postgres redis ldap mailhog backend worker beat frontend

# Применить миграции
docker compose exec backend alembic upgrade head

# Запустить тесты
docker compose exec backend pytest --cov=app --cov-report=term-missing -v

# Посмотреть логи
docker compose logs -f backend worker beat

# Сброс данных (с подтверждением)
bash scripts/reset.sh
```

## Структура проекта

```
access_guard/
├── docker-compose.yml
├── .env.example
├── docs/
│   ├── full-spec.md         # Полное техническое задание
│   ├── architecture.md      # Архитектурные диаграммы
│   └── events.md            # Каталог Kafka-событий
├── backend/
│   ├── app/
│   │   ├── main.py          # FastAPI app, роутеры
│   │   ├── celery_app.py    # Celery + beat расписания
│   │   ├── kafka/           # producer, consumer base, events, topics
│   │   ├── elastic/         # ES client, index templates, search
│   │   ├── core/            # JWT auth, deps, security
│   │   └── modules/
│   │       ├── identity/    # Users, LDAP, HR sync
│   │       ├── access/      # RBAC, Redis cache, requests
│   │       ├── monitor/     # Audit log, rules, alerts
│   │       └── reports/     # Templates, generators, renderers
│   └── tests/
├── frontend/src/
│   ├── pages/               # Identity, Access, Monitor, Reports
│   ├── api/                 # axios API clients
│   ├── store/               # Zustand (auth)
│   └── components/          # Layout, shared UI
├── hr-mock/                 # FastAPI симулятор HR-системы
├── logstash/pipeline/       # audit.conf
├── kibana/dashboards/       # 5 NDJSON дашбордов
└── scripts/
    ├── seed.sh              # Полный запуск с демо-данными
    ├── seed_data.py         # Python seeder (50 сотрудников, ~5000 аудит-записей)
    ├── reset.sh             # Сброс БД
    ├── elastic-init.sh      # Инициализация ES index templates
    └── kibana-import.sh     # Импорт Kibana дашбордов
```

## Тесты

```bash
# Все тесты
docker compose exec backend pytest -v

# С покрытием
docker compose exec backend pytest --cov=app --cov-report=html

# Конкретный модуль
docker compose exec backend pytest tests/test_identity/ -v
docker compose exec backend pytest tests/test_access/ -v
docker compose exec backend pytest tests/test_monitor/ -v
docker compose exec backend pytest tests/test_reports/ -v
```

Цель покрытия: **≥ 70%**

## Полная спецификация

Детальное ТЗ со всеми REST endpoint, моделями данных, правилами выявления
и переменными окружения: [`docs/full-spec.md`](docs/full-spec.md)
