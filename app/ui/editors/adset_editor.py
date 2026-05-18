"""Ad Set editor panel — edit an AdSetData object."""

from __future__ import annotations

from PyQt6.QtCore import Qt, QDateTime
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QFormLayout,
    QLineEdit,
    QComboBox,
    QGroupBox,
    QScrollArea,
    QLabel,
    QDoubleSpinBox,
    QRadioButton,
    QButtonGroup,
    QHBoxLayout,
    QSpinBox,
    QDateTimeEdit,
    QAbstractSpinBox,
    QCheckBox,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QAbstractItemView,
)

from app.models.campaign_data import AdSetData
from app.models.enums import (
    AdStatus, BidStrategy, OptimizationGoal, BillingEvent, PixelEvent,
    opt_goal_labels, opt_goal_label_to_value, opt_goal_value_to_label,
)
from app.ui.editors._promo_mixin import _PromotedObjectMixin


_STATUSES = [e.value for e in AdStatus]
_OPT_GOALS = opt_goal_labels()
_BILLING_EVENTS = [e.value for e in BillingEvent]
_BID_STRATEGIES = BidStrategy.labels()


class AdSetEditorPanel(_PromotedObjectMixin, QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._data: AdSetData | None = None
        self._client = None
        self._audience_worker = None
        self._available_custom: list[dict] = []
        self._available_lookalike: list[dict] = []
        self._available_presets: list[dict] = []
        self._pending_include_ids: set[str] = set()
        self._pending_exclude_ids: set[str] = set()
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

        title = QLabel("Ad Set Settings")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title)

        # Basic
        basic_group = QGroupBox("Basic")
        form = QFormLayout(basic_group)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("e.g. 18-35 US Women")
        form.addRow("Name *", self.name_edit)

        self.status_combo = QComboBox()
        self.status_combo.addItems(_STATUSES)
        form.addRow("Status *", self.status_combo)

        self.opt_goal_combo = QComboBox()
        self.opt_goal_combo.addItems(_OPT_GOALS)
        form.addRow("Optimization Goal *", self.opt_goal_combo)

        self.billing_event_combo = QComboBox()
        self.billing_event_combo.addItems(_BILLING_EVENTS)
        form.addRow("Billing Event *", self.billing_event_combo)

        self.bid_strategy_combo = QComboBox()
        self.bid_strategy_combo.addItems(_BID_STRATEGIES)
        form.addRow("Bid Strategy", self.bid_strategy_combo)

        self.bid_amount_spin = QDoubleSpinBox()
        self.bid_amount_spin.setPrefix("€ ")
        self.bid_amount_spin.setRange(0, 9999)
        self.bid_amount_spin.setDecimals(2)
        self.bid_amount_spin.setSpecialValueText("Auto")
        self.bid_amount_spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        form.addRow("Bid Amount", self.bid_amount_spin)

        self.dynamic_creative_check = QCheckBox("Enable Dynamic Creative")
        form.addRow("", self.dynamic_creative_check)

        layout.addWidget(basic_group)

        # Budget
        budget_group = QGroupBox("Budget *")
        budget_layout = QVBoxLayout(budget_group)

        radio_row = QHBoxLayout()
        self.daily_radio = QRadioButton("Daily Budget")
        self.lifetime_radio = QRadioButton("Lifetime Budget")
        self.daily_radio.setChecked(True)
        self._budget_group = QButtonGroup()
        self._budget_group.addButton(self.daily_radio)
        self._budget_group.addButton(self.lifetime_radio)
        radio_row.addWidget(self.daily_radio)
        radio_row.addWidget(self.lifetime_radio)
        radio_row.addStretch()
        budget_layout.addLayout(radio_row)

        self.budget_spin = QDoubleSpinBox()
        self.budget_spin.setPrefix("€ ")
        self.budget_spin.setRange(0, 999_999)
        self.budget_spin.setDecimals(2)
        self.budget_spin.setValue(0)
        self.budget_spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        budget_layout.addWidget(self.budget_spin)

        layout.addWidget(budget_group)

        # Schedule
        sched_group = QGroupBox("Schedule")
        sched_form = QFormLayout(sched_group)
        sched_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.start_dt = QDateTimeEdit()
        self.start_dt.setDisplayFormat("yyyy-MM-dd HH:mm")
        self.start_dt.setDateTime(QDateTime.currentDateTime())
        self.start_dt.setCalendarPopup(True)
        sched_form.addRow("Start Time", self.start_dt)

        self.end_dt = QDateTimeEdit()
        self.end_dt.setDisplayFormat("yyyy-MM-dd HH:mm")
        self.end_dt.setDateTime(QDateTime.currentDateTime().addDays(30))
        self.end_dt.setCalendarPopup(True)
        sched_form.addRow("End Time (optional)", self.end_dt)

        self.no_end_check_label = QLabel(
            "Leave End Time as-is to include it. Clear the field in session JSON to omit."
        )
        self.no_end_check_label.setStyleSheet("color: gray; font-size: 11px;")
        sched_form.addRow("", self.no_end_check_label)

        layout.addWidget(sched_group)

        # Targeting
        targeting_group = QGroupBox("Targeting")
        targeting_form = QFormLayout(targeting_group)
        targeting_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.countries_edit = QLineEdit()
        self.countries_edit.setText("LT")
        self.countries_edit.setPlaceholderText(
            "US, GB, CA  (comma-separated ISO codes)"
        )
        targeting_form.addRow("Countries *", self.countries_edit)

        self.age_min_spin = QSpinBox()
        self.age_min_spin.setRange(13, 65)
        self.age_min_spin.setValue(18)
        self.age_min_spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        targeting_form.addRow("Age Min", self.age_min_spin)

        self.age_max_spin = QSpinBox()
        self.age_max_spin.setRange(13, 65)
        self.age_max_spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.age_max_spin.setValue(65)
        targeting_form.addRow("Age Max", self.age_max_spin)

        self.gender_combo = QComboBox()
        self.gender_combo.addItems(["All", "Male", "Female"])
        targeting_form.addRow("Gender", self.gender_combo)

        # Placement targeting
        self.publisher_platforms_edit = QLineEdit()
        self.publisher_platforms_edit.setPlaceholderText(
            "facebook, instagram, audience_network, messenger  (blank = all)"
        )
        targeting_form.addRow("Publisher Platforms", self.publisher_platforms_edit)

        self.device_platforms_edit = QLineEdit()
        self.device_platforms_edit.setPlaceholderText(
            "mobile, desktop  (blank = all)"
        )
        targeting_form.addRow("Device Platforms", self.device_platforms_edit)

        self.positions_edit = QLineEdit()
        self.positions_edit.setPlaceholderText(
            "feed, story, reels, search, video_feeds, right_hand_column, …  (blank = all)"
        )
        targeting_form.addRow("Positions", self.positions_edit)

        layout.addWidget(targeting_group)

        # Audiences
        audiences_group = QGroupBox("Audiences")
        aud_layout = QVBoxLayout(audiences_group)

        # Custom audiences (include)
        aud_layout.addWidget(QLabel("Custom Audiences (include)"))
        self.custom_audience_list = QListWidget()
        self.custom_audience_list.setSelectionMode(
            QAbstractItemView.SelectionMode.MultiSelection
        )
        self.custom_audience_list.setMaximumHeight(110)
        aud_layout.addWidget(self.custom_audience_list)

        # Lookalike audiences (include)
        aud_layout.addWidget(QLabel("Lookalike Audiences (include)"))
        self.lookalike_audience_list = QListWidget()
        self.lookalike_audience_list.setSelectionMode(
            QAbstractItemView.SelectionMode.MultiSelection
        )
        self.lookalike_audience_list.setMaximumHeight(110)
        aud_layout.addWidget(self.lookalike_audience_list)

        # Excluded audiences
        aud_layout.addWidget(QLabel("Excluded Audiences"))
        self.excluded_audience_list = QListWidget()
        self.excluded_audience_list.setSelectionMode(
            QAbstractItemView.SelectionMode.MultiSelection
        )
        self.excluded_audience_list.setMaximumHeight(110)
        aud_layout.addWidget(self.excluded_audience_list)

        # Targeting presets (saved audiences)
        preset_row = QHBoxLayout()
        preset_row.addWidget(QLabel("Targeting Preset:"))
        self.preset_combo = QComboBox()
        self.preset_combo.addItem("(none)", None)
        preset_row.addWidget(self.preset_combo, stretch=1)
        self.apply_preset_btn = QPushButton("Apply")
        self.apply_preset_btn.setFixedWidth(60)
        self.apply_preset_btn.clicked.connect(self._on_apply_preset_clicked)
        preset_row.addWidget(self.apply_preset_btn)
        aud_layout.addLayout(preset_row)

        # Refresh + status
        refresh_row = QHBoxLayout()
        self.audience_status_label = QLabel("")
        self.audience_status_label.setStyleSheet("color: gray; font-size: 11px;")
        refresh_row.addWidget(self.audience_status_label, stretch=1)
        self.refresh_audiences_btn = QPushButton("Refresh Audiences")
        self.refresh_audiences_btn.setFixedWidth(130)
        self.refresh_audiences_btn.clicked.connect(self._load_audiences)
        refresh_row.addWidget(self.refresh_audiences_btn)
        aud_layout.addLayout(refresh_row)

        layout.addWidget(audiences_group)

        # DSA (EU compliance)
        dsa_group = QGroupBox(
            "DSA Compliance (EU only — leave blank if not applicable)"
        )
        dsa_form = QFormLayout(dsa_group)
        dsa_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.dsa_payor_combo = QComboBox()
        self.dsa_payor_combo.setEditable(True)
        self.dsa_payor_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.dsa_payor_combo.lineEdit().setPlaceholderText("Who pays for the ad")
        dsa_form.addRow("DSA Payor", self.dsa_payor_combo)

        self.dsa_beneficiary_combo = QComboBox()
        self.dsa_beneficiary_combo.setEditable(True)
        self.dsa_beneficiary_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.dsa_beneficiary_combo.lineEdit().setPlaceholderText("Who benefits from the ad")
        dsa_form.addRow("DSA Beneficiary", self.dsa_beneficiary_combo)

        layout.addWidget(dsa_group)

        # Promoted Object (required at ad set level for some objectives)
        promo_group = QGroupBox("Promoted Object (required for some objectives)")
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
            "Required on the ad set for OUTCOME_APP_PROMOTION. "
            "Also used by OUTCOME_SALES when pixel tracking is set here instead of the campaign. "
            "Select OTHER to specify a fully custom event name."
        )
        promo_hint.setWordWrap(True)
        promo_hint.setStyleSheet("color: gray; font-size: 11px;")
        promo_form.addRow("", promo_hint)

        layout.addWidget(promo_group)
        layout.addStretch()

    # ── Audience loading ──────────────────────────────────────────────

    def get_loaded_resources(self) -> dict:
        """Return cached audience and DSA data for sharing with the bulk edit panel."""
        dsa_payors = [
            self.dsa_payor_combo.itemText(i)
            for i in range(self.dsa_payor_combo.count())
            if self.dsa_payor_combo.itemText(i)
        ]
        dsa_benes = [
            self.dsa_beneficiary_combo.itemText(i)
            for i in range(self.dsa_beneficiary_combo.count())
            if self.dsa_beneficiary_combo.itemText(i)
        ]
        return {
            "custom": list(self._available_custom),
            "lookalike": list(self._available_lookalike),
            "dsa_payors": dsa_payors,
            "dsa_beneficiaries": dsa_benes,
        }

    def set_client(self, client) -> None:
        self._client = client
        self._load_audiences()

    def set_meta_resources(self, pixels: list[dict], apps: list[dict]) -> None:
        self._repopulate_promo_combos(
            pixels,
            apps,
            current_pixel=self.pixel_id_combo.currentText(),
            current_app=self.app_id_combo.currentText(),
        )

    def _load_audiences(self) -> None:
        if self._client is None:
            self.audience_status_label.setText("Configure API credentials to load audiences.")
            return
        # Deferred to avoid circular import at module level
        from app.workers.audience_worker import AudienceWorker  # pylint: disable=import-outside-toplevel
        if self._audience_worker and self._audience_worker.isRunning():
            return
        self.audience_status_label.setText("Loading audiences…")
        self.refresh_audiences_btn.setEnabled(False)
        self._audience_worker = AudienceWorker(self._client, parent=self)
        self._audience_worker.finished.connect(self._on_audiences_loaded)
        self._audience_worker.error.connect(self._on_audiences_error)
        self._audience_worker.start()

    def _on_audiences_loaded(  # pylint: disable=too-many-arguments
        self, custom: list, lookalike: list, saved: list,
        dsa_payors: list, dsa_beneficiaries: list,
    ) -> None:
        self._available_custom = custom
        self._available_lookalike = lookalike
        self._available_presets = saved

        current_payor = self.dsa_payor_combo.currentText()
        current_bene = self.dsa_beneficiary_combo.currentText()

        self.dsa_payor_combo.clear()
        self.dsa_payor_combo.addItem("")
        for v in dsa_payors:
            self.dsa_payor_combo.addItem(v)
        self.dsa_payor_combo.setCurrentText(current_payor)

        self.dsa_beneficiary_combo.clear()
        self.dsa_beneficiary_combo.addItem("")
        for v in dsa_beneficiaries:
            self.dsa_beneficiary_combo.addItem(v)
        self.dsa_beneficiary_combo.setCurrentText(current_bene)

        self._populate_audience_list(self.custom_audience_list, custom)
        self._populate_audience_list(self.lookalike_audience_list, lookalike)
        self._populate_audience_list(self.excluded_audience_list, custom + lookalike)

        # Re-apply pending selections from load()
        if self._pending_include_ids:
            self._select_audience_ids(self.custom_audience_list, self._pending_include_ids)
            self._select_audience_ids(self.lookalike_audience_list, self._pending_include_ids)
        if self._pending_exclude_ids:
            self._select_audience_ids(self.excluded_audience_list, self._pending_exclude_ids)

        # Populate preset combo
        self.preset_combo.clear()
        self.preset_combo.addItem("(none)", None)
        for p in saved:
            self.preset_combo.addItem(p.get("name", p["id"]), p)

        self.audience_status_label.setText(
            f"{len(custom)} custom, {len(lookalike)} lookalike, {len(saved)} preset(s)"
        )
        self.refresh_audiences_btn.setEnabled(True)

    def _on_audiences_error(self, msg: str) -> None:
        self.audience_status_label.setText(f"Error: {msg}")
        self.refresh_audiences_btn.setEnabled(True)

    @staticmethod
    def _populate_audience_list(list_widget: QListWidget, audiences: list[dict]) -> None:
        # Preserve currently selected IDs before clearing
        selected_ids: set[str] = set()
        for i in range(list_widget.count()):
            item = list_widget.item(i)
            if item.isSelected():
                selected_ids.add(item.data(Qt.ItemDataRole.UserRole))
        list_widget.clear()
        for aud in audiences:
            item = QListWidgetItem(f"{aud.get('name', '')}  [{aud['id']}]")
            item.setData(Qt.ItemDataRole.UserRole, aud["id"])
            list_widget.addItem(item)
        # Re-select previously selected items
        if selected_ids:
            AdSetEditorPanel._select_audience_ids(list_widget, selected_ids)

    @staticmethod
    def _select_audience_ids(list_widget: QListWidget, ids: set[str]) -> None:
        for i in range(list_widget.count()):
            item = list_widget.item(i)
            if item.data(Qt.ItemDataRole.UserRole) in ids:
                item.setSelected(True)

    def _on_apply_preset_clicked(self) -> None:
        preset = self.preset_combo.currentData()
        if preset is None:
            return
        self._apply_preset_targeting(preset.get("targeting", {}))

    def _apply_preset_targeting(self, t: dict) -> None:
        if "geo_locations" in t:
            countries = t["geo_locations"].get("countries", [])
            self.countries_edit.setText(", ".join(countries))
        if "age_min" in t:
            self.age_min_spin.setValue(t["age_min"])
        if "age_max" in t:
            self.age_max_spin.setValue(t["age_max"])
        if "genders" in t:
            g = t["genders"]
            if g == [1]:
                self.gender_combo.setCurrentText("Male")
            elif g == [2]:
                self.gender_combo.setCurrentText("Female")
            else:
                self.gender_combo.setCurrentText("All")
        if "publisher_platforms" in t:
            self.publisher_platforms_edit.setText(", ".join(t["publisher_platforms"]))
        if "device_platforms" in t:
            self.device_platforms_edit.setText(", ".join(t["device_platforms"]))
        if "facebook_positions" in t:
            self.positions_edit.setText(", ".join(t["facebook_positions"]))
        if "custom_audiences" in t:
            ids = {a["id"] for a in t["custom_audiences"]}
            self._select_audience_ids(self.custom_audience_list, ids)
            self._select_audience_ids(self.lookalike_audience_list, ids)
        if "excluded_custom_audiences" in t:
            ids = {a["id"] for a in t["excluded_custom_audiences"]}
            self._select_audience_ids(self.excluded_audience_list, ids)

    # ─────────────────────────────────────────────────────────────────

    def load(self, data: AdSetData) -> None:
        self._data = data
        self.name_edit.setText(data.name)
        self.status_combo.setCurrentText(data.status.value)
        self.opt_goal_combo.setCurrentText(opt_goal_value_to_label(data.optimization_goal.value))
        self.billing_event_combo.setCurrentText(data.billing_event.value)
        self.bid_strategy_combo.setCurrentText(data.bid_strategy.label)
        self.bid_amount_spin.setValue((data.bid_amount or 0) / 100)
        self.dynamic_creative_check.setChecked(data.use_dynamic_creative)

        if data.lifetime_budget is not None:
            self.lifetime_radio.setChecked(True)
            self.budget_spin.setValue(data.lifetime_budget / 100)
        else:
            self.daily_radio.setChecked(True)
            self.budget_spin.setValue((data.daily_budget or 0) / 100)

        if data.start_time:
            self.start_dt.setDateTime(self._parse_datetime(data.start_time))
        if data.end_time:
            self.end_dt.setDateTime(self._parse_datetime(data.end_time))

        self.dsa_payor_combo.setCurrentText(data.dsa_payor)
        self.dsa_beneficiary_combo.setCurrentText(data.dsa_beneficiary)

        self._load_targeting_fields(data.targeting)
        self._load_promo_fields(data.promoted_object or {})

    def _load_targeting_fields(self, targeting: dict) -> None:
        countries = targeting.get("geo_locations", {}).get("countries", []) or ["LT"]
        self.countries_edit.setText(", ".join(countries))
        self.age_min_spin.setValue(targeting.get("age_min", 18))
        self.age_max_spin.setValue(targeting.get("age_max", 65))
        genders = targeting.get("genders", [])
        if genders == [1]:
            self.gender_combo.setCurrentText("Male")
        elif genders == [2]:
            self.gender_combo.setCurrentText("Female")
        else:
            self.gender_combo.setCurrentText("All")
        self.publisher_platforms_edit.setText(
            ", ".join(targeting.get("publisher_platforms", []))
        )
        self.device_platforms_edit.setText(
            ", ".join(targeting.get("device_platforms", []))
        )
        self.positions_edit.setText(
            ", ".join(targeting.get("facebook_positions", []))
        )
        include_ids = {a["id"] for a in targeting.get("custom_audiences", [])}
        exclude_ids = {a["id"] for a in targeting.get("excluded_custom_audiences", [])}
        self._pending_include_ids = include_ids
        self._pending_exclude_ids = exclude_ids
        if self._available_custom or self._available_lookalike:
            self._select_audience_ids(self.custom_audience_list, include_ids)
            self._select_audience_ids(self.lookalike_audience_list, include_ids)
            self._select_audience_ids(self.excluded_audience_list, exclude_ids)

    @staticmethod
    def _parse_datetime(text: str) -> QDateTime:
        """Parse a datetime string, trying multiple formats."""
        for fmt in (
            "yyyy-MM-dd HH:mm:ss",
            "yyyy-MM-dd HH:mm",
            "yyyy-MM-ddTHH:mm:ss",
            "yyyy-MM-ddTHH:mm",
        ):
            dt = QDateTime.fromString(text[:19], fmt)
            if dt.isValid():
                return dt
        # Fallback: try just the date part
        dt = QDateTime.fromString(text[:10], "yyyy-MM-dd")
        if dt.isValid():
            return dt
        return QDateTime.currentDateTime()

    def commit(self) -> None:
        if self._data is None:
            return
        self._data.name = self.name_edit.text().strip()
        try:
            self._data.status = AdStatus(self.status_combo.currentText())
            self._data.optimization_goal = OptimizationGoal(
                opt_goal_label_to_value(self.opt_goal_combo.currentText())
            )
            self._data.billing_event = BillingEvent(
                self.billing_event_combo.currentText()
            )
            self._data.bid_strategy = BidStrategy.from_label(self.bid_strategy_combo.currentText())
        except ValueError:
            pass

        self._data.use_dynamic_creative = self.dynamic_creative_check.isChecked()
        bid = self.bid_amount_spin.value()
        self._data.bid_amount = int(bid * 100) if bid > 0 else None

        budget_cents = int(self.budget_spin.value() * 100)
        budget_value = budget_cents if budget_cents > 0 else None
        if self.lifetime_radio.isChecked():
            self._data.lifetime_budget = budget_value
            self._data.daily_budget = None
        else:
            self._data.daily_budget = budget_value
            self._data.lifetime_budget = None

        self._data.start_time = (
            self.start_dt.dateTime()
            .toString("yyyy-MM-ddTHH:mm:sszzz")
            .replace("zzz", "+0000")[:16]
            + ":00+0000"
        )
        self._data.end_time = (
            self.end_dt.dateTime()
            .toString("yyyy-MM-ddTHH:mm:sszzz")
            .replace("zzz", "+0000")[:16]
            + ":00+0000"
        )

        self._data.dsa_payor = self.dsa_payor_combo.currentText().strip()
        self._data.dsa_beneficiary = self.dsa_beneficiary_combo.currentText().strip()

        self._data.targeting = self._build_targeting()

        self._data.promoted_object = self._commit_promo_fields()

    def _collect_include_audience_ids(self) -> list[dict]:
        ids: list[dict] = []
        for lst in (self.custom_audience_list, self.lookalike_audience_list):
            for i in range(lst.count()):
                item = lst.item(i)
                if item.isSelected():
                    aud_id = item.data(Qt.ItemDataRole.UserRole)
                    if not any(a["id"] == aud_id for a in ids):
                        ids.append({"id": aud_id})
        return ids

    def _collect_exclude_audience_ids(self) -> list[dict]:
        ids: list[dict] = []
        for i in range(self.excluded_audience_list.count()):
            item = self.excluded_audience_list.item(i)
            if item.isSelected():
                ids.append({"id": item.data(Qt.ItemDataRole.UserRole)})
        return ids

    def _build_targeting(self) -> dict:
        raw_countries = [
            c.strip().upper()
            for c in self.countries_edit.text().split(",")
            if c.strip()
        ]
        targeting: dict = {
            "geo_locations": {"countries": raw_countries},
            "age_min": self.age_min_spin.value(),
            "age_max": self.age_max_spin.value(),
        }
        gender_text = self.gender_combo.currentText()
        if gender_text == "Male":
            targeting["genders"] = [1]
        elif gender_text == "Female":
            targeting["genders"] = [2]

        publisher_platforms = [
            p.strip().lower()
            for p in self.publisher_platforms_edit.text().split(",")
            if p.strip()
        ]
        if publisher_platforms:
            targeting["publisher_platforms"] = publisher_platforms

        device_platforms = [
            p.strip().lower()
            for p in self.device_platforms_edit.text().split(",")
            if p.strip()
        ]
        if device_platforms:
            targeting["device_platforms"] = device_platforms

        positions = [
            p.strip().lower()
            for p in self.positions_edit.text().split(",")
            if p.strip()
        ]
        if positions:
            targeting["facebook_positions"] = positions

        include_ids = self._collect_include_audience_ids()
        if include_ids:
            targeting["custom_audiences"] = include_ids

        exclude_ids = self._collect_exclude_audience_ids()
        if exclude_ids:
            targeting["excluded_custom_audiences"] = exclude_ids

        return targeting
