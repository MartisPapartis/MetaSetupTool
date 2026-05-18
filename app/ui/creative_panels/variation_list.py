"""Reusable list widget for managing multiple text or media variations."""

from __future__ import annotations
import os
from dataclasses import dataclass, field

from PyQt6.QtCore import QSize, pyqtSignal
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
)

from app.ui.media_library import MediaPickerDialog
from app.utils.thumbnail import generate_thumbnail

THUMB_SMALL = (60, 45)


@dataclass
class MediaItem:
    """Represents one entry in the MediaVariationList.

    source_path — real local file; empty string if the item was pulled from Meta.
    display_path — path used for thumbnail rendering (may be a cached preview).
    fb_hash — existing Meta image hash; non-empty means reuse on upload, no re-upload needed.
    fb_video_id — existing Meta video ID; same reuse semantics as fb_hash.
    pulled_dims — (width, height) stored at pull time; empty tuple if this is a local file.
    """

    source_path: str
    display_path: str
    fb_hash: str = ""
    fb_video_id: str = ""
    pulled_dims: tuple = field(default_factory=tuple)


class TextVariationList(QWidget):
    """Multi-line plain-text input — one variation per line.

    No buttons needed: just type each variation on its own line.
    Empty lines are ignored when reading back.
    """

    def __init__(self, label: str = "Variations", placeholder: str = "", parent=None):
        super().__init__(parent)
        self._setup_ui(label, placeholder)

    def _setup_ui(self, label: str, placeholder: str) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(4)

        layout.addWidget(QLabel(f"{label}  (one per line)"))

        self.text_edit = QPlainTextEdit()
        self.text_edit.setMaximumHeight(90)
        self.text_edit.setPlaceholderText(
            placeholder or "Type each variation on a new line…"
        )
        self.text_edit.setStyleSheet("QPlainTextEdit { background: #252526; }")
        layout.addWidget(self.text_edit)

    def get_texts(self) -> list[str]:
        return [
            line.strip()
            for line in self.text_edit.toPlainText().splitlines()
            if line.strip()
        ]

    def set_texts(self, texts: list[str]) -> None:
        self.text_edit.setPlainText("\n".join(texts))


class MediaVariationList(QWidget):
    """A compact list widget for adding/removing media file variations.

    Supports two item types via add_local() and add_pulled():
      - Local items have a real source file and are uploaded on push.
      - Pulled items came from Meta; their existing hash is reused on push
        without re-uploading.  They show a "[Meta]" prefix in the list.
    """

    paths_changed = pyqtSignal()

    def __init__(
        self,
        label: str = "Additional Media",
        image_only: bool = False,
        video_only: bool = False,
        parent=None,
    ):
        super().__init__(parent)
        self._image_only = image_only
        self._video_only = video_only
        self._items: list[MediaItem] = []
        self._setup_ui(label)

    def _setup_ui(self, label: str) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(4)

        header = QHBoxLayout()
        header.addWidget(QLabel(label))
        header.addStretch()
        self.add_btn = QPushButton("+ Add")
        self.add_btn.setFixedWidth(60)
        self.add_btn.clicked.connect(self._pick_media)
        header.addWidget(self.add_btn)
        layout.addLayout(header)

        self.list_widget = QListWidget()
        self.list_widget.setMaximumHeight(110)
        self.list_widget.setIconSize(QSize(*THUMB_SMALL))
        self.list_widget.setStyleSheet("QListWidget { background: #252526; }")
        layout.addWidget(self.list_widget)

        remove_row = QHBoxLayout()
        remove_row.addStretch()
        self.remove_btn = QPushButton("Remove Selected")
        self.remove_btn.setFixedWidth(120)
        self.remove_btn.clicked.connect(self._remove_selected)
        remove_row.addWidget(self.remove_btn)
        layout.addLayout(remove_row)

    def _pick_media(self) -> None:
        dialog = MediaPickerDialog(
            image_only=self._image_only,
            video_only=self._video_only,
            multi_select=True,
            parent=self,
        )
        if dialog.exec() and dialog.selected_paths:
            for path in dialog.selected_paths:
                self.add_local(path)
            self.paths_changed.emit()

    def _append_list_item(self, item: MediaItem) -> None:
        pixmap = generate_thumbnail(item.display_path, THUMB_SMALL)
        if item.source_path:
            label = os.path.basename(item.source_path)
        else:
            label = f"[Meta] {os.path.basename(item.display_path)}"
        list_item = QListWidgetItem(QIcon(pixmap), label)
        self.list_widget.addItem(list_item)

    def add_local(self, path: str) -> None:
        """Add a local file as a new list entry. Silently skips duplicates."""
        if any(it.source_path == path for it in self._items):
            return
        item = MediaItem(source_path=path, display_path=path)
        self._items.append(item)
        self._append_list_item(item)

    def add_pulled(
        self,
        display_path: str,
        fb_hash: str = "",
        fb_video_id: str = "",
        pulled_dims: tuple = (),
    ) -> None:
        """Add a pulled Meta item using its cached preview thumbnail."""
        item = MediaItem(
            source_path="",
            display_path=display_path,
            fb_hash=fb_hash,
            fb_video_id=fb_video_id,
            pulled_dims=pulled_dims,
        )
        self._items.append(item)
        self._append_list_item(item)

    def _add_path(self, path: str) -> None:
        """Backward-compatible private alias for add_local."""
        self.add_local(path)

    def _remove_selected(self) -> None:
        for list_item in self.list_widget.selectedItems():
            row = self.list_widget.row(list_item)
            if 0 <= row < len(self._items):
                self._items.pop(row)
            self.list_widget.takeItem(row)
        self.paths_changed.emit()

    def get_items(self) -> list[MediaItem]:
        """Return the full ordered item list including pulled entries."""
        return list(self._items)

    def get_paths(self) -> list[str]:
        """Return only local source paths (backward-compatible)."""
        return [it.source_path for it in self._items if it.source_path]

    def set_paths(self, paths: list[str]) -> None:
        self.list_widget.clear()
        self._items.clear()
        for p in paths:
            if p:
                self.add_local(p)
