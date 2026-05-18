"""Media library panel + shared store + media picker dialog."""

from __future__ import annotations
import os

from PyQt6.QtCore import Qt, QSize, pyqtSignal, QRunnable, QThreadPool, QObject
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QFileDialog,
    QDialog,
    QDialogButtonBox,
    QLineEdit,
    QMessageBox,
)

_IMAGE_SIZE_LIMIT = 30 * 1024 * 1024        # 30 MB
_VIDEO_SIZE_LIMIT = 4 * 1024 * 1024 * 1024  # 4 GB

from app.utils.thumbnail import generate_thumbnail, IMAGE_EXTENSIONS, VIDEO_EXTENSIONS

# ---------------------------------------------------------------------------
# Module-level media store — shared between panels and dialogs
# ---------------------------------------------------------------------------
_store: dict = {"folder": "", "files": []}


def set_media_folder(folder: str, files: list[str]) -> None:
    _store["folder"] = folder
    _store["files"] = list(files)


def get_media_files() -> list[str]:
    return list(_store["files"])


def get_media_folder() -> str:
    return _store["folder"]


# ---------------------------------------------------------------------------
# Background thumbnail loader
# ---------------------------------------------------------------------------
class _ThumbnailSignals(QObject):
    done = pyqtSignal(str, QPixmap)  # path, pixmap


class _ThumbnailTask(QRunnable):
    def __init__(self, path: str, size: tuple[int, int]):
        super().__init__()
        self.path = path
        self.size = size
        self.signals = _ThumbnailSignals()

    def run(self) -> None:
        pixmap = generate_thumbnail(self.path, self.size)
        self.signals.done.emit(self.path, pixmap)


# ---------------------------------------------------------------------------
# Media Library Panel
# ---------------------------------------------------------------------------
ICON_SIZE = 100


class MediaLibraryPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        title = QLabel("Media Library")
        title.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(title)

        # Toolbar row
        toolbar = QHBoxLayout()
        self.select_folder_btn = QPushButton("Select Folder...")
        self.select_folder_btn.clicked.connect(self._select_folder)
        toolbar.addWidget(self.select_folder_btn)

        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self._refresh)
        toolbar.addWidget(self.refresh_btn)

        toolbar.addStretch()
        layout.addLayout(toolbar)

        # Folder path label
        self.folder_label = QLabel("No folder selected")
        self.folder_label.setStyleSheet("color: gray; font-size: 11px;")
        self.folder_label.setWordWrap(True)
        layout.addWidget(self.folder_label)

        # Filter
        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText("Filter by filename...")
        self.filter_edit.textChanged.connect(self._apply_filter)
        layout.addWidget(self.filter_edit)

        # Count label
        self.count_label = QLabel("")
        self.count_label.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(self.count_label)

        # Thumbnail grid
        self.list_widget = QListWidget()
        self.list_widget.setViewMode(QListWidget.ViewMode.IconMode)
        self.list_widget.setIconSize(QSize(ICON_SIZE, ICON_SIZE))
        self.list_widget.setGridSize(QSize(ICON_SIZE + 30, ICON_SIZE + 30))
        self.list_widget.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.list_widget.setMovement(QListWidget.Movement.Static)
        self.list_widget.setWordWrap(True)
        layout.addWidget(self.list_widget)

        # Load existing folder if already set
        if get_media_folder():
            self._load_folder(get_media_folder())

    def _select_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self, "Select Media Folder", get_media_folder() or ""
        )
        if folder:
            self._load_folder(folder)

    def _refresh(self) -> None:
        if get_media_folder():
            self._load_folder(get_media_folder())

    def _load_folder(self, folder: str) -> None:
        self.folder_label.setText(folder)
        all_exts = IMAGE_EXTENSIONS | VIDEO_EXTENSIONS
        all_files = sorted(
            os.path.join(root, f)
            for root, _dirs, files in os.walk(folder)
            for f in files
            if os.path.splitext(f)[1].lower() in all_exts
        )

        accepted, rejected = [], []
        for path in all_files:
            ext = os.path.splitext(path)[1].lower()
            size = os.path.getsize(path)
            if ext in IMAGE_EXTENSIONS and size > _IMAGE_SIZE_LIMIT:
                rejected.append((os.path.basename(path), size, "image", _IMAGE_SIZE_LIMIT))
            elif ext in VIDEO_EXTENSIONS and size > _VIDEO_SIZE_LIMIT:
                rejected.append((os.path.basename(path), size, "video", _VIDEO_SIZE_LIMIT))
            else:
                accepted.append(path)

        if rejected:
            lines = []
            for name, size, kind, limit in rejected:
                size_mb = size / (1024 * 1024)
                limit_label = f"{limit // (1024 * 1024)} MB" if kind == "image" else f"{limit // (1024 ** 3)} GB"
                lines.append(f"• {name}  ({size_mb:.1f} MB) — exceeds {kind} limit of {limit_label}")
            QMessageBox.warning(
                self,
                "Files Exceed Size Limit",
                "The following files were not loaded because they exceed the size limit:\n\n"
                + "\n".join(lines),
            )

        set_media_folder(folder, accepted)
        self._populate_list(accepted)

    def _populate_list(self, files: list[str]) -> None:
        self.list_widget.clear()
        self.count_label.setText(f"{len(files)} file(s)")

        pool = QThreadPool.globalInstance()
        for path in files:
            filename = os.path.basename(path)
            item = QListWidgetItem(filename)
            item.setData(Qt.ItemDataRole.UserRole, path)
            item.setToolTip(path)
            # Placeholder icon while loading
            placeholder = generate_thumbnail(path, (ICON_SIZE, ICON_SIZE))
            item.setIcon(QIcon(placeholder))
            self.list_widget.addItem(item)

            task = _ThumbnailTask(path, (ICON_SIZE, ICON_SIZE))
            task.signals.done.connect(self._on_thumbnail_ready)
            pool.start(task)

    def _on_thumbnail_ready(self, path: str, pixmap: QPixmap) -> None:
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == path:
                item.setIcon(QIcon(pixmap))
                break

    def _apply_filter(self, text: str) -> None:
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            item.setHidden(text.lower() not in item.text().lower())

    def get_files(self) -> list[str]:
        return get_media_files()


# ---------------------------------------------------------------------------
# Media Picker Dialog — opened from creative panels
# ---------------------------------------------------------------------------
class MediaPickerDialog(QDialog):
    def __init__(
        self,
        image_only: bool = False,
        video_only: bool = False,
        multi_select: bool = False,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Select Media")
        self.setMinimumSize(640, 480)
        self.selected_path: str = ""
        self.selected_paths: list[str] = []
        self._image_only = image_only
        self._video_only = video_only
        self._multi_select = multi_select
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Header
        if self._image_only:
            hint = "Select an image file"
        elif self._video_only:
            hint = "Select a video file"
        else:
            hint = "Select an image or video file"
        layout.addWidget(QLabel(hint))

        # Filter
        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText("Filter by filename...")
        self.filter_edit.textChanged.connect(self._apply_filter)
        layout.addWidget(self.filter_edit)

        # File list
        self.list_widget = QListWidget()
        self.list_widget.setViewMode(QListWidget.ViewMode.IconMode)
        self.list_widget.setIconSize(QSize(120, 90))
        self.list_widget.setGridSize(QSize(150, 120))
        self.list_widget.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.list_widget.setMovement(QListWidget.Movement.Static)
        self.list_widget.setWordWrap(True)
        if self._multi_select:
            self.list_widget.setSelectionMode(
                QListWidget.SelectionMode.ExtendedSelection
            )
        self.list_widget.itemDoubleClicked.connect(self._accept_selection)
        layout.addWidget(self.list_widget)

        # No media warning
        self.no_media_label = QLabel(
            "No media loaded. Open the Media Library tab and select a folder first."
        )
        self.no_media_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.no_media_label.setStyleSheet("color: orange;")
        layout.addWidget(self.no_media_label)

        # Buttons
        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btn_box.accepted.connect(self._accept_selection)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

        self._load_files()

    def _load_files(self) -> None:
        files = get_media_files()
        if self._image_only:
            files = [
                f for f in files if os.path.splitext(f)[1].lower() in IMAGE_EXTENSIONS
            ]
        elif self._video_only:
            files = [
                f for f in files if os.path.splitext(f)[1].lower() in VIDEO_EXTENSIONS
            ]

        self.no_media_label.setVisible(not files)
        self.list_widget.setVisible(bool(files))

        for path in files:
            filename = os.path.basename(path)
            item = QListWidgetItem(filename)
            item.setData(Qt.ItemDataRole.UserRole, path)
            item.setToolTip(path)
            pixmap = generate_thumbnail(path, (120, 90))
            item.setIcon(QIcon(pixmap))
            self.list_widget.addItem(item)

    def _apply_filter(self, text: str) -> None:
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            item.setHidden(text.lower() not in item.text().lower())

    def _accept_selection(self) -> None:
        items = self.list_widget.selectedItems()
        if items:
            self.selected_paths = [
                item.data(Qt.ItemDataRole.UserRole) for item in items
            ]
            self.selected_path = self.selected_paths[0]
            self.accept()
