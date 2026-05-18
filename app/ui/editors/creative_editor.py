"""Creative editor — format selector + stacked format-specific panels."""

from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QGroupBox,
    QStackedWidget,
)

from app.models.campaign_data import CreativeData, VIDEO_EXTENSIONS
from app.models.enums import AdFormat
from app.ui.creative_panels.single_image_panel import SingleImagePanel
from app.ui.creative_panels.single_video_panel import SingleVideoPanel
from app.ui.creative_panels.carousel_panel import CarouselPanel
from app.ui.creative_panels.enhancements_panel import EnhancementsPanel

_FORMAT_LABELS = {
    AdFormat.SINGLE_IMAGE: "Single Image",
    AdFormat.SINGLE_VIDEO: "Single Video",
    AdFormat.CAROUSEL: "Carousel",
}
_LABEL_TO_FORMAT = {v: k for k, v in _FORMAT_LABELS.items()}


class CreativeEditorPanel(QGroupBox):
    format_changed = pyqtSignal(object)  # emits AdFormat

    def __init__(self, parent=None):
        super().__init__("Creative", parent)
        self._data: CreativeData | None = None
        self._syncing = False
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Format selector row
        format_row = QHBoxLayout()
        format_row.addWidget(QLabel("Ad Format *"))
        self.format_combo = QComboBox()
        for label in _FORMAT_LABELS.values():
            self.format_combo.addItem(label)
        self.format_combo.currentIndexChanged.connect(self._on_format_changed)
        format_row.addWidget(self.format_combo)
        format_row.addStretch()
        layout.addLayout(format_row)

        # Stacked panels
        self.stack = QStackedWidget()
        self.image_panel = SingleImagePanel()
        self.video_panel = SingleVideoPanel()
        self.carousel_panel = CarouselPanel()

        self.stack.addWidget(self.image_panel)  # 0 — SINGLE_IMAGE
        self.stack.addWidget(self.video_panel)  # 1 — SINGLE_VIDEO
        self.stack.addWidget(self.carousel_panel)  # 2 — CAROUSEL

        layout.addWidget(self.stack)

        self.image_panel.media_list.paths_changed.connect(self._on_image_media_changed)
        self.video_panel.media_list.paths_changed.connect(self._on_video_media_changed)

        # Advantage+ creative enhancements (format-agnostic)
        self.enhancements_group = QGroupBox("Advantage+ Creative Enhancements")
        enh_layout = QVBoxLayout(self.enhancements_group)
        self.enhancements_panel = EnhancementsPanel()
        enh_layout.addWidget(self.enhancements_panel)
        layout.addWidget(self.enhancements_group)

    def _on_format_changed(self, index: int) -> None:
        self.stack.setCurrentIndex(index)
        fmt = _LABEL_TO_FORMAT.get(self.format_combo.currentText(), AdFormat.SINGLE_IMAGE)
        self.format_changed.emit(fmt)

    def _on_image_media_changed(self) -> None:
        if not self._syncing:
            self._sync_media_and_format(self.image_panel)

    def _on_video_media_changed(self) -> None:
        if not self._syncing:
            self._sync_media_and_format(self.video_panel)

    def _sync_media_and_format(self, source_panel) -> None:
        import os
        paths = source_panel.media_list.get_paths()
        if not paths:
            return
        has_video = any(os.path.splitext(p)[1].lower() in VIDEO_EXTENSIONS for p in paths)
        fmt = AdFormat.SINGLE_VIDEO if has_video else AdFormat.SINGLE_IMAGE
        target_panel = self.video_panel if fmt == AdFormat.SINGLE_VIDEO else self.image_panel
        if source_panel is not target_panel:
            self._syncing = True
            try:
                target_panel.media_list.set_paths(paths)
                source_panel.media_list.set_paths([])
            finally:
                self._syncing = False
        self.format_combo.setCurrentText(_FORMAT_LABELS[fmt])

    def load(self, data: CreativeData) -> None:
        self._data = data
        label = _FORMAT_LABELS.get(data.ad_format, "Single Image")
        self.format_combo.setCurrentText(label)
        self._on_format_changed(self.format_combo.currentIndex())
        self.image_panel.load(data)
        self.video_panel.load(data)
        self.carousel_panel.load(data)
        self.enhancements_panel.load(data.creative_enhancements)

    def commit(self) -> None:
        if self._data is None:
            return
        label = self.format_combo.currentText()
        self._data.ad_format = _LABEL_TO_FORMAT.get(label, AdFormat.SINGLE_IMAGE)

        idx = self.stack.currentIndex()
        if idx == 0:
            self.image_panel.commit(self._data)
        elif idx == 1:
            self.video_panel.commit(self._data)
        elif idx == 2:
            self.carousel_panel.commit(self._data)

        self._data.creative_enhancements = self.enhancements_panel.commit()
