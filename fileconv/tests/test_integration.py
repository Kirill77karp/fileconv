"""Integration-тесты: API + БД + очередь (мок)."""
import io

import pytest
from httpx import AsyncClient
from PIL import Image


def _png_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (10, 10), (0, 0, 255)).save(buf, format="PNG")
    return buf.getvalue()


@pytest.mark.asyncio
async def test_full_convert_flow(auth_client: AsyncClient, monkeypatch) -> None:
    """Полный цикл: загрузка -> задача -> получение статуса."""
    # Мокаем Celery, чтобы не требовался брокер.
    from src import worker

    monkeypatch.setattr(worker.convert_task, "delay", lambda task_id: None)

    r = await auth_client.post(
        "/api/v1/convert",
        files={"file": ("a.png", _png_bytes(), "image/png")},
        data={"target_format": "webp"},
    )
    assert r.status_code == 202
    task_id = r.json()["id"]

    r2 = await auth_client.get(f"/api/v1/tasks/{task_id}")
    assert r2.status_code == 200
    assert r2.json()["id"] == task_id


@pytest.mark.asyncio
async def test_reject_unsupported_source(auth_client: AsyncClient) -> None:
    r = await auth_client.post(
        "/api/v1/convert",
        files={"file": ("a.exe", b"MZ", "application/octet-stream")},
        data={"target_format": "jpg"},
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_delete_task(auth_client: AsyncClient, monkeypatch) -> None:
    from src import worker

    monkeypatch.setattr(worker.convert_task, "delay", lambda task_id: None)

    r = await auth_client.post(
        "/api/v1/convert",
        files={"file": ("b.png", _png_bytes(), "image/png")},
        data={"target_format": "jpg"},
    )
    task_id = r.json()["id"]

    r2 = await auth_client.delete(f"/api/v1/tasks/{task_id}")
    assert r2.status_code == 204

    r3 = await auth_client.get(f"/api/v1/tasks/{task_id}")
    assert r3.status_code == 404