"""Работа с локальным хранилищем файлов.

В MVP используем локальную папку — этого достаточно для одной ноды.
При масштабировании заменяется на S3 (см. ADR-002, ADR-003).
"""
import shutil
import uuid
from pathlib import Path

from src.config import get_settings

settings = get_settings()


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def save_upload(content: bytes, original_name: str, user_id: uuid.UUID) -> str:
    """Сохраняет файл на диск, возвращает относительный путь."""
    user_dir = Path(settings.storage_dir) / str(user_id)
    _ensure_dir(user_dir)

    ext = Path(original_name).suffix.lower().lstrip(".") or "bin"
    filename = f"{uuid.uuid4()}.{ext}"
    full_path = user_dir / filename

    full_path.write_bytes(content)
    return str(full_path)


def make_result_path(task_id: uuid.UUID, target_format: str) -> str:
    """Формирует путь для результата конвертации."""
    out_dir = Path(settings.storage_dir) / "results"
    _ensure_dir(out_dir)
    return str(out_dir / f"{task_id}.{target_format}")


def delete_file(path: str) -> None:
    """Удаляет файл, если он существует."""
    p = Path(path)
    if p.exists():
        p.unlink()


def copy_file(src: str, dst: str) -> None:
    """Копирует файл (используется в fallback-конвертерах)."""
    shutil.copyfile(src, dst)