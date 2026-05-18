"""Bulk edit toolbar shown when multiple tree items are selected."""

from __future__ import annotations

from PyQt6.QtCore import Qt, QDateTime
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QDoubleSpinBox,
    QSpinBox,
    QPushButton,
    QGroupBox,
    QFormLayout,
    QCheckBox,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QAbstractItemView,
    QAbstractSpinBox,
    QScrollArea,
    QDateTimeEdit,
)

from app.models.enums import (
    AdObjective, AdStatus, BidStrategy, BillingEvent,
    CallToAction, OptimizationGoal, PixelEvent, SpecialAdCategory,
    opt_goal_labels, opt_goal_label_to_value,
)
from app.ui.media_library import MediaPickerDialog


class BulkEditPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._node_type = ""
        self._count = 0
        self._pending_media_paths: list[str] = []
        self._setup_ui()

    def _setup_ui(self) -> None:  # pylint: disable=too-many-statements,too-many-locals
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Header (outside scroll)
        header = QWidget()
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(16, 16, 16, 8)
        header_layout.setSpacing(4)

        self.title_label = QLabel("Bulk Edit")
        self.title_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #9cdcfe;")
        header_layout.addWidget(self.title_label)

        self.subtitle_label = QLabel("")
        self.subtitle_label.setStyleSheet("color: #888; font-size: 12px;")
        header_layout.addWidget(self.subtitle_label)

        outer.addWidget(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        outer.addWidget(scroll, stretch=1)

        container = QWidget()
        scroll.setWidget(container)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(16, 8, 16, 16)
        layout.setSpacing(12)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # ── Shared: Status ────────────────────────────────────────────
        status_box = QGroupBox("Status")
        status_form = QFormLayout(status_box)
        self.status_check = QCheckBox("Change status")
        self.status_combo = QComboBox()
        self.status_combo.addItems([s.value for s in AdStatus if s != AdStatus.DELETED])
        self.status_combo.setEnabled(False)
        self.status_check.toggled.connect(self.status_combo.setEnabled)
        status_form.addRow(self.status_check)
        status_form.addRow("New status:", self.status_combo)
        layout.addWidget(status_box)

        # ── Campaign-only fields ──────────────────────────────────────
        self.campaign_box = QGroupBox("Campaign Settings")
        camp_layout = QVBoxLayout(self.campaign_box)
        camp_form = QFormLayout()
        camp_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.camp_objective_check = QCheckBox("Change objective")
        self.camp_objective_combo = QComboBox()
        self.camp_objective_combo.addItems(AdObjective.labels())
        self.camp_objective_combo.setEnabled(False)
        self.camp_objective_check.toggled.connect(self.camp_objective_combo.setEnabled)
        camp_form.addRow(self.camp_objective_check)
        camp_form.addRow("Objective:", self.camp_objective_combo)

        self.camp_bid_strategy_check = QCheckBox("Change bid strategy")
        self.camp_bid_strategy_combo = QComboBox()
        self.camp_bid_strategy_combo.addItems(BidStrategy.labels())
        self.camp_bid_strategy_combo.setEnabled(False)
        self.camp_bid_strategy_check.toggled.connect(self.camp_bid_strategy_combo.setEnabled)
        camp_form.addRow(self.camp_bid_strategy_check)
        camp_form.addRow("Bid strategy:", self.camp_bid_strategy_combo)

        self.camp_budget_check = QCheckBox("Change campaign budget")
        self.camp_budget_type_combo = QComboBox()
        self.camp_budget_type_combo.addItems(["No Campaign Budget", "Daily Budget", "Lifetime Budget"])
        self.camp_budget_type_combo.setEnabled(False)
        self.camp_budget_type_combo.currentIndexChanged.connect(self._on_camp_budget_type_changed)
        self.camp_budget_spin = QDoubleSpinBox()
        self.camp_budget_spin.setPrefix("€ ")
        self.camp_budget_spin.setRange(0.01, 9_999_999)
        self.camp_budget_spin.setDecimals(2)
        self.camp_budget_spin.setValue(20.00)
        self.camp_budget_spin.setEnabled(False)
        self.camp_budget_spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.camp_budget_check.toggled.connect(self._on_camp_budget_check_toggled)
        camp_form.addRow(self.camp_budget_check)
        camp_form.addRow("Budget type:", self.camp_budget_type_combo)
        camp_form.addRow("Amount:", self.camp_budget_spin)

        self.camp_spend_cap_check = QCheckBox("Change spend cap")
        self.camp_spend_cap_spin = QDoubleSpinBox()
        self.camp_spend_cap_spin.setPrefix("€ ")
        self.camp_spend_cap_spin.setRange(0, 9_999_999)
        self.camp_spend_cap_spin.setDecimals(2)
        self.camp_spend_cap_spin.setSpecialValueText("None")
        self.camp_spend_cap_spin.setEnabled(False)
        self.camp_spend_cap_spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.camp_spend_cap_check.toggled.connect(self.camp_spend_cap_spin.setEnabled)
        camp_form.addRow(self.camp_spend_cap_check)
        camp_form.addRow("Spend cap:", self.camp_spend_cap_spin)

        self.camp_budget_sharing_check = QCheckBox("Change budget sharing")
        self.camp_budget_sharing_value = QCheckBox("Allow ad sets to share up to 20% of budget")
        self.camp_budget_sharing_value.setEnabled(False)
        self.camp_budget_sharing_check.toggled.connect(self.camp_budget_sharing_value.setEnabled)
        camp_form.addRow(self.camp_budget_sharing_check)
        camp_form.addRow("", self.camp_budget_sharing_value)

        camp_layout.addLayout(camp_form)

        # Special Ad Categories
        self.camp_cats_check = QCheckBox("Change special ad categories")
        camp_layout.addWidget(self.camp_cats_check)
        cats_hint = QLabel("  Select all that apply (replaces existing):")
        cats_hint.setStyleSheet("color: #888; font-size: 11px;")
        camp_layout.addWidget(cats_hint)
        self.camp_cats_list = QListWidget()
        self.camp_cats_list.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        self.camp_cats_list.setMaximumHeight(90)
        self.camp_cats_list.setEnabled(False)
        for cat in SpecialAdCategory:
            self.camp_cats_list.addItem(cat.value)
        self.camp_cats_check.toggled.connect(self.camp_cats_list.setEnabled)
        camp_layout.addWidget(self.camp_cats_list)

        # Campaign Promoted Object
        camp_promo_group = QGroupBox("Promoted Object")
        camp_promo_form = QFormLayout(camp_promo_group)
        camp_promo_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self.camp_promo_check = QCheckBox("Change promoted object")
        camp_promo_form.addRow(self.camp_promo_check)

        self.camp_pixel_id_combo = QComboBox()
        self.camp_pixel_id_combo.setEditable(True)
        self.camp_pixel_id_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.camp_pixel_id_combo.lineEdit().setPlaceholderText("Pixel ID (leave blank to clear)")
        self.camp_pixel_id_combo.setEnabled(False)
        camp_promo_form.addRow("Pixel ID:", self.camp_pixel_id_combo)

        self.camp_pixel_event_combo = QComboBox()
        self.camp_pixel_event_combo.addItem("(none)", "")
        for evt in PixelEvent:
            self.camp_pixel_event_combo.addItem(evt.value, evt.value)
        self.camp_pixel_event_combo.setEnabled(False)
        self.camp_pixel_event_combo.currentIndexChanged.connect(self._on_camp_pixel_event_changed)
        camp_promo_form.addRow("Pixel Event:", self.camp_pixel_event_combo)

        self.camp_custom_event_edit = QLineEdit()
        self.camp_custom_event_edit.setPlaceholderText("Custom event name")
        self.camp_custom_event_edit.setEnabled(False)
        self.camp_custom_event_edit.setVisible(False)
        camp_promo_form.addRow("Custom Event:", self.camp_custom_event_edit)

        self.camp_app_id_combo = QComboBox()
        self.camp_app_id_combo.setEditable(True)
        self.camp_app_id_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.camp_app_id_combo.lineEdit().setPlaceholderText("Application ID (leave blank to clear)")
        self.camp_app_id_combo.setEnabled(False)
        camp_promo_form.addRow("Application ID:", self.camp_app_id_combo)

        self.camp_store_url_edit = QLineEdit()
        self.camp_store_url_edit.setPlaceholderText("App Store / Play Store URL")
        self.camp_store_url_edit.setEnabled(False)
        camp_promo_form.addRow("Object Store URL:", self.camp_store_url_edit)

        self.camp_promo_check.toggled.connect(self._on_camp_promo_check_toggled)
        camp_layout.addWidget(camp_promo_group)

        layout.addWidget(self.campaign_box)

        # ── Ad Set-only fields ────────────────────────────────────────
        self.adset_box = QGroupBox("Ad Set Settings")
        adset_layout = QVBoxLayout(self.adset_box)
        adset_form = QFormLayout()
        adset_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.adset_opt_goal_check = QCheckBox("Change optimization goal")
        self.adset_opt_goal_combo = QComboBox()
        self.adset_opt_goal_combo.addItems(opt_goal_labels())
        self.adset_opt_goal_combo.setEnabled(False)
        self.adset_opt_goal_check.toggled.connect(self.adset_opt_goal_combo.setEnabled)
        adset_form.addRow(self.adset_opt_goal_check)
        adset_form.addRow("Optimization goal:", self.adset_opt_goal_combo)

        self.adset_billing_event_check = QCheckBox("Change billing event")
        self.adset_billing_event_combo = QComboBox()
        self.adset_billing_event_combo.addItems([e.value for e in BillingEvent])
        self.adset_billing_event_combo.setEnabled(False)
        self.adset_billing_event_check.toggled.connect(self.adset_billing_event_combo.setEnabled)
        adset_form.addRow(self.adset_billing_event_check)
        adset_form.addRow("Billing event:", self.adset_billing_event_combo)

        self.adset_bid_strategy_check = QCheckBox("Change bid strategy")
        self.adset_bid_strategy_combo = QComboBox()
        self.adset_bid_strategy_combo.addItems(BidStrategy.labels())
        self.adset_bid_strategy_combo.setEnabled(False)
        self.adset_bid_strategy_check.toggled.connect(self.adset_bid_strategy_combo.setEnabled)
        adset_form.addRow(self.adset_bid_strategy_check)
        adset_form.addRow("Bid strategy:", self.adset_bid_strategy_combo)

        self.adset_bid_amount_check = QCheckBox("Change bid amount")
        self.adset_bid_amount_spin = QDoubleSpinBox()
        self.adset_bid_amount_spin.setPrefix("€ ")
        self.adset_bid_amount_spin.setRange(0, 9999)
        self.adset_bid_amount_spin.setDecimals(2)
        self.adset_bid_amount_spin.setSpecialValueText("Auto")
        self.adset_bid_amount_spin.setEnabled(False)
        self.adset_bid_amount_spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.adset_bid_amount_check.toggled.connect(self.adset_bid_amount_spin.setEnabled)
        adset_form.addRow(self.adset_bid_amount_check)
        adset_form.addRow("Bid amount:", self.adset_bid_amount_spin)

        self.adset_dynamic_creative_check = QCheckBox("Change dynamic creative")
        self.adset_dynamic_creative_value = QCheckBox("Enable Dynamic Creative")
        self.adset_dynamic_creative_value.setEnabled(False)
        self.adset_dynamic_creative_check.toggled.connect(self.adset_dynamic_creative_value.setEnabled)
        adset_form.addRow(self.adset_dynamic_creative_check)
        adset_form.addRow("", self.adset_dynamic_creative_value)

        self.adset_budget_check = QCheckBox("Change budget")
        self.adset_budget_type_combo = QComboBox()
        self.adset_budget_type_combo.addItems(["Daily Budget", "Lifetime Budget"])
        self.adset_budget_type_combo.setEnabled(False)
        self.adset_budget_spin = QDoubleSpinBox()
        self.adset_budget_spin.setPrefix("€ ")
        self.adset_budget_spin.setRange(0.01, 999_999)
        self.adset_budget_spin.setDecimals(2)
        self.adset_budget_spin.setValue(1.00)
        self.adset_budget_spin.setEnabled(False)
        self.adset_budget_spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.adset_budget_check.toggled.connect(self.adset_budget_type_combo.setEnabled)
        self.adset_budget_check.toggled.connect(self.adset_budget_spin.setEnabled)
        adset_form.addRow(self.adset_budget_check)
        adset_form.addRow("Budget type:", self.adset_budget_type_combo)
        adset_form.addRow("Amount:", self.adset_budget_spin)

        self.adset_start_time_check = QCheckBox("Change start time")
        self.adset_start_dt = QDateTimeEdit()
        self.adset_start_dt.setDisplayFormat("yyyy-MM-dd HH:mm")
        self.adset_start_dt.setDateTime(QDateTime.currentDateTime())
        self.adset_start_dt.setCalendarPopup(True)
        self.adset_start_dt.setEnabled(False)
        self.adset_start_time_check.toggled.connect(self.adset_start_dt.setEnabled)
        adset_form.addRow(self.adset_start_time_check)
        adset_form.addRow("Start time:", self.adset_start_dt)

        self.adset_end_time_check = QCheckBox("Change end time")
        self.adset_end_dt = QDateTimeEdit()
        self.adset_end_dt.setDisplayFormat("yyyy-MM-dd HH:mm")
        self.adset_end_dt.setDateTime(QDateTime.currentDateTime().addDays(30))
        self.adset_end_dt.setCalendarPopup(True)
        self.adset_end_dt.setEnabled(False)
        self.adset_end_time_check.toggled.connect(self.adset_end_dt.setEnabled)
        adset_form.addRow(self.adset_end_time_check)
        adset_form.addRow("End time:", self.adset_end_dt)

        adset_layout.addLayout(adset_form)

        # Targeting sub-group
        targeting_group = QGroupBox("Targeting")
        targeting_form = QFormLayout(targeting_group)
        targeting_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.adset_countries_check = QCheckBox("Change countries")
        self.adset_countries_edit = QLineEdit()
        self.adset_countries_edit.setPlaceholderText("US, GB, LT  (comma-separated ISO codes)")
        self.adset_countries_edit.setEnabled(False)
        self.adset_countries_check.toggled.connect(self.adset_countries_edit.setEnabled)
        targeting_form.addRow(self.adset_countries_check)
        targeting_form.addRow("Countries:", self.adset_countries_edit)

        self.adset_age_min_check = QCheckBox("Change age min")
        self.adset_age_min_spin = QSpinBox()
        self.adset_age_min_spin.setRange(13, 65)
        self.adset_age_min_spin.setValue(18)
        self.adset_age_min_spin.setEnabled(False)
        self.adset_age_min_spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.adset_age_min_check.toggled.connect(self.adset_age_min_spin.setEnabled)
        targeting_form.addRow(self.adset_age_min_check)
        targeting_form.addRow("Age min:", self.adset_age_min_spin)

        self.adset_age_max_check = QCheckBox("Change age max")
        self.adset_age_max_spin = QSpinBox()
        self.adset_age_max_spin.setRange(13, 65)
        self.adset_age_max_spin.setValue(65)
        self.adset_age_max_spin.setEnabled(False)
        self.adset_age_max_spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.adset_age_max_check.toggled.connect(self.adset_age_max_spin.setEnabled)
        targeting_form.addRow(self.adset_age_max_check)
        targeting_form.addRow("Age max:", self.adset_age_max_spin)

        self.adset_gender_check = QCheckBox("Change gender")
        self.adset_gender_combo = QComboBox()
        self.adset_gender_combo.addItems(["All", "Male", "Female"])
        self.adset_gender_combo.setEnabled(False)
        self.adset_gender_check.toggled.connect(self.adset_gender_combo.setEnabled)
        targeting_form.addRow(self.adset_gender_check)
        targeting_form.addRow("Gender:", self.adset_gender_combo)

        self.adset_pub_platforms_check = QCheckBox("Change publisher platforms")
        self.adset_pub_platforms_edit = QLineEdit()
        self.adset_pub_platforms_edit.setPlaceholderText("facebook, instagram, …  (blank = all)")
        self.adset_pub_platforms_edit.setEnabled(False)
        self.adset_pub_platforms_check.toggled.connect(self.adset_pub_platforms_edit.setEnabled)
        targeting_form.addRow(self.adset_pub_platforms_check)
        targeting_form.addRow("Publisher platforms:", self.adset_pub_platforms_edit)

        self.adset_device_platforms_check = QCheckBox("Change device platforms")
        self.adset_device_platforms_edit = QLineEdit()
        self.adset_device_platforms_edit.setPlaceholderText("mobile, desktop  (blank = all)")
        self.adset_device_platforms_edit.setEnabled(False)
        self.adset_device_platforms_check.toggled.connect(self.adset_device_platforms_edit.setEnabled)
        targeting_form.addRow(self.adset_device_platforms_check)
        targeting_form.addRow("Device platforms:", self.adset_device_platforms_edit)

        self.adset_positions_check = QCheckBox("Change positions")
        self.adset_positions_edit = QLineEdit()
        self.adset_positions_edit.setPlaceholderText("feed, story, reels, …  (blank = all)")
        self.adset_positions_edit.setEnabled(False)
        self.adset_positions_check.toggled.connect(self.adset_positions_edit.setEnabled)
        targeting_form.addRow(self.adset_positions_check)
        targeting_form.addRow("Positions:", self.adset_positions_edit)

        adset_layout.addWidget(targeting_group)

        # Audiences sub-group
        aud_group = QGroupBox("Audiences")
        aud_layout = QVBoxLayout(aud_group)

        self.adset_aud_check = QCheckBox("Change audiences (replaces existing)")
        aud_layout.addWidget(self.adset_aud_check)

        aud_hint = QLabel("Populated from the Ad Set editor's loaded audience list.")
        aud_hint.setStyleSheet("color: #888; font-size: 11px;")
        aud_hint.setWordWrap(True)
        aud_layout.addWidget(aud_hint)

        aud_layout.addWidget(QLabel("Custom Audiences (include):"))
        self.adset_custom_aud_list = QListWidget()
        self.adset_custom_aud_list.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        self.adset_custom_aud_list.setMaximumHeight(90)
        self.adset_custom_aud_list.setEnabled(False)
        aud_layout.addWidget(self.adset_custom_aud_list)

        aud_layout.addWidget(QLabel("Lookalike Audiences (include):"))
        self.adset_lookalike_aud_list = QListWidget()
        self.adset_lookalike_aud_list.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        self.adset_lookalike_aud_list.setMaximumHeight(90)
        self.adset_lookalike_aud_list.setEnabled(False)
        aud_layout.addWidget(self.adset_lookalike_aud_list)

        aud_layout.addWidget(QLabel("Excluded Audiences:"))
        self.adset_excluded_aud_list = QListWidget()
        self.adset_excluded_aud_list.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        self.adset_excluded_aud_list.setMaximumHeight(90)
        self.adset_excluded_aud_list.setEnabled(False)
        aud_layout.addWidget(self.adset_excluded_aud_list)

        self.adset_aud_check.toggled.connect(self.adset_custom_aud_list.setEnabled)
        self.adset_aud_check.toggled.connect(self.adset_lookalike_aud_list.setEnabled)
        self.adset_aud_check.toggled.connect(self.adset_excluded_aud_list.setEnabled)

        adset_layout.addWidget(aud_group)

        # DSA
        dsa_group = QGroupBox("DSA Compliance")
        dsa_form = QFormLayout(dsa_group)
        dsa_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.adset_dsa_payor_check = QCheckBox("Change DSA payor")
        self.adset_dsa_payor_combo = QComboBox()
        self.adset_dsa_payor_combo.setEditable(True)
        self.adset_dsa_payor_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.adset_dsa_payor_combo.lineEdit().setPlaceholderText("Who pays for the ad")
        self.adset_dsa_payor_combo.setEnabled(False)
        self.adset_dsa_payor_check.toggled.connect(self.adset_dsa_payor_combo.setEnabled)
        dsa_form.addRow(self.adset_dsa_payor_check)
        dsa_form.addRow("DSA Payor:", self.adset_dsa_payor_combo)

        self.adset_dsa_beneficiary_check = QCheckBox("Change DSA beneficiary")
        self.adset_dsa_beneficiary_combo = QComboBox()
        self.adset_dsa_beneficiary_combo.setEditable(True)
        self.adset_dsa_beneficiary_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.adset_dsa_beneficiary_combo.lineEdit().setPlaceholderText("Who benefits from the ad")
        self.adset_dsa_beneficiary_combo.setEnabled(False)
        self.adset_dsa_beneficiary_check.toggled.connect(self.adset_dsa_beneficiary_combo.setEnabled)
        dsa_form.addRow(self.adset_dsa_beneficiary_check)
        dsa_form.addRow("DSA Beneficiary:", self.adset_dsa_beneficiary_combo)

        adset_layout.addWidget(dsa_group)

        # Ad Set Promoted Object
        adset_promo_group = QGroupBox("Promoted Object")
        adset_promo_form = QFormLayout(adset_promo_group)
        adset_promo_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self.adset_promo_check = QCheckBox("Change promoted object")
        adset_promo_form.addRow(self.adset_promo_check)

        self.adset_pixel_id_combo = QComboBox()
        self.adset_pixel_id_combo.setEditable(True)
        self.adset_pixel_id_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.adset_pixel_id_combo.lineEdit().setPlaceholderText("Pixel ID (leave blank to clear)")
        self.adset_pixel_id_combo.setEnabled(False)
        adset_promo_form.addRow("Pixel ID:", self.adset_pixel_id_combo)

        self.adset_pixel_event_combo = QComboBox()
        self.adset_pixel_event_combo.addItem("(none)", "")
        for evt in PixelEvent:
            self.adset_pixel_event_combo.addItem(evt.value, evt.value)
        self.adset_pixel_event_combo.setEnabled(False)
        self.adset_pixel_event_combo.currentIndexChanged.connect(self._on_adset_pixel_event_changed)
        adset_promo_form.addRow("Pixel Event:", self.adset_pixel_event_combo)

        self.adset_custom_event_edit = QLineEdit()
        self.adset_custom_event_edit.setPlaceholderText("Custom event name")
        self.adset_custom_event_edit.setEnabled(False)
        self.adset_custom_event_edit.setVisible(False)
        adset_promo_form.addRow("Custom Event:", self.adset_custom_event_edit)

        self.adset_app_id_combo = QComboBox()
        self.adset_app_id_combo.setEditable(True)
        self.adset_app_id_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.adset_app_id_combo.lineEdit().setPlaceholderText("Application ID (leave blank to clear)")
        self.adset_app_id_combo.setEnabled(False)
        adset_promo_form.addRow("Application ID:", self.adset_app_id_combo)

        self.adset_store_url_edit = QLineEdit()
        self.adset_store_url_edit.setPlaceholderText("App Store / Play Store URL")
        self.adset_store_url_edit.setEnabled(False)
        adset_promo_form.addRow("Object Store URL:", self.adset_store_url_edit)

        self.adset_promo_check.toggled.connect(self._on_adset_promo_check_toggled)
        adset_layout.addWidget(adset_promo_group)

        layout.addWidget(self.adset_box)

        # ── Ad creative group (ads only) ──────────────────────────────
        self.creative_box = QGroupBox("Creative")
        creative_form = QFormLayout(self.creative_box)
        creative_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.headline_check = QCheckBox("Set headline")
        self.headline_edit = QLineEdit()
        self.headline_edit.setEnabled(False)
        self.headline_check.toggled.connect(self.headline_edit.setEnabled)
        creative_form.addRow(self.headline_check)
        creative_form.addRow("Headline:", self.headline_edit)

        self.body_check = QCheckBox("Set primary text")
        self.body_edit = QLineEdit()
        self.body_edit.setEnabled(False)
        self.body_check.toggled.connect(self.body_edit.setEnabled)
        creative_form.addRow(self.body_check)
        creative_form.addRow("Primary text:", self.body_edit)

        self.description_check = QCheckBox("Set description")
        self.description_edit = QLineEdit()
        self.description_edit.setEnabled(False)
        self.description_check.toggled.connect(self.description_edit.setEnabled)
        creative_form.addRow(self.description_check)
        creative_form.addRow("Description:", self.description_edit)

        self.link_url_check = QCheckBox("Set link URL")
        self.link_url_edit = QLineEdit()
        self.link_url_edit.setEnabled(False)
        self.link_url_check.toggled.connect(self.link_url_edit.setEnabled)
        creative_form.addRow(self.link_url_check)
        creative_form.addRow("Link URL:", self.link_url_edit)

        self.cta_check = QCheckBox("Set call to action")
        self.cta_combo = QComboBox()
        self.cta_combo.addItems([c.value for c in CallToAction])
        self.cta_combo.setCurrentText(CallToAction.LEARN_MORE.value)
        self.cta_combo.setEnabled(False)
        self.cta_check.toggled.connect(self.cta_combo.setEnabled)
        creative_form.addRow(self.cta_check)
        creative_form.addRow("Call to action:", self.cta_combo)

        layout.addWidget(self.creative_box)

        # ── Media group (ads only) ────────────────────────────────────
        self.media_box = QGroupBox("Add Media from Library")
        media_layout = QVBoxLayout(self.media_box)

        self.media_label = QLabel("No media selected")
        self.media_label.setStyleSheet("color: #888; font-size: 11px;")
        media_layout.addWidget(self.media_label)

        media_btn_row = QHBoxLayout()
        self.pick_media_btn = QPushButton("Pick from Media Library…")
        self.pick_media_btn.clicked.connect(self._pick_media)
        self.clear_media_btn = QPushButton("Clear")
        self.clear_media_btn.clicked.connect(self._clear_media)
        media_btn_row.addWidget(self.pick_media_btn)
        media_btn_row.addWidget(self.clear_media_btn)
        media_layout.addLayout(media_btn_row)

        layout.addWidget(self.media_box)
        layout.addStretch()

        # Apply button (outside scroll)
        btn_widget = QWidget()
        btn_layout = QHBoxLayout(btn_widget)
        btn_layout.setContentsMargins(16, 8, 16, 16)
        self.apply_btn = QPushButton("Apply to Selected")
        self.apply_btn.setMinimumHeight(32)
        btn_layout.addStretch()
        btn_layout.addWidget(self.apply_btn)
        outer.addWidget(btn_widget)

    # ── resource population ────────────────────────────────────────────

    def set_meta_resources(self, pixels: list[dict], apps: list[dict]) -> None:
        """Populate Pixel ID and App ID dropdowns for both campaign and adset sections."""
        for pixel_combo in (self.camp_pixel_id_combo, self.adset_pixel_id_combo):
            current = pixel_combo.currentText().strip()
            pixel_combo.clear()
            pixel_combo.addItem("", "")
            for p in pixels:
                label = f"{p['name']}  ({p['id']})" if p.get("name") else p["id"]
                pixel_combo.addItem(label, p["id"])
            if current:
                pixel_combo.setCurrentText(current)

        for app_combo in (self.camp_app_id_combo, self.adset_app_id_combo):
            current = app_combo.currentText().strip()
            app_combo.clear()
            app_combo.addItem("", "")
            for a in apps:
                label = f"{a['name']}  ({a['id']})" if a.get("name") else a["id"]
                app_combo.addItem(label, a["id"])
            if current:
                app_combo.setCurrentText(current)

    def set_audience_data(
        self,
        custom: list[dict],
        lookalike: list[dict],
        dsa_payors: list[str],
        dsa_beneficiaries: list[str],
    ) -> None:
        """Populate audience lists and DSA dropdowns from the adset editor's loaded data."""
        self._populate_audience_list(self.adset_custom_aud_list, custom)
        self._populate_audience_list(self.adset_lookalike_aud_list, lookalike)
        self._populate_audience_list(self.adset_excluded_aud_list, custom + lookalike)

        for combo, values in (
            (self.adset_dsa_payor_combo, dsa_payors),
            (self.adset_dsa_beneficiary_combo, dsa_beneficiaries),
        ):
            current = combo.currentText()
            combo.clear()
            combo.addItem("")
            for v in values:
                combo.addItem(v)
            if current:
                combo.setCurrentText(current)

    @staticmethod
    def _populate_audience_list(list_widget: QListWidget, audiences: list[dict]) -> None:
        list_widget.clear()
        for aud in audiences:
            item = QListWidgetItem(f"{aud.get('name', '')}  [{aud['id']}]")
            item.setData(Qt.ItemDataRole.UserRole, aud["id"])
            list_widget.addItem(item)

    # ── slots ──────────────────────────────────────────────────────────

    def _on_camp_budget_check_toggled(self, checked: bool) -> None:
        self.camp_budget_type_combo.setEnabled(checked)
        if checked:
            self._on_camp_budget_type_changed(self.camp_budget_type_combo.currentIndex())
        else:
            self.camp_budget_spin.setEnabled(False)

    def _on_camp_budget_type_changed(self, index: int) -> None:
        if self.camp_budget_check.isChecked():
            self.camp_budget_spin.setEnabled(index != 0)

    def _on_camp_promo_check_toggled(self, checked: bool) -> None:
        for w in (self.camp_pixel_id_combo, self.camp_pixel_event_combo,
                  self.camp_app_id_combo, self.camp_store_url_edit):
            w.setEnabled(checked)
        if checked:
            is_other = self.camp_pixel_event_combo.currentData() == PixelEvent.OTHER.value
            self.camp_custom_event_edit.setVisible(is_other)
            self.camp_custom_event_edit.setEnabled(is_other)
        else:
            self.camp_custom_event_edit.setVisible(False)

    def _on_camp_pixel_event_changed(self, _index: int) -> None:
        is_other = self.camp_pixel_event_combo.currentData() == PixelEvent.OTHER.value
        self.camp_custom_event_edit.setVisible(is_other)
        self.camp_custom_event_edit.setEnabled(is_other and self.camp_promo_check.isChecked())

    def _on_adset_promo_check_toggled(self, checked: bool) -> None:
        for w in (self.adset_pixel_id_combo, self.adset_pixel_event_combo,
                  self.adset_app_id_combo, self.adset_store_url_edit):
            w.setEnabled(checked)
        if checked:
            is_other = self.adset_pixel_event_combo.currentData() == PixelEvent.OTHER.value
            self.adset_custom_event_edit.setVisible(is_other)
            self.adset_custom_event_edit.setEnabled(is_other)
        else:
            self.adset_custom_event_edit.setVisible(False)

    def _on_adset_pixel_event_changed(self, _index: int) -> None:
        is_other = self.adset_pixel_event_combo.currentData() == PixelEvent.OTHER.value
        self.adset_custom_event_edit.setVisible(is_other)
        self.adset_custom_event_edit.setEnabled(is_other and self.adset_promo_check.isChecked())

    def _pick_media(self) -> None:
        dlg = MediaPickerDialog(parent=self, multi_select=True)
        if dlg.exec():
            paths = dlg.selected_paths or []
            if paths:
                self._pending_media_paths = paths
                names = [p.split("/")[-1].split("\\")[-1] for p in paths]
                preview = ", ".join(names[:3])
                if len(names) > 3:
                    preview += f" (+{len(names) - 3} more)"
                self.media_label.setText(preview)
                self.media_label.setStyleSheet("color: #d4d4d4; font-size: 11px;")

    def _clear_media(self) -> None:
        self._pending_media_paths = []
        self.media_label.setText("No media selected")
        self.media_label.setStyleSheet("color: #888; font-size: 11px;")

    # ── public API ─────────────────────────────────────────────────────

    def configure(self, node_type: str, count: int) -> None:
        self._node_type = node_type
        self._count = count
        _labels = {"campaign": "campaigns", "adset": "ad sets", "ad": "ads"}
        type_label = _labels.get(node_type, node_type)
        self.title_label.setText("Bulk Edit")
        self.subtitle_label.setText(f"{count} {type_label} selected — changes apply to all")
        self.campaign_box.setVisible(node_type == "campaign")
        self.adset_box.setVisible(node_type == "adset")
        self.creative_box.setVisible(node_type == "ad")
        self.media_box.setVisible(node_type == "ad")
        self._reset_all()

    def _reset_all(self) -> None:
        for cb in (
            self.status_check,
            self.camp_objective_check, self.camp_bid_strategy_check,
            self.camp_budget_check, self.camp_spend_cap_check,
            self.camp_budget_sharing_check, self.camp_cats_check,
            self.camp_promo_check,
            self.adset_opt_goal_check, self.adset_billing_event_check,
            self.adset_bid_strategy_check, self.adset_bid_amount_check,
            self.adset_dynamic_creative_check, self.adset_budget_check,
            self.adset_start_time_check, self.adset_end_time_check,
            self.adset_countries_check, self.adset_age_min_check,
            self.adset_age_max_check, self.adset_gender_check,
            self.adset_pub_platforms_check, self.adset_device_platforms_check,
            self.adset_positions_check, self.adset_aud_check,
            self.adset_dsa_payor_check, self.adset_dsa_beneficiary_check,
            self.adset_promo_check,
            self.headline_check, self.body_check, self.description_check,
            self.link_url_check, self.cta_check,
        ):
            cb.setChecked(False)
        self.camp_cats_list.clearSelection()
        self.adset_custom_aud_list.clearSelection()
        self.adset_lookalike_aud_list.clearSelection()
        self.adset_excluded_aud_list.clearSelection()
        self._clear_media()

    # ── getters (shared) ───────────────────────────────────────────────

    def get_new_status(self) -> AdStatus | None:
        if not self.status_check.isChecked():
            return None
        return AdStatus(self.status_combo.currentText())

    # ── getters (campaign) ─────────────────────────────────────────────

    def get_campaign_objective(self) -> AdObjective | None:
        if not self.camp_objective_check.isChecked():
            return None
        try:
            return AdObjective.from_label(self.camp_objective_combo.currentText())
        except ValueError:
            return None

    def get_campaign_bid_strategy(self) -> BidStrategy | None:
        if not self.camp_bid_strategy_check.isChecked():
            return None
        try:
            return BidStrategy.from_label(self.camp_bid_strategy_combo.currentText())
        except ValueError:
            return None

    def get_campaign_budget(self) -> tuple[str, int | None] | None:
        """Returns (budget_type, amount_cents) or None if not checked.
        budget_type is 'none', 'daily', or 'lifetime'.
        """
        if not self.camp_budget_check.isChecked():
            return None
        idx = self.camp_budget_type_combo.currentIndex()
        if idx == 0:
            return ("none", None)
        amount = int(self.camp_budget_spin.value() * 100)
        return ("daily" if idx == 1 else "lifetime", amount)

    def get_campaign_spend_cap(self) -> int | None:
        """Returns cents, 0 means clear, None means no change."""
        if not self.camp_spend_cap_check.isChecked():
            return None
        val = self.camp_spend_cap_spin.value()
        return int(val * 100) if val > 0 else 0

    def get_campaign_budget_sharing(self) -> bool | None:
        if not self.camp_budget_sharing_check.isChecked():
            return None
        return self.camp_budget_sharing_value.isChecked()

    def get_campaign_special_categories(self) -> list[str] | None:
        if not self.camp_cats_check.isChecked():
            return None
        selected = [
            self.camp_cats_list.item(i).text()
            for i in range(self.camp_cats_list.count())
            if self.camp_cats_list.item(i).isSelected()
        ]
        return selected if selected else ["NONE"]

    def get_campaign_promoted_object(self) -> dict | None:
        if not self.camp_promo_check.isChecked():
            return None
        promo: dict = {}
        pixel_id = self._combo_id(self.camp_pixel_id_combo)
        if pixel_id:
            promo["pixel_id"] = pixel_id
        event_val = self.camp_pixel_event_combo.currentData()
        if event_val:
            promo["custom_event_type"] = event_val
            if event_val == PixelEvent.OTHER.value:
                custom = self.camp_custom_event_edit.text().strip()
                if custom:
                    promo["custom_event_str"] = custom
        app_id = self._combo_id(self.camp_app_id_combo)
        if app_id:
            promo["application_id"] = app_id
        store_url = self.camp_store_url_edit.text().strip()
        if store_url:
            promo["object_store_url"] = store_url
        return promo

    # ── getters (adset) ────────────────────────────────────────────────

    def get_adset_opt_goal(self) -> OptimizationGoal | None:
        if not self.adset_opt_goal_check.isChecked():
            return None
        try:
            return OptimizationGoal(opt_goal_label_to_value(self.adset_opt_goal_combo.currentText()))
        except (ValueError, KeyError):
            return None

    def get_adset_billing_event(self) -> BillingEvent | None:
        if not self.adset_billing_event_check.isChecked():
            return None
        try:
            return BillingEvent(self.adset_billing_event_combo.currentText())
        except ValueError:
            return None

    def get_adset_bid_strategy(self) -> BidStrategy | None:
        if not self.adset_bid_strategy_check.isChecked():
            return None
        try:
            return BidStrategy.from_label(self.adset_bid_strategy_combo.currentText())
        except ValueError:
            return None

    def get_adset_bid_amount(self) -> int | None:
        if not self.adset_bid_amount_check.isChecked():
            return None
        val = self.adset_bid_amount_spin.value()
        return int(val * 100) if val > 0 else None

    def get_adset_dynamic_creative(self) -> bool | None:
        if not self.adset_dynamic_creative_check.isChecked():
            return None
        return self.adset_dynamic_creative_value.isChecked()

    def get_adset_budget(self) -> tuple[str, int] | None:
        """Returns ('daily'|'lifetime', amount_cents) or None if not checked."""
        if not self.adset_budget_check.isChecked():
            return None
        is_lifetime = self.adset_budget_type_combo.currentIndex() == 1
        amount = int(self.adset_budget_spin.value() * 100)
        return ("lifetime" if is_lifetime else "daily", amount)

    def get_adset_start_time(self) -> str | None:
        if not self.adset_start_time_check.isChecked():
            return None
        return (
            self.adset_start_dt.dateTime()
            .toString("yyyy-MM-ddTHH:mm:sszzz")
            .replace("zzz", "+0000")[:16]
            + ":00+0000"
        )

    def get_adset_end_time(self) -> str | None:
        if not self.adset_end_time_check.isChecked():
            return None
        return (
            self.adset_end_dt.dateTime()
            .toString("yyyy-MM-ddTHH:mm:sszzz")
            .replace("zzz", "+0000")[:16]
            + ":00+0000"
        )

    def get_adset_countries(self) -> list[str] | None:
        if not self.adset_countries_check.isChecked():
            return None
        return [c.strip().upper() for c in self.adset_countries_edit.text().split(",") if c.strip()]

    def get_adset_age_min(self) -> int | None:
        return self.adset_age_min_spin.value() if self.adset_age_min_check.isChecked() else None

    def get_adset_age_max(self) -> int | None:
        return self.adset_age_max_spin.value() if self.adset_age_max_check.isChecked() else None

    def get_adset_gender(self) -> str | None:
        return self.adset_gender_combo.currentText() if self.adset_gender_check.isChecked() else None

    def get_adset_publisher_platforms(self) -> list[str] | None:
        if not self.adset_pub_platforms_check.isChecked():
            return None
        return [p.strip().lower() for p in self.adset_pub_platforms_edit.text().split(",") if p.strip()]

    def get_adset_device_platforms(self) -> list[str] | None:
        if not self.adset_device_platforms_check.isChecked():
            return None
        return [p.strip().lower() for p in self.adset_device_platforms_edit.text().split(",") if p.strip()]

    def get_adset_positions(self) -> list[str] | None:
        if not self.adset_positions_check.isChecked():
            return None
        return [p.strip().lower() for p in self.adset_positions_edit.text().split(",") if p.strip()]

    def get_adset_audiences(self) -> tuple[list[dict], list[dict]] | None:
        """Returns (include_ids, exclude_ids) as [{id: ...}] lists, or None if not checked."""
        if not self.adset_aud_check.isChecked():
            return None
        include: list[dict] = []
        seen: set[str] = set()
        for lst in (self.adset_custom_aud_list, self.adset_lookalike_aud_list):
            for i in range(lst.count()):
                item = lst.item(i)
                if item.isSelected():
                    aud_id = item.data(Qt.ItemDataRole.UserRole)
                    if aud_id not in seen:
                        include.append({"id": aud_id})
                        seen.add(aud_id)
        exclude: list[dict] = []
        for i in range(self.adset_excluded_aud_list.count()):
            item = self.adset_excluded_aud_list.item(i)
            if item.isSelected():
                exclude.append({"id": item.data(Qt.ItemDataRole.UserRole)})
        return include, exclude

    def get_adset_dsa_payor(self) -> str | None:
        return self.adset_dsa_payor_combo.currentText().strip() if self.adset_dsa_payor_check.isChecked() else None

    def get_adset_dsa_beneficiary(self) -> str | None:
        return self.adset_dsa_beneficiary_combo.currentText().strip() if self.adset_dsa_beneficiary_check.isChecked() else None

    def get_adset_promoted_object(self) -> dict | None:
        if not self.adset_promo_check.isChecked():
            return None
        promo: dict = {}
        pixel_id = self._combo_id(self.adset_pixel_id_combo)
        if pixel_id:
            promo["pixel_id"] = pixel_id
        event_val = self.adset_pixel_event_combo.currentData()
        if event_val:
            promo["custom_event_type"] = event_val
            if event_val == PixelEvent.OTHER.value:
                custom = self.adset_custom_event_edit.text().strip()
                if custom:
                    promo["custom_event_str"] = custom
        app_id = self._combo_id(self.adset_app_id_combo)
        if app_id:
            promo["application_id"] = app_id
        store_url = self.adset_store_url_edit.text().strip()
        if store_url:
            promo["object_store_url"] = store_url
        return promo

    # ── getters (ad creative) ──────────────────────────────────────────

    def get_new_headline(self) -> str | None:
        return self.headline_edit.text().strip() if self.headline_check.isChecked() else None

    def get_new_body(self) -> str | None:
        return self.body_edit.text().strip() if self.body_check.isChecked() else None

    def get_new_description(self) -> str | None:
        return self.description_edit.text().strip() if self.description_check.isChecked() else None

    def get_new_link_url(self) -> str | None:
        return self.link_url_edit.text().strip() if self.link_url_check.isChecked() else None

    def get_new_cta(self) -> CallToAction | None:
        if not self.cta_check.isChecked():
            return None
        return CallToAction(self.cta_combo.currentText())

    def get_media_paths(self) -> list[str]:
        return list(self._pending_media_paths)

    # ── helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _combo_id(combo: QComboBox) -> str:
        """Return stored data ID from combo, falling back to typed text."""
        data = combo.currentData()
        if data:
            return str(data)
        return combo.currentText().strip()
