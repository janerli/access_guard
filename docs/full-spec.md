# Техническое задание

## Система мониторинга и управления доступом к информационным ресурсам организации

**Кодовое имя проекта:** AccessGuard
**Версия ТЗ:** 2.0
**Целевой исполнитель:** Claude Code
**Целевой результат:** работоспособный прототип системы из 4 модулей с тестами и документацией, готовый к демонстрации на защите дипломного проекта.

**Изменения версии 2.0 относительно версии 1.0:**
- Добавлен стек ELK (Elasticsearch + Logstash + Kibana) для аналитики и поиска по журналу аудита.
- Добавлена шина событий Apache Kafka для асинхронного взаимодействия между модулями.
- Журнал аудита переведён на двухконтурное хранение (PostgreSQL — источник истины, Elasticsearch — поисковый и аналитический индекс).

---

## 1. Общие сведения

### 1.1. Контекст и назначение

Система предназначена для среднего коммерческого предприятия (ООО, 50–500 сотрудников, единая корпоративная сеть, парк серверных и пользовательских информационных систем). Система решает задачи:

- централизованного управления учётными записями сотрудников во взаимодействии с кадровой системой;
- разграничения доступа к информационным ресурсам организации на основе ролевой модели;
- непрерывного мониторинга действий пользователей и автоматического выявления подозрительной активности;
- формирования сводной отчётности для целей внутреннего аудита и принятия управленческих решений.

Система разрабатывается как групповой дипломный проект, в составе четырёх взаимосвязанных модулей. Каждый модуль является самостоятельной частью одного приложения, развёртываемой совместно с остальными.

### 1.2. Состав модулей

1. **Модуль управления учётными записями** (Identity) — централизованное управление жизненным циклом учётной записи: создание, модификация, блокировка, удаление; интеграция с кадровой системой.
2. **Модуль контроля доступа** (Access) — ролевая модель разграничения прав, проверка полномочий, матрица доступа.
3. **Модуль мониторинга, регистрации событий и оповещения** (Monitor) — журнал аудита в PostgreSQL и Elasticsearch, аналитические дашборды в Kibana, правила выявления подозрительной активности, уведомления администратора.
4. **Модуль формирования отчётности** (Reports) — построение сводных отчётов в форматах PDF, XLSX, CSV; шаблоны и параметризация.

### 1.3. Принципы построения

- **Модульная архитектура**: каждый модуль — отдельный пакет в составе единого backend-приложения; модули могут разрабатываться и тестироваться независимо.
- **Event-driven взаимодействие**: модули общаются между собой через шину событий Apache Kafka. Это обеспечивает слабую связанность, масштабируемость и устойчивость к сбоям отдельных модулей.
- **Двухконтурное хранение журнала аудита**: записи аудита одновременно сохраняются в PostgreSQL (как источник истины с гарантиями ACID и append-only-режимом) и индексируются в Elasticsearch (для быстрого полнотекстового поиска и построения аналитических дашбордов).
- **Единая основная база данных PostgreSQL** со схемой, разбитой по модулям, для оперативных данных и журнала аудита.
- Backend публикует REST API; frontend — единое веб-приложение (SPA) с разделением функций по модулям через маршрутизацию. Аналитические дашборды модуля Monitor интегрированы с Kibana.
- Развёртывание — через Docker Compose; внешние зависимости поднимаются как контейнеры (PostgreSQL, Redis, OpenLDAP, Kafka, Zookeeper, Elasticsearch, Logstash, Kibana).
- Имитация интеграции с кадровой системой через локальный «mock-сервис» (отдельный контейнер с тестовыми данными в формате 1С:ЗУП).

---

## 2. Технологический стек

### 2.1. Backend

| Компонент | Технология | Назначение |
|---|---|---|
| Язык | Python 3.11 | Основной язык backend |
| Веб-фреймворк | FastAPI 0.110+ | REST API, OpenAPI-документация |
| ASGI-сервер | Uvicorn | Запуск FastAPI |
| ORM | SQLAlchemy 2.0 + Alembic | Работа с БД, миграции |
| Валидация | Pydantic 2.x | Схемы запросов/ответов |
| Аутентификация | python-jose, passlib[bcrypt] | JWT-токены, хеширование паролей |
| LDAP-клиент | ldap3 | Взаимодействие с каталогом учётных записей |
| Kafka-клиент | aiokafka | Публикация и потребление событий |
| Elasticsearch-клиент | elasticsearch[async] 8.x | Поиск и индексация в Elasticsearch |
| Очередь задач | Celery 5 + Redis | Фоновые технические задачи (генерация отчётов, очистка) |
| Шаблоны отчётов | Jinja2, WeasyPrint, openpyxl | Генерация PDF, XLSX, CSV |
| Тесты | pytest, pytest-asyncio, httpx, testcontainers | Юнит- и интеграционное тестирование |

### 2.2. Frontend

| Компонент | Технология | Назначение |
|---|---|---|
| Фреймворк | React 18 + TypeScript | Веб-приложение SPA |
| Сборщик | Vite | Сборка и dev-сервер |
| UI | shadcn/ui + Tailwind CSS | Компонентная библиотека |
| HTTP-клиент | axios | Запросы к API |
| Маршрутизация | react-router-dom | Маршрутизация по модулям |
| Графики | recharts | Дашборды модуля Monitor |
| Управление состоянием | Zustand | Глобальное состояние |
| Встраивание Kibana | iframe + Kibana embedded mode | Аналитические дашборды |

### 2.3. Инфраструктура

| Компонент | Технология | Назначение |
|---|---|---|
| СУБД | PostgreSQL 15 | Основное хранилище, источник истины для аудита |
| Кэш и брокер Celery | Redis 7 | Очереди Celery, кэширование |
| Каталог | OpenLDAP (osixia/openldap) | Эмуляция корпоративного каталога |
| Шина событий | Apache Kafka 3.6 + Zookeeper 3.8 | Межмодульное асинхронное взаимодействие |
| Поисковый индекс | Elasticsearch 8.11 | Полнотекстовый поиск, аналитика по журналу аудита |
| ETL-конвейер | Logstash 8.11 | Перекладывание событий из Kafka в Elasticsearch |
| Аналитический интерфейс | Kibana 8.11 | Дашборды и визуализации, встраиваемые в frontend |
| Контейнеризация | Docker + Docker Compose | Развёртывание |
| HR-mock | Отдельный FastAPI-сервис | Эмуляция кадровой системы |
| SMTP-сервер | MailHog | Тестовый SMTP для оповещений |
| Документация | OpenAPI (Swagger UI) | Документация REST API |

### 2.4. Версии и образы Docker

```
postgres:15-alpine
redis:7-alpine
osixia/openldap:1.5.0
mailhog/mailhog:latest
confluentinc/cp-zookeeper:7.5.0
confluentinc/cp-kafka:7.5.0
docker.elastic.co/elasticsearch/elasticsearch:8.11.0
docker.elastic.co/logstash/logstash:8.11.0
docker.elastic.co/kibana/kibana:8.11.0
```

---

## 3. Архитектура системы

### 3.1. Структура репозитория

```
accessguard/
├── README.md                     # Описание проекта, инструкция по запуску
├── docker-compose.yml            # Оркестрация всех сервисов
├── .env.example                  # Шаблон переменных окружения
├── docs/
│   ├── architecture.md           # Описание архитектуры
│   ├── api.md                    # Сводка по REST API
│   ├── events.md                 # Каталог Kafka-событий
│   ├── elasticsearch.md          # Схемы индексов Elasticsearch
│   ├── modules/
│   │   ├── identity.md           # Модуль 1
│   │   ├── access.md             # Модуль 2
│   │   ├── monitor.md            # Модуль 3
│   │   └── reports.md            # Модуль 4
│   └── diagrams/                 # Диаграммы (PNG/SVG, исходники в Mermaid)
├── backend/
│   ├── pyproject.toml
│   ├── Dockerfile
│   ├── alembic.ini
│   ├── alembic/                  # Миграции БД
│   ├── app/
│   │   ├── main.py               # Точка входа FastAPI
│   │   ├── config.py             # Настройки (Pydantic Settings)
│   │   ├── database.py           # Подключение к БД, сессии
│   │   ├── celery_app.py         # Конфигурация Celery
│   │   ├── kafka/
│   │   │   ├── producer.py       # Общий продьюсер
│   │   │   ├── consumer.py       # Базовый потребитель
│   │   │   ├── events.py         # Pydantic-схемы событий
│   │   │   └── topics.py         # Константы имён топиков
│   │   ├── elastic/
│   │   │   ├── client.py         # Клиент Elasticsearch
│   │   │   ├── indices.py        # Определения индексов и mapping'ов
│   │   │   └── search.py         # Сервисы поиска
│   │   ├── core/                 # Общие компоненты (auth, deps, logging)
│   │   ├── models/               # ORM-модели (общие справочники)
│   │   ├── schemas/              # Общие Pydantic-схемы
│   │   ├── modules/
│   │   │   ├── identity/         # Модуль 1
│   │   │   ├── access/           # Модуль 2
│   │   │   ├── monitor/          # Модуль 3
│   │   │   └── reports/          # Модуль 4
│   │   └── seeds/                # Демо-данные
│   └── tests/
│       ├── conftest.py
│       ├── test_identity/
│       ├── test_access/
│       ├── test_monitor/
│       ├── test_reports/
│       └── test_kafka/           # Тесты межмодульного взаимодействия
├── frontend/                     # как было в v1.0
├── hr-mock/                      # Эмулятор кадровой системы
├── logstash/
│   ├── pipeline/
│   │   └── audit.conf            # Конфиг Logstash: Kafka → Elasticsearch
│   └── config/
│       └── logstash.yml
├── kibana/
│   └── dashboards/               # Экспорты дашбордов (NDJSON)
└── scripts/
    ├── seed.sh                   # Скрипт первичного наполнения данными
    ├── reset.sh                  # Сброс всех хранилищ к чистому состоянию
    ├── kibana-import.sh          # Импорт предустановленных дашбордов
    └── elastic-init.sh           # Создание индексов и шаблонов в Elasticsearch
```

### 3.2. Контейнерная архитектура

Сервисы в `docker-compose.yml`:

- `postgres` — PostgreSQL 15, основная БД `accessguard`
- `redis` — Redis 7
- `ldap` — OpenLDAP с предзагруженным деревом для тестовой организации
- `mailhog` — тестовый SMTP-сервер (порт 1025), веб-интерфейс на 8025
- `zookeeper` — для Kafka
- `kafka` — Apache Kafka, порт 9092 (внутр.), 9094 (внеш.)
- `kafka-init` — одноразовый контейнер для создания топиков при первом запуске
- `elasticsearch` — Elasticsearch 8.11, single-node mode, без security (для прототипа), порт 9200
- `logstash` — Logstash, читает из Kafka, пишет в Elasticsearch
- `kibana` — Kibana, порт 5601, anonymous-доступ для встраивания
- `hr-mock` — мок-сервис кадровой системы (порт 8001)
- `backend` — FastAPI-приложение (порт 8000)
- `worker` — Celery-воркер (тот же образ, что `backend`)
- `beat` — Celery-планировщик
- `kafka-consumer` — отдельный процесс на образе `backend`, потребляющий события из Kafka и обрабатывающий их
- `frontend` — Vite/React-приложение

Зависимости через `depends_on` с `condition: service_healthy` для критичных связей. Healthcheck'и на каждый сервис.

### 3.3. Шина событий Kafka

#### 3.3.1. Топики

| Имя топика | Партиций | Retention | Производители | Потребители |
|---|---|---|---|---|
| `identity.users` | 3 | 7 дней | Identity | Access, Monitor, Reports |
| `identity.lifecycle` | 3 | 7 дней | Identity | Monitor |
| `access.roles` | 3 | 7 дней | Access | Monitor, Reports |
| `access.permissions` | 3 | 7 дней | Access | Monitor |
| `access.requests` | 3 | 7 дней | Access | Monitor |
| `monitor.alerts` | 3 | 30 дней | Monitor | Reports |
| `audit.events` | 6 | 30 дней | все модули | Logstash → Elasticsearch |
| `hr.events` | 3 | 7 дней | HR-mock | Identity |

#### 3.3.2. Формат сообщений

Все события сериализуются в JSON и имеют общий конверт:

```json
{
  "event_id": "uuid",
  "event_type": "user.created | user.updated | user.blocked | role.assigned | ...",
  "occurred_at": "2026-05-01T10:30:00Z",
  "producer": "identity | access | monitor | reports",
  "correlation_id": "uuid",
  "version": "1.0",
  "payload": { /* содержательная часть, специфичная для типа */ }
}
```

`correlation_id` пробрасывается через цепочку обработки: один первичный триггер (например, кадровое событие) → одинаковый correlation_id во всех порождённых событиях. Это критично для расследования инцидентов.

#### 3.3.3. Каталог типов событий

Полный реестр в `docs/events.md`. Базовые:

**Топик `identity.users`:**
- `user.created` — учётная запись создана
- `user.updated` — атрибуты изменены
- `user.suspended` — приостановлена
- `user.restored` — восстановлена
- `user.blocked` — заблокирована
- `user.deleted` — удалена

**Топик `identity.lifecycle`:**
- `lifecycle.hired` — новый сотрудник принят
- `lifecycle.transferred` — перевод
- `lifecycle.terminated` — увольнение

**Топик `access.roles`:**
- `role.assigned` — роль назначена
- `role.revoked` — роль отозвана
- `role.created` — создана новая роль
- `role.permissions_changed` — изменён состав полномочий

**Топик `access.requests`:**
- `request.submitted` — заявка подана
- `request.approved` — одобрена
- `request.rejected` — отклонена

**Топик `monitor.alerts`:**
- `alert.triggered` — оповещение сработало
- `alert.acknowledged` — принято в работу
- `alert.resolved` — закрыто

**Топик `audit.events`:**
- общий поток событий аудита, сюда дублируются все значимые операции для последующей индексации в Elasticsearch.

#### 3.3.4. Гарантии и идемпотентность

- Продьюсер настроен с `acks=all`, `enable.idempotence=true` для exactly-once записи в один топик в одну партицию.
- Потребители используют group-based consumption с manual commit после успешной обработки.
- Потребители идемпотентны: повторная обработка того же `event_id` не приводит к дублированию (хранится таблица `processed_events` с TTL).

### 3.4. Двухконтурное хранение журнала аудита

#### 3.4.1. Контур 1 — PostgreSQL (источник истины)

Таблица `audit_log` в PostgreSQL — append-only, защищена триггером, гарантирует целостность и юридическую доказательность. Все модули пишут сюда **синхронно** в той же транзакции, что и основная операция. Это исключает рассогласование данных и журнала.

#### 3.4.2. Контур 2 — Elasticsearch (поисковый индекс)

После успешной записи в `audit_log` модуль публикует событие в топик `audit.events`. Logstash читает топик и индексирует записи в Elasticsearch (индекс с rolling-схемой `audit-events-YYYY.MM`).

**Зачем два контура:**

- PostgreSQL даёт целостность и неизменяемость. Если Elasticsearch потеряет данные — их можно восстановить из Postgres.
- Elasticsearch даёт быстрый полнотекстовый поиск, агрегации, аналитику. Запрос «все события пользователя X за 6 месяцев с фильтром по операции» в PostgreSQL может занять минуты, в Elasticsearch — миллисекунды.
- Kibana как интерфейс к Elasticsearch даёт мощные дашборды без написания кода.

#### 3.4.3. Схема индекса Elasticsearch

Индекс `audit-events-YYYY.MM` (rolling по месяцам). Mapping:

```json
{
  "mappings": {
    "properties": {
      "event_id":         { "type": "keyword" },
      "audit_log_id":     { "type": "long" },
      "timestamp":        { "type": "date" },
      "actor_id":         { "type": "keyword" },
      "actor_username":   { "type": "keyword" },
      "target_type":      { "type": "keyword" },
      "target_id":        { "type": "keyword" },
      "operation":        { "type": "keyword" },
      "module":           { "type": "keyword" },
      "result":           { "type": "keyword" },
      "ip_address":       { "type": "ip" },
      "user_agent":       { "type": "text" },
      "details":          { "type": "object", "enabled": true },
      "correlation_id":   { "type": "keyword" },
      "department_code":  { "type": "keyword" },
      "position_code":    { "type": "keyword" }
    }
  }
}
```

Index template `audit-events-template` применяется ко всем индексам по паттерну `audit-events-*`.

#### 3.4.4. Конфигурация Logstash

Файл `logstash/pipeline/audit.conf`:

- input: kafka, топик `audit.events`, group_id `logstash-audit`
- filter: парсинг JSON, добавление @timestamp из поля timestamp
- output: elasticsearch, index `audit-events-%{+YYYY.MM}`

### 3.5. Аутентификация и авторизация системы

Сама система также защищена аутентификацией: администратор системы входит через login/password, получает JWT-токен (access + refresh). У администратора есть встроенные роли:

- `system_admin` — полный доступ ко всем модулям;
- `security_officer` — доступ к Monitor, Reports, чтению Identity и Access;
- `hr_operator` — доступ к Identity (управление учётными записями);
- `auditor` — только чтение Monitor и Reports.

Учётные записи администраторов хранятся отдельно от управляемых учётных записей сотрудников. Роли администраторов проверяются на каждом эндпоинте через зависимость FastAPI.

---

## 4. Модуль 1. Управление учётными записями (Identity)

### 4.1. Назначение

Централизованное управление жизненным циклом учётных записей сотрудников организации в корпоративном каталоге. Интеграция с кадровой системой для автоматической обработки кадровых событий. Публикация событий жизненного цикла в Kafka для оповещения других модулей.

### 4.2. Сущности и модель данных

**Таблица `users_ext`** — расширенные атрибуты пользователей:
- `id` (PK, UUID)
- `ldap_dn` (string, уникальный) — distinguished name в LDAP
- `employee_id` (string, уникальный) — табельный номер из кадровой системы
- `username` (string, уникальный) — логин
- `email` (string)
- `full_name` (string)
- `position_id` (FK → positions)
- `department_id` (FK → departments)
- `status` (enum: new, active, suspended, blocked, deleted)
- `created_at`, `updated_at` (timestamp)

**Таблица `positions`** — справочник должностей:
- `id` (PK), `code` (string), `name` (string), `level` (int)

**Таблица `departments`** — оргструктура:
- `id` (PK), `code`, `name`, `parent_id` (FK → departments, self), `manager_user_id` (FK → users_ext, nullable)

**Таблица `lifecycle_events`** — кадровые события:
- `id` (PK), `user_id` (FK), `event_type` (enum: hire, transfer, leave_start, leave_end, terminate)
- `source` (enum: hr_system, manual, scheduled)
- `payload` (JSONB) — оригинальные данные события
- `processed_at` (timestamp), `status` (enum: pending, processed, failed)
- `kafka_offset` (bigint, nullable) — для отслеживания обработки из Kafka

### 4.3. REST API

```
POST   /api/identity/users                 # Создать пользователя
GET    /api/identity/users                 # Список пользователей (фильтры, пагинация)
GET    /api/identity/users/{id}            # Карточка пользователя
PATCH  /api/identity/users/{id}            # Обновить атрибуты
POST   /api/identity/users/{id}/suspend    # Перевод в suspended
POST   /api/identity/users/{id}/restore    # Возврат в active
POST   /api/identity/users/{id}/block      # Блокировка
DELETE /api/identity/users/{id}            # Полное удаление (после 90 дней блокировки)
POST   /api/identity/users/{id}/reset-password   # Сброс пароля

GET    /api/identity/events                # Просмотр истории кадровых событий
POST   /api/identity/sync                  # Полная сверка с HR-системой

GET    /api/identity/positions             # Справочник должностей
GET    /api/identity/departments           # Оргструктура
```

### 4.4. Жизненный цикл учётной записи

Состояния: `new` → `active` ↔ `suspended` → `blocked` → `deleted`.

Переходы:
- `new → active`: автоматически при первом входе пользователя или вручную администратором
- `active → suspended`: при кадровом событии `leave_start` (длительный отпуск, командировка)
- `suspended → active`: при кадровом событии `leave_end`
- `active|suspended → blocked`: при кадровом событии `terminate` (увольнение)
- `blocked → deleted`: автоматически по расписанию через 90 дней (Celery beat задача)

Каждый переход порождает событие в топике `identity.users` (тип события соответствует переходу) с полным контекстом операции.

### 4.5. Интеграция с LDAP

При операциях создания, модификации, блокировки учётной записи модуль выполняет соответствующие операции в OpenLDAP через библиотеку `ldap3`:

- создание — `add` записи в OU, соответствующее отделу;
- модификация — `modify` атрибутов;
- блокировка — установка атрибута `pwdAccountLockedTime`;
- удаление — `delete` записи.

Структура DIT (Directory Information Tree):
```
dc=accessguard,dc=local
├── ou=people
│   ├── ou=it-department
│   ├── ou=hr-department
│   └── ou=...
├── ou=groups
│   ├── cn=role-system_admin
│   ├── cn=role-manager
│   └── ...
└── ou=service
    └── cn=admin
```

LDAP-операции выполняются в той же транзакции, что и операции в БД (через паттерн саги: при ошибке LDAP откатываются изменения в БД).

### 4.6. Интеграция с кадровой системой

HR-mock публикует кадровые события в топик Kafka `hr.events`. Identity подписан на этот топик через специальный consumer:

```json
{
  "event_type": "hire | transfer | leave_start | leave_end | terminate",
  "employee_id": "E-1234",
  "effective_date": "2026-05-01",
  "data": {
    "full_name": "Иванов Иван Иванович",
    "position_code": "DEV-MID",
    "department_code": "IT-DEV",
    "email": "i.ivanov@accessguard.local",
    "phone": "+7-900-000-00-00"
  }
}
```

Identity-consumer:
1. Читает событие из `hr.events`.
2. Сохраняет в `lifecycle_events` со статусом `pending`.
3. Обрабатывает событие через сервисный слой (создаёт/изменяет/блокирует пользователя).
4. Публикует одно или несколько событий в `identity.users` и `identity.lifecycle`.
5. Записывает в `audit_log` (PostgreSQL) и в `audit.events` (Kafka → Elasticsearch).
6. Помечает `lifecycle_events.status = processed`, фиксирует Kafka offset.

При ошибке — статус `failed`, событие переотправляется через Dead Letter Queue (топик `hr.events.dlq`).

Дополнительно поддерживается webhook `POST /api/identity/events/hr` для внешних систем, не работающих с Kafka (резервный канал).

### 4.7. Фоновые задачи (Celery)

- `cleanup_blocked_users()` — Celery beat-задача, ежесуточно проверяет учётные записи в состоянии `blocked` и переводит в `deleted` тех, кто пробыл в `blocked` более 90 дней.
- `reconcile_with_hr()` — Celery beat-задача, ежесуточно сверяет состав активных сотрудников между БД и HR-mock через REST API HR-mock'а.

### 4.8. UI-страницы

- `/identity/users` — таблица пользователей с фильтрами по отделу, должности, статусу, поиском по имени. Действия: создать, редактировать, блокировать, восстановить, сбросить пароль.
- `/identity/users/:id` — карточка пользователя: атрибуты, история кадровых событий, текущие роли (с переходом в Access).
- `/identity/structure` — оргструктура (дерево отделов).
- `/identity/events` — журнал кадровых событий с возможностью фильтрации по типу, статусу, дате.

---

## 5. Модуль 2. Контроль доступа (Access)

### 5.1. Назначение

Реализация ролевой модели разграничения доступа (RBAC). Управление ролями, полномочиями, назначениями ролей пользователям. Проверка прав при обращении к защищённым ресурсам системы. Подписка на события Identity для автоматического управления ролями при кадровых изменениях.

### 5.2. Сущности и модель данных

**Таблица `roles`** — каталог ролей:
- `id` (PK), `code` (уникальный, snake_case), `name`, `description`, `is_privileged` (bool), `owner_user_id` (FK → users_ext, владелец роли)

**Таблица `permissions`** — каталог полномочий:
- `id` (PK), `code` (формат `resource:action`, например `documents:read`), `description`

**Таблица `role_permissions`** — связь ролей и полномочий (M:N):
- `role_id`, `permission_id`

**Таблица `user_roles`** — назначения ролей пользователям:
- `id`, `user_id`, `role_id`, `granted_at`, `granted_by` (FK → users_ext), `expires_at` (nullable), `request_id` (FK → access_requests, nullable)

**Таблица `resources`** — каталог защищаемых ресурсов:
- `id`, `code`, `name`, `type` (enum: file_share, application, database, api), `owner_user_id`

**Таблица `access_requests`** — заявки на расширенный доступ:
- `id`, `user_id`, `role_id`, `justification` (text), `status` (enum: pending, approved, rejected, withdrawn), `created_at`, `decided_at`, `decided_by`, `decision_comment`

**Таблица `position_role_defaults`** — матрица «должность → набор ролей по умолчанию»:
- `position_id`, `role_id`

**Таблица `processed_events`** — для идемпотентности Kafka-потребления:
- `event_id` (PK), `processed_at`, `consumer_group`

### 5.3. Базовый набор ролей и полномочий

Предустановленные роли (создаются миграцией):
- `system_admin` — полный доступ
- `security_officer` — мониторинг и аудит
- `hr_operator` — управление учётными записями
- `auditor` — только чтение журналов
- `manager` — управление подчинёнными
- `employee` — базовая роль сотрудника
- `guest` — минимальный доступ

Базовые полномочия по ресурсам системы:
- `users:read`, `users:write`, `users:delete`
- `roles:read`, `roles:write`, `roles:assign`
- `audit:read`, `audit:export`
- `reports:read`, `reports:generate`
- `documents:read`, `documents:write`, `documents:delete`

### 5.4. REST API

```
GET    /api/access/roles                    # Список ролей
POST   /api/access/roles                    # Создать роль
GET    /api/access/roles/{id}               # Карточка роли
PATCH  /api/access/roles/{id}               # Обновить
DELETE /api/access/roles/{id}               # Удалить
POST   /api/access/roles/{id}/permissions   # Изменить набор полномочий

GET    /api/access/permissions              # Каталог полномочий
GET    /api/access/resources                # Каталог ресурсов

POST   /api/access/users/{user_id}/roles    # Назначить роль
DELETE /api/access/users/{user_id}/roles/{role_id}    # Отозвать роль
GET    /api/access/users/{user_id}/roles    # Текущие роли пользователя
GET    /api/access/users/{user_id}/permissions    # Эффективные полномочия

POST   /api/access/check                    # Проверка полномочия (для других сервисов)

GET    /api/access/requests                 # Заявки на доступ
POST   /api/access/requests                 # Подать заявку
POST   /api/access/requests/{id}/approve    # Одобрить
POST   /api/access/requests/{id}/reject     # Отклонить

GET    /api/access/matrix                   # Матрица «должность → роли»
PUT    /api/access/matrix/{position_id}     # Изменить набор ролей для должности
```

### 5.5. Бизнес-логика и реакция на события Identity

Access-consumer подписан на топик `identity.users`:

- При получении `user.created` → автоматическое назначение базовых ролей из `position_role_defaults`. Каждое назначение порождает событие `role.assigned` в `access.roles`.
- При получении `lifecycle.transferred` → пересмотр ролей:
  1. Определяется новый базовый набор ролей по должности.
  2. Сравнивается с текущим набором.
  3. Добавляются недостающие.
  4. Для удаляемых ролей применяется правило отложенного удаления: `expires_at = now + 14 days`.
- При получении `user.blocked` → отзыв всех ролей пользователя.

**Проверка полномочий:** функция `check_permission(user_id, permission_code) → bool` агрегирует все роли пользователя, собирает их полномочия и возвращает True/False. Используется как в FastAPI-зависимости для защиты эндпоинтов, так и через REST API `POST /api/access/check` для внешних потребителей. Результат проверки кэшируется в Redis на 60 секунд для снижения нагрузки.

**Согласование заявок на доступ:**
1. Пользователь подаёт заявку с указанием роли и обоснованием → событие `request.submitted`.
2. Заявка направляется руководителю отдела (через `manager_user_id` отдела).
3. После одобрения руководителем — направляется владельцу роли (`owner_user_id`).
4. Если роль помечена как `is_privileged` — дополнительно требуется одобрение security_officer.
5. После всех одобрений роль автоматически назначается с `granted_at` = now, событие `request.approved` + `role.assigned`.

### 5.6. UI-страницы

- `/access/roles` — каталог ролей с поиском, фильтрацией по `is_privileged`.
- `/access/roles/:id` — редактор роли: атрибуты, набор полномочий (через диалог-выборщик из `permissions`).
- `/access/matrix` — таблица «должность × роль» с переключателями.
- `/access/requests` — заявки на доступ; раздельный вид для подающего и согласующего.
- `/access/users/:id` — текущие роли и эффективные полномочия пользователя (вкладка карточки пользователя).

---

## 6. Модуль 3. Мониторинг, регистрация событий и оповещение (Monitor)

### 6.1. Назначение

Регистрация всех значимых действий пользователей и администраторов в системе. Хранение журнала аудита с гарантиями целостности (PostgreSQL). Индексация в Elasticsearch для быстрого поиска и аналитики. Дашборды в Kibana, встраиваемые в frontend. Автоматическое выявление подозрительной активности по настраиваемым правилам. Уведомление администратора безопасности об инцидентах.

### 6.2. Сущности и модель данных

**Таблица `audit_log`** — журнал аудита в PostgreSQL (append-only):
- `id` (PK, BIGSERIAL)
- `event_id` (UUID, уникальный) — соответствует `event_id` в Kafka и Elasticsearch
- `timestamp` (timestamp с tz, индекс)
- `actor_id` (FK → users_ext, nullable — для системных событий)
- `actor_username` (string, дублирование на случай удаления пользователя)
- `target_type` (enum: user, role, resource, system)
- `target_id` (string, идентификатор объекта операции)
- `operation` (enum: create, read, update, delete, login_success, login_failure, permission_check, role_assign, role_revoke, password_reset, ...)
- `module` (enum: identity, access, monitor, reports)
- `result` (enum: success, failure, denied)
- `ip_address` (inet)
- `user_agent` (string, обрезается до 500 символов)
- `details` (JSONB) — дополнительные сведения
- `correlation_id` (UUID) — для связи событий одной транзакции
- `published_to_kafka` (bool, default false) — флаг успешной публикации в Kafka

Защита от модификации: триггер на уровне БД, отклоняющий UPDATE и DELETE для всех записей старше 1 минуты, и роль `audit_writer` без права UPDATE/DELETE.

**Таблица `alert_rules`** — правила выявления:
- `id` (PK), `code` (уникальный), `name`, `description`
- `condition_type` (enum: threshold, pattern, anomaly)
- `condition_config` (JSONB) — параметры правила
- `severity` (enum: info, low, medium, high, critical)
- `is_enabled` (bool)
- `cooldown_seconds` (int)
- `data_source` (enum: postgres, elasticsearch) — где правило ищет данные

**Таблица `alerts`** — сработавшие оповещения:
- `id` (PK), `rule_id` (FK), `triggered_at`, `subject_user_id` (FK), `severity`
- `status` (enum: new, acknowledged, resolved, false_positive)
- `correlation_id` (UUID), `details` (JSONB)
- `acknowledged_at`, `acknowledged_by`, `resolution_comment`

**Таблица `notification_channels`** — каналы доставки:
- `id`, `code`, `type` (enum: email, webhook, log, kafka), `config` (JSONB), `is_enabled`

### 6.3. Базовый набор правил выявления

Предустанавливаются миграцией. Правила теперь делятся на два типа по источнику данных:

**Простые (data_source: postgres)** — реальное время, выполняются после каждой записи в `audit_log`:
1. `multiple_failed_logins` — 5+ неудачных попыток входа за 15 минут от одного пользователя → severity high
2. `privileged_role_assigned` — назначение привилегированной роли → severity high
3. `audit_log_tampering_attempt` — попытка UPDATE/DELETE в audit_log → severity critical
4. `admin_password_reset` — сброс пароля привилегированного пользователя → severity high

**Сложные (data_source: elasticsearch)** — выполняются по расписанию (Celery beat, каждые 1–5 минут), используют агрегации Elasticsearch:
5. `login_outside_hours` — успешный вход в нерабочее время (22:00–06:00) → severity medium
6. `mass_permission_failures` — 10+ отказов в доступе за 5 минут от одного пользователя → severity medium
7. `bulk_user_changes` — 20+ операций изменения учётных записей за 10 минут от одного администратора → severity medium
8. `inactive_user_login` — вход под учётной записью, неактивной более 90 дней → severity high
9. `unusual_geo_login` (бонус) — вход с IP из необычной страны (по агрегации `ip_address` за 30 дней) → severity high
10. `data_exfiltration_pattern` (бонус) — массовое чтение документов одним пользователем за короткий период → severity high

### 6.4. REST API

```
GET    /api/monitor/audit                   # Поиск по журналу через Elasticsearch (полнотекст, агрегации)
GET    /api/monitor/audit/{event_id}        # Карточка записи (из PostgreSQL)
GET    /api/monitor/audit/export            # Выгрузка в CSV/JSON (из Elasticsearch)
POST   /api/monitor/audit                   # Внутренний эндпоинт (используется другими модулями)

GET    /api/monitor/rules                   # Список правил
POST   /api/monitor/rules                   # Создать правило
PATCH  /api/monitor/rules/{id}              # Изменить
POST   /api/monitor/rules/{id}/toggle       # Включить/выключить
POST   /api/monitor/rules/{id}/test         # Запустить правило вручную для проверки

GET    /api/monitor/alerts                  # Лента оповещений с фильтрами
GET    /api/monitor/alerts/{id}             # Карточка оповещения с контекстом
POST   /api/monitor/alerts/{id}/acknowledge # Принять в работу
POST   /api/monitor/alerts/{id}/resolve     # Закрыть
POST   /api/monitor/alerts/{id}/false-positive    # Отметить как ложное срабатывание

GET    /api/monitor/channels                # Каналы оповещения
POST   /api/monitor/channels                # Добавить
PATCH  /api/monitor/channels/{id}           # Изменить

GET    /api/monitor/dashboard               # Сводные метрики для главного экрана
GET    /api/monitor/kibana-token            # Получение токена для встраивания Kibana
```

### 6.5. Механизм регистрации событий

В backend реализован сервис `audit_service.log(...)`, который вызывается из всех модулей в ключевых точках. Запись выполняется в **двух шагах** в одной транзакции:

1. **Синхронная запись в PostgreSQL** — гарантирует целостность.
2. **Публикация в топик Kafka `audit.events`** — делается в той же транзакции через паттерн **transactional outbox**:
   - в той же транзакции создаётся запись в таблице `outbox_events` со статусом `pending`;
   - отдельный Kafka-publisher (фоновый процесс) читает таблицу, отправляет в Kafka, помечает `published`;
   - после успешной публикации в `audit_log.published_to_kafka` ставится `true`.

Это исключает потерю событий: даже если приложение упадёт между записью в БД и публикацией в Kafka, событие будет отправлено при следующем запуске publisher'а.

Logstash потребляет `audit.events` и индексирует в Elasticsearch.

### 6.6. Механизм выявления подозрительной активности

**Простые правила** (4 шт.) выполняются синхронно после каждой записи в `audit_log` через сигнал SQLAlchemy `after_insert` в Celery-задаче `evaluate_simple_rules(audit_id)`. Использует данные из PostgreSQL.

**Сложные правила** (6 шт.) выполняются периодически через Celery beat:
- задача `evaluate_complex_rules` запускается каждые 60 секунд;
- для каждого включённого правила с `data_source=elasticsearch` строится запрос с агрегациями к Elasticsearch;
- по результатам формируются alert'ы.

При срабатывании правила:
1. Проверяется cooldown по субъекту.
2. Создаётся запись в `alerts` со статусом `new`.
3. Публикуется событие `alert.triggered` в топик `monitor.alerts`.
4. Через `notification_service.send(alert)` отправляются уведомления по всем включённым каналам.

### 6.7. Каналы оповещения

В прототипе реализуются четыре канала:
- `email` — через SMTP на MailHog (можно посмотреть письма по `http://localhost:8025`);
- `webhook` — POST с JSON-телом на настраиваемый URL (имитация интеграции с внешней SIEM);
- `log` — запись в файл `/var/log/accessguard/alerts.log`;
- `kafka` — публикация в отдельный топик (для интеграции с внешними потребителями).

### 6.8. Интеграция с Kibana

Предустановленные дашборды экспортируются в `kibana/dashboards/` в формате NDJSON и импортируются скриптом `kibana-import.sh` при первом запуске:

1. **Audit Overview** — общая активность: события по времени, по модулям, по результатам.
2. **User Activity** — активность пользователей: топ-10 по числу действий, географическое распределение IP, тепловая карта по часам.
3. **Security Incidents** — карта сработавших правил, динамика инцидентов, топ нарушителей.
4. **Access Patterns** — паттерны доступа: какие ресурсы запрашиваются, какие отклонены.
5. **Compliance** — соответствие политикам: распределение по operation, attempted vs successful.

Дашборды встраиваются в frontend через iframe. Для прототипа Kibana работает в anonymous-режиме без аутентификации (для упрощения). В продакшене предусматривается интеграция через Kibana API + JWT.

### 6.9. UI-страницы

- `/monitor` — дашборд: 4 карточки с метриками + встроенный главный дашборд Kibana через iframe.
- `/monitor/audit` — журнал событий: таблица с расширенными фильтрами (поиск через Elasticsearch), экспорт.
- `/monitor/audit/:event_id` — карточка события: все поля из PostgreSQL, связанные события по `correlation_id` (запрос в Elasticsearch).
- `/monitor/alerts` — лента оповещений (карточный вид с цветовой индикацией severity), действия acknowledge/resolve.
- `/monitor/rules` — таблица правил с переключателями `is_enabled`, редактор условия, кнопка «Тестировать».
- `/monitor/kibana` — полноэкранное встраивание Kibana для глубокой аналитики.

---

## 7. Модуль 4. Формирование отчётности (Reports)

### 7.1. Назначение

Сбор данных из других модулей (через PostgreSQL для оперативных данных и через Elasticsearch для аналитики аудита) и формирование сводных отчётов в форматах PDF, XLSX, CSV. Поддержка предопределённых шаблонов и параметризованного формирования. Интеграция с Kafka для регулярных отчётов и нотификаций о готовности.

### 7.2. Сущности и модель данных

**Таблица `report_templates`** — каталог шаблонов:
- `id` (PK), `code` (уникальный), `name`, `description`
- `data_source` (enum: postgres, elasticsearch, combined)
- `parameters_schema` (JSONB) — JSON-Schema для входных параметров
- `output_formats` (string[], подмножество `[pdf, xlsx, csv]`)

**Таблица `reports`** — сформированные отчёты:
- `id` (PK, UUID), `template_id` (FK), `requested_by` (FK → users_ext)
- `parameters` (JSONB), `format` (enum: pdf, xlsx, csv)
- `status` (enum: pending, generating, ready, failed)
- `created_at`, `completed_at`
- `file_path` (string) — путь к сформированному файлу
- `file_size` (int), `error_message` (text, nullable)

**Таблица `report_schedules`** — расписания регулярных отчётов:
- `id`, `template_id`, `parameters`, `format`, `cron_expression`, `delivery_channel_id`, `is_enabled`

### 7.3. Предустановленные шаблоны отчётов

1. `users_report` (data_source: postgres) — список пользователей с фильтрацией по отделу, статусу, должности.
2. `roles_matrix` (postgres) — матрица «пользователи × роли» с группировкой по отделу.
3. `access_requests_report` (postgres) — отчёт по заявкам на доступ за период.
4. `audit_summary` (elasticsearch) — сводный отчёт аудита через агрегации Elasticsearch.
5. `security_incidents` (combined) — отчёт об инцидентах: alerts из postgres + контекст из Elasticsearch.
6. `inactive_users` (elasticsearch) — список пользователей без активности более N дней.
7. `permissions_audit` (postgres) — аудит назначений привилегированных ролей за период.
8. `compliance_overview` (combined) — комплексный отчёт по состоянию системы.

### 7.4. REST API

```
GET    /api/reports/templates               # Каталог шаблонов
GET    /api/reports/templates/{code}        # Описание шаблона со схемой параметров

POST   /api/reports                         # Запрос на формирование
GET    /api/reports                         # История отчётов пользователя
GET    /api/reports/{id}                    # Статус и метаданные
GET    /api/reports/{id}/download           # Скачать файл

GET    /api/reports/schedules               # Расписания
POST   /api/reports/schedules               # Создать
PATCH  /api/reports/schedules/{id}          # Изменить
DELETE /api/reports/schedules/{id}          # Удалить

POST   /api/reports/schedules/{id}/run      # Запустить вручную
```

### 7.5. Архитектура генератора отчётов

Базовый класс `BaseReportGenerator`:
- `collect_data(parameters)` — сбор данных. Для postgres-источников — SQL/ORM; для elasticsearch — search queries с aggregations.
- `validate_parameters(parameters)` — валидация по схеме.
- `generate(parameters, format)` — оркестрирует процесс.

Для шаблонов с `data_source=elasticsearch` используется специальный сборщик `ElasticDataCollector`, выполняющий запросы к Elasticsearch с использованием date_range, term, aggs (terms, date_histogram, cardinality).

Форматирование выполняется через слой рендереров:
- `PdfRenderer` — Jinja2 + WeasyPrint;
- `XlsxRenderer` — openpyxl со стилизацией;
- `CsvRenderer` — стандартный csv с разделителем `;`.

### 7.6. Асинхронная генерация и интеграция с Kafka

Запрос на формирование отчёта возвращает `report_id` сразу. Генерация — фоновая задача Celery `generate_report(report_id)`.

После завершения генерации публикуется событие `report.ready` в топик `reports.notifications`. Frontend подписывается на свои отчёты через WebSocket (отдельный эндпоинт `/ws/reports`), backend форвардит туда события из Kafka.

### 7.7. Регулярные отчёты по расписанию

Celery beat задача `check_report_schedules` каждую минуту проверяет таблицу `report_schedules`. Для расписаний, время которых наступило, создаётся обычный report, после генерации — доставляется через указанный канал (email, webhook, или публикация в `reports.notifications`).

### 7.8. UI-страницы

- `/reports/templates` — каталог шаблонов с описанием и кнопкой «Сформировать».
- `/reports/new/:template_code` — форма параметров, генерируемая по `parameters_schema`.
- `/reports/history` — история сформированных отчётов с возможностью скачивания. Live-обновление статуса через WebSocket.
- `/reports/schedules` — управление расписаниями.
- `/reports/preview/:id` — предпросмотр сформированного отчёта.

---

## 8. Поперечные требования

### 8.1. Безопасность

- Все REST API защищены JWT (access-токен в заголовке, refresh — в HttpOnly cookie).
- Пароли — bcrypt (стоимость 12).
- Минимальная длина пароля — 12 символов; проверка по списку 1000 распространённых паролей.
- Защита от brute-force: блокировка после 5 неудачных попыток на 15 минут.
- CSRF-защита для cookie-эндпоинтов.
- CORS через переменную окружения.
- HTTPS в продакшене — через nginx.
- SQL-инъекции исключены через SQLAlchemy ORM.
- XSS — за счёт React-экранирования.
- **Kafka в прототипе работает без TLS и SASL** — для упрощения; в продакшене предусматривается mTLS и SASL/SCRAM.
- **Elasticsearch** — без security в прототипе (xpack.security.enabled=false); в продакшене — встроенная аутентификация Elastic Security.

### 8.2. Производительность

- Целевая нагрузка прототипа: до 5000 учётных записей, до 1 миллиона записей в `audit_log`, до 100 одновременных запросов.
- Все часто запрашиваемые поля индексируются.
- Постраничная выгрузка (лимит 100 по умолчанию, максимум 1000).
- Поиск по аудиту — через Elasticsearch (миллисекунды для миллиона записей).
- Кэширование результатов проверки полномочий в Redis (TTL 60 сек).
- Kafka-потребители обрабатывают сообщения батчами по 100 штук с timeout 5 сек.

### 8.3. Логирование и наблюдаемость

- Структурированные JSON-логи через `structlog`.
- Уровни: DEBUG (только разработка), INFO, WARNING, ERROR.
- Каждый HTTP-запрос логируется в middleware: метод, путь, статус, время, user_id.
- Корреляционный ID (`X-Correlation-ID`) пробрасывается через HTTP-запросы, Kafka-сообщения и попадает в audit_log.
- Логи приложения **не дублируются** в Elasticsearch (там только бизнес-аудит); приложение пишет в stdout, который собирается Docker-логами.

### 8.4. Тестирование

Покрытие — не менее 70% строк backend.

Виды тестов:
- **Юнит-тесты** для сервисного слоя (бизнес-логика без БД, через mocks).
- **Интеграционные тесты** API через `httpx.AsyncClient` и тестовую БД (PostgreSQL в Docker через `testcontainers`, чистая на каждый прогон).
- **Тесты Kafka-потребителей** — через `testcontainers` с реальным Kafka в Docker.
- **Тесты Elasticsearch-запросов** — через `testcontainers` с реальным Elasticsearch.
- **Тесты правил выявления** для модуля Monitor.
- **E2E-сценарии**:
  1. Цепочка: HR-mock публикует `hire` → Identity создаёт пользователя → Access назначает роли → запись в audit_log → индексация в Elasticsearch → видна в Kibana.
  2. Цепочка: 5 неудачных входов → срабатывание правила → alert → email на MailHog.
  3. Подача заявки → согласование → назначение роли → видно во всех модулях.
  4. Формирование отчёта по audit-данным из Elasticsearch.

CI: GitHub Actions, `.github/workflows/ci.yml`.

### 8.5. Документация

- `README.md` — что это, как запустить, что увидите. Скриншоты ключевых экранов (frontend + Kibana).
- `docs/architecture.md` — архитектура со схемами (диаграммы в Mermaid).
- `docs/api.md` — обзор REST API; полная Swagger UI на `http://localhost:8000/docs`.
- `docs/events.md` — каталог Kafka-событий с примерами JSON.
- `docs/elasticsearch.md` — описание индексов и примеры запросов.
- `docs/modules/{identity,access,monitor,reports}.md` — описание каждого модуля.
- Docstrings на все публичные функции сервисного слоя.

### 8.6. Демонстрационные данные

Скрипт `scripts/seed.sh`:

- 5 отделов в иерархии 3 уровня;
- 30 должностей;
- 50 пользователей-сотрудников (русские ФИО через `faker[ru_RU]`);
- 4 администратора системы;
- ~5000 случайных записей audit_log за 90 дней (PostgreSQL → Kafka → Elasticsearch);
- набор сработавших оповещений разных severity;
- несколько готовых отчётов в истории;
- предустановленные дашборды Kibana импортируются автоматически.

После `docker-compose up -d && ./scripts/seed.sh`:
- frontend: `http://localhost:5173`
- backend Swagger: `http://localhost:8000/docs`
- Kibana: `http://localhost:5601`
- MailHog: `http://localhost:8025`
- учётные данные администраторов выводятся в консоль.

### 8.7. Переменные окружения

Шаблон `.env.example`:

```
# PostgreSQL
DATABASE_URL=postgresql+asyncpg://accessguard:secret@postgres:5432/accessguard

# Redis
REDIS_URL=redis://redis:6379/0

# LDAP
LDAP_URI=ldap://ldap:389
LDAP_BASE_DN=dc=accessguard,dc=local
LDAP_BIND_DN=cn=admin,dc=accessguard,dc=local
LDAP_BIND_PASSWORD=admin

# HR-mock
HR_MOCK_URL=http://hr-mock:8001

# Kafka
KAFKA_BOOTSTRAP_SERVERS=kafka:9092
KAFKA_CONSUMER_GROUP_PREFIX=accessguard
KAFKA_PRODUCER_ACKS=all
KAFKA_PRODUCER_IDEMPOTENCE=true

# Elasticsearch
ELASTICSEARCH_URL=http://elasticsearch:9200
ELASTICSEARCH_AUDIT_INDEX_PREFIX=audit-events

# Kibana
KIBANA_URL=http://kibana:5601
KIBANA_EMBED_URL=http://localhost:5601/app/dashboards#/view

# JWT
JWT_SECRET=<сгенерируйте>
JWT_ACCESS_TTL_MIN=15
JWT_REFRESH_TTL_DAYS=7

# SMTP
SMTP_HOST=mailhog
SMTP_PORT=1025

# Прочее
CORS_ORIGINS=http://localhost:5173
LOG_LEVEL=INFO
```

---

## 9. Этапы реализации

### Этап 1. Фундамент (приоритет: критический)
1.1. Структура репозитория, `pyproject.toml`, `package.json`, `docker-compose.yml`, `.env.example`.
1.2. Базовое FastAPI-приложение с подключением к PostgreSQL.
1.3. Alembic с initial-миграцией (общие таблицы).
1.4. Настройка docker-compose с **базовыми сервисами**: postgres, redis, ldap, mailhog.
1.5. Аутентификация администраторов: модели, JWT, эндпоинты `/auth/*`.
1.6. Frontend-каркас: маршрутизация, страница логина, layout с навигацией.
1.7. README.

### Этап 2. Инфраструктура Kafka и Elasticsearch (приоритет: критический)
2.1. Добавление в docker-compose: zookeeper, kafka, kafka-init (создание топиков), elasticsearch, logstash, kibana.
2.2. Healthcheck'и для всех сервисов; правильная последовательность запуска.
2.3. `kafka/producer.py`, `kafka/consumer.py`, `kafka/events.py` с базовым конвертом.
2.4. `elastic/client.py`, `elastic/indices.py` с index template для audit-events.
2.5. Скрипт `scripts/elastic-init.sh` — создание индексов и шаблонов при первом запуске.
2.6. Конфиг Logstash `logstash/pipeline/audit.conf`.
2.7. Тестовая публикация события: продьюсер пишет в `audit.events`, проверяется появление в Elasticsearch.

### Этап 3. Модуль Identity (приоритет: высокий)
3.1. ORM-модели и миграции.
3.2. Сервисный слой с публикацией событий в `identity.users`, `identity.lifecycle`.
3.3. LDAP-клиент.
3.4. REST API.
3.5. HR-mock сервис, публикация событий в `hr.events`.
3.6. Identity-consumer для `hr.events`.
3.7. Webhook (резервный канал).
3.8. Celery: cleanup, reconcile.
3.9. Frontend: `/identity/*`.
3.10. Тесты (включая Kafka через testcontainers).

### Этап 4. Модуль Access (приоритет: высокий)
4.1. ORM-модели и миграции, начальные данные.
4.2. Сервисный слой с публикацией событий в `access.*`.
4.3. Access-consumer для `identity.users` и `identity.lifecycle`.
4.4. REST API, кэширование проверок в Redis.
4.5. Процесс согласования заявок.
4.6. Frontend: `/access/*`.
4.7. Тесты.

### Этап 5. Модуль Monitor (приоритет: высокий)
5.1. ORM-модели; миграция с триггером append-only для `audit_log`.
5.2. `audit_service.log` с **transactional outbox**-паттерном (запись в БД + outbox + публикация в Kafka).
5.3. Интеграция в Identity, Access (везде, где нужен аудит).
5.4. Базовый класс `BaseRule`, реализация 4 простых + 6 сложных правил.
5.5. Celery beat для сложных правил.
5.6. REST API; поиск по audit через Elasticsearch.
5.7. Каналы оповещения (email, webhook, log, kafka).
5.8. Frontend: дашборд, журнал, оповещения.
5.9. Импорт готовых дашбордов в Kibana через `kibana-import.sh`.
5.10. Встраивание Kibana через iframe.
5.11. Тесты правил.

### Этап 6. Модуль Reports (приоритет: средний)
6.1. ORM-модели, миграции с предустановленными шаблонами.
6.2. Базовый класс генератора и три рендерера.
6.3. `ElasticDataCollector` для агрегаций.
6.4. Реализация 8 шаблонов.
6.5. Асинхронная генерация через Celery, нотификация через Kafka + WebSocket.
6.6. Регулярные отчёты по расписанию.
6.7. REST API.
6.8. Frontend.
6.9. Тесты.

### Этап 7. Полировка (приоритет: средний)
7.1. Скрипт `seed.sh` с реалистичными данными (включая публикацию в Kafka для индексации в Elasticsearch).
7.2. Документация: `architecture.md`, `api.md`, `events.md`, `elasticsearch.md`, описания модулей.
7.3. Mermaid-диаграммы.
7.4. Скриншоты в README.
7.5. CI-пайплайн.
7.6. Финальная проверка: чистый clone → запуск → всё работает за 15 минут.

---

## 10. Критерии приёмки

Прототип готов, если:

1. ✅ `git clone` → `cp .env.example .env` → `docker-compose up -d` → `./scripts/seed.sh` запускает всю систему с нуля без ручных шагов.
2. ✅ Веб-интерфейс на `http://localhost:5173`, Swagger на `http://localhost:8000/docs`, Kibana на `http://localhost:5601`, MailHog на `http://localhost:8025`.
3. ✅ Сценарий: вход → создать пользователя через HR-mock webhook → автоматическое появление пользователя в Identity → автоматическое назначение базовых ролей в Access → запись в audit_log → появление в Elasticsearch → отображение в Kibana.
4. ✅ Все 10 правил выявления срабатывают на синтетических данных в тестах.
5. ✅ Все 8 шаблонов отчётов формируются в трёх форматах без ошибок.
6. ✅ В Kibana доступны 5 предустановленных дашбордов с данными.
7. ✅ Демонстрация transactional outbox: можно остановить Kafka, продолжить работу backend (записи копятся в outbox), запустить Kafka — записи догоняются и появляются в Elasticsearch.
8. ✅ `pytest` проходит, покрытие ≥ 70%.
9. ✅ В `docs/` лежат все указанные файлы; диаграммы открываются.

---

## 11. Что НЕ делать (out of scope)

- ❌ SAML/OAuth2/OIDC SSO — только локальный JWT.
- ❌ Multi-tenant — одна организация.
- ❌ BI с OLAP-кубами — отчёты табличные.
- ❌ DLP, антивирус, IDS/IPS.
- ❌ Мобильное приложение — только веб.
- ❌ Локализация на несколько языков — только русский.
- ❌ Federated LDAP — один OpenLDAP, plain bind.
- ❌ Kafka Streams / KSQL — только обычные продьюсеры/потребители.
- ❌ Elastic APM, Beats, Filebeat — только базовый стек ELK для аудита.
- ❌ Production-grade Kafka (без TLS, SASL, multi-broker) — single broker для прототипа.
- ❌ Production-grade Elasticsearch (single-node, без security, без shards/replicas) — для прототипа.

---

## Приложение А. Глоссарий

| Термин | Расшифровка |
|---|---|
| RBAC | Role-Based Access Control — управление доступом на основе ролей |
| IdM | Identity Management — управление учётными записями |
| LDAP | Lightweight Directory Access Protocol — протокол доступа к каталогу |
| DIT | Directory Information Tree — иерархия записей в LDAP |
| DN | Distinguished Name — уникальный путь к записи в LDAP |
| OU | Organizational Unit — организационное подразделение в LDAP |
| JWT | JSON Web Token — формат токена аутентификации |
| Cooldown | Минимальный интервал между повторными срабатываниями |
| Append-only | Режим хранения, при котором записи можно только добавлять |
| SPA | Single Page Application — одностраничное веб-приложение |
| ELK | Elasticsearch + Logstash + Kibana — стек для логирования и аналитики |
| Topic (Kafka) | Топик — канал доставки событий |
| Partition (Kafka) | Партиция — единица параллелизма топика |
| Consumer Group | Группа потребителей — несколько процессов, делящих партиции |
| Idempotent producer | Идемпотентный продьюсер — гарантия отсутствия дубликатов |
| Transactional Outbox | Паттерн: запись событий в таблицу-outbox в одной транзакции с бизнес-данными, отдельный publisher отправляет в Kafka |
| Rolling index | Индекс с разбиением по времени (audit-events-YYYY.MM) |
| DLQ | Dead Letter Queue — топик для необработанных сообщений |
| mTLS | Mutual TLS — двусторонняя аутентификация по TLS |

---

*Конец технического задания.*
