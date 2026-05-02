# AccessGuard

Система мониторинга и управления доступом к информационным ресурсам организации.

## Быстрый старт

```bash
# 1. Клонировать / перейти в папку проекта
cp .env.example .env          # скопировать конфиг

# 2. Запустить инфраструктуру
docker compose up -d

# 3. Наполнить тестовыми данными
bash scripts/seed.sh
```

## Интерфейсы

| Сервис       | Адрес                        |
|---|---|
| Frontend     | http://localhost:5173         |
| API Swagger  | http://localhost:8000/docs    |
| Kibana       | http://localhost:5601         |
| MailHog      | http://localhost:8025         |
| HR-mock      | http://localhost:8001/docs    |

## Учётные данные администраторов (после seed.sh)

| Пользователь   | Пароль         | Роль                    |
|---|---|---|
| admin          | Admin123456789 | Системный администратор |
| security_admin | Security123456 | Офицер безопасности     |
| hr_admin       | HrAdmin123456  | HR-оператор             |
| auditor        | Auditor123456  | Аудитор                 |

## Архитектура

Система состоит из 4 модулей в едином FastAPI-приложении:

1. **Identity** — управление учётными записями, LDAP, интеграция с HR через Kafka
2. **Access** — RBAC, проверка полномочий (кэш Redis), заявки на доступ
3. **Monitor** — двухконтурный аудит (PostgreSQL + Elasticsearch), правила выявления, оповещения
4. **Reports** — 8 шаблонов, PDF/XLSX/CSV, асинхронная генерация через Celery

**Межмодульное взаимодействие** — через Apache Kafka (8 топиков).  
**Аудит** — transactional outbox: PostgreSQL (источник истины) → Kafka → Logstash → Elasticsearch → Kibana.

## Стек

- Backend: Python 3.11, FastAPI, SQLAlchemy 2.0, Alembic, Celery
- Frontend: React 18 + TypeScript, Vite, shadcn/ui, Tailwind
- Инфраструктура: PostgreSQL 15, Redis 7, OpenLDAP, Kafka 3.6, Elasticsearch 8.11, Kibana 8.11

## Разработка

```bash
# Только базовые сервисы (Этап 1)
docker compose up -d postgres redis ldap mailhog backend worker beat frontend

# Запустить миграции вручную
docker compose exec backend alembic upgrade head

# Тесты
docker compose exec backend pytest --cov=app --cov-report=term-missing

# Логи
docker compose logs -f backend
```

Подробная спецификация: `docs/full-spec.md`
