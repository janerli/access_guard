#!/usr/bin/env python3
"""
seed_data.py — реалистичное наполнение AccessGuard демо-данными.
Запускается внутри контейнера backend:
  docker compose exec -T backend python scripts/seed_data.py
"""
import asyncio
import json
import random
import sys
import uuid
from datetime import datetime, timedelta, timezone

# ---------------------------------------------------------------------------
# Данные для генерации
# ---------------------------------------------------------------------------

DEPARTMENTS = [
    # (code, name, parent_code)
    ("IT",     "Департамент информационных технологий", None),
    ("IT-DEV", "Отдел разработки",                     "IT"),
    ("IT-OPS", "Отдел эксплуатации",                   "IT"),
    ("HR",     "Отдел кадров",                          None),
    ("FIN",    "Финансовый отдел",                      None),
]

POSITIONS = [
    # (code, name, level)
    ("CTO",       "Технический директор",      5),
    ("DEV-LEAD",  "Ведущий разработчик",       4),
    ("DEV-SEN",   "Старший разработчик",       3),
    ("DEV-MID",   "Разработчик",               2),
    ("DEV-JUN",   "Младший разработчик",       1),
    ("OPS-LEAD",  "Ведущий администратор",     4),
    ("OPS-SEN",   "Старший системный администратор", 3),
    ("OPS-MID",   "Системный администратор",   2),
    ("HR-HEAD",   "Начальник отдела кадров",   4),
    ("HR-SEN",    "Старший HR-специалист",     3),
    ("HR-MID",    "HR-специалист",             2),
    ("FIN-HEAD",  "Главный бухгалтер",         4),
    ("FIN-SEN",   "Старший бухгалтер",         3),
    ("FIN-MID",   "Бухгалтер",                 2),
    ("SEC-HEAD",  "Начальник службы безопасности", 4),
    ("ANALYST",   "Аналитик",                  2),
    ("QA-SEN",    "Ведущий тестировщик",       3),
    ("QA-MID",    "Тестировщик",               2),
    ("PM",        "Менеджер проектов",         3),
    ("INTERN",    "Стажёр",                    1),
]

FIRST_NAMES = [
    "Александр", "Дмитрий", "Максим", "Сергей", "Андрей",
    "Алексей", "Артём", "Илья", "Кирилл", "Михаил",
    "Анна", "Мария", "Елена", "Ольга", "Екатерина",
    "Наталья", "Ирина", "Юлия", "Татьяна", "Светлана",
    "Владимир", "Никита", "Иван", "Павел", "Роман",
]

LAST_NAMES = [
    "Иванов", "Смирнов", "Кузнецов", "Попов", "Соколов",
    "Лебедев", "Козлов", "Новиков", "Морозов", "Петров",
    "Волков", "Соловьёв", "Васильев", "Зайцев", "Павлов",
    "Семёнов", "Голубев", "Виноградов", "Богданов", "Воробьёв",
    "Фёдоров", "Михайлов", "Беляев", "Тарасов", "Белов",
]

PATRONYMICS = [
    "Александрович", "Дмитриевич", "Сергеевич", "Владимирович", "Андреевич",
    "Александровна", "Дмитриевна", "Сергеевна", "Владимировна", "Андреевна",
]

IPS = [
    "192.168.1.10", "192.168.1.11", "192.168.1.15", "192.168.1.20",
    "10.0.0.5", "10.0.0.10", "10.0.0.15", "10.0.0.100",
    "172.16.0.5", "172.16.0.10",
]

OPERATIONS = [
    ("login_success", "auth", "system", "success"),
    ("login_failure", "auth", "system", "failure"),
    ("create", "identity", "user", "success"),
    ("update", "identity", "user", "success"),
    ("block", "identity", "user", "success"),
    ("role_assign", "access", "role", "success"),
    ("role_revoke", "access", "role", "success"),
    ("permission_check", "access", "resource", "success"),
    ("permission_check", "access", "resource", "denied"),
    ("read", "identity", "user", "success"),
    ("password_reset", "identity", "user", "success"),
    ("request_submit", "access", "role", "success"),
    ("request_approve", "access", "role", "success"),
]


async def run():
    from sqlalchemy import select, func
    from app.database import AsyncSessionLocal
    from app.models.admin import AdminUser, AdminRole
    from app.models.identity import Department, Position, UserExt, UserStatus
    from app.models.access import Role, UserRole
    from app.models.monitor import (
        AuditLog, AuditModule, AuditOperation, AuditResult, AuditTargetType,
        Alert, AlertRule, AlertStatus, OutboxEvent, OutboxStatus,
    )
    from app.core.security import hash_password
    from app.kafka.topics import TOPIC_AUDIT_EVENTS

    async with AsyncSessionLocal() as db:

        # ── 1. Администраторы ─────────────────────────────────────────────────
        print("→ Создание администраторов...")
        admins_data = [
            ("admin",          "admin@accessguard.local",    "Главный администратор",    AdminRole.system_admin,     "Admin123456789"),
            ("security_admin", "security@accessguard.local", "Офицер безопасности",      AdminRole.security_officer, "Security123456"),
            ("hr_admin",       "hr@accessguard.local",        "HR-администратор",         AdminRole.hr_operator,      "HrAdmin123456"),
            ("auditor_user",   "auditor@accessguard.local",   "Аудитор",                  AdminRole.auditor,          "Auditor123456"),
        ]
        admin_objs: list[AdminUser] = []
        for username, email, full_name, role, password in admins_data:
            existing = (await db.execute(select(AdminUser).where(AdminUser.username == username))).scalar_one_or_none()
            if existing:
                admin_objs.append(existing)
                continue
            a = AdminUser(id=uuid.uuid4(), username=username, email=email, full_name=full_name,
                          role=role, hashed_password=hash_password(password))
            db.add(a)
            admin_objs.append(a)
        await db.commit()
        print(f"  {len(admin_objs)} администраторов.")

        # ── 2. Отделы ─────────────────────────────────────────────────────────
        print("→ Создание отделов...")
        dept_map: dict[str, Department] = {}
        for code, name, parent_code in DEPARTMENTS:
            existing = (await db.execute(select(Department).where(Department.code == code))).scalar_one_or_none()
            if existing:
                dept_map[code] = existing
                continue
            parent_id = dept_map[parent_code].id if parent_code else None
            d = Department(id=uuid.uuid4(), code=code, name=name, parent_id=parent_id)
            db.add(d)
            dept_map[code] = d
        await db.commit()
        print(f"  {len(dept_map)} отделов.")

        # ── 3. Должности ──────────────────────────────────────────────────────
        print("→ Создание должностей...")
        pos_map: dict[str, Position] = {}
        for code, name, level in POSITIONS:
            existing = (await db.execute(select(Position).where(Position.code == code))).scalar_one_or_none()
            if existing:
                pos_map[code] = existing
                continue
            p = Position(id=uuid.uuid4(), code=code, name=name, level=level)
            db.add(p)
            pos_map[code] = p
        await db.commit()
        print(f"  {len(pos_map)} должностей.")

        # ── 4. Пользователи ───────────────────────────────────────────────────
        print("→ Создание 50 сотрудников...")
        existing_count = (await db.execute(select(func.count(UserExt.id)))).scalar_one()
        dept_codes = list(dept_map.keys())
        pos_codes = list(pos_map.keys())
        users_created = []
        needed = 50

        if existing_count < needed:
            for i in range(existing_count, needed):
                fn = random.choice(FIRST_NAMES)
                ln = random.choice(LAST_NAMES)
                pat = random.choice(PATRONYMICS)
                emp_id = f"E-{1000 + i:04d}"
                username = f"{ln.lower()[:6]}{i:03d}"
                email = f"{username}@accessguard.local"
                dept_code = random.choice(dept_codes)
                pos_code = random.choice(pos_codes)
                status = random.choices(
                    [UserStatus.active, UserStatus.suspended, UserStatus.blocked],
                    weights=[85, 10, 5],
                )[0]
                u = UserExt(
                    id=uuid.uuid4(),
                    employee_id=emp_id,
                    username=username,
                    email=email,
                    full_name=f"{ln} {fn} {pat}",
                    status=status,
                    department_id=dept_map[dept_code].id,
                    position_id=pos_map[pos_code].id,
                )
                db.add(u)
                users_created.append(u)
            await db.commit()
        users_all = (await db.execute(select(UserExt).limit(50))).scalars().all()
        print(f"  {len(users_all)} пользователей.")

        # ── 5. Назначить базовые роли ─────────────────────────────────────────
        print("→ Назначение ролей пользователям...")
        employee_role = (await db.execute(select(Role).where(Role.code == "employee"))).scalar_one_or_none()
        manager_role = (await db.execute(select(Role).where(Role.code == "manager"))).scalar_one_or_none()
        roles_assigned = 0
        if employee_role:
            for u in users_all:
                existing_role = (await db.execute(
                    select(UserRole).where(UserRole.user_id == u.id, UserRole.role_id == employee_role.id)
                )).scalar_one_or_none()
                if not existing_role:
                    ur = UserRole(id=uuid.uuid4(), user_id=u.id, role_id=employee_role.id,
                                  granted_by=admin_objs[0].id)
                    db.add(ur)
                    roles_assigned += 1
        if manager_role:
            for u in random.sample(list(users_all), min(5, len(users_all))):
                existing_role = (await db.execute(
                    select(UserRole).where(UserRole.user_id == u.id, UserRole.role_id == manager_role.id)
                )).scalar_one_or_none()
                if not existing_role:
                    ur = UserRole(id=uuid.uuid4(), user_id=u.id, role_id=manager_role.id,
                                  granted_by=admin_objs[0].id)
                    db.add(ur)
                    roles_assigned += 1
        await db.commit()
        print(f"  {roles_assigned} назначений ролей.")

        # ── 6. ~5000 записей audit_log за 90 дней ────────────────────────────
        print("→ Генерация ~5000 записей audit_log...")
        existing_audit = (await db.execute(select(func.count(AuditLog.id)))).scalar_one()

        if existing_audit < 1000:
            now = datetime.now(timezone.utc)
            usernames = [u.username for u in users_all] + [a.username for a in admin_objs]
            user_ids = {u.username: u.id for u in users_all}

            batch: list[AuditLog] = []
            outbox_batch: list[OutboxEvent] = []

            for i in range(5000):
                days_ago = random.uniform(0, 90)
                ts = now - timedelta(days=days_ago)
                op_tuple = random.choices(
                    OPERATIONS,
                    weights=[20, 5, 8, 8, 2, 5, 3, 15, 5, 12, 2, 3, 2],
                )[0]
                op, module, target_type, result = op_tuple
                username = random.choice(usernames)
                actor_id = user_ids.get(username)
                ip = random.choice(IPS)
                corr_id = uuid.uuid4()
                entry_id = uuid.uuid4()

                details = {}
                if op == "role_assign":
                    details = {"role_code": "employee", "is_privileged": random.random() < 0.05}
                elif op == "password_reset":
                    details = {"target_is_privileged": random.random() < 0.1}
                elif op == "permission_check" and result == "denied":
                    details = {"permission": "documents:write", "reason": "insufficient_role"}

                entry = AuditLog(
                    event_id=entry_id,
                    timestamp=ts,
                    actor_id=actor_id,
                    actor_username=username,
                    target_type=AuditTargetType(target_type),
                    target_id=str(uuid.uuid4())[:8],
                    operation=AuditOperation(op),
                    module=AuditModule(module),
                    result=AuditResult(result),
                    ip_address=ip,
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AccessGuard/1.0",
                    details=details or None,
                    correlation_id=corr_id,
                    published_to_kafka=False,
                )
                batch.append(entry)

                if len(batch) >= 500:
                    db.add_all(batch)
                    await db.flush()
                    for e in batch:
                        payload = {
                            "event_id": str(e.event_id),
                            "audit_log_id": e.id,
                            "timestamp": e.timestamp.isoformat(),
                            "actor_id": str(e.actor_id) if e.actor_id else None,
                            "actor_username": e.actor_username,
                            "target_type": e.target_type.value,
                            "target_id": e.target_id,
                            "operation": e.operation.value,
                            "module": e.module.value,
                            "result": e.result.value,
                            "ip_address": e.ip_address,
                            "details": e.details or {},
                            "correlation_id": str(e.correlation_id) if e.correlation_id else None,
                        }
                        outbox_batch.append(OutboxEvent(
                            audit_log_id=e.id,
                            topic=TOPIC_AUDIT_EVENTS,
                            payload=payload,
                            status=OutboxStatus.pending,
                        ))
                    db.add_all(outbox_batch)
                    await db.commit()
                    print(f"  ... {i + 1}/5000")
                    batch.clear()
                    outbox_batch.clear()

            if batch:
                db.add_all(batch)
                await db.flush()
                for e in batch:
                    payload = {
                        "event_id": str(e.event_id), "audit_log_id": e.id,
                        "timestamp": e.timestamp.isoformat(),
                        "actor_id": str(e.actor_id) if e.actor_id else None,
                        "actor_username": e.actor_username,
                        "target_type": e.target_type.value, "target_id": e.target_id,
                        "operation": e.operation.value, "module": e.module.value,
                        "result": e.result.value, "ip_address": e.ip_address,
                        "details": e.details or {},
                        "correlation_id": str(e.correlation_id) if e.correlation_id else None,
                    }
                    db.add(OutboxEvent(audit_log_id=e.id, topic=TOPIC_AUDIT_EVENTS, payload=payload, status=OutboxStatus.pending))
                await db.commit()
            print("  5000 записей создано.")
        else:
            print(f"  audit_log уже содержит {existing_audit} записей, пропускаем.")

        # ── 7. Создать тестовые алерты ────────────────────────────────────────
        print("→ Создание тестовых алертов...")
        existing_alerts = (await db.execute(select(func.count(Alert.id)))).scalar_one()
        if existing_alerts < 5:
            rules = (await db.execute(select(AlertRule).limit(4))).scalars().all()
            now = datetime.now(timezone.utc)
            for i, rule in enumerate(rules):
                severity = rule.severity
                status = random.choice([AlertStatus.new, AlertStatus.new, AlertStatus.acknowledged, AlertStatus.resolved])
                subject = random.choice(users_all).id if users_all else None
                alert = Alert(
                    id=uuid.uuid4(),
                    rule_id=rule.id,
                    triggered_at=now - timedelta(hours=random.randint(1, 72)),
                    subject_user_id=subject,
                    severity=severity,
                    status=status,
                    details={"generated_by": "seed", "count": random.randint(1, 20)},
                )
                db.add(alert)
            await db.commit()
            print("  4 тестовых алерта создано.")

        # ── 8. Создать тестовые отчёты (в статусе ready, с файлами) ──────────
        print("→ Создание тестовых отчётов...")
        import os
        from app.models.reports import Report, ReportTemplate, ReportFormat, ReportStatus

        existing_reports = (await db.execute(select(func.count(Report.id)))).scalar_one()
        if existing_reports < 3:
            reports_dir = os.environ.get("REPORTS_DIR", "/tmp/reports")
            os.makedirs(reports_dir, exist_ok=True)
            templates_to_seed = ["users_report", "access_requests_report", "roles_matrix"]
            for tmpl_code in templates_to_seed:
                tmpl = (await db.execute(
                    select(ReportTemplate).where(ReportTemplate.code == tmpl_code)
                )).scalar_one_or_none()
                if not tmpl:
                    continue
                from app.modules.reports.generators.renderers import CsvRenderer
                dummy_data = {
                    "title": tmpl.name,
                    "headers": ["Данные"],
                    "rows": [["Демо-данные для отчёта"], ["Сгенерировано seed_data.py"]],
                    "count": 2,
                }
                content = CsvRenderer().render(dummy_data)
                report_id = uuid.uuid4()
                file_path = os.path.join(reports_dir, f"{report_id}.csv")
                with open(file_path, "wb") as f:
                    f.write(content)
                r = Report(
                    id=report_id, template_id=tmpl.id,
                    parameters={}, format=ReportFormat.csv,
                    status=ReportStatus.ready,
                    created_at=datetime.now(timezone.utc) - timedelta(hours=random.randint(1, 48)),
                    completed_at=datetime.now(timezone.utc) - timedelta(minutes=random.randint(1, 60)),
                    file_path=file_path, file_size=len(content),
                )
                db.add(r)
            await db.commit()
            print("  3 тестовых отчёта создано.")

    print("\n✓ Наполнение данными завершено.")
    print("  Пользователей: 50 | Отделов: 5 | Должностей: 20")
    print("  Записей аудита: ~5000 | Алертов: 4 | Отчётов: 3")


if __name__ == "__main__":
    asyncio.run(run())
