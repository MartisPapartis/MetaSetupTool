"""Campaign editor panel — edit a CampaignData object."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLineEdit,
    QComboBox,
    QCheckBox,
    QGroupBox,
    QScrollArea,
    QLabel,
    QPushButton,
    QAbstractSpinBox,
    QDoubleSpinBox,
)

from app.models.campaign_data import CampaignData
from app.models.enums import AdObjective, AdStatus, BidStrategy, PixelEvent, SpecialAdCategory
from app.ui.editors._promo_mixin import _PromotedObjectMixin


_OBJECTIVES = AdObjective.labels()
_STATUSES = [e.value for e in AdStatus]
_BID_STRATEGIES = BidStrategy.labels()
_SPECIAL_CATEGORIES = [e.value for e in SpecialAdCategory]


class CampaignEditorPanel(_PromotedObjectMixin, QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._data: CampaignData | None = None
        self._pixels: list[dict] = []
        self._apps: list[dict] = []
        self._setup_ui()

    def _setup_ui(self) -> None:  # pylint: disable=too-many-locals,too-many-statements
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

        title = QLabel("Campaign Settings")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title)

        # Basic fields
        basic_group = QGroupBox("Basic")
        form = QFormLayout(basic_group)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("e.g. Summer Sale 2025")
        form.addRow("Name *", self.name_edit)

        self.objective_combo = QComboBox()
        self.objective_combo.addItems(_OBJECTIVES)
        form.addRow("Objective *", self.objective_combo)

        self.status_combo = QComboBox()
        self.status_combo.addItems(_STATUSES)
        form.addRow("Status *", self.status_combo)

        self.bid_strategy_combo = QComboBox()
        self.bid_strategy_combo.addItems(_BID_STRATEGIES)
        form.addRow("Bid Strategy", self.bid_strategy_combo)

        layout.addWidget(basic_group)

        # Campaign Budget (CBO / Advantage Campaign Budget)
        budget_group = QGroupBox(
            "Campaign Budget (optional — enables Advantage Campaign Budget)"
        )
        budget_form = QFormLayout(budget_group)
        budget_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.budget_type_combo = QComboBox()
        self.budget_type_combo.addItems(
            ["No Campaign Budget", "Daily Budget", "Lifetime Budget"]
        )
        self.budget_type_combo.currentIndexChanged.connect(self._on_budget_type_changed)
        budget_form.addRow("Budget Type", self.budget_type_combo)

        self.budget_spin = QDoubleSpinBox()
        self.budget_spin.setPrefix("€ ")
        self.budget_spin.setRange(0.01, 9_999_999)
        self.budget_spin.setDecimals(2)
        self.budget_spin.setValue(20.00)
        self.budget_spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.budget_spin.setEnabled(False)
        budget_form.addRow("Amount", self.budget_spin)

        self.spend_cap_spin = QDoubleSpinBox()
        self.spend_cap_spin.setPrefix("€ ")
        self.spend_cap_spin.setRange(0, 9_999_999)
        self.spend_cap_spin.setDecimals(2)
        self.spend_cap_spin.setSpecialValueText("None")
        self.spend_cap_spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        spend_cap_clear_btn = QPushButton("Clear")
        spend_cap_clear_btn.setFixedWidth(48)
        spend_cap_clear_btn.clicked.connect(lambda: self.spend_cap_spin.setValue(0))
        spend_cap_row = QHBoxLayout()
        spend_cap_row.addWidget(self.spend_cap_spin)
        spend_cap_row.addWidget(spend_cap_clear_btn)
        budget_form.addRow("Spend Cap", spend_cap_row)

        self.budget_sharing_check = QCheckBox(
            "Allow ad sets to share up to 20% of budget"
        )
        self.budget_sharing_check.setToolTip(
            "is_adset_budget_sharing_enabled — Meta optimizes spend across ad sets"
        )
        self.budget_sharing_check.setChecked(False)
        budget_form.addRow("Budget Sharing", self.budget_sharing_check)

        budget_hint = QLabel(
            "When set, Meta distributes budget across ad sets automatically "
            "(Advantage Campaign Budget). Bid strategy and budget sharing "
            "only apply when a campaign budget is set."
        )
        budget_hint.setWordWrap(True)
        budget_hint.setStyleSheet("color: gray; font-size: 11px;")
        budget_form.addRow("", budget_hint)

        layout.addWidget(budget_group)

        # Special ad categories
        cat_group = QGroupBox("Special Ad Categories *")
        cat_layout = QVBoxLayout(cat_group)
        cat_layout.addWidget(QLabel("Select all that apply (required):"))
        self._cat_checks: dict[str, QCheckBox] = {}
        for cat in _SPECIAL_CATEGORIES:
            cb = QCheckBox(cat)
            self._cat_checks[cat] = cb
            cat_layout.addWidget(cb)
        layout.addWidget(cat_group)

        # Promoted object (optional — for SALES, APP_PROMOTION, etc.)
        promo_group = QGroupBox("Promoted Object (optional)")
        promo_form = QFormLayout(promo_group)
        promo_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.pixel_id_combo = QComboBox()
        self.pixel_id_combo.setEditable(True)
        self.pixel_id_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.pixel_id_combo.lineEdit().setPlaceholderText("Facebook Pixel ID")
        promo_form.addRow("Pixel ID", self.pixel_id_combo)

        self.pixel_event_combo = QComboBox()
        self.pixel_event_combo.addItem("(none)", "")
        for evt in PixelEvent:
            self.pixel_event_combo.addItem(evt.value, evt.value)
        self.pixel_event_combo.currentIndexChanged.connect(self._on_pixel_event_changed)
        promo_form.addRow("Pixel Event", self.pixel_event_combo)

        self.custom_event_name_edit = QLineEdit()
        self.custom_event_name_edit.setPlaceholderText("e.g. ViewedCheckout")
        self.custom_event_name_edit.setVisible(False)
        promo_form.addRow("Custom Event Name", self.custom_event_name_edit)

        self.app_id_combo = QComboBox()
        self.app_id_combo.setEditable(True)
        self.app_id_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.app_id_combo.lineEdit().setPlaceholderText("Application ID (for app promotion)")
        promo_form.addRow("Application ID", self.app_id_combo)

        self.object_store_url_edit = QLineEdit()
        self.object_store_url_edit.setPlaceholderText("App Store / Play Store URL")
        promo_form.addRow("Object Store URL", self.object_store_url_edit)

        promo_hint = QLabel(
            "Used for OUTCOME_SALES (Pixel) and OUTCOME_APP_PROMOTION objectives. "
            "Select OTHER to specify a fully custom event name."
        )
        promo_hint.setWordWrap(True)
        promo_hint.setStyleSheet("color: gray; font-size: 11px;")
        promo_form.addRow("", promo_hint)

        layout.addWidget(promo_group)

        layout.addStretch()

    def set_meta_resources(self, pixels: list[dict], apps: list[dict]) -> None:
        """Populate Pixel ID and App ID dropdowns from fetched Meta resources."""
        self._pixels = pixels
        self._apps = apps
        self._repopulate_resource_combos()

    def _repopulate_resource_combos(self) -> None:
        self._repopulate_promo_combos(
            self._pixels,
            self._apps,
            current_pixel=self.pixel_id_combo.currentText().strip(),
            current_app=self.app_id_combo.currentText().strip(),
        )

    def _on_budget_type_changed(self, index: int) -> None:
        has_budget = index != 0
        self.budget_spin.setEnabled(has_budget)
        self.budget_sharing_check.setEnabled(has_budget)
        self.bid_strategy_combo.setEnabled(has_budget)

    def load(self, data: CampaignData) -> None:
        self._data = data
        self.name_edit.setText(data.name)
        self.objective_combo.setCurrentText(data.objective.label)
        self.status_combo.setCurrentText(data.status.value)
        self.bid_strategy_combo.setCurrentText(data.bid_strategy.label)
        # Campaign budget type
        if data.daily_budget is not None:
            self.budget_type_combo.setCurrentIndex(1)
            self.budget_spin.setValue(data.daily_budget / 100)
        elif data.lifetime_budget is not None:
            self.budget_type_combo.setCurrentIndex(2)
            self.budget_spin.setValue(data.lifetime_budget / 100)
        else:
            self.budget_type_combo.setCurrentIndex(0)
            self.budget_spin.setValue(20.00)

        self.spend_cap_spin.setValue((data.spend_cap or 0) / 100)
        self.budget_sharing_check.setChecked(data.is_budget_sharing_enabled)

        for cat, cb in self._cat_checks.items():
            cb.setChecked(cat in data.special_ad_categories)

        self._load_promo_fields(data.promoted_object or {})

    def commit(self) -> None:
        if self._data is None:
            return
        self._data.name = self.name_edit.text().strip()
        try:
            self._data.objective = AdObjective.from_label(self.objective_combo.currentText())
        except ValueError:
            pass
        try:
            self._data.status = AdStatus(self.status_combo.currentText())
        except ValueError:
            pass
        try:
            self._data.bid_strategy = BidStrategy.from_label(self.bid_strategy_combo.currentText())
        except ValueError:
            pass

        # Campaign budget
        budget_idx = self.budget_type_combo.currentIndex()
        budget_val = int(self.budget_spin.value() * 100)
        if budget_idx == 1:
            self._data.daily_budget = budget_val
            self._data.lifetime_budget = None
        elif budget_idx == 2:
            self._data.lifetime_budget = budget_val
            self._data.daily_budget = None
        else:
            self._data.daily_budget = None
            self._data.lifetime_budget = None

        cap_val = self.spend_cap_spin.value()
        self._data.spend_cap = int(cap_val * 100) if cap_val > 0 else None
        self._data.is_budget_sharing_enabled = self.budget_sharing_check.isChecked()

        selected_cats = [cat for cat, cb in self._cat_checks.items() if cb.isChecked()]
        self._data.special_ad_categories = selected_cats if selected_cats else ["NONE"]

        self._data.promoted_object = self._commit_promo_fields()
