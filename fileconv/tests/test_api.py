"""Тесты REST API."""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health(client: AsyncClient) -> None:
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_register_and_login(client: AsyncClient) -> None:
    email = "user1@example.com"
    r = await client.post(
        "/api/v1/auth/register", json={"email": email, "password": "password123"}
    )
    assert r.status_code == 200
    token = r.json()["access_token"]
    assert token

    r2 = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": "password123"}
    )
    assert r2.status_code == 200
    assert r2.json()["access_token"]


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient) -> None:
    await client.post(
        "/api/v1/auth/register",
        json={"email": "u2@example.com", "password": "password123"},
    )
    r = await client.post(
        "/api/v1/auth/login", json={"email": "u2@example.com", "password": "wrong"}
    )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_formats(client: AsyncClient) -> None:
    r = await client.get("/api/v1/formats")
    assert r.status_code == 200
    data = r.json()
    assert "png" in data["source"]
    assert "pdf" in data["target"]


@pytest.mark.asyncio
async def test_convert_requires_auth(client: AsyncClient) -> None:
    r = await client.post(
        "/api/v1/convert",
        files={"file": ("a.png", b"fake", "image/png")},
        data={"target_format": "jpg"},
    )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_create_task(auth_client: AsyncClient) -> None:
    from PIL import Image
    import io

    buf = io.BytesIO()
    Image.new("RGB", (10, 10), (0, 255, 0)).save(buf, format="PNG")
    buf.seek(0)

    r = await auth_client.post(
        "/api/v1/convert",
        files={"file": ("test.png", buf.getvalue(), "image/png")},
        data={"target_format": "jpg"},
    )
    assert r.status_code == 202
    body = r.json()
    assert body["source_format"] == "png"
    assert body["target_format"] == "jpg"
    assert body["status"] in ("pending", "processing")


@pytest.mark.asyncio
async def test_list_tasks(auth_client: AsyncClient) -> None:
    r = await auth_client.get("/api/v1/tasks")
    assert r.status_code == 200
    assert "items" in r.json()
    assert "total" in r.json()


@pytest.mark.asyncio
async def test_get_task_404(auth_client: AsyncClient) -> None:
    import uuid

    r = await auth_client.get(f"/api/v1/tasks/{uuid.uuid4()}")
    assert r.status_code == 404