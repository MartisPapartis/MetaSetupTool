"""Main application window."""

from __future__ import annotations
import json
import os

from PyQt6.QtCore import Qt, QObject, QEvent
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QMainWindow,
    QWidget,
    QSplitter,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QStackedWidget,
    QTabWidget,
    QFileDialog,
    QMessageBox,
    QStatusBar,
    QComboBox,
    QFormLayout,
    QAbstractSpinBox,
    QLineEdit,
)


from app.models.campaign_data import (
    SessionData,
    CampaignData,
    AdSetData,
    AdData,
    CreativeData,
)
from app.ui.campaign_tree import (
    CampaignTreeWidget,
    NODE_CAMPAIGN,
    NODE_ADSET,
    NODE_AD,
    _ID_ROLE,
    _TYPE_ROLE,
)
from app.ui.editors.campaign_editor import CampaignEditorPanel
from app.ui.editors.adset_editor import AdSetEditorPanel
from app.ui.editors.ad_editor import AdEditorPanel
from app.ui.bulk_edit_panel import BulkEditPanel
from app.ui.media_library import MediaLibraryPanel
from app.ui.settings_dialog import SettingsDialog
from app.ui.excel_dialog import ExcelImportDialog
from app.ui.plan_import_dialog import PlanImportDialog
from app.ui.upload_dialog import UploadProgressDialog
from app.ui.pull_dialog import PullProgressDialog
from app.ui.push_dialog import PushProgressDialog
from app.workers.worker_config import WorkerConfig
from app.ui.select_campaigns_dialog import SelectCampaignsDialog
from app.ui.select_push_dialog import SelectPushDialog
from app.utils.settings_store import SettingsStore
from app.utils.validators import validate_campaign
from app.api.client import MetaApiClient, MetaApiError
from app.api.campaign_reader import list_pixels, list_apps
from app.ui.commands import (
    CommandHistory,
    AddCampaignCommand,
    AddAdSetCommand,
    AddAdCommand,
    RemoveCampaignCommand,
    RemoveAdSetCommand,
    RemoveAdCommand,
    BatchRemoveCommand,
    DuplicateCampaignCommand,
    DuplicateAdSetCommand,
    DuplicateAdCommand,
    RenameNodeCommand,
    MoveAdSetCommand,
    MoveAdCommand,
    AdSetMoveContext,
    AdMoveContext,
)


class _WheelBlockFilter(QObject):
    """Unconditionally blocks mouse-wheel value changes on combo boxes
    and spin boxes so scrolling the page never alters a field."""

    def eventFilter(self, obj, event):  # pylint: disable=invalid-name
        if event.type() == QEvent.Type.Wheel and isinstance(
            obj, (QComboBox, QAbstractSpinBox)
        ):
            event.ignore()
            return True
        return super().eventFilter(obj, event)


_APP_STYLESHEET = """
QMainWindow, QWidget {
    background-color: #1e1e1e;
    color: #d4d4d4;
    font-family: "Segoe UI", Arial, sans-serif;
    font-size: 13px;
}
QGroupBox {
    border: 1px solid #3a3a3a;
    border-radius: 4px;
    margin-top: 8px;
    padding-top: 8px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 8px;
    color: #9cdcfe;
    font-weight: bold;
}
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QPlainTextEdit, QTextEdit, QDateTimeEdit {
    background-color: #2d2d2d;
    border: 1px solid #3a3a3a;
    border-radius: 3px;
    padding: 4px 6px;
    color: #d4d4d4;
    selection-background-color: #264f78;
}
QLineEdit:focus, QComboBox:focus, QPlainTextEdit:focus, QTextEdit:focus, QDateTimeEdit:focus {
    border-color: #007acc;
}
QPushButton {
    background-color: #0e639c;
    color: #ffffff;
    border: none;
    border-radius: 3px;
    padding: 5px 12px;
    min-height: 22px;
}
QPushButton:hover { background-color: #1177bb; }
QPushButton:pressed { background-color: #0a4d7a; }
QPushButton:disabled { background-color: #3a3a3a; color: #666; }
QPushButton[danger="true"] { background-color: #8b1a1a; }
QPushButton[danger="true"]:hover { background-color: #aa2222; }
QTreeWidget {
    background-color: #252526;
    border: 1px solid #3a3a3a;
    alternate-background-color: #2a2a2a;
}
QTreeWidget::item:selected { background-color: #094771; }
QTreeWidget::item:hover { background-color: #2a2d2e; }
QTabWidget::pane { border: 1px solid #3a3a3a; }
QTabBar::tab {
    background: #2d2d2d;
    color: #ccc;
    padding: 6px 14px;
    border: 1px solid #3a3a3a;
    border-bottom: none;
    border-top-left-radius: 3px;
    border-top-right-radius: 3px;
}
QTabBar::tab:selected { background: #1e1e1e; color: #fff; }
QTabBar::tab:hover { background: #333; }
QScrollBar:vertical {
    background: #1e1e1e; width: 10px; margin: 0;
}
QScrollBar::handle:vertical { background: #424242; border-radius: 4px; min-height: 20px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal { background: #1e1e1e; height: 10px; }
QScrollBar::handle:horizontal { background: #424242; border-radius: 4px; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
QProgressBar {
    background: #2d2d2d;
    border: 1px solid #3a3a3a;
    border-radius: 3px;
    text-align: center;
}
QProgressBar::chunk { background: #007acc; border-radius: 2px; }
QListWidget {
    background: #252526;
    border: 1px solid #3a3a3a;
}
QListWidget::item:selected { background: #094771; }
QCheckBox { spacing: 6px; }
QCheckBox::indicator {
    width: 14px; height: 14px;
    border: 1px solid #555; border-radius: 2px; background: #2d2d2d;
}
QCheckBox::indicator:checked { background: #007acc; border-color: #007acc; }
QRadioButton { spacing: 6px; }
QRadioButton::indicator {
    width: 14px; height: 14px;
    border: 1px solid #555; border-radius: 7px; background: #2d2d2d;
}
QRadioButton::indicator:checked {
    background: qradialgradient(cx:0.5, cy:0.5, radius:0.5,
        fx:0.5, fy:0.5, stop:0 #ffffff, stop:0.35 #ffffff,
        stop:0.36 #007acc, stop:1 #007acc);
    border-color: #007acc;
}
QSplitter::handle { background: #3a3a3a; }
QLabel { color: #d4d4d4; }
QStatusBar { background: #007acc; color: white; }
QMenuBar {
    background-color: #2d2d2d;
    color: #d4d4d4;
    spacing: 0px;
}
QMenuBar::item {
    background: transparent;
    padding: 4px 10px;
}
QMenuBar::item:selected { background: #094771; }
QMenuBar::item:pressed { background: #094771; }
QMenu {
    background-color: #252526;
    border: 1px solid #454545;
    color: #d4d4d4;
    padding: 4px 0px;
}
QMenu::item {
    padding: 5px 32px 5px 20px;
    min-width: 160px;
}
QMenu::item:selected { background-color: #094771; }
QMenu::item:disabled { color: #666666; }
QMenu::separator {
    height: 1px;
    background: #454545;
    margin: 3px 8px;
}
"""


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.session = SessionData()
        self.settings_store = SettingsStore()
        self._session_path: str = ""
        self._current_node_type: str = ""
        self._current_node_id: str = ""
        self._history = CommandHistory()
        self._pixels: list[dict] = []
        self._apps: list[dict] = []

        self.setWindowTitle("Meta Campaign Setup Tool")
        self.setMinimumSize(1280, 800)
        self.setStyleSheet(_APP_STYLESHEET)

        # Block accidental wheel-scroll value changes on combos/spins
        self._wheel_filter = _WheelBlockFilter(self)
        app = QApplication.instance()
        if app:
            app.installEventFilter(self._wheel_filter)

        self._setup_ui()
        self._setup_menus()
        self._connect_signals()
        self._update_status("Ready")

    # ------------------------------------------------------------------
    # UI Setup
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:  # pylint: disable=too-many-statements
        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # ── Main splitter ─────────────────────────────────────────────
        splitter = QSplitter(Qt.Orientation.Horizontal)
        root_layout.addWidget(splitter)

        # Left: tree panel
        left_panel = QWidget()
        left_panel.setMinimumWidth(220)
        left_panel.setMaximumWidth(340)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(8, 8, 8, 8)
        left_layout.setSpacing(6)

        tree_title = QLabel("Campaigns")
        tree_title.setStyleSheet("font-weight: bold; font-size: 14px; color: #9cdcfe;")
        left_layout.addWidget(tree_title)

        # Account / Page selectors
        selector_form = QFormLayout()
        selector_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        selector_form.setContentsMargins(0, 0, 0, 4)

        self.account_combo = QComboBox()
        self.account_combo.setStyleSheet("font-size: 11px;")
        self.account_combo.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        selector_form.addRow("Account", self.account_combo)

        self.page_combo = QComboBox()
        self.page_combo.setStyleSheet("font-size: 11px;")
        self.page_combo.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        selector_form.addRow("Page", self.page_combo)

        self.instagram_combo = QComboBox()
        self.instagram_combo.setStyleSheet("font-size: 11px;")
        self.instagram_combo.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        selector_form.addRow("Instagram", self.instagram_combo)

        left_layout.addLayout(selector_form)
        self._load_account_page_combos()

        self.tree_search = QLineEdit()
        self.tree_search.setPlaceholderText("Search…")
        self.tree_search.setClearButtonEnabled(True)
        self.tree_search.setStyleSheet("font-size: 12px;")
        left_layout.addWidget(self.tree_search)

        self.campaign_tree = CampaignTreeWidget()
        left_layout.addWidget(self.campaign_tree)

        # Action buttons
        btn_row1 = QHBoxLayout()
        self.btn_add_campaign = QPushButton("+ Campaign")
        self.btn_add_adset = QPushButton("+ Ad Set")
        btn_row1.addWidget(self.btn_add_campaign)
        btn_row1.addWidget(self.btn_add_adset)
        left_layout.addLayout(btn_row1)

        btn_row2 = QHBoxLayout()
        self.btn_add_ad = QPushButton("+ Ad")
        self.btn_duplicate = QPushButton("Duplicate")
        btn_row2.addWidget(self.btn_add_ad)
        btn_row2.addWidget(self.btn_duplicate)
        left_layout.addLayout(btn_row2)

        btn_row3 = QHBoxLayout()
        self.btn_remove = QPushButton("Remove")
        self.btn_remove.setProperty("danger", "true")
        self.btn_remove.style().polish(self.btn_remove)
        btn_row3.addWidget(self.btn_remove)
        left_layout.addLayout(btn_row3)

        splitter.addWidget(left_panel)

        # Right: tabs
        self.right_tabs = QTabWidget()
        splitter.addWidget(self.right_tabs)
        splitter.setSizes([260, 1020])

        # ── Editor tab ────────────────────────────────────────────────
        editor_container = QWidget()
        editor_layout = QVBoxLayout(editor_container)
        editor_layout.setContentsMargins(0, 0, 0, 0)

        self.editor_stack = QStackedWidget()

        # Index 0: welcome screen
        welcome = QLabel(
            "Select a Campaign, Ad Set, or Ad from the left panel\n"
            "or click  + Campaign  to create a new one."
        )
        welcome.setAlignment(Qt.AlignmentFlag.AlignCenter)
        welcome.setStyleSheet("color: #666; font-size: 14px;")
        self.editor_stack.addWidget(welcome)  # 0

        self.campaign_editor = CampaignEditorPanel()
        self.editor_stack.addWidget(self.campaign_editor)  # 1

        self.adset_editor = AdSetEditorPanel()
        self.editor_stack.addWidget(self.adset_editor)  # 2

        self.ad_editor = AdEditorPanel()
        self.editor_stack.addWidget(self.ad_editor)  # 3

        self.bulk_edit_panel = BulkEditPanel()
        self.editor_stack.addWidget(self.bulk_edit_panel)  # 4

        editor_layout.addWidget(self.editor_stack)
        self.right_tabs.addTab(editor_container, "Editor")

        # ── Media Library tab ─────────────────────────────────────────
        self.media_library = MediaLibraryPanel()
        self.right_tabs.addTab(self.media_library, "Media Library")

        # ── Status bar ────────────────────────────────────────────────
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

    def _setup_menus(self) -> None:
        mb = self.menuBar()

        # File
        file_menu = mb.addMenu("File")
        file_menu.addAction("New Session", self._new_session).setShortcut("Ctrl+N")
        file_menu.addAction("Open Session…", self._open_session).setShortcut("Ctrl+O")
        file_menu.addAction("Save Session", self._save_session).setShortcut("Ctrl+S")
        file_menu.addAction("Save Session As…", self._save_session_as).setShortcut(
            "Ctrl+Shift+S"
        )
        file_menu.addSeparator()
        self._recent_menu = file_menu.addMenu("Recent Sessions")
        self._rebuild_recent_menu()
        file_menu.addSeparator()
        file_menu.addAction("Exit", self.close)

        # Edit
        edit_menu = mb.addMenu("Edit")
        self._undo_action = edit_menu.addAction("Undo", self._undo)
        self._undo_action.setShortcut("Ctrl+Z")
        self._undo_action.setEnabled(False)
        self._redo_action = edit_menu.addAction("Redo", self._redo)
        self._redo_action.setShortcut("Ctrl+Y")
        self._redo_action.setEnabled(False)
        edit_menu.addSeparator()
        edit_menu.addAction("Settings / API Config…", self._open_settings)
        edit_menu.addAction("Import from Excel…", self._open_excel_import)
        edit_menu.addAction("Import from Plan…", self._open_plan_import)

        # Upload
        upload_menu = mb.addMenu("Upload")
        upload_menu.addAction("Validate All", self._validate_only).setShortcut(
            "Ctrl+Shift+V"
        )
        upload_menu.addAction(
            "Test Upload", self._start_test_upload
        ).setShortcut("Ctrl+Shift+D")
        upload_menu.addAction("Start Upload", self._start_upload).setShortcut("Ctrl+U")

        # API Sync
        sync_menu = mb.addMenu("API Sync")
        sync_menu.addAction("Pull from API…", self._start_pull).setShortcut(
            "Ctrl+Shift+P"
        )
        sync_menu.addAction("Push Updates to API…", self._start_push).setShortcut(
            "Ctrl+Shift+U"
        )

    def _load_account_page_combos(self) -> None:
        """Populate Account / Page dropdowns from settings."""
        settings = self.settings_store.load()

        self.account_combo.clear()
        for entry in settings.get("ad_accounts", []):
            label = entry.get("label", entry.get("id", ""))
            entry_id = entry.get("id", "")
            self.account_combo.addItem(f"{label}  ({entry_id})", entry_id)
        # Fallback: legacy single value
        if self.account_combo.count() == 0:
            legacy = settings.get("ad_account_id", "").strip()
            if legacy:
                self.account_combo.addItem(legacy, legacy)

        self.page_combo.clear()
        for entry in settings.get("pages", []):
            label = entry.get("label", entry.get("id", ""))
            entry_id = entry.get("id", "")
            self.page_combo.addItem(f"{label}  ({entry_id})", entry_id)
        # Fallback: legacy single value
        if self.page_combo.count() == 0:
            legacy = settings.get("page_id", "").strip()
            if legacy:
                self.page_combo.addItem(legacy, legacy)

        self.instagram_combo.clear()
        for entry in settings.get("instagram_accounts", []):
            label = entry.get("label", entry.get("id", ""))
            entry_id = entry.get("id", "")
            self.instagram_combo.addItem(f"{label}  ({entry_id})", entry_id)

    def _connect_signals(self) -> None:
        self.campaign_tree.currentItemChanged.connect(self._on_tree_selection_changed)
        self.campaign_tree.itemSelectionChanged.connect(self._on_selection_changed)
        self.campaign_tree.node_renamed.connect(self._on_node_renamed)
        self.campaign_tree.node_moved.connect(self._on_node_moved)
        self.campaign_tree.action_add_campaign.connect(self._add_campaign)
        self.campaign_tree.action_add_adset.connect(self._add_adset)
        self.campaign_tree.action_add_ad.connect(self._add_ad)
        self.campaign_tree.action_duplicate.connect(self._duplicate_selected)
        self.campaign_tree.action_remove.connect(self._remove_selected)
        self.tree_search.textChanged.connect(self.campaign_tree.filter)
        self.bulk_edit_panel.apply_btn.clicked.connect(self._apply_bulk_edit)
        self.btn_add_campaign.clicked.connect(self._add_campaign)
        self.btn_add_adset.clicked.connect(self._add_adset)
        self.btn_add_ad.clicked.connect(self._add_ad)
        self.btn_duplicate.clicked.connect(self._duplicate_selected)
        self.btn_remove.clicked.connect(self._remove_selected)

    # ------------------------------------------------------------------
    # Tree selection
    # ------------------------------------------------------------------

    def _on_tree_selection_changed(self, current, _previous) -> None:
        self._commit_current()

        if current is None:
            self.editor_stack.setCurrentIndex(0)
            self._current_node_type = ""
            self._current_node_id = ""
            return

        node_type = current.data(0, _TYPE_ROLE)
        node_id = current.data(0, _ID_ROLE)
        self._current_node_type = node_type
        self._current_node_id = node_id

        if node_type == NODE_CAMPAIGN:
            campaign = self._find_campaign(node_id)
            if campaign:
                if not self._pixels and not self._apps:
                    self._fetch_meta_resources()
                self.campaign_editor.load(campaign)
                self.editor_stack.setCurrentIndex(1)
                self._update_status(f"Campaign: {campaign.name}")

        elif node_type == NODE_ADSET:
            adset = self._find_adset(node_id)
            if adset:
                client = self._get_client_silently()
                if client:
                    self.adset_editor.set_client(client)
                if not self._pixels and not self._apps:
                    self._fetch_meta_resources()
                self.adset_editor.set_meta_resources(self._pixels, self._apps)
                self.adset_editor.load(adset)
                self.editor_stack.setCurrentIndex(2)
                self._update_status(f"Ad Set: {adset.name}")

        elif node_type == NODE_AD:
            ad = self._find_ad(node_id)
            if ad:
                self.ad_editor.load(ad)
                self.editor_stack.setCurrentIndex(3)
                self._update_status(f"Ad: {ad.name}")

    def _on_selection_changed(self) -> None:
        """Switch to bulk edit panel when multiple same-type items are selected."""
        selected = self.campaign_tree.get_selected_items()
        if len(selected) <= 1:
            return  # single-select handled by currentItemChanged
        types = {t for t, _ in selected}
        if len(types) != 1:
            # Mixed types — don't show bulk panel, just stay on current editor
            return
        node_type = next(iter(types))
        self._commit_current()
        self.bulk_edit_panel.configure(node_type, len(selected))
        self.bulk_edit_panel.set_meta_resources(self._pixels, self._apps)
        if node_type == "adset":
            self.bulk_edit_panel.set_audience_data(
                **self.adset_editor.get_loaded_resources()
            )
        self.editor_stack.setCurrentIndex(4)
        self._update_status(f"{len(selected)} {node_type}(s) selected — bulk edit active")

    def _bulk_apply_campaign(self, obj, panel) -> None:  # pylint: disable=too-many-branches
        new_status = panel.get_new_status()
        if new_status is not None:
            obj.status = new_status
        new_objective = panel.get_campaign_objective()
        if new_objective is not None:
            obj.objective = new_objective
        new_bid_strategy = panel.get_campaign_bid_strategy()
        if new_bid_strategy is not None:
            obj.bid_strategy = new_bid_strategy
        budget = panel.get_campaign_budget()
        if budget is not None:
            btype, amount = budget
            if btype == "none":
                obj.daily_budget = None
                obj.lifetime_budget = None
            elif btype == "daily":
                obj.daily_budget = amount
                obj.lifetime_budget = None
            else:
                obj.lifetime_budget = amount
                obj.daily_budget = None
        spend_cap = panel.get_campaign_spend_cap()
        if spend_cap is not None:
            obj.spend_cap = spend_cap if spend_cap > 0 else None
        budget_sharing = panel.get_campaign_budget_sharing()
        if budget_sharing is not None:
            obj.is_budget_sharing_enabled = budget_sharing
        special_cats = panel.get_campaign_special_categories()
        if special_cats is not None:
            obj.special_ad_categories = special_cats
        promo = panel.get_campaign_promoted_object()
        if promo is not None:
            obj.promoted_object = promo if promo else None

    def _bulk_apply_adset(self, obj, panel) -> None:  # pylint: disable=too-many-branches,too-many-statements
        new_status = panel.get_new_status()
        if new_status is not None:
            obj.status = new_status
        opt_goal = panel.get_adset_opt_goal()
        if opt_goal is not None:
            obj.optimization_goal = opt_goal
        billing_event = panel.get_adset_billing_event()
        if billing_event is not None:
            obj.billing_event = billing_event
        bid_strategy = panel.get_adset_bid_strategy()
        if bid_strategy is not None:
            obj.bid_strategy = bid_strategy
        bid_amount = panel.get_adset_bid_amount()
        if bid_amount is not None:
            obj.bid_amount = bid_amount
        dynamic_creative = panel.get_adset_dynamic_creative()
        if dynamic_creative is not None:
            obj.use_dynamic_creative = dynamic_creative
        budget = panel.get_adset_budget()
        if budget is not None:
            btype, amount = budget
            if btype == "lifetime":
                obj.lifetime_budget = amount
                obj.daily_budget = None
            else:
                obj.daily_budget = amount
                obj.lifetime_budget = None
        start_time = panel.get_adset_start_time()
        if start_time is not None:
            obj.start_time = start_time
        end_time = panel.get_adset_end_time()
        if end_time is not None:
            obj.end_time = end_time
        # Targeting fields — patch into existing targeting dict
        targeting = dict(obj.targeting or {})
        countries = panel.get_adset_countries()
        if countries is not None:
            targeting.setdefault("geo_locations", {})["countries"] = countries
        age_min = panel.get_adset_age_min()
        if age_min is not None:
            targeting["age_min"] = age_min
        age_max = panel.get_adset_age_max()
        if age_max is not None:
            targeting["age_max"] = age_max
        gender = panel.get_adset_gender()
        if gender is not None:
            if gender == "Male":
                targeting["genders"] = [1]
            elif gender == "Female":
                targeting["genders"] = [2]
            else:
                targeting.pop("genders", None)
        pub_platforms = panel.get_adset_publisher_platforms()
        if pub_platforms is not None:
            if pub_platforms:
                targeting["publisher_platforms"] = pub_platforms
            else:
                targeting.pop("publisher_platforms", None)
        device_platforms = panel.get_adset_device_platforms()
        if device_platforms is not None:
            if device_platforms:
                targeting["device_platforms"] = device_platforms
            else:
                targeting.pop("device_platforms", None)
        positions = panel.get_adset_positions()
        if positions is not None:
            if positions:
                targeting["facebook_positions"] = positions
            else:
                targeting.pop("facebook_positions", None)
        audiences = panel.get_adset_audiences()
        if audiences is not None:
            include_ids, exclude_ids = audiences
            targeting["custom_audiences"] = include_ids
            targeting["excluded_custom_audiences"] = exclude_ids
        obj.targeting = targeting
        dsa_payor = panel.get_adset_dsa_payor()
        if dsa_payor is not None:
            obj.dsa_payor = dsa_payor
        dsa_beneficiary = panel.get_adset_dsa_beneficiary()
        if dsa_beneficiary is not None:
            obj.dsa_beneficiary = dsa_beneficiary
        promo = panel.get_adset_promoted_object()
        if promo is not None:
            obj.promoted_object = promo if promo else None

    def _bulk_apply_ad(self, obj, new_status, new_headline, new_body,
                       new_description, new_link_url, new_cta, new_media_paths) -> None:
        if new_status is not None:
            obj.status = new_status
        c = obj.creative
        if new_headline is not None:
            c.headline = new_headline
        if new_body is not None:
            c.body = new_body
        if new_description is not None:
            c.description = new_description
        if new_link_url is not None:
            c.link_url = new_link_url
        if new_cta is not None:
            c.call_to_action = new_cta
        for path in new_media_paths:
            if not c.media_path:
                c.media_path = path
            elif path not in c.all_media_paths:
                c.extra_media_paths.append(path)

    def _apply_bulk_edit(self) -> None:
        """Apply bulk edits to all selected items."""
        selected = self.campaign_tree.get_selected_items()
        if not selected:
            return

        panel = self.bulk_edit_panel
        new_headline = panel.get_new_headline()
        new_body = panel.get_new_body()
        new_description = panel.get_new_description()
        new_link_url = panel.get_new_link_url()
        new_cta = panel.get_new_cta()
        new_media_paths = panel.get_media_paths()
        new_status = panel.get_new_status()

        count = 0
        for node_type, node_id in selected:
            if node_type == NODE_CAMPAIGN:
                obj = self._find_campaign(node_id)
                if obj:
                    self._bulk_apply_campaign(obj, panel)
                    count += 1
            elif node_type == NODE_ADSET:
                obj = self._find_adset(node_id)
                if obj:
                    self._bulk_apply_adset(obj, panel)
                    count += 1
            elif node_type == NODE_AD:
                obj = self._find_ad(node_id)
                if obj:
                    self._bulk_apply_ad(obj, new_status, new_headline, new_body,
                                        new_description, new_link_url, new_cta, new_media_paths)
                    count += 1

        if count:
            self._update_status(f"Bulk edit applied to {count} item(s)")

    def _commit_current(self) -> None:
        idx = self.editor_stack.currentIndex()
        if idx == 1:
            self.campaign_editor.commit()
            # Sync label in tree
            if self._current_node_id:
                campaign = self._find_campaign(self._current_node_id)
                if campaign:
                    self.campaign_tree.update_item_label(
                        campaign.id, campaign.name or "(unnamed campaign)"
                    )
        elif idx == 2:
            self.adset_editor.commit()
            if self._current_node_id:
                adset = self._find_adset(self._current_node_id)
                if adset:
                    self.campaign_tree.update_item_label(
                        adset.id, adset.name or "(unnamed ad set)"
                    )
        elif idx == 3:
            self.ad_editor.commit()
            if self._current_node_id:
                ad = self._find_ad(self._current_node_id)
                if ad:
                    self.campaign_tree.update_item_label(
                        ad.id, ad.name or "(unnamed ad)"
                    )

    def _on_node_renamed(self, node_type: str, node_id: str, new_name: str) -> None:
        """Sync inline tree rename back to data model."""
        if node_type == NODE_CAMPAIGN:
            obj = self._find_campaign(node_id)
        elif node_type == NODE_ADSET:
            obj = self._find_adset(node_id)
        elif node_type == NODE_AD:
            obj = self._find_ad(node_id)
        else:
            return
        if obj:
            old_name = obj.name
            obj.name = new_name
            if old_name != new_name:
                self._history.record(RenameNodeCommand(obj, old_name, new_name))
                self._update_undo_redo_actions()

    def _on_node_moved(self, node_type: str, node_id: str,
                       old_parent_id: str, new_parent_id: str, new_index: int) -> None:
        """Sync a drag-and-drop tree move back to the data model."""
        self._commit_current()
        if node_type == NODE_ADSET:
            adset = self._find_adset(node_id)
            from_campaign = self._find_campaign(old_parent_id)
            to_campaign = self._find_campaign(new_parent_id)
            if not (adset and from_campaign and to_campaign):
                return
            from_index = from_campaign.ad_sets.index(adset) if adset in from_campaign.ad_sets else 0
            cmd = MoveAdSetCommand(
                adset,
                AdSetMoveContext(from_campaign, to_campaign, from_index, new_index),
            )
            cmd.execute()
            self._history.record(cmd)
        elif node_type == NODE_AD:
            ad = self._find_ad(node_id)
            from_adset = self._find_adset(old_parent_id)
            to_adset = self._find_adset(new_parent_id)
            if not (ad and from_adset and to_adset):
                return
            from_index = from_adset.ads.index(ad) if ad in from_adset.ads else 0
            cmd = MoveAdCommand(ad, AdMoveContext(from_adset, to_adset, from_index, new_index))
            cmd.execute()
            self._history.record(cmd)
        else:
            return
        self._after_command(node_id)
        self._update_status(f"Moved: {node_id[:8]}…")

    # ------------------------------------------------------------------
    # Undo / Redo
    # ------------------------------------------------------------------

    def _undo(self) -> None:
        self._commit_current()
        cmd = self._history.undo()
        if cmd:
            self._after_command(cmd.undo_select_id)
            self._update_status(f"Undo: {cmd.description}")

    def _redo(self) -> None:
        self._commit_current()
        cmd = self._history.redo()
        if cmd:
            self._after_command(cmd.select_id)
            self._update_status(f"Redo: {cmd.description}")

    def _after_command(self, select_id: str = "") -> None:
        """Rebuild tree from session and optionally select a node."""
        self.campaign_tree.load_session(self.session)
        if select_id:
            self.campaign_tree.select_by_id(select_id)
            # Trigger selection changed to load editor
            item = self.campaign_tree.currentItem()
            if item:
                self._on_tree_selection_changed(item, None)
        else:
            self.editor_stack.setCurrentIndex(0)
            self._current_node_type = ""
            self._current_node_id = ""
        self._update_undo_redo_actions()

    def _update_undo_redo_actions(self) -> None:
        can_undo = self._history.can_undo
        can_redo = self._history.can_redo
        self._undo_action.setEnabled(can_undo)
        self._redo_action.setEnabled(can_redo)
        self._undo_action.setText(
            f"Undo: {self._history.undo_description}" if can_undo else "Undo"
        )
        self._redo_action.setText(
            f"Redo: {self._history.redo_description}" if can_redo else "Redo"
        )

    # ------------------------------------------------------------------
    # Add / Remove nodes
    # ------------------------------------------------------------------

    def _add_campaign(self) -> None:
        self._commit_current()
        campaign = CampaignData(name="New Campaign")
        cmd = AddCampaignCommand(self.session, campaign)
        self._history.push(cmd)
        self._after_command(cmd.select_id)
        self._update_status("New campaign added")

    def _add_adset(self) -> None:
        self._commit_current()
        camp_id, _, _ = self.campaign_tree.get_selected_ids()
        if not camp_id:
            QMessageBox.information(
                self, "Select a Campaign", "Please select a campaign first."
            )
            return
        campaign = self._find_campaign(camp_id)
        if not campaign:
            return
        adset = AdSetData(name="New Ad Set")
        cmd = AddAdSetCommand(campaign, adset)
        self._history.push(cmd)
        self._after_command(cmd.select_id)
        self._update_status("New ad set added")

    def _add_ad(self) -> None:
        self._commit_current()
        _, adset_id, _ = self.campaign_tree.get_selected_ids()
        if not adset_id:
            QMessageBox.information(
                self, "Select an Ad Set", "Please select an ad set first."
            )
            return
        adset = self._find_adset(adset_id)
        if not adset:
            return
        ad = AdData(name="New Ad", creative=CreativeData())
        cmd = AddAdCommand(adset, ad)
        self._history.push(cmd)
        self._after_command(cmd.select_id)
        self._update_status("New ad added")

    def _duplicate_selected(self) -> None:
        self._commit_current()
        selected = self.campaign_tree.get_selected_items_with_context()
        if not selected:
            return

        last_cmd = None
        count = 0
        for node_type, node_id, camp_id, adset_id in selected:
            if node_type == NODE_CAMPAIGN:
                campaign = self._find_campaign(node_id)
                if not campaign:
                    continue
                dup = campaign.duplicate()
                cmd = DuplicateCampaignCommand(self.session, dup)
            elif node_type == NODE_ADSET:
                campaign = self._find_campaign(camp_id)
                adset = self._find_adset(node_id)
                if not campaign or not adset:
                    continue
                dup = adset.duplicate()
                cmd = DuplicateAdSetCommand(campaign, dup)
            elif node_type == NODE_AD:
                adset = self._find_adset(adset_id)
                ad = self._find_ad(node_id)
                if not adset or not ad:
                    continue
                dup = ad.duplicate()
                cmd = DuplicateAdCommand(adset, dup)
            else:
                continue
            self._history.push(cmd)
            last_cmd = cmd
            count += 1

        if last_cmd is None:
            return
        self._after_command(last_cmd.select_id)
        if count == 1:
            self._update_status(f"Duplicated: {dup.name}")
        else:
            self._update_status(f"Duplicated {count} items")

    def _remove_selected(self) -> None:
        selected = self.campaign_tree.get_selected_items_with_context()
        if not selected:
            return

        if len(selected) == 1:
            current = self.campaign_tree.currentItem()
            name = current.text(0) if current else selected[0][1]
            confirm_msg = f'Remove "{name}" and all its children?\n\nYou can undo this with Ctrl+Z.'
        else:
            name = None
            confirm_msg = f'Remove {len(selected)} items and all their children?\n\nYou can undo this with Ctrl+Z.'

        reply = QMessageBox.question(
            self,
            "Confirm Remove",
            confirm_msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self._commit_current()

        # Remove children before parents to avoid broken references during batch
        type_order = {NODE_AD: 0, NODE_ADSET: 1, NODE_CAMPAIGN: 2}
        sorted_selected = sorted(selected, key=lambda x: type_order.get(x[0], 3))

        commands = []
        for node_type, node_id, camp_id, adset_id in sorted_selected:
            if node_type == NODE_CAMPAIGN:
                campaign = self._find_campaign(node_id)
                if campaign:
                    commands.append(RemoveCampaignCommand(self.session, campaign))
            elif node_type == NODE_ADSET:
                campaign = self._find_campaign(camp_id)
                adset = self._find_adset(node_id)
                if campaign and adset:
                    commands.append(RemoveAdSetCommand(campaign, adset))
            elif node_type == NODE_AD:
                adset = self._find_adset(adset_id)
                ad = self._find_ad(node_id)
                if adset and ad:
                    commands.append(RemoveAdCommand(adset, ad))

        if not commands:
            return

        if len(commands) == 1:
            cmd = commands[0]
            self._history.push(cmd)
            self._after_command(cmd.select_id)
            self._update_status(f"Removed: {name}")
        else:
            batch = BatchRemoveCommand(commands)
            self._history.push(batch)
            self._after_command(batch.select_id)
            self._update_status(f"Removed {len(commands)} items")

    # ------------------------------------------------------------------
    # Session persistence
    # ------------------------------------------------------------------

    def _new_session(self) -> None:
        if self.session.campaigns:
            reply = QMessageBox.question(
                self,
                "New Session",
                "Discard the current session and start fresh?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        self.session = SessionData()
        self._session_path = ""
        self._history.clear()
        self._update_undo_redo_actions()
        self.campaign_tree.load_session(self.session)
        self.editor_stack.setCurrentIndex(0)
        self.setWindowTitle("Meta Campaign Setup Tool")
        self._update_status("New session started")

    def _open_session(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Session", "", "JSON Files (*.json)"
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.session = SessionData.from_dict(data)
            self._session_path = path
            self._history.clear()
            self._update_undo_redo_actions()
            self.campaign_tree.load_session(self.session)
            self.editor_stack.setCurrentIndex(0)
            self.setWindowTitle(f"Meta Campaign Setup Tool — {os.path.basename(path)}")
            self._add_recent(path)
            self._update_status(f"Session loaded: {path}")
        except (OSError, ValueError, KeyError) as e:
            QMessageBox.critical(self, "Error Loading Session", str(e))

    def _save_session(self) -> None:
        if not self._session_path:
            self._save_session_as()
            return
        self._commit_current()
        try:
            with open(self._session_path, "w", encoding="utf-8") as f:
                json.dump(self.session.to_dict(), f, indent=2)
            self._add_recent(self._session_path)
            self._update_status(f"Saved: {self._session_path}")
        except OSError as e:
            QMessageBox.critical(self, "Error Saving Session", str(e))

    def _save_session_as(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Session As", "", "JSON Files (*.json)"
        )
        if path:
            self._session_path = path
            self.setWindowTitle(f"Meta Campaign Setup Tool — {os.path.basename(path)}")
            self._save_session()

    # ------------------------------------------------------------------
    # Settings + Import
    # ------------------------------------------------------------------

    def _fetch_meta_resources(self) -> None:
        """Fetch pixels and apps for the current account and push to campaign editor."""
        client = self._get_client_silently()
        if not client:
            return
        try:
            self._pixels = list_pixels(client)
        except (MetaApiError, OSError):
            self._pixels = []
        try:
            self._apps = list_apps(client)
        except (MetaApiError, OSError):
            self._apps = []
        self.campaign_editor.set_meta_resources(self._pixels, self._apps)
        self.adset_editor.set_meta_resources(self._pixels, self._apps)
        self.bulk_edit_panel.set_meta_resources(self._pixels, self._apps)

    def _open_settings(self) -> None:
        dialog = SettingsDialog(self.settings_store, parent=self)
        if dialog.exec():
            self._load_account_page_combos()
            self._fetch_meta_resources()

    def _open_plan_import(self) -> None:
        self._commit_current()
        dialog = PlanImportDialog(parent=self)
        if dialog.exec() and dialog.imported_campaigns:
            for campaign in dialog.imported_campaigns:
                self.session.campaigns.append(campaign)
            self.campaign_tree.load_session(self.session)
            self._update_status(
                f"Imported {len(dialog.imported_campaigns)} campaign(s) from Plan"
            )

    def _open_excel_import(self) -> None:
        self._commit_current()
        dialog = ExcelImportDialog(parent=self)
        if dialog.exec() and dialog.imported_campaigns:
            for campaign in dialog.imported_campaigns:
                self.session.campaigns.append(campaign)
            self.campaign_tree.load_session(self.session)
            self._update_status(
                f"Imported {len(dialog.imported_campaigns)} campaign(s) from Excel"
            )

    # ------------------------------------------------------------------
    # Validate + Upload
    # ------------------------------------------------------------------

    def _validate_only(self) -> None:
        self._commit_current()
        errors: list[str] = []
        for campaign in self.session.campaigns:
            errors.extend(validate_campaign(campaign))

        if not self.session.campaigns:
            QMessageBox.information(
                self, "Nothing to Validate", "No campaigns in the current session."
            )
            return

        if errors:
            msg = f"Found {len(errors)} issue(s):\n\n" + "\n".join(errors)
            QMessageBox.warning(self, "Validation Errors", msg)
        else:
            QMessageBox.information(
                self,
                "Validation Passed",
                f"All {len(self.session.campaigns)} campaign(s) are valid and ready for upload.",
            )

    def _prepare_upload(self) -> tuple[MetaApiClient, str, str] | None:
        """Validate session, check credentials, and return (client, page_id, instagram_user_id) or None."""
        self._commit_current()

        if not self.session.campaigns:
            QMessageBox.information(
                self, "Nothing to Process", "No campaigns in the current session."
            )
            return None

        errors: list[str] = []
        for campaign in self.session.campaigns:
            errors.extend(validate_campaign(campaign))
        if errors:
            msg = f"Please fix {len(errors)} validation error(s):\n\n" + "\n".join(
                errors
            )
            QMessageBox.warning(self, "Validation Errors", msg)
            return None

        settings = self.settings_store.load()
        access_token = settings.get("access_token", "").strip()

        # Read selected account / page / instagram from dropdowns
        ad_account_id = self.account_combo.currentData() or ""
        page_id = self.page_combo.currentData() or ""
        instagram_user_id = self.instagram_combo.currentData() or ""

        missing = []
        if not access_token:
            missing.append("Access Token (configure in Settings)")
        if not ad_account_id:
            missing.append("Ad Account (select from left panel or add in Settings)")
        if not page_id:
            missing.append("Page (select from left panel or add in Settings)")
        if missing:
            QMessageBox.warning(
                self,
                "Missing API Credentials",
                "Please configure the following:\n• " + "\n• ".join(missing),
            )
            return None

        client = MetaApiClient(
            access_token=access_token,
            ad_account_id=ad_account_id,
            api_version=settings.get("api_version", "v25.0"),
        )
        return client, page_id, instagram_user_id

    def _start_upload(self) -> None:
        result = self._prepare_upload()
        if result is None:
            return
        client, page_id, instagram_user_id = result

        dialog = UploadProgressDialog(
            WorkerConfig(self.session.campaigns, client, page_id, instagram_user_id=instagram_user_id),
            parent=self,
        )
        dialog.exec()

    def _start_test_upload(self) -> None:
        result = self._prepare_upload()
        if result is None:
            return
        client, page_id, instagram_user_id = result

        dialog = UploadProgressDialog(
            WorkerConfig(self.session.campaigns, client, page_id, instagram_user_id=instagram_user_id, validate_only=True),
            parent=self,
        )
        dialog.exec()

    # ------------------------------------------------------------------
    # API Sync — Pull / Push
    # ------------------------------------------------------------------

    def _get_client_silently(self) -> MetaApiClient | None:
        """Build a MetaApiClient if credentials are available, without showing any dialogs."""
        settings = self.settings_store.load()
        token = settings.get("access_token", "").strip()
        account_id = self.account_combo.currentData() or ""
        if not token or not account_id:
            return None
        return MetaApiClient(
            access_token=token,
            ad_account_id=account_id,
            api_version=settings.get("api_version", "v25.0"),
        )

    def _prepare_client(self) -> tuple[MetaApiClient, str] | None:
        """Check credentials and return (client, page_id) without validating campaigns."""
        settings = self.settings_store.load()
        access_token = settings.get("access_token", "").strip()
        ad_account_id = self.account_combo.currentData() or ""
        page_id = self.page_combo.currentData() or ""

        missing = []
        if not access_token:
            missing.append("Access Token (configure in Settings)")
        if not ad_account_id:
            missing.append("Ad Account (select from left panel or add in Settings)")
        if not page_id:
            missing.append("Page (select from left panel or add in Settings)")
        if missing:
            QMessageBox.warning(
                self,
                "Missing API Credentials",
                "Please configure the following:\n• " + "\n• ".join(missing),
            )
            return None

        client = MetaApiClient(
            access_token=access_token,
            ad_account_id=ad_account_id,
            api_version=settings.get("api_version", "v25.0"),
        )
        return client, page_id

    def _start_pull(self) -> None:
        """Pull existing campaigns from the Meta API into the current session."""
        result = self._prepare_client()
        if result is None:
            return
        client, _ = result

        # Let user select which campaigns to pull and filter by status
        select_dialog = SelectCampaignsDialog(client, parent=self)
        if select_dialog.exec() != QDialog.DialogCode.Accepted:
            return
        campaign_ids = select_dialog.selected_ids
        status_filter = select_dialog.status_filter
        if campaign_ids is not None and len(campaign_ids) == 0:
            QMessageBox.information(self, "Nothing Selected", "No campaigns were selected.")
            return

        dialog = PullProgressDialog(
            client,
            parent=self,
            campaign_ids=campaign_ids,
            status_filter=status_filter,
        )
        dialog.exec()

        if dialog.success and dialog.pulled_campaigns:
            self._commit_current()
            for campaign in dialog.pulled_campaigns:
                self.session.campaigns.append(campaign)
            self.campaign_tree.load_session(self.session)
            self.editor_stack.setCurrentIndex(0)
            self._update_status(
                f"Pulled {len(dialog.pulled_campaigns)} campaign(s) from API"
            )

    def _start_push(self) -> None:
        """Push updates for campaigns that have FB IDs back to the API."""
        self._commit_current()

        # Only push campaigns that have been uploaded (have fb_campaign_id)
        pushable = [c for c in self.session.campaigns if c.fb_campaign_id]
        if not pushable:
            QMessageBox.information(
                self,
                "Nothing to Push",
                "No campaigns with existing Facebook IDs found.\n"
                "Only campaigns that have been uploaded or pulled from the API can be pushed.",
            )
            return

        result = self._prepare_client()
        if result is None:
            return
        client, page_id = result
        instagram_user_id = self.instagram_combo.currentData() or ""

        # Let user select which campaigns/adsets/ads to push (or preview)
        select_dialog = SelectPushDialog(pushable, parent=self)
        if select_dialog.exec() != QDialog.DialogCode.Accepted:
            return
        selected_ids = select_dialog.selected_ids
        preview_only = select_dialog.preview_only
        if not selected_ids:
            QMessageBox.information(self, "Nothing Selected", "No objects were selected.")
            return

        if not preview_only:
            reply = QMessageBox.question(
                self,
                "Push Updates to API",
                f"This will update {len(selected_ids)} selected object(s) on the Meta API.\n\n"
                "Note: Creative content is immutable — if creative content was changed, "
                "a new creative will be created and swapped.\n\nContinue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        dialog = PushProgressDialog(
            WorkerConfig(pushable, client, page_id, instagram_user_id=instagram_user_id, selected_ids=selected_ids, validate_only=preview_only),
            parent=self,
        )
        dialog.exec()

    # ------------------------------------------------------------------
    # Data lookup helpers
    # ------------------------------------------------------------------

    def _find_campaign(self, campaign_id: str) -> CampaignData | None:
        return next((c for c in self.session.campaigns if c.id == campaign_id), None)

    def _find_adset(self, adset_id: str) -> AdSetData | None:
        for c in self.session.campaigns:
            for a in c.ad_sets:
                if a.id == adset_id:
                    return a
        return None

    def _find_ad(self, ad_id: str) -> AdData | None:
        for c in self.session.campaigns:
            for a in c.ad_sets:
                for ad in a.ads:
                    if ad.id == ad_id:
                        return ad
        return None

    # ------------------------------------------------------------------
    # Recent sessions
    # ------------------------------------------------------------------

    _MAX_RECENT = 5

    def _rebuild_recent_menu(self) -> None:
        self._recent_menu.clear()
        settings = self.settings_store.load()
        recent: list[str] = settings.get("recent_sessions", [])
        if not recent:
            action = self._recent_menu.addAction("(no recent sessions)")
            action.setEnabled(False)
            return
        for path in recent:
            display = os.path.basename(path)
            action = self._recent_menu.addAction(display)
            action.setToolTip(path)
            action.triggered.connect(lambda checked, p=path: self._open_recent(p))

    def _add_recent(self, path: str) -> None:
        settings = self.settings_store.load()
        recent: list[str] = settings.get("recent_sessions", [])
        # Move to front, deduplicate
        if path in recent:
            recent.remove(path)
        recent.insert(0, path)
        recent = recent[: self._MAX_RECENT]
        settings["recent_sessions"] = recent
        self.settings_store.save(settings)
        self._rebuild_recent_menu()

    def _open_recent(self, path: str) -> None:
        if not os.path.exists(path):
            QMessageBox.warning(self, "File Not Found", f"Could not find:\n{path}")
            return
        self._commit_current()
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.session = SessionData.from_dict(data)
            self._session_path = path
            self._history.clear()
            self._update_undo_redo_actions()
            self._add_recent(path)
            self.campaign_tree.load_session(self.session)
            self.editor_stack.setCurrentIndex(0)
            self.setWindowTitle(f"Meta Campaign Setup Tool — {os.path.basename(path)}")
            self._update_status(f"Session loaded: {path}")
        except (OSError, ValueError, KeyError) as e:
            QMessageBox.critical(self, "Error Loading Session", str(e))

    # ------------------------------------------------------------------
    # Misc
    # ------------------------------------------------------------------

    def _update_status(self, message: str) -> None:
        self.status_bar.showMessage(message)

    def closeEvent(self, event) -> None:  # pylint: disable=invalid-name
        self._commit_current()
        event.accept()
