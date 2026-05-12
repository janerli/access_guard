import asyncio
from typing import AsyncGenerator
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Import app (triggers model registration into Base.metadata)
from app.database import Base, get_db
from app.main import app  # noqa: F401 — side-effect: registers all routers + models

TEST_DATABASE_URL = "postgresql+asyncpg://accessguard:secret@localhost:5432/accessguard_test"


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(scope="session")
async def seed_admin(test_engine):
    """Создаёт системного администратора один раз на весь тестовый прогон."""
    from app.core.security import hash_password
    from app.models.admin import AdminRole, AdminUser

    session_factory = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_factory() as session:
        existing = (await session.execute(
            select(AdminUser).where(AdminUser.username == "_pytest_admin")
        )).scalar_one_or_none()
        if not existing:
            admin = AdminUser(
                id=uuid4(),
                username="_pytest_admin",
                email="_pytest@test.local",
                full_name="Pytest Admin",
                hashed_password=hash_password("TestPass123!"),
                role=AdminRole.system_admin,
            )
            session.add(admin)
            await session.commit()
    return {"username": "_pytest_admin", "password": "TestPass123!"}


@pytest_asyncio.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(test_engine) -> AsyncGenerator[AsyncClient, None]:
    # HTTP requests should use independent DB sessions to avoid sharing one
    # AsyncSession/connection across concurrent FastAPI dependencies.
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False)

    async def _get_test_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = _get_test_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def admin_token(client: AsyncClient, seed_admin) -> str:
    resp = await client.post("/api/auth/login", json=seed_admin)
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    return resp.json()["access_token"]


@pytest_asyncio.fixture(scope="session")
async def seed_user_ext(test_engine) -> str:
    """Создаёт одного UserExt один раз на весь тестовый прогон. Возвращает user_id."""
    from uuid import uuid4
    from app.models.identity import UserExt, UserStatus

    session_factory = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_factory() as session:
        existing = (await session.execute(
            select(UserExt).where(UserExt.employee_id == "_pytest_user")
        )).scalar_one_or_none()
        if existing:
            return str(existing.id)
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
        return str(user.id)
