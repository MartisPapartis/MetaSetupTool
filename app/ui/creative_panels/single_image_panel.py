"""Single image creative panel."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLineEdit,
    QComboBox,
    QPlainTextEdit,
    QGroupBox,
    QLabel,
)

from app.models.campaign_data import CreativeData
from app.models.enums import CallToAction
from app.ui.creative_panels.variation_list import (
    TextVariationList,
    MediaVariationList,
)

_CTAS = [e.value for e in CallToAction]


class SingleImagePanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:  # pylint: disable=too-many-statements
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Pulled preview — shown when a campaign was pulled from Facebook with no local file
        self._pulled_preview = QWidget()
        row = QHBoxLayout(self._pulled_preview)
        row.setContentsMargins(0, 0, 0, 6)
        self._preview_thumb = QLabel()
        self._preview_thumb.setFixedSize(60, 45)
        self._preview_thumb.setStyleSheet("background: #2a2a2a; border: 1px solid #555;")
        self._preview_thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        row.addWidget(self._preview_thumb)
        info = QLabel(
            "Pulled from Facebook — no local file.\nAdd an image above to enable re-upload."
        )
        info.setStyleSheet("color: #aaa; font-size: 10px;")
        info.setWordWrap(True)
        row.addWidget(info)
        row.addStretch()
        self._pulled_preview.hide()
        layout.addWidget(self._pulled_preview)

        # Unified media list — all images are equal, no primary/extra distinction
        self.media_list = MediaVariationList(label="Media  (select one or more)")
        layout.addWidget(self.media_list)

        # Creative fields
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.headline_edit = QLineEdit()
        self.headline_edit.setPlaceholderText("Max 255 characters")
        self.headline_edit.setMaxLength(255)
        form.addRow("Headline", self.headline_edit)

        self.body_edit = QPlainTextEdit()
        self.body_edit.setPlaceholderText(
            "Primary text (max 125 characters recommended)"
        )
        self.body_edit.setMaximumHeight(80)
        form.addRow("Primary Text", self.body_edit)

        self.description_edit = QLineEdit()
        self.description_edit.setPlaceholderText("Optional link description")
        form.addRow("Description", self.description_edit)

        self.link_url_edit = QLineEdit()
        self.link_url_edit.setPlaceholderText("https://example.com")
        form.addRow("Link URL *", self.link_url_edit)

        self.link_utm_edit = QLineEdit()
        self.link_utm_edit.setPlaceholderText("?utm_source=...")
        form.addRow("Link UTM", self.link_utm_edit)

        self.display_url_edit = QLineEdit()
        self.display_url_edit.setPlaceholderText("example.com  (optional)")
        form.addRow("Display URL", self.display_url_edit)

        self.cta_combo = QComboBox()
        self.cta_combo.addItems(_CTAS)
        self.cta_combo.setCurrentText("LEARN_MORE")
        form.addRow("Call to Action", self.cta_combo)

        layout.addLayout(form)

        # Text variations
        variations_group = QGroupBox(
            "Text Variations (optional — Meta tests combinations)"
        )
        var_layout = QVBoxLayout(variations_group)
        self.extra_headlines = TextVariationList(
            label="Additional Headlines", placeholder="Another headline"
        )
        var_layout.addWidget(self.extra_headlines)
        self.extra_bodies = TextVariationList(
            label="Additional Primary Texts", placeholder="Another primary text"
        )
        var_layout.addWidget(self.extra_bodies)
        layout.addWidget(variations_group)

    def load(self, data: CreativeData) -> None:
        self.media_list.set_paths([])
        self._pulled_preview.hide()

        # Primary slot
        if data.media_path:
            self.media_list.add_local(data.media_path)
        elif data.fb_image_hash:
            dims = tuple(data.pulled_media_dimensions.get(data.fb_image_hash, ()))
            self.media_list.add_pulled(
                display_path=data.cached_preview_path,
                fb_hash=data.fb_image_hash,
                pulled_dims=dims,
            )

        # Extra slots — fb_extra_image_hashes and extra_cached_preview_paths are parallel
        for i, fb_hash in enumerate(data.fb_extra_image_hashes):
            if not fb_hash:
                continue
            preview = (
                data.extra_cached_preview_paths[i]
                if i < len(data.extra_cached_preview_paths)
                else ""
            )
            dims = tuple(data.pulled_media_dimensions.get(fb_hash, ()))
            self.media_list.add_pulled(
                display_path=preview,
                fb_hash=fb_hash,
                pulled_dims=dims,
            )

        # Local extra files (added by user, not pulled)
        for path in data.extra_media_paths:
            if path:
                self.media_list.add_local(path)

        self.headline_edit.setText(data.headline)
        self.body_edit.setPlainText(data.body)
        self.description_edit.setText(data.description)
        self.link_url_edit.setText(data.link_url)
        self.link_utm_edit.setText(data.link_utm)
        self.display_url_edit.setText(data.display_url)
        self.cta_combo.setCurrentText(data.call_to_action.value)

        self.extra_headlines.set_texts(data.extra_headlines)
        self.extra_bodies.set_texts(data.extra_bodies)

    def commit(self, data: CreativeData) -> None:
        items = self.media_list.get_items()

        # Separate pulled items (reuse existing hash) from local items (upload file)
        local_items = [it for it in items if it.source_path]
        pulled_items = [it for it in items if not it.source_path and it.fb_hash]

        if local_items:
            data.media_path = local_items[0].source_path
            data.fb_image_hash = ""
            data.extra_media_paths = [it.source_path for it in local_items[1:]]
        else:
            data.media_path = ""
            data.fb_image_hash = pulled_items[0].fb_hash if pulled_items else ""
            data.extra_media_paths = []

        if not local_items and pulled_items:
            # Primary is pulled; remaining pulled items are extras
            data.fb_extra_image_hashes = [it.fb_hash for it in pulled_items[1:]]
            reuse_pulled = pulled_items[1:]
        else:
            # Primary is local; all pulled items become extras
            data.fb_extra_image_hashes = [it.fb_hash for it in pulled_items]
            reuse_pulled = pulled_items

        data.extra_cached_preview_paths = [it.display_path for it in reuse_pulled]

        # Update pulled_media_dimensions to only keep entries for current items
        new_dims: dict = {}
        for it in items:
            asset_id = it.fb_hash or it.fb_video_id
            if asset_id and it.pulled_dims:
                new_dims[asset_id] = list(it.pulled_dims)
        data.pulled_media_dimensions = new_dims

        data.headline = self.headline_edit.text().strip()
        data.body = self.body_edit.toPlainText().strip()
        data.description = self.description_edit.text().strip()
        data.link_url = self.link_url_edit.text().strip()
        data.link_utm = self.link_utm_edit.text().strip()
        data.display_url = self.display_url_edit.text().strip()
        data.extra_headlines = self.extra_headlines.get_texts()
        data.extra_bodies = self.extra_bodies.get_texts()
        try:
            data.call_to_action = CallToAction(self.cta_combo.currentText())
        except ValueError:
            pass
