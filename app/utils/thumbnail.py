"""Thumbnail generation for images and video placeholders."""

from __future__ import annotations
import os

from PyQt6.QtCore import Qt, QRect
from PyQt6.QtGui import QPixmap, QImage, QColor, QPainter, QFont, QIcon

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".m4v", ".wmv", ".flv"}


def generate_thumbnail(path: str, size: tuple[int, int] = (160, 120)) -> QPixmap:
    """Return a QPixmap thumbnail for the given file path."""
    ext = os.path.splitext(path)[1].lower()
    if ext in IMAGE_EXTENSIONS:
        return _image_thumbnail(path, size)
    if ext in VIDEO_EXTENSIONS:
        return _placeholder(size, "\u25b6", QColor(40, 60, 100), QColor(160, 200, 255))
    return _placeholder(size, "?", QColor(60, 60, 60), QColor(180, 180, 180))


def _image_thumbnail(path: str, size: tuple[int, int]) -> QPixmap:
    try:
        from PIL import Image  # pylint: disable=import-outside-toplevel

        img = Image.open(path)
        img.thumbnail(size, Image.LANCZOS)
        img = img.convert("RGBA")
        data = img.tobytes("raw", "RGBA")
        qimg = QImage(data, img.width, img.height, QImage.Format.Format_RGBA8888)
        return QPixmap.fromImage(qimg)
    except OSError:
        return _placeholder(size, "IMG", QColor(80, 80, 80), QColor(200, 200, 200))


def _placeholder(
    size: tuple[int, int],
    label: str,
    bg: QColor,
    fg: QColor,
) -> QPixmap:
    pixmap = QPixmap(size[0], size[1])
    pixmap.fill(bg)
    painter = QPainter(pixmap)
    painter.setPen(fg)
    painter.setFont(QFont("Arial", max(10, size[1] // 6), QFont.Weight.Bold))
    painter.drawText(
        QRect(0, 0, size[0], size[1]),
        Qt.AlignmentFlag.AlignCenter,
        label,
    )
    painter.end()
    return pixmap


def file_icon(path: str, icon_size: int = 64) -> QIcon:
    return QIcon(generate_thumbnail(path, (icon_size, icon_size)))
