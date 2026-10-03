"""Pydantic-схемы — валидация запросов и сериализация ответов."""
import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from src.models import TaskStatus


# ---------- Auth ----------
class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ---------- Task ----------
class TaskCreate(BaseModel):
    target_format: str = Field(
        description="Целевой формат: pdf, png, jpg, webp, xlsx",
        examples=["pdf"],
    )


class TaskRead(BaseModel):
    id: uuid.UUID
    source_format: str
    target_format: str
    status: TaskStatus
    file_size: int
    error_message: str | None = None
    created_at: datetime
    finished_at: datetime | None = None

    model_config = {"from_attributes": True}


class TaskListResponse(BaseModel):
    items: list[TaskRead]
    total: int


class FormatInfo(BaseModel):
    source: list[str]
    target: list[str]


class ErrorResponse(BaseModel):
    detail: str