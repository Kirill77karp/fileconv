"""Celery-воркер для асинхронной конвертации."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from celery import Celery
from sqlalchemy import select

from src.config import get_settings
from src.converters import UnsupportedFormatError, convert
from src.database import AsyncSessionLocal
from src.models import Task, TaskStatus
from src.storage import make_result_path

settings = get_settings()

celery_app = Celery(
    "fileconv",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    task_track_started=True,
)


@celery_app.task(name="fileconv.convert_task", bind=True, max_retries=2)
def convert_task(self, task_id: str) -> dict:
    """Асинхронно конвертирует файл по task_id.

    Обновляет статус в БД: pending -> processing -> done/failed.
    """
    import asyncio

    return asyncio.run(_run(task_id))


async def _run(task_id: str) -> dict:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Task).where(Task.id == uuid.UUID(task_id)))
        task = result.scalar_one_or_none()
        if task is None:
            return {"ok": False, "error": "task not found"}

        task.status = TaskStatus.PROCESSING
        await db.commit()

        try:
            source_ext = task.source_format
            target_ext = task.target_format
            dst = make_result_path(task.id, target_ext)

            convert(task.source_path, dst, source_ext, target_ext)

            task.result_path = dst
            task.status = TaskStatus.DONE
            task.finished_at = datetime.now(timezone.utc)
            await db.commit()
            return {"ok": True, "task_id": task_id}

        except UnsupportedFormatError as exc:
            task.status = TaskStatus.FAILED
            task.error_message = str(exc)
            task.finished_at = datetime.now(timezone.utc)
            await db.commit()
            return {"ok": False, "error": str(exc)}

        except Exception as exc:  # noqa: BLE001
            task.status = TaskStatus.FAILED
            task.error_message = f"unexpected: {exc}"
            task.finished_at = datetime.now(timezone.utc)
            await db.commit()
            raise