# Каталог Kafka-событий AccessGuard

Все события передаются в формате `KafkaEvent`:

```json
{
  "event_id": "uuid",
  "event_type": "entity.action",
  "topic": "topic.name",
  "payload": { ... },
  "timestamp": "ISO8601",
  "correlation_id": "uuid",
  "source_service": "accessguard-backend"
}
```

---

## Топик: `hr.events`

Продюсер: **HR-mock** (`hr-mock/`)

### `employee.hired`
```json
{
  "employee_id": "EMP-001",
  "full_name": "Иванов Иван Иванович",
  "email": "ivanov@company.local",
  "position": "Разработчик ПО",
  "department": "IT",
  "hire_date": "2024-01-15",
  "manager_id": "EMP-000"
}
```

### `employee.updated`
```json
{
  "employee_id": "EMP-001",
  "changes": {
    "position": "Старший разработчик",
    "department": "IT-DEV"
  }
}
```

### `employee.terminated`
```json
{
  "employee_id": "EMP-001",
  "termination_date": "2024-06-30",
  "reason": "resignation"
}
```

---

## Топик: `identity.users`

Продюсер: **Identity module** (`modules/identity/service.py`)

### `user.created`
```json
{
  "user_id": "uuid",
  "username": "i.ivanov",
  "full_name": "Иванов Иван Иванович",
  "email": "i.ivanov@company.local",
  "position_id": "uuid",
  "department_id": "uuid",
  "status": "active"
}
```

### `user.updated`
```json
{
  "user_id": "uuid",
  "changes": {
    "position_id": "uuid",
    "department_id": "uuid"
  },
  "previous": {
    "position_id": "uuid-old",
    "department_id": "uuid-old"
  }
}
```

### `user.blocked`
```json
{
  "user_id": "uuid",
  "reason": "termination",
  "blocked_at": "ISO8601"
}
```

### `user.deleted`
```json
{
  "user_id": "uuid",
  "deleted_at": "ISO8601"
}
```

---

## Топик: `identity.lifecycle`

Продюсер: **Identity module**

### `lifecycle.event`
```json
{
  "user_id": "uuid",
  "event_type": "hire|transfer|promotion|termination|leave|return",
  "effective_date": "ISO8601",
  "details": { ... }
}
```

---

## Топик: `access.roles`

Продюсер: **Access module** (`modules/access/service.py`)

### `role.assigned`
```json
{
  "user_id": "uuid",
  "role_id": "uuid",
  "role_name": "it_admin",
  "granted_by": "admin-uuid",
  "reason": "Новая должность",
  "expires_at": null
}
```

### `role.revoked`
```json
{
  "user_id": "uuid",
  "role_id": "uuid",
  "role_name": "it_admin",
  "revoked_by": "admin-uuid"
}
```

### `roles.revoked_all`
```json
{
  "user_id": "uuid",
  "reason": "user_blocked",
  "revoked_count": 3
}
```

---

## Топик: `access.requests`

Продюсер: **Access module**

### `request.created`
```json
{
  "request_id": "uuid",
  "user_id": "uuid",
  "resource_id": "uuid",
  "action": "read",
  "justification": "Требуется для выполнения задачи"
}
```

### `request.approved`
```json
{
  "request_id": "uuid",
  "decided_by": "admin-uuid",
  "decision_comment": "Одобрено"
}
```

### `request.rejected`
```json
{
  "request_id": "uuid",
  "decided_by": "admin-uuid",
  "decision_comment": "Не обосновано"
}
```

---

## Топик: `monitor.alerts`

Продюсер: **Monitor module** (`modules/monitor/alert_service.py`)

### `alert.fired`
```json
{
  "alert_id": "uuid",
  "rule_name": "multiple_failed_logins",
  "severity": "high",
  "subject_user_id": "uuid",
  "details": {
    "failed_count": 7,
    "window_minutes": 10
  },
  "correlation_id": "uuid"
}
```

### `alert.acknowledged`
```json
{
  "alert_id": "uuid",
  "acknowledged_by": "admin-uuid",
  "note": "Ложное срабатывание"
}
```

---

## Топик: `audit.events`

Продюсер: **Outbox publisher** (`modules/monitor/tasks.py` → `publish_outbox`)

Этот топик содержит все записи `audit_log`, экспортированные через transactional outbox.
Потребитель: Logstash → Elasticsearch → Kibana.

```json
{
  "audit_id": 12345,
  "timestamp": "ISO8601",
  "operation": "login",
  "module": "auth",
  "target_type": "admin_user",
  "target_id": "uuid",
  "result": "success",
  "actor_id": "uuid",
  "actor_username": "admin",
  "ip_address": "192.168.1.100",
  "user_agent": "Mozilla/5.0...",
  "details": { ... },
  "correlation_id": "uuid"
}
```

Операции (`operation` field):

| Операция             | Модуль   | Описание                          |
|----------------------|----------|-----------------------------------|
| `login`              | auth     | Вход в систему                    |
| `logout`             | auth     | Выход из системы                  |
| `login_failed`       | auth     | Неудачная попытка входа           |
| `user_create`        | identity | Создание учётной записи           |
| `user_update`        | identity | Изменение данных пользователя     |
| `user_delete`        | identity | Удаление учётной записи           |
| `user_blocked`       | identity | Блокировка пользователя           |
| `user_unblocked`     | identity | Разблокировка пользователя        |
| `password_reset`     | identity | Сброс пароля                      |
| `role_assigned`      | access   | Назначение роли                   |
| `role_revoked`       | access   | Отзыв роли                        |
| `permission_grant`   | access   | Выдача разрешения                 |
| `permission_revoke`  | access   | Отзыв разрешения                  |
| `access_check`       | access   | Проверка доступа                  |
| `request_created`    | access   | Создание заявки на доступ         |
| `request_approved`   | access   | Одобрение заявки                  |
| `request_rejected`   | access   | Отклонение заявки                 |
| `resource_create`    | access   | Создание ресурса                  |
| `resource_delete`    | access   | Удаление ресурса                  |
| `report_generated`   | reports  | Генерация отчёта                  |
| `config_change`      | system   | Изменение конфигурации            |
| `alert_fired`        | monitor  | Сработало правило выявления       |
| `rule_test`          | monitor  | Тестирование правила              |

---

## Топик: `reports.notifications`

Продюсер: **Reports module** (`modules/reports/tasks.py`)

### `report.ready`
```json
{
  "report_id": "uuid",
  "template_code": "users_report",
  "format": "xlsx",
  "file_path": "/tmp/reports/uuid.xlsx",
  "generated_at": "ISO8601",
  "requested_by": "admin-uuid"
}
```

### `report.failed`
```json
{
  "report_id": "uuid",
  "template_code": "users_report",
  "error": "ElasticsearchException: ...",
  "failed_at": "ISO8601"
}
```
