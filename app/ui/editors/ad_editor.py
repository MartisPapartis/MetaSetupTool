"""Ad editor panel — edit an AdData object including its creative."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QFormLayout,
    QLineEdit,
    QComboBox,
    QGroupBox,
    QScrollArea,
    QLabel,
)

from app.models.campaign_data import AdData, default_ad_name, is_default_ad_name
from app.models.enums import AdFormat, AdStatus
from app.ui.editors.creative_editor import CreativeEditorPanel


_STATUSES = [e.value for e in AdStatus]


class AdEditorPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._data: AdData | None = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        outer.addWidget(scroll)

        container = QWidget()
        scroll.setWidget(container)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        title = QLabel("Ad Settings")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title)

        # Basic
        basic_group = QGroupBox("Basic")
        form = QFormLayout(basic_group)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("e.g. Ad_v1_Image")
        form.addRow("Name *", self.name_edit)

        self.status_combo = QComboBox()
        self.status_combo.addItems(_STATUSES)
        form.addRow("Status *", self.status_combo)

        layout.addWidget(basic_group)

        # Creative
        self.creative_editor = CreativeEditorPanel()
        self.creative_editor.format_changed.connect(self._on_format_changed)
        layout.addWidget(self.creative_editor)
        layout.addStretch()

    def load(self, data: AdData) -> None:
        self._data = data
        self.name_edit.setText(data.name)
        self.status_combo.setCurrentText(data.status.value)
        self.creative_editor.load(data.creative)

    def _on_format_changed(self, fmt: AdFormat) -> None:
        if is_default_ad_name(self.name_edit.text()):
            self.name_edit.setText(default_ad_name(fmt))

    def commit(self) -> None:
        if self._data is None:
            return
        self._data.name = self.name_edit.text().strip()
        try:
            self._data.status = AdStatus(self.status_combo.currentText())
        except ValueError:
            pass
        self.creative_editor.commit()
