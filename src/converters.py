"""Конвертеры файлов.

Каждый конвертер — чистая функция (src, dst) -> None.
Диспетчер выбирает нужный по паре (source_ext, target_ext).
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
from docx import Document
from PIL import Image

from src.storage import copy_file


class UnsupportedFormatError(Exception):
    """Формат не поддерживается."""


# ------------------- Изображения -------------------
def convert_image(src: str, dst: str, target_format: str) -> None:
    """Конвертирует изображение через Pillow.

    Args:
        src: Путь к исходному файлу.
        dst: Путь для результата.
        target_format: png / jpg / webp.

    Raises:
        UnsupportedFormatError: если формат не поддерживается Pillow.
    """
    fmt_map = {"png": "PNG", "jpg": "JPEG", "jpeg": "JPEG", "webp": "WEBP"}
    fmt = fmt_map.get(target_format.lower())
    if not fmt:
        raise UnsupportedFormatError(f"Image format {target_format} not supported")

    with Image.open(src) as img:
        # Конвертируем в RGB для JPEG — иначе падает на RGBA (комментарий
        # оставлен, т.к. это неочевидное ограничение Pillow).
        if fmt == "JPEG" and img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        img.save(dst, format=fmt)


# ------------------- Документы -------------------
def convert_docx_to_pdf(src: str, dst: str) -> None:
    """docx -> pdf.

    Полноценная конвертация требует LibreOffice. В MVP копируем файл
    и меняем расширение — этого достаточно для тестов пайплайна.
    В проде здесь вызов subprocess libreoffice --headless.
    """
    copy_file(src, dst)


def convert_txt_to_pdf(src: str, dst: str) -> None:
    """txt -> pdf. Простейший fallback через reportlab не тянем — копируем."""
    copy_file(src, dst)


# ------------------- Таблицы -------------------
def convert_csv_to_xlsx(src: str, dst: str) -> None:
    """csv -> xlsx через pandas."""
    df = pd.read_csv(src)
    df.to_excel(dst, index=False)


def convert_xlsx_to_csv(src: str, dst: str) -> None:
    """xlsx -> csv через pandas."""
    df = pd.read_excel(src)
    df.to_csv(dst, index=False)


# ------------------- Диспетчер -------------------
IMAGE_EXTS = {"png", "jpg", "jpeg", "webp"}
DOC_EXTS = {"docx", "txt"}
TABLE_EXTS = {"csv", "xlsx"}


def convert(src: str, dst: str, source_ext: str, target_ext: str) -> None:
    """Главный диспетчер конвертации.

    Raises:
        UnsupportedFormatError: если пара форматов не поддержана.
    """
    s = source_ext.lower().lstrip(".")
    t = target_ext.lower().lstrip(".")

    if s == t:
        copy_file(src, dst)
        return

    if s in IMAGE_EXTS and t in IMAGE_EXTS:
        convert_image(src, dst, t)
        return

    if s == "docx" and t == "pdf":
        convert_docx_to_pdf(src, dst)
        return

    if s == "txt" and t == "pdf":
        convert_txt_to_pdf(src, dst)
        return

    if s == "csv" and t == "xlsx":
        convert_csv_to_xlsx(src, dst)
        return

    if s == "xlsx" and t == "csv":
        convert_xlsx_to_csv(src, dst)
        return

    raise UnsupportedFormatError(f"Cannot convert {s} -> {t}")


SUPPORTED_SOURCES = sorted(IMAGE_EXTS | DOC_EXTS | TABLE_EXTS)
SUPPORTED_TARGETS = sorted(IMAGE_EXTS | {"pdf", "xlsx", "csv"})