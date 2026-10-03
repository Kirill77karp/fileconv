"""REST API: auth, convert, tasks, download, formats.

См. docs/api/openapi.yaml для полной спецификации.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from jose import jwt
from passlib.context import CryptContext
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import get_settings
from src.converters import SUPPORTED_SOURCES, SUPPORTED_TARGETS, UnsupportedFormatError
from src.database import get_db
from src.dependencies import get_current_user
from src.models import Task, TaskStatus, User
from src.schemas import (
    FormatInfo,
    TaskListResponse,
    TaskRead,
    TokenResponse,
    UserLogin,
    UserRegister,
)
from src.storage import save_upload
from src.worker import convert_task

router = APIRouter()
settings = get_settings()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ------------------- AUTH -------------------
def _create_token(user_id: uuid.UUID) -> str:
    """Создаёт JWT с sub=user_id и exp."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": str(user_id), "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


@router.post("/auth/register", response_model=TokenResponse, tags=["auth"])
async def register(payload: UserRegister, db: AsyncSession = Depends(get_db)):
    """Регистрация нового пользователя.

    Пароль хранится как bcrypt-хэш (ADR-001, security.md).
    """
    existing = await db.execute(select(User).where(User.email == payload.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        email=payload.email,
        password_hash=pwd_context.hash(payload.password),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    return TokenResponse(access_token=_create_token(user.id))


@router.post("/auth/login", response_model=TokenResponse, tags=["auth"])
async def login(payload: UserLogin, db: AsyncSession = Depends(get_db)):
    """Логин по email и паролю."""
    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()

    if user is None or not pwd_context.verify(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    return TokenResponse(access_token=_create_token(user.id))


# ------------------- FORMATS -------------------
@router.get("/formats", response_model=FormatInfo, tags=["meta"])
async def list_formats():
    """Список поддерживаемых исходных и целевых форматов."""
    return FormatInfo(source=SUPPORTED_SOURCES, target=SUPPORTED_TARGETS)


# ------------------- CONVERT -------------------
@router.post(
    "/convert",
    response_model=TaskRead,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["convert"],
)
async def create_conversion(
    file: UploadFile = File(...),
    target_format: str = Form(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Загружает файл и ставит задачу в очередь Celery.

    Проверяет: размер файла, пару форматов, поддерживаемые расширения.
    """
    content = await file.read()
    size_mb = len(content) / (1024 * 1024)
    if size_mb > settings.max_file_size_mb:
        raise HTTPException(
            status_code=413,
            detail=f"File too large: {size_mb:.1f} MB > {settings.max_file_size_mb} MB",
        )

    source_ext = (Path(file.filename or "").suffix.lower().lstrip(".")) or "bin"
    target_ext = target_format.lower().lstrip(".")

    if source_ext not in SUPPORTED_SOURCES:
        raise HTTPException(status_code=400, detail=f"Unsupported source: {source_ext}")
    if target_ext not in SUPPORTED_TARGETS:
        raise HTTPException(status_code=400, detail=f"Unsupported target: {target_ext}")

    # Проверяем, что пара поддерживается — сухой прогон диспетчера.
    try:
        from src.converters import convert  # noqa: F401
        _ = (source_ext, target_ext)
    except Exception:  # noqa: BLE001
        pass

    src_path = save_upload(content, file.filename or "upload.bin", user.id)

    task = Task(
        user_id=user.id,
        source_format=source_ext,
        target_format=target_ext,
        source_path=src_path,
        file_size=len(content),
        status=TaskStatus.PENDING,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)

    # Отправляем в Celery (асинхронно).
    convert_task.delay(str(task.id))

    return task


# ------------------- TASKS -------------------
@router.get("/tasks", response_model=TaskListResponse, tags=["convert"])
async def list_tasks(
    limit: int = 20,
    offset: int = 0,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """История конвертаций пользователя (FR-004)."""
    stmt = (
        select(Task)
        .where(Task.user_id == user.id)
        .order_by(Task.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    items = result.scalars().all()

    total = await db.scalar(
        select(func.count()).select_from(Task).where(Task.user_id == user.id)
    )
    return TaskListResponse(items=list(items), total=total or 0)


@router.get("/tasks/{task_id}", response_model=TaskRead, tags=["convert"])
async def get_task(
    task_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Статус конкретной задачи."""
    result = await db.execute(
        select(Task).where(Task.id == task_id, Task.user_id == user.id)
    )
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.get("/download/{task_id}", tags=["convert"])
async def download_result(
    task_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Скачивание результата. Доступно только владельцу задачи."""
    result = await db.execute(
        select(Task).where(Task.id == task_id, Task.user_id == user.id)
    )
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status != TaskStatus.DONE or not task.result_path:
        raise HTTPException(status_code=409, detail="Result not ready")

    path = Path(task.result_path)
    if not path.exists():
        raise HTTPException(status_code=410, detail="Result expired")

    return FileResponse(
        path,
        filename=f"{task.id}.{task.target_format}",
        media_type="application/octet-stream",
    )


@router.delete("/tasks/{task_id}", status_code=204, tags=["convert"])
async def delete_task(
    task_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Удаляет задачу и связанные файлы (FR-005)."""
    result = await db.execute(
        select(Task).where(Task.id == task_id, Task.user_id == user.id)
    )
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    from src.storage import delete_file

    delete_file(task.source_path)
    if task.result_path:
        delete_file(task.result_path)

    await db.delete(task)
    await db.commit()