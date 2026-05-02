#!/usr/bin/env bash
# seed.sh — Наполнение системы демо-данными
set -e

BASE_URL="http://localhost:8000"
ADMIN_USER="admin"
ADMIN_PASS="Admin123456789"

echo "=== AccessGuard: наполнение демо-данными ==="

# ── 1. Ждём готовности backend ────────────────────────────────────────────────
echo "→ Ожидание backend..."
until curl -sf "$BASE_URL/health" > /dev/null; do
  echo "  backend недоступен, ждём 3 сек..."
  sleep 3
done
echo "  backend готов."

# ── 2. Создаём администраторов через Python-скрипт в контейнере ──────────────
echo "→ Создание администраторов..."
docker compose exec -T backend python - <<'PYEOF'
import asyncio, uuid
from app.database import AsyncSessionLocal
from app.models.admin import AdminUser, AdminRole
from app.core.security import hash_password
from sqlalchemy import select

ADMINS = [
    ("admin",           "admin@accessguard.local",    "Главный администратор",       AdminRole.system_admin,     "Admin123456789"),
    ("security_admin",  "security@accessguard.local", "Офицер безопасности",         AdminRole.security_officer, "Security123456"),
    ("hr_admin",        "hr@accessguard.local",        "HR-администратор",            AdminRole.hr_operator,      "HrAdmin123456"),
    ("auditor",         "auditor@accessguard.local",   "Аудитор",                     AdminRole.auditor,          "Auditor123456"),
]

async def seed():
    async with AsyncSessionLocal() as db:
        for username, email, full_name, role, password in ADMINS:
            result = await db.execute(select(AdminUser).where(AdminUser.username == username))
            if result.scalar_one_or_none():
                print(f"  {username} уже существует, пропускаем")
                continue
            user = AdminUser(
                id=uuid.uuid4(),
                username=username,
                email=email,
                full_name=full_name,
                role=role,
                hashed_password=hash_password(password),
            )
            db.add(user)
        await db.commit()
        print("  Администраторы созданы.")

asyncio.run(seed())
PYEOF

# ── 3. Запускаем elastic-init.sh ─────────────────────────────────────────────
echo "→ Инициализация Elasticsearch..."
if curl -sf "http://localhost:9200/_cluster/health" > /dev/null 2>&1; then
  bash "$(dirname "$0")/elastic-init.sh"
else
  echo "  Elasticsearch недоступен, пропускаем"
fi

# ── 4. Seed HR-mock сотрудников ───────────────────────────────────────────────
echo "→ Создание 20 тестовых сотрудников через HR-mock..."
if curl -sf "http://localhost:8001/health" > /dev/null 2>&1; then
  curl -sf -X POST "http://localhost:8001/events/seed?count=20" | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'  Создано: {d[\"created\"]} сотрудников')"
else
  echo "  HR-mock недоступен, пропускаем"
fi

# ── 5. Импорт Kibana дашбордов ────────────────────────────────────────────────
echo "→ Импорт дашбордов Kibana..."
if curl -sf "http://localhost:5601/api/status" > /dev/null 2>&1; then
  bash "$(dirname "$0")/kibana-import.sh"
else
  echo "  Kibana недоступна, пропускаем"
fi

echo ""
echo "=== Готово! ==="
echo ""
echo "  Frontend:    http://localhost:5173"
echo "  API Swagger: http://localhost:8000/docs"
echo "  Kibana:      http://localhost:5601"
echo "  MailHog:     http://localhost:8025"
echo ""
echo "  Учётные данные администраторов:"
echo "  ┌─────────────────┬───────────────────┐"
echo "  │ admin           │ Admin123456789    │"
echo "  │ security_admin  │ Security123456    │"
echo "  │ hr_admin        │ HrAdmin123456     │"
echo "  │ auditor         │ Auditor123456     │"
echo "  └─────────────────┴───────────────────┘"
