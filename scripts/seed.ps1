# seed.ps1 — Windows-аналог seed.sh
# Запуск: .\scripts\seed.ps1  (из корня проекта)
Set-StrictMode -Off
$ErrorActionPreference = "Continue"

$BASE_URL = "http://localhost:8000"

Write-Host "=== AccessGuard: наполнение демо-данными ===" -ForegroundColor Cyan

# ── 1. Ждём готовности backend ─────────────────────────────────────────────────
Write-Host "-> Ожидание backend..."
$ready = $false
for ($i = 0; $i -lt 30; $i++) {
    try {
        $r = Invoke-WebRequest -Uri "$BASE_URL/health" -UseBasicParsing -TimeoutSec 3 -ErrorAction Stop
        if ($r.StatusCode -eq 200) { $ready = $true; break }
    } catch {}
    Write-Host "   backend недоступен, ждём 5 сек..."
    Start-Sleep 5
}
if (-not $ready) { Write-Host "Backend не ответил — проверь docker compose up" -ForegroundColor Red; exit 1 }
Write-Host "   backend готов." -ForegroundColor Green

# ── 2. Создаём администраторов ─────────────────────────────────────────────────
Write-Host "-> Создание администраторов..."
$adminPy = @'
import asyncio, uuid
from app.database import AsyncSessionLocal
from app.models.admin import AdminUser, AdminRole
from app.core.security import hash_password
from sqlalchemy import select

ADMINS = [
    ("admin",          "admin@accessguard.local",    "Главный администратор",  AdminRole.system_admin,     "Admin123456789"),
    ("security_admin", "security@accessguard.local", "Офицер безопасности",    AdminRole.security_officer, "Security123456"),
    ("hr_admin",       "hr@accessguard.local",       "HR-администратор",       AdminRole.hr_operator,      "HrAdmin123456"),
    ("auditor",        "auditor@accessguard.local",  "Аудитор",                AdminRole.auditor,          "Auditor123456"),
]

async def seed():
    async with AsyncSessionLocal() as db:
        for username, email, full_name, role, password in ADMINS:
            exists = (await db.execute(select(AdminUser).where(AdminUser.username == username))).scalar_one_or_none()
            if exists:
                print(f"  {username} уже существует, пропускаем")
                continue
            db.add(AdminUser(id=uuid.uuid4(), username=username, email=email,
                             full_name=full_name, role=role, hashed_password=hash_password(password)))
        await db.commit()
        print("  Администраторы созданы.")

asyncio.run(seed())
'@
$adminPy | docker compose exec -T backend python -
if ($LASTEXITCODE -ne 0) { Write-Host "  Ошибка создания администраторов" -ForegroundColor Yellow }

# ── 3. Инициализация Elasticsearch ────────────────────────────────────────────
Write-Host "-> Инициализация Elasticsearch..."
try {
    $es = Invoke-WebRequest -Uri "http://localhost:9200/_cluster/health" -UseBasicParsing -TimeoutSec 5 -ErrorAction Stop
    if ($es.StatusCode -eq 200) {
        $esPy = @'
import asyncio, httpx, json
INDICES = {
    "audit-logs": {
        "mappings": {"properties": {
            "timestamp":      {"type": "date"},
            "actor_id":       {"type": "keyword"},
            "actor_username": {"type": "keyword"},
            "operation":      {"type": "keyword"},
            "module":         {"type": "keyword"},
            "target_type":    {"type": "keyword"},
            "target_id":      {"type": "keyword"},
            "result":         {"type": "keyword"},
            "ip_address":     {"type": "ip",      "ignore_malformed": True},
            "details":        {"type": "object",  "dynamic": True},
            "correlation_id": {"type": "keyword"}
        }}
    },
    "monitor-alerts": {
        "mappings": {"properties": {
            "created_at":   {"type": "date"},
            "rule_code":    {"type": "keyword"},
            "severity":     {"type": "keyword"},
            "status":       {"type": "keyword"},
            "actor_id":     {"type": "keyword"},
            "details":      {"type": "object", "dynamic": True}
        }}
    }
}
async def init():
    async with httpx.AsyncClient(base_url="http://elasticsearch:9200", timeout=10) as c:
        for name, body in INDICES.items():
            r = await c.put(f"/{name}", json=body)
            if r.status_code in (200, 400):
                print(f"  Index {name}: {'ok' if r.status_code==200 else 'already exists'}")
            else:
                print(f"  Index {name}: {r.status_code} {r.text[:100]}")
asyncio.run(init())
'@
        $esPy | docker compose exec -T backend python -
    }
} catch {
    Write-Host "   Elasticsearch недоступен, пропускаем" -ForegroundColor Yellow
}

# ── 4. Seed HR-mock ────────────────────────────────────────────────────────────
Write-Host "-> Создание тестовых сотрудников через HR-mock..."
try {
    $hr = Invoke-WebRequest -Uri "http://localhost:8001/health" -UseBasicParsing -TimeoutSec 3 -ErrorAction Stop
    if ($hr.StatusCode -eq 200) {
        $hrSeed = Invoke-WebRequest -Uri "http://localhost:8001/events/seed?count=20" -Method POST -UseBasicParsing -TimeoutSec 15
        $hrData = $hrSeed.Content | ConvertFrom-Json
        Write-Host "   Создано: $($hrData.created) сотрудников" -ForegroundColor Green
    }
} catch {
    Write-Host "   HR-mock недоступен, пропускаем" -ForegroundColor Yellow
}

# ── 5. Расширенный seed (демо-данные) ─────────────────────────────────────────
Write-Host "-> Генерация демо-данных..."
docker compose exec -T -e PYTHONPATH=/app backend python /app/scripts/seed_data.py
if ($LASTEXITCODE -eq 0) {
    Write-Host "   Демо-данные созданы." -ForegroundColor Green
} else {
    Write-Host "   seed_data.py: возможно данные уже существуют" -ForegroundColor Yellow
}

# ── 6. Kibana дашборды ────────────────────────────────────────────────────────
Write-Host "-> Проверка Kibana..."
try {
    $kb = Invoke-WebRequest -Uri "http://localhost:5601/api/status" -UseBasicParsing -TimeoutSec 5 -ErrorAction Stop
    Write-Host "   Kibana доступна на http://localhost:5601" -ForegroundColor Green
} catch {
    Write-Host "   Kibana недоступна, пропускаем" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "=== Готово! ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Frontend:    http://localhost:5173"
Write-Host "  API Swagger: http://localhost:8000/docs"
Write-Host "  Kibana:      http://localhost:5601"
Write-Host "  MailHog:     http://localhost:8025"
Write-Host ""
Write-Host "  Учётные данные:"
Write-Host "  admin          / Admin123456789"
Write-Host "  security_admin / Security123456"
Write-Host "  hr_admin       / HrAdmin123456"
Write-Host "  auditor        / Auditor123456"
