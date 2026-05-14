"""HR-mock — эмулятор кадровой системы (1С:ЗУП).

Публикует события в формате KafkaEvent-конверта:
  event_type: hire | transfer | leave_start | leave_end | terminate
  payload: employee_id, effective_date, full_name, position_code, ...
"""
import json
import os
import uuid
from datetime import date, datetime, timezone
from typing import Literal, Optional

from faker import Faker
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

fake = Faker("ru_RU")

KAFKA_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")

DEPARTMENTS = [
    {"code": "IT-DEV", "name": "Отдел разработки"},
    {"code": "IT-OPS", "name": "Отдел эксплуатации"},
    {"code": "HR", "name": "Отдел кадров"},
    {"code": "FINANCE", "name": "Финансовый отдел"},
    {"code": "SECURITY", "name": "Отдел информационной безопасности"},
]

POSITIONS = [
    {"code": "DEV-JUN", "name": "Разработчик (Junior)", "level": 1},
    {"code": "DEV-MID", "name": "Разработчик (Middle)", "level": 2},
    {"code": "DEV-SEN", "name": "Разработчик (Senior)", "level": 3},
    {"code": "OPS-ENG", "name": "Инженер эксплуатации", "level": 2},
    {"code": "HR-SPEC", "name": "HR-специалист", "level": 2},
    {"code": "FIN-ANAL", "name": "Финансовый аналитик", "level": 2},
    {"code": "SEC-ANALYST", "name": "Аналитик ИБ", "level": 2},
    {"code": "MANAGER", "name": "Руководитель отдела", "level": 4},
]

_employees: dict[str, dict] = {}


def _gen_employee(employee_id: Optional[str] = None) -> dict:
    emp_id = employee_id or f"E-{fake.numerify('####')}"
    dept = fake.random_element(DEPARTMENTS)
    pos = fake.random_element(POSITIONS)
    first_name = fake.first_name()
    last_name = fake.last_name()
    username = f"{first_name[0].lower()}.{last_name.lower()}"[:20]
    return {
        "employee_id": emp_id,
        "full_name": f"{last_name} {first_name} {fake.middle_name()}",
        "position_code": pos["code"],
        "department_code": dept["code"],
        "email": f"{username}@accessguard.local",
        "phone": fake.phone_number(),
        "hire_date": fake.date_between(start_date="-5y", end_date="today").isoformat(),
        "status": "active",
    }


async def _publish_kafka(event_type: str, employee_id: str, payload: dict) -> str:
    import asyncio
    import logging
    from aiokafka import AIOKafkaProducer

    log = logging.getLogger("hr-mock")
    event_id = str(uuid.uuid4())
    message = {
        "event_id": event_id,
        "event_type": event_type,
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "producer": "hr-mock",
        "correlation_id": str(uuid.uuid4()),
        "version": "1.0",
        "payload": payload,
    }

    log.info(f"Connecting to Kafka at {KAFKA_SERVERS}...")
    producer = AIOKafkaProducer(
        bootstrap_servers=KAFKA_SERVERS,
        value_serializer=lambda v: json.dumps(v, default=str).encode("utf-8"),
        request_timeout_ms=4000,
        connections_max_idle_ms=5000,
        metadata_max_age_ms=5000,
    )
    try:
        await asyncio.wait_for(producer.start(), timeout=5)
        log.info("Kafka connected, sending message...")
        await asyncio.wait_for(
            producer.send_and_wait("hr.events", value=message, key=employee_id.encode()),
            timeout=5,
        )
        log.info(f"Message sent: {event_id}")
    finally:
        try:
            await asyncio.wait_for(producer.stop(), timeout=3)
        except Exception:
            pass

    return event_id


class HREventRequest(BaseModel):
    event_type: Literal["hire", "transfer", "leave_start", "leave_end", "terminate"]
    employee_id: str
    effective_date: str = ""
    data: dict


app = FastAPI(title="HR Mock", description="Эмулятор кадровой системы (1С:ЗУП)")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/employees")
def list_employees():
    return list(_employees.values())


@app.get("/employees/{employee_id}")
def get_employee(employee_id: str):
    emp = _employees.get(employee_id)
    if not emp:
        raise HTTPException(status_code=404, detail="Сотрудник не найден")
    return emp


@app.post("/events/publish")
async def publish_event(event: HREventRequest):
    """Публикует одно кадровое событие в Kafka топик hr.events (KafkaEvent формат)."""
    try:
        payload = {
            "employee_id": event.employee_id,
            "effective_date": event.effective_date or date.today().isoformat(),
            **event.data,
        }
        event_id = await _publish_kafka(event.event_type, event.employee_id, payload)

        if event.event_type == "hire":
            emp = {"employee_id": event.employee_id, **event.data, "status": "active"}
            _employees[event.employee_id] = emp
        elif event.event_type == "terminate":
            if event.employee_id in _employees:
                _employees[event.employee_id]["status"] = "terminated"

        return {"published": True, "event_id": event_id}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/events/seed")
async def seed_employees(count: int = 10, kafka: bool = True):
    """Создаёт N новых сотрудников. kafka=false — пропустить публикацию в Kafka."""
    import logging
    log = logging.getLogger("hr-mock")
    results = []
    kafka_errors = 0
    for _ in range(count):
        emp = _gen_employee()
        _employees[emp["employee_id"]] = emp
        if kafka:
            try:
                log.info(f"Publishing hire event for {emp['employee_id']}...")
                event_id = await _publish_kafka("hire", emp["employee_id"], {
                    **emp, "effective_date": emp["hire_date"],
                })
                results.append({"employee_id": emp["employee_id"], "published": True, "event_id": event_id})
                log.info(f"Published {emp['employee_id']}")
            except Exception as exc:
                log.warning(f"Kafka publish failed for {emp['employee_id']}: {exc}")
                kafka_errors += 1
                results.append({"employee_id": emp["employee_id"], "published": False, "error": str(exc)})
        else:
            results.append({"employee_id": emp["employee_id"], "published": False, "skipped": True})
    return {"created": len(results), "kafka_errors": kafka_errors, "employees": results}


@app.get("/structure/departments")
def get_departments():
    return DEPARTMENTS


@app.get("/structure/positions")
def get_positions():
    return POSITIONS
