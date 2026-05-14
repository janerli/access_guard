from typing import AsyncGenerator
from uuid import uuid4

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base, get_db
from app.main import app  # noqa: F401 — side-effect: registers all routers + models

TEST_DATABASE_URL = "postgresql+asyncpg://accessguard:secret@localhost:5432/accessguard_test"


def _engine():
    return create_async_engine(TEST_DATABASE_URL, echo=False)


# ── Schema (runs once per session, disposes engine immediately) ───────────────

@pytest_asyncio.fixture(scope="session", autouse=True)
async def _create_schema():
    engine = _engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()
    yield
    engine = _engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


# ── Seed data (session-scoped, each uses its own engine that it disposes) ─────

@pytest_asyncio.fixture(scope="session")
async def seed_admin(_create_schema):
    from app.core.security import hash_password
    from app.models.admin import AdminRole, AdminUser

    engine = _engine()
    async with async_sessionmaker(engine, expire_on_commit=False)() as session:
        exists = (await session.execute(
            select(AdminUser).where(AdminUser.username == "_pytest_admin")
        )).scalar_one_or_none()
        if not exists:
            session.add(AdminUser(
                id=uuid4(),
                username="_pytest_admin",
                email="_pytest@test.local",
                full_name="Pytest Admin",
                hashed_password=hash_password("TestPass123!"),
                role=AdminRole.system_admin,
            ))
            await session.commit()
    await engine.dispose()
    return {"username": "_pytest_admin", "password": "TestPass123!"}


@pytest_asyncio.fixture(scope="session")
async def seed_user_ext(_create_schema) -> str:
    from app.models.identity import UserExt, UserStatus

    engine = _engine()
    user_id: str
    async with async_sessionmaker(engine, expire_on_commit=False)() as session:
        existing = (await session.execute(
            select(UserExt).where(UserExt.employee_id == "_pytest_user")
        )).scalar_one_or_none()
        if existing:
            user_id = str(existing.id)
        else:
            user = UserExt(
                id=uuid4(),
                employee_id="_pytest_user",
                username="_pytest_userext",
                email="_pytest_user@test.local",
                full_name="Pytest User",
                status=UserStatus.active,
            )
            session.add(user)
            await session.commit()
            user_id = str(user.id)
    await engine.dispose()
    return user_id


# ── Per-test fixtures (each test gets its own engine + connections) ────────────

@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    engine = _engine()
    async with async_sessionmaker(engine, expire_on_commit=False)() as session:
        yield session
        await session.rollback()
    await engine.dispose()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    def _override():
        async def _get():
            yield db_session
        return _get

    app.dependency_overrides[get_db] = _override()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def admin_token(client: AsyncClient, seed_admin) -> str:
    resp = await client.post("/api/auth/login", json=seed_admin)
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    return resp.json()["access_token"]
