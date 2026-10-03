"""Unit-тесты конвертеров (10+)."""
from pathlib import Path

import pandas as pd
import pytest
from PIL import Image

from src.converters import (
    UnsupportedFormatError,
    convert,
    convert_csv_to_xlsx,
    convert_image,
)


def _make_png(path: Path, size=(20, 20), color=(255, 0, 0)) -> None:
    img = Image.new("RGB", size, color)
    img.save(path, format="PNG")


def test_convert_image_png_to_jpg(tmp_path: Path) -> None:
    src = tmp_path / "in.png"
    dst = tmp_path / "out.jpg"
    _make_png(src)
    convert_image(str(src), str(dst), "jpg")
    assert dst.exists()
    assert Image.open(dst).format == "JPEG"


def test_convert_image_png_to_webp(tmp_path: Path) -> None:
    src = tmp_path / "in.png"
    dst = tmp_path / "out.webp"
    _make_png(src)
    convert_image(str(src), str(dst), "webp")
    assert dst.exists()
    assert Image.open(dst).format == "WEBP"


def test_convert_image_unsupported_format(tmp_path: Path) -> None:
    src = tmp_path / "in.png"
    dst = tmp_path / "out.bmp"
    _make_png(src)
    with pytest.raises(UnsupportedFormatError):
        convert_image(str(src), str(dst), "bmp")


def test_convert_csv_to_xlsx(tmp_path: Path) -> None:
    src = tmp_path / "in.csv"
    dst = tmp_path / "out.xlsx"
    pd.DataFrame({"a": [1, 2], "b": [3, 4]}).to_csv(src, index=False)
    convert_csv_to_xlsx(str(src), str(dst))
    assert dst.exists()
    df = pd.read_excel(dst)
    assert list(df.columns) == ["a", "b"]
    assert len(df) == 2


def test_dispatch_same_format_copies(tmp_path: Path) -> None:
    src = tmp_path / "in.png"
    dst = tmp_path / "out.png"
    _make_png(src)
    convert(str(src), str(dst), "png", "png")
    assert dst.exists()


def test_dispatch_png_to_webp(tmp_path: Path) -> None:
    src = tmp_path / "in.png"
    dst = tmp_path / "out.webp"
    _make_png(src)
    convert(str(src), str(dst), "png", "webp")
    assert dst.exists()


def test_dispatch_unsupported(tmp_path: Path) -> None:
    src = tmp_path / "in.bmp"
    dst = tmp_path / "out.png"
    src.write_bytes(b"x")
    with pytest.raises(UnsupportedFormatError):
        convert(str(src), str(dst), "bmp", "png")


def test_supported_sources_contains_expected() -> None:
    from src.converters import SUPPORTED_SOURCES

    assert "png" in SUPPORTED_SOURCES
    assert "jpg" in SUPPORTED_SOURCES
    assert "csv" in SUPPORTED_SOURCES
    assert "docx" in SUPPORTED_SOURCES


def test_supported_targets_contains_pdf() -> None:
    from src.converters import SUPPORTED_TARGETS

    assert "pdf" in SUPPORTED_TARGETS
    assert "xlsx" in SUPPORTED_TARGETS


def test_convert_docx_to_pdf_fallback(tmp_path: Path) -> None:
    src = tmp_path / "in.docx"
    dst = tmp_path / "out.pdf"
    src.write_bytes(b"fake-docx")
    convert(str(src), str(dst), "docx", "pdf")
    assert dst.exists()