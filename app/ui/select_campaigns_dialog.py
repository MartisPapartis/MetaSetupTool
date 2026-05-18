"""Pre-pull dialog: fetch campaign list, let user select which to pull + filter by status."""

from __future__ import annotations

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QProgressBar,
    QCheckBox,
)

from app.api.client import MetaApiClient, MetaApiError
from app.api.campaign_reader import list_campaigns


# ── Background thread to fetch campaign list ───────────────────────────────


class _FetchWorker(QThread):
    done = pyqtSignal(list)    # list[dict]
    error = pyqtSignal(str)

    def __init__(self, client: MetaApiClient, parent=None):
        super().__init__(parent)
        self.client = client

    def run(self) -> None:
        try:
            campaigns = list_campaigns(self.client)
            self.done.emit(campaigns)
        except MetaApiError as e:
            self.error.emit(f"API Error (code {e.code}): {e}")
        except Exception as e:  # pylint: disable=broad-exception-caught
            # Worker thread — must not propagate; surface all failures via signal
            self.error.emit(str(e))


# ── Dialog ─────────────────────────────────────────────────────────────────


_STATUS_OPTIONS = ["All statuses", "ACTIVE", "PAUSED", "ARCHIVED", "IN_PROCESS"]


class SelectCampaignsDialog(QDialog):
    """
    Shows a list of campaigns from the API and lets the user:
      - filter by status
      - check/uncheck individual campaigns
    Returns selected campaign IDs and status_filter via .selected_ids / .status_filter.
    """

    def __init__(self, client: MetaApiClient, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Campaigns to Pull")
        self.setMinimumSize(600, 500)
        self.setModal(True)

        self._client = client
        self._all_campaigns: list[dict] = []
        self.selected_ids: list[str] | None = None   # None = user cancelled
        self.status_filter: list[str] | None = None  # None = no filter

        self._setup_ui()
        self._fetch()

    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Status filter row
        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Filter by status:"))
        self.status_combo = QComboBox()
        self.status_combo.addItems(_STATUS_OPTIONS)
        self.status_combo.currentIndexChanged.connect(self._apply_filter)
        filter_row.addWidget(self.status_combo)
        filter_row.addStretch()
        layout.addLayout(filter_row)

        # Loading indicator
        self.loading_bar = QProgressBar()
        self.loading_bar.setRange(0, 0)  # indeterminate
        layout.addWidget(self.loading_bar)

        self.error_label = QLabel("")
        self.error_label.setStyleSheet("color: #f44336;")
        self.error_label.hide()
        layout.addWidget(self.error_label)

        # Select-all checkbox + count label row
        sel_row = QHBoxLayout()
        self.select_all_chk = QCheckBox("Select all")
        self.select_all_chk.setChecked(True)
        self.select_all_chk.toggled.connect(self._toggle_all)
        sel_row.addWidget(self.select_all_chk)
        self.count_label = QLabel("")
        self.count_label.setStyleSheet("color: #888; font-size: 11px;")
        sel_row.addStretch()
        sel_row.addWidget(self.count_label)
        layout.addLayout(sel_row)

        # Campaign list
        self.list_widget = QListWidget()
        self.list_widget.itemChanged.connect(self._update_count)
        layout.addWidget(self.list_widget)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        self.pull_btn = QPushButton("Pull Selected")
        self.pull_btn.setEnabled(False)
        self.pull_btn.clicked.connect(self._accept)
        btn_row.addWidget(self.cancel_btn)
        btn_row.addWidget(self.pull_btn)
        layout.addLayout(btn_row)

    def _fetch(self) -> None:
        self._worker = _FetchWorker(self._client, parent=self)
        self._worker.done.connect(self._on_fetched)
        self._worker.error.connect(self._on_fetch_error)
        self._worker.start()

    def _on_fetched(self, campaigns: list[dict]) -> None:
        self._all_campaigns = campaigns
        self.loading_bar.hide()
        self.pull_btn.setEnabled(True)
        self._apply_filter()

    def _on_fetch_error(self, msg: str) -> None:
        self.loading_bar.hide()
        self.error_label.setText(f"Error fetching campaigns: {msg}")
        self.error_label.show()

    def _apply_filter(self) -> None:
        selected_status = self.status_combo.currentText()
        if selected_status == "All statuses":
            visible = self._all_campaigns
        else:
            visible = [
                c for c in self._all_campaigns
                if c.get("status", "").upper() == selected_status
            ]

        self.list_widget.blockSignals(True)
        self.list_widget.clear()
        for c in visible:
            status = c.get("status", "")
            name = c.get("name", "(unnamed)")
            item = QListWidgetItem(f"{name}  [{status}]")
            item.setData(Qt.ItemDataRole.UserRole, c.get("id", ""))
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked)
            self.list_widget.addItem(item)
        self.list_widget.blockSignals(False)
        self._update_count()

    def _toggle_all(self, checked: bool) -> None:
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        self.list_widget.blockSignals(True)
        for i in range(self.list_widget.count()):
            self.list_widget.item(i).setCheckState(state)
        self.list_widget.blockSignals(False)
        self._update_count()

    def _update_count(self) -> None:
        checked = sum(
            1 for i in range(self.list_widget.count())
            if self.list_widget.item(i).checkState() == Qt.CheckState.Checked
        )
        total = self.list_widget.count()
        self.count_label.setText(f"{checked} / {total} selected")

    def _accept(self) -> None:
        self.selected_ids = [
            self.list_widget.item(i).data(Qt.ItemDataRole.UserRole)
            for i in range(self.list_widget.count())
            if self.list_widget.item(i).checkState() == Qt.CheckState.Checked
        ]
        chosen_status = self.status_combo.currentText()
        self.status_filter = None if chosen_status == "All statuses" else [chosen_status]
        self.accept()

    def closeEvent(self, event) -> None:  # pylint: disable=invalid-name
        if hasattr(self, "_worker") and self._worker.isRunning():
            self._worker.wait(3000)
        super().closeEvent(event)
