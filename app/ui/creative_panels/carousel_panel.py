"""Carousel creative panel — manages a list of CarouselCardWidget items."""

from __future__ import annotations
import os

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLineEdit,
    QComboBox,
    QPushButton,
    QLabel,
    QScrollArea,
    QFrame,
    QPlainTextEdit,
)

from app.models.campaign_data import CreativeData, CarouselCard
from app.models.enums import CallToAction
from app.ui.media_library import MediaPickerDialog
from app.utils.thumbnail import generate_thumbnail

_CTAS = [e.value for e in CallToAction]
THUMB_SIZE = (100, 75)


class CarouselCardWidget(QFrame):
    """Editable widget for one carousel card."""

    def __init__(self, card: CarouselCard, index: int, parent=None):
        super().__init__(parent)
        self.card = card
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet(
            "QFrame { border: 1px solid #444; border-radius: 4px; padding: 4px; }"
        )
        self._setup_ui(index)
        self._load()

    def _setup_ui(self, index: int) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(6)

        # Header row with card number + remove button
        header = QHBoxLayout()
        self.index_label = QLabel(f"Card {index}")
        self.index_label.setStyleSheet("font-weight: bold;")
        header.addWidget(self.index_label)
        header.addStretch()
        self.remove_btn = QPushButton("Remove")
        self.remove_btn.setFixedWidth(70)
        header.addWidget(self.remove_btn)
        layout.addLayout(header)

        # Media row
        media_row = QHBoxLayout()
        self.thumb_label = QLabel()
        self.thumb_label.setFixedSize(*THUMB_SIZE)
        self.thumb_label.setStyleSheet("background: #2a2a2a; border: 1px solid #555;")
        self.thumb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumb_label.setText("No media")
        media_row.addWidget(self.thumb_label)

        btn_col = QVBoxLayout()
        self.pick_btn = QPushButton("Choose Media...")
        self.pick_btn.clicked.connect(self._pick_media)
        self.file_label = QLabel("No file selected")
        self.file_label.setStyleSheet("color: gray; font-size: 10px;")
        self.file_label.setWordWrap(True)
        btn_col.addWidget(self.pick_btn)
        btn_col.addWidget(self.file_label)
        btn_col.addStretch()
        media_row.addLayout(btn_col)
        layout.addLayout(media_row)

        # Fields
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setContentsMargins(0, 0, 0, 0)

        self.headline_edit = QLineEdit()
        self.headline_edit.setMaxLength(255)
        form.addRow("Headline", self.headline_edit)

        self.description_edit = QLineEdit()
        form.addRow("Description", self.description_edit)

        self.link_url_edit = QLineEdit()
        self.link_url_edit.setPlaceholderText("https://example.com")
        form.addRow("Link URL *", self.link_url_edit)

        self.cta_combo = QComboBox()
        self.cta_combo.addItems(_CTAS)
        form.addRow("Call to Action", self.cta_combo)

        layout.addLayout(form)

    def _pick_media(self) -> None:
        dialog = MediaPickerDialog(parent=self)
        if dialog.exec() and dialog.selected_path:
            self._set_media(dialog.selected_path)

    def _set_media(self, path: str) -> None:
        self.file_label.setText(os.path.basename(path))
        self.file_label.setProperty("media_path", path)
        pixmap = generate_thumbnail(path, THUMB_SIZE)
        self.thumb_label.setPixmap(
            pixmap.scaled(
                QSize(*THUMB_SIZE),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

    def _load(self) -> None:
        if self.card.media_path:
            self._set_media(self.card.media_path)
        elif self.card.cached_preview_path and os.path.exists(self.card.cached_preview_path):
            self._set_media(self.card.cached_preview_path)
            self.file_label.setText("Pulled from Facebook")
            self.file_label.setStyleSheet("color: #aaa; font-size: 10px;")
        self.headline_edit.setText(self.card.headline)
        self.description_edit.setText(self.card.description)
        self.link_url_edit.setText(self.card.link_url)
        self.cta_combo.setCurrentText(self.card.call_to_action.value)

    def commit_to_card(self) -> None:
        self.card.media_path = self.file_label.property("media_path") or ""
        self.card.headline = self.headline_edit.text().strip()
        self.card.description = self.description_edit.text().strip()
        self.card.link_url = self.link_url_edit.text().strip()
        try:
            self.card.call_to_action = CallToAction(self.cta_combo.currentText())
        except ValueError:
            pass

    def update_index_label(self, index: int) -> None:
        self.index_label.setText(f"Card {index}")


class CarouselPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._data: CreativeData | None = None
        self._card_widgets: list[CarouselCardWidget] = []
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Global carousel fields
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.body_edit = QPlainTextEdit()
        self.body_edit.setPlaceholderText("Primary text shown above carousel")
        self.body_edit.setMaximumHeight(60)
        form.addRow("Primary Text", self.body_edit)

        self.link_url_edit = QLineEdit()
        self.link_url_edit.setPlaceholderText("Default destination URL")
        form.addRow("Default Link URL", self.link_url_edit)

        layout.addLayout(form)

        # Add card button
        add_row = QHBoxLayout()
        self.add_card_btn = QPushButton("+ Add Card")
        self.add_card_btn.clicked.connect(self._add_card)
        add_row.addWidget(self.add_card_btn)
        hint = QLabel("Min 2 cards, max 10 cards")
        hint.setStyleSheet("color: gray; font-size: 11px;")
        add_row.addWidget(hint)
        add_row.addStretch()
        layout.addLayout(add_row)

        # Scrollable card list
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        layout.addWidget(scroll)

        self._cards_container = QWidget()
        self._cards_layout = QVBoxLayout(self._cards_container)
        self._cards_layout.setSpacing(8)
        self._cards_layout.addStretch()
        scroll.setWidget(self._cards_container)

    def _add_card(self, card: CarouselCard | None = None) -> None:
        if len(self._card_widgets) >= 10:
            return
        if card is None:
            card = CarouselCard()
            if self._data is not None:
                self._data.carousel_cards.append(card)

        idx = len(self._card_widgets) + 1
        widget = CarouselCardWidget(card, idx)
        widget.remove_btn.clicked.connect(lambda: self._remove_card(widget))
        # Insert before the stretch
        self._cards_layout.insertWidget(self._cards_layout.count() - 1, widget)
        self._card_widgets.append(widget)

    def _remove_card(self, widget: CarouselCardWidget) -> None:
        if len(self._card_widgets) <= 2:
            return  # keep minimum 2
        self._card_widgets.remove(widget)
        if self._data is not None and widget.card in self._data.carousel_cards:
            self._data.carousel_cards.remove(widget.card)
        widget.setParent(None)
        widget.deleteLater()
        self._renumber()

    def _renumber(self) -> None:
        for i, w in enumerate(self._card_widgets, 1):
            w.update_index_label(i)

    def load(self, data: CreativeData) -> None:
        self._data = data
        # Clear existing widgets
        for w in list(self._card_widgets):
            w.setParent(None)
            w.deleteLater()
        self._card_widgets.clear()

        self.body_edit.setPlainText(data.body)
        self.link_url_edit.setText(data.link_url)

        # Ensure minimum 2 cards
        while len(data.carousel_cards) < 2:
            card = CarouselCard()
            data.carousel_cards.append(card)

        for card in data.carousel_cards:
            self._add_card(card)

    def commit(self, data: CreativeData) -> None:
        data.body = self.body_edit.toPlainText().strip()
        data.link_url = self.link_url_edit.text().strip()
        for widget in self._card_widgets:
            widget.commit_to_card()
        # Sync card list order
        data.carousel_cards = [w.card for w in self._card_widgets]
