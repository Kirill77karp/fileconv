"""Конфигурация приложения. Читает переменные окружения.

Используем pydantic-settings — валидация типов и автодок.
См. ADR-003 (слоистая архитектура) — конфиг изолирован от логики.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Настройки сервиса FileConv.

    Все значения переопределяются через переменные окружения
    или .env-файл (см. .env.example).
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- Приложение ---
    app_name: str = "fileconv"
    debug: bool = False
    api_prefix: str = "/api/v1"

    # --- База данных ---
    database_url: str = "postgresql+asyncpg://fileconv:fileconv@localhost:5432/fileconv"

    # --- Redis / Celery ---
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"

    # --- Хранилище ---
    storage_dir: str = "./storage"
    file_ttl_hours: int = 24
    max_file_size_mb: int = 50

    # --- Безопасность ---
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60
    rate_limit_per_minute: int = 60


@lru_cache
def get_settings() -> Settings:
    """Возвращает singleton-настройки.

    lru_cache гарантирует, что .env читается один раз за процесс.
    """
    return Settings()