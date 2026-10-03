"""Общие фикстуры: in-memory SQLite, тестовый клиент, авторизованный юзер."""
import asyncio
import uuid
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.database import Base, get_db
from src.main import app
from src.models import User


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Создаёт SQLite in-memory и таблицы для каждого теста."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as session:
        yield session

    await engine.dispose()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """HTTPX-клиент с подменённой зависимостью get_db."""

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def auth_client(client: AsyncClient, db_session: AsyncSession) -> AsyncClient:
    """Клиент с зарегистрированным и залогиненным пользователем."""
    email = f"test-{uuid.uuid4().hex[:8]}@example.com"
    password = "supersecret123"

    reg = await client.post(
        "/api/v1/auth/register", json={"email": email, "password": password}
    )
    token = reg.json()["access_token"]
    client.headers["Authorization"] = f"Bearer {token}"
    return client