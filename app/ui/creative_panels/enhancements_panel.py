"""Advantage+ creative enhancements toggle panel."""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QCheckBox,
    QLabel,
    QGroupBox,
    QPushButton,
)

# Enhancements shown in the UI, grouped by category.
# Key = API field name, Value = human-friendly label.
ENHANCEMENT_GROUPS: dict[str, list[tuple[str, str]]] = {
    "Media": [
        ("adapt_to_placement", "Adapt media to placement"),
        ("image_brightness_and_contrast", "Visual touch-ups (brightness / contrast)"),
        ("image_touchups", "Image auto-crop & enhance"),
        ("image_uncrop", "AI image expansion (uncrop)"),
        ("video_auto_crop", "Video auto-crop for placements"),
    ],
    "AI-Generated": [
        ("image_background_gen", "AI background generation"),
        ("image_templates", "Text overlay templates"),
        ("image_animation", "Animate static images"),
        ("text_generation", "AI text generation"),
    ],
    "Text & Display": [
        ("text_optimizations", "Dynamic text placement"),
        ("enhance_cta", "Enhanced call-to-action"),
        ("inline_comment", "Show relevant comments"),
    ],
}

# Flat list of all feature keys for iteration
ALL_FEATURES: list[str] = [
    key for group in ENHANCEMENT_GROUPS.values() for key, _ in group
]


class EnhancementsPanel(QWidget):
    """Checkbox panel for Advantage+ creative enhancements."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._checkboxes: dict[str, QCheckBox] = {}
        self._setup_ui()

    def _setup_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(8)

        # Batch toggle buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        all_on_btn = QPushButton("All On")
        all_on_btn.setFixedWidth(60)
        all_on_btn.clicked.connect(self._all_on)
        all_off_btn = QPushButton("All Off")
        all_off_btn.setFixedWidth(60)
        all_off_btn.clicked.connect(self._all_off)
        btn_row.addWidget(all_on_btn)
        btn_row.addWidget(all_off_btn)
        btn_row.addStretch()
        outer.addLayout(btn_row)

        for group_name, features in ENHANCEMENT_GROUPS.items():
            group = QGroupBox(group_name)
            group.setStyleSheet(
                "QGroupBox { font-weight: bold; } "
                "QGroupBox::title { padding: 2px 6px; }"
            )
            group_layout = QVBoxLayout(group)
            group_layout.setSpacing(4)
            group_layout.setContentsMargins(8, 12, 8, 8)

            for key, label in features:
                cb = QCheckBox(label)
                cb.setToolTip(f"API field: {key}")
                self._checkboxes[key] = cb
                group_layout.addWidget(cb)

            outer.addWidget(group)

        hint = QLabel(
            "Checked = OPT_IN (Meta may modify your creative). Unchecked = OPT_OUT."
        )
        hint.setStyleSheet("color: gray; font-size: 11px;")
        hint.setWordWrap(True)
        outer.addWidget(hint)

    def _all_on(self) -> None:
        for cb in self._checkboxes.values():
            cb.setChecked(True)

    def _all_off(self) -> None:
        for cb in self._checkboxes.values():
            cb.setChecked(False)

    def load(self, enhancements: dict) -> None:
        """Load enhancement settings — checked if OPT_IN, unchecked otherwise."""
        for key, cb in self._checkboxes.items():
            cb.setChecked(enhancements.get(key) == "OPT_IN")

    def commit(self) -> dict:
        """Return a dict of {feature: "OPT_IN"|"OPT_OUT"} for all features."""
        result: dict[str, str] = {}
        for key, cb in self._checkboxes.items():
            result[key] = "OPT_IN" if cb.isChecked() else "OPT_OUT"
        return result
