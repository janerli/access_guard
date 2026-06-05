<div align="center">

# 🛡️ AccessGuard

**Корпоративная система мониторинга и управления доступом**

*Дипломный проект · Python + FastAPI + React + Kafka + Elasticsearch*

[![CI](https://github.com/janerli/access_guard/actions/workflows/ci.yml/badge.svg)](https://github.com/janerli/access_guard/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/janerli/access_guard/branch/main/graph/badge.svg)](https://codecov.io/gh/janerli/access_guard)
![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python&logoColor=white)
![React](https://img.shields.io/badge/React-18-61dafb?logo=react&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.110-009688?logo=fastapi&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-336791?logo=postgresql&logoColor=white)

</div>

---

## О проекте

AccessGuard — прототип корпоративной системы управления доступом к информационным ресурсам для организаций численностью **50–500 сотрудников**. Реализует полный цикл: от найма сотрудника до аудита его действий и автоматического выявления угроз безопасности.

### Ключевые возможности

- 🔐 **Управление жизненным циклом** учётных записей с интеграцией HR-системы и OpenLDAP
- 🎭 **RBAC с матрицей доступа** — 7 ролей, 14 разрешений, заявки с согласованием
- 📊 **Двухконтурный аудит** — PostgreSQL (источник истины) + Elasticsearch (поиск и агрегации)
- 🚨 **10 правил выявления угроз** — 4 real-time (PostgreSQL) + 6 через ES aggregations
- 📈 **6 Kibana дашбордов** с корректным keyword-маппингом для всех полей
- 📄 **8 шаблонов отчётов** в форматах PDF / XLSX / CSV с асинхронной генерацией
- 🧪 **Симулятор угроз** на отдельном порту `:8001` — воспроизведение каждого правила одной кнопкой
- 🔍 **Предпросмотр отчётов** с встроенным PDF-viewer и панелью метаданных
- 🕵️ **Карточка события аудита** с цепочкой correlation_id из Elasticsearch

---

## Быстрый старт

```bash
# 1. Клонировать и настроить окружение
git clone https://github.com/janerli/access_guard.git && cd access_guard
cp .env.example .env

# 2. Запустить все сервисы (16 контейнеров)
docker compose up -d

# 3. Подождать 3–4 минуты — elastic-init запустится автоматически
#    после готовности ES и создаст index templates ДО первой записи Logstash
docker compose ps   # все сервисы должны быть healthy / exited(0) для elastic-init

# 4. Заполнить демо-данными и импортировать Kibana-дашборды
bash scripts/seed.sh
```

> ⚠️ **После обновления кода** (если ES-данные были накоплены со старым маппингом):
> ```bash
> docker compose down -v   # удаляет тома — все данные ES/PG сотрутся
> docker compose up -d
> bash scripts/seed.sh
> ```

> 💡 На удалённом сервере замени `localhost` на IP-адрес машины во всех ссылках ниже.

---

## Адреса сервисов

| Сервис | Адрес | Назначение |
|--------|-------|------------|
| 🖥️ **Frontend** | [localhost:5173](http://localhost:5173) | Основной веб-интерфейс |
| 📋 **API Swagger** | [localhost:8000/docs](http://localhost:8000/docs) | Документация REST API |
| 📊 **Kibana** | [localhost:5601](http://localhost:5601) | Дашборды событий безопасности |
| 📧 **MailHog** | [localhost:8025](http://localhost:8025) | Перехват email-оповещений |
| 🔀 **Kafka UI** | [localhost:8080](http://localhost:8080) | Топики, сообщения, consumer groups |
| 🌸 **Flower** | [localhost:5555](http://localhost:5555) | Мониторинг Celery-задач |
| 👥 **HR-mock** | [localhost:8001/docs](http://localhost:8001/docs) | Симулятор кадровой системы |
| 🧪 **Симулятор угроз** | [localhost:8002](http://localhost:8002) | Внешняя тест-панель симуляции угроз |

---

## Учётные записи

| Логин | Пароль | Роль | Права |
|-------|--------|------|-------|
| `admin` | `Admin123456789` | Системный администратор | Полный доступ |
| `security_admin` | `Security123456` | Офицер безопасности | Аудит, алерты, отчёты |
| `hr_admin` | `HrAdmin123456` | HR-оператор | Управление пользователями |
| `auditor_user` | `Auditor123456` | Аудитор | Просмотр и отчёты |

---

## Архитектура

```
┌─────────────┐    hr.events     ┌──────────────┐  identity.users  ┌──────────────┐
│   HR-mock   │ ──────────────► │   Identity   │ ───────────────► │    Access    │
│  (FastAPI)  │                  │   Module     │                   │    Module    │
└─────────────┘                  └──────┬───────┘                   └──────┬───────┘
                                        │ audit                            │ audit
                                        ▼                                  ▼
                                 ┌──────────────────────────────────────────────────┐
                                 │                Monitor Module                    │
                                 │  audit_log (PostgreSQL) + outbox_events          │
                                 └──────────────────┬───────────────────────────────┘
                                                    │ Kafka: audit.events
                                                    ▼
                                      ┌─────────────────────────┐
                                      │  elastic-init (one-shot) │  ← создаёт index templates
                                      └────────────┬────────────┘    ДО первой записи
                                                   │
                                             ┌─────▼──────┐
                                             │  Logstash  │  ← @timestamp из поля timestamp
                                             └─────┬──────┘
                                                   │
                                             ┌─────▼──────┐
                                             │Elasticsearch│◄── 10 правил выявления
                                             └─────┬──────┘     (6 сложных через aggregations)
                                                   │
                                    ┌──────────────┼──────────────┐
                                    ▼              ▼              ▼
                                  Kibana        Reports        Alerts → MailHog
                               (6 dashboards) (8 templates)  (email/webhook/kafka)
```

### Ключевые архитектурные решения

| Паттерн | Реализация |
|---------|-----------|
| **Transactional outbox** | `audit_log` + `outbox_events` в одной транзакции → Celery publisher → Kafka |
| **Идемпотентные консьюмеры** | Таблица `processed_events` с `event_id + consumer_group` |
| **Redis-кэш прав** | `check_permission` кэшируется на 60 сек, инвалидируется при смене ролей |
| **Append-only аудит** | PostgreSQL-триггер запрещает UPDATE/DELETE записей старше 1 минуты |
| **Сквозной correlation_id** | Все события, записи аудита и алерты связаны единым UUID |
| **elastic-init first** | Сервис `elastic-init` запускается до Logstash — гарантирует keyword-маппинг |

---

## Модули

<details>
<summary><b>🧑‍💼 Identity — управление учётными записями</b></summary>

- Жизненный цикл: `new → active → suspended → blocked → deleted`
- Автоматическая синхронизация с HR-системой через Kafka (`hr.events`)
- Provisioning / deprovisioning в OpenLDAP
- Celery-задачи: `cleanup_blocked_users` (90 дней), `reconcile_with_hr` (ежесуточно)
- **API:** `GET|POST /api/identity/users`, `PATCH /:id`, `/suspend`, `/restore`, `/block`, `/sync`

</details>

<details>
<summary><b>🎭 Access — контроль доступа (RBAC)</b></summary>

- 7 ролей: `system_admin`, `security_officer`, `hr_operator`, `auditor`, `manager`, `employee`, `guest`
- 14 разрешений, матрица `должность → роли` (`position_role_defaults`)
- Заявки на доступ: `pending → approved/rejected` с согласованием менеджера и офицера ИБ
- Проверка прав с кэшом Redis (TTL 60 сек)
- **API:** `/api/access/roles`, `/permissions`, `/resources`, `/requests`, `/matrix`, `/check`

</details>

<details>
<summary><b>🔍 Monitor — мониторинг и аудит</b></summary>

- **Двухконтурный аудит:** PostgreSQL (гарантии) + Elasticsearch (поиск, агрегации)
- **10 правил выявления:**

  | Тип | Правила |
  |-----|---------|
  | Real-time (PostgreSQL) | Множественные неудачные входы, назначение привилегированной роли, попытка изменить audit_log, сброс пароля администратора |
  | Периодические (Elasticsearch, каждые 60 сек) | Аномальная активность по часам, нарушение SoD, privilege escalation, входы с разных IP, аномальная частота ошибок, активность после увольнения |

- **Каналы оповещений:** email (MailHog), webhook, log, Kafka
- **Карточка события** `/monitor/audit/:event_id` — детали + цепочка correlation_id из ES
- **API:** `/api/monitor/dashboard`, `/audit`, `/rules`, `/alerts`, `/channels`, `/health`

</details>

<details>
<summary><b>📄 Reports — отчётность</b></summary>

- **8 шаблонов:** список пользователей, матрица ролей, заявки на доступ, сводка аудита, инциденты безопасности, неактивные пользователи, аудит привилегий, обзор соответствия
- **Форматы:** CSV · XLSX (openpyxl со стилями) · PDF (WeasyPrint, fallback на текст)
- Асинхронная генерация через Celery, статус по WebSocket (`/ws/reports`)
- **Предпросмотр** `/reports/preview/:id` — PDF-viewer (65%) + метаданные + кнопка «Сформировать повторно»
- Расписания с cron-выражениями (`@daily`, `@weekly`, `@hourly`, `HH:MM`)
- **API:** `/api/reports/templates`, `/reports`, `/schedules`

</details>

<details>
<summary><b>🧪 Симулятор угроз — внешняя тест-панель</b></summary>

Standalone HTML-страница на **[localhost:8002](http://localhost:8002)** — отдельный Docker-сервис, не требующий сборки.

- Вводишь API URL + логин/пароль → подключается → показывает все 10 сценариев
- Кнопка «Симулировать» на каждый сценарий + «Запустить все»
- Live-лог выполнения в реальном времени
- Простые правила: создаёт реальные записи в `audit_log` и немедленно проверяет правило
- Сложные правила: создаёт alert напрямую с реалистичными деталями
- После нажатия алерт мгновенно появляется в `/monitor/alerts` и письмо уходит в MailHog
- **API:** `POST /api/simulation/run/{rule_code}`, `POST /api/simulation/run-all`

</details>

---

## Kafka-топики

| Топик | Продюсер | Консьюмер | Описание |
|-------|----------|-----------|----------|
| `hr.events` | HR-mock | Identity | Кадровые события: найм, перевод, увольнение |
| `identity.users` | Identity | Access | Создание/изменение/блокировка пользователей |
| `identity.lifecycle` | Identity | Monitor | Жизненный цикл для аудита |
| `access.roles` | Access | Monitor | Назначение/отзыв ролей |
| `access.requests` | Access | Monitor | Заявки на доступ |
| `monitor.alerts` | Monitor | — | Сработавшие правила выявления |
| `audit.events` | Outbox publisher | Logstash → ES | Поток аудит-событий (6 партиций) |
| `reports.notifications` | Reports | — | Готовность отчётов |

---

## Разработка

### Тесты

```bash
# Запустить все тесты
docker compose exec backend pytest -v

# С отчётом о покрытии
docker compose exec backend pytest --cov=app --cov-report=term-missing

# Конкретный модуль
docker compose exec backend pytest tests/test_monitor/ -v
```

> Целевое покрытие: **≥ 70%**

### Локально (без Docker)

```bash
cd backend
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload

cd frontend
npm install && npm run dev
```

### Полезные команды

```bash
# Статус контейнеров
docker compose ps

# Логи конкретного сервиса
docker compose logs -f backend
docker compose logs -f worker
docker compose logs -f elastic-init   # проверить что templates создались

# Применить новые миграции
docker compose exec backend alembic upgrade head

# Переинициализировать ES (пересоздаёт templates и удаляет старые индексы)
bash scripts/elastic-init.sh

# Принудительно импортировать Kibana-дашборды
bash scripts/kibana-import.sh

# Полный сброс с нуля (удаляет ВСЕ тома)
docker compose down -v && docker compose up -d && sleep 120 && bash scripts/seed.sh
```

### Типичные проблемы

| Проблема | Решение |
|----------|---------|
| Kibana показывает ошибки полей (Terms aggregation) | Старые индексы с неверным маппингом. Запусти: `bash scripts/elastic-init.sh` — скрипт удалит старые индексы, потом `bash scripts/seed.sh` |
| Отчёт завис в `pending` или «ES недоступен» | Пересобрать образы worker и beat: `docker compose build --no-cache worker beat && docker compose up -d --no-deps worker beat` |
| `elastic-init` завис | `docker compose logs elastic-init` — обычно ES ещё не готов, подождать и перезапустить: `docker compose restart elastic-init` |
| Нет данных в Kibana / 0 документов в ES | Проверить Logstash: `docker compose logs logstash --tail=30`. Если данные есть в Kafka но не в ES — сбросить оффсеты: `docker stop <logstash> && kafka-consumer-groups --reset-offsets --to-earliest ... && docker start <logstash>` |
| Симулятор угроз: «Failed to fetch» | Добавить `http://localhost:8002` в `CORS_ORIGINS` в `.env`, затем пересоздать контейнер: `docker compose up -d --no-deps backend` (не просто restart) |
| Kafka не стартует | Подождать 1–2 мин, Zookeeper поднимается медленно: `docker compose logs kafka --tail=20` |
| ES показывает down в health-панели | Первые 2–3 минуты ES прогревается, это нормально. Если постоянно — проверить версию клиента: `docker compose exec backend pip show elasticsearch` — должна быть 8.x. При 9.x пересобрать: `docker compose build --no-cache backend` |

---

## Структура проекта

```
access_guard/
├── 📄 docker-compose.yml          # 16 сервисов с healthcheck
├── 📄 .env.example                # Шаблон переменных окружения
├── 📁 docs/
│   ├── full-spec.md               # Полное техническое задание
│   └── events.md                  # Каталог Kafka-событий
├── 📁 backend/
│   ├── app/
│   │   ├── main.py                # FastAPI приложение
│   │   ├── celery_app.py          # Celery + beat расписания
│   │   ├── kafka/                 # Producer, consumer, events, topics
│   │   ├── elastic/               # ES client, index templates, search
│   │   ├── core/                  # JWT auth, deps, security, LDAP
│   │   └── modules/
│   │       ├── identity/          # Пользователи, LDAP, HR-синхронизация
│   │       ├── access/            # RBAC, Redis cache, заявки
│   │       ├── monitor/           # Audit log, правила, алерты, health
│   │       ├── reports/           # Шаблоны, генераторы, рендереры
│   │       └── simulation/        # Симулятор угроз (API)
│   ├── alembic/versions/          # 7 миграций БД
│   └── tests/                     # pytest, coverage ≥ 70%
├── 📁 frontend/src/
│   ├── pages/
│   │   ├── identity/              # Users, Structure, Events, UserDetail
│   │   ├── access/                # Roles, Matrix, Requests, RoleGraph
│   │   ├── monitor/               # Dashboard, AuditLog, AuditEventDetail,
│   │   │                          # Alerts, Rules, SystemHealth, Kibana
│   │   └── reports/               # Templates, NewReport, History,
│   │                              # PreviewReport, Schedules
│   ├── api/                       # axios API клиенты
│   ├── store/                     # Zustand (auth)
│   └── components/                # Layout, shadcn/ui компоненты
├── 📁 simulator-panel/
│   └── index.html                 # Standalone тест-панель (порт 8002)
├── 📁 hr-mock/                    # FastAPI симулятор HR-системы
├── 📁 logstash/pipeline/
│   └── audit.conf                 # Kafka → ES (устанавливает @timestamp из поля timestamp)
├── 📁 kibana/dashboards/          # 6 NDJSON дашбордов (единый index-pattern)
└── 📁 scripts/
    ├── seed.sh                    # Полный старт с демо-данными
    ├── seed_data.py               # 50 сотрудников, ~5000 аудит-записей
    ├── reset.sh                   # Сброс БД
    ├── elastic-init.sh            # Создаёт index templates + удаляет индексы с неверным маппингом
    └── kibana-import.sh           # Импорт Kibana дашбордов
```

---

## Стек технологий

**Backend**
`Python 3.11` · `FastAPI` · `SQLAlchemy 2.0 async` · `Alembic` · `Pydantic 2` · `aiokafka` · `elasticsearch[async] 8.x` · `Celery 5` · `Redis` · `ldap3` · `openpyxl` · `WeasyPrint`

**Frontend**
`React 18` · `TypeScript` · `Vite` · `shadcn/ui` · `Tailwind CSS` · `recharts` · `Zustand` · `react-router-dom` · `axios`

**Инфраструктура**
`PostgreSQL 15` · `Redis 7` · `OpenLDAP` · `Apache Kafka 3.6` · `Zookeeper` · `Elasticsearch 8.11` · `Logstash 8.11` · `Kibana 8.11` · `Kafka UI` · `Flower` · `MailHog` · `Docker Compose`

---

<div align="center">

📖 Детальное ТЗ со всеми REST-эндпоинтами, моделями данных и правилами выявления: [`docs/full-spec.md`](docs/full-spec.md)

</div>
