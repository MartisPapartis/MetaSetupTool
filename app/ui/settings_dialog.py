"""Settings dialog — API credentials configuration."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLineEdit,
    QPushButton,
    QDialogButtonBox,
    QLabel,
    QComboBox,
    QGroupBox,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
)

from app.utils.settings_store import SettingsStore

_API_VERSIONS = [
    "v25.0",
    "v24.0",
    "v23.0",
    "v22.0",
    "v21.0",
]

_ID_ROLE = Qt.ItemDataRole.UserRole


class _EntryListWidget(QGroupBox):
    """Reusable group box with a list of id/label entries and add/remove buttons."""

    def __init__(
        self, title: str, id_placeholder: str, label_placeholder: str, parent=None
    ):
        super().__init__(title, parent)
        self._id_placeholder = id_placeholder
        self._label_placeholder = label_placeholder
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        self.list_widget = QListWidget()
        self.list_widget.setMaximumHeight(100)
        layout.addWidget(self.list_widget)

        add_row = QHBoxLayout()
        self.id_edit = QLineEdit()
        self.id_edit.setPlaceholderText(self._id_placeholder)
        add_row.addWidget(self.id_edit, stretch=2)

        self.label_edit = QLineEdit()
        self.label_edit.setPlaceholderText(self._label_placeholder)
        add_row.addWidget(self.label_edit, stretch=2)

        self.add_btn = QPushButton("Add")
        self.add_btn.setFixedWidth(60)
        self.add_btn.clicked.connect(self._add_entry)
        add_row.addWidget(self.add_btn)

        layout.addLayout(add_row)

        remove_row = QHBoxLayout()
        remove_row.addStretch()
        self.remove_btn = QPushButton("Remove Selected")
        self.remove_btn.setFixedWidth(120)
        self.remove_btn.clicked.connect(self._remove_selected)
        remove_row.addWidget(self.remove_btn)
        layout.addLayout(remove_row)

    def _add_entry(self) -> None:
        entry_id = self.id_edit.text().strip().lstrip("act_")
        label = self.label_edit.text().strip() or entry_id
        if not entry_id:
            return
        # Prevent duplicates
        for i in range(self.list_widget.count()):
            if self.list_widget.item(i).data(_ID_ROLE) == entry_id:
                return
        item = QListWidgetItem(f"{label}  ({entry_id})")
        item.setData(_ID_ROLE, entry_id)
        item.setData(_ID_ROLE + 1, label)
        self.list_widget.addItem(item)
        self.id_edit.clear()
        self.label_edit.clear()

    def _remove_selected(self) -> None:
        for item in self.list_widget.selectedItems():
            self.list_widget.takeItem(self.list_widget.row(item))

    def get_entries(self) -> list[dict]:
        entries = []
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            entries.append(
                {
                    "id": item.data(_ID_ROLE),
                    "label": item.data(_ID_ROLE + 1),
                }
            )
        return entries

    def set_entries(self, entries: list[dict]) -> None:
        self.list_widget.clear()
        for e in entries:
            entry_id = e.get("id", "")
            label = e.get("label", entry_id)
            if not entry_id:
                continue
            item = QListWidgetItem(f"{label}  ({entry_id})")
            item.setData(_ID_ROLE, entry_id)
            item.setData(_ID_ROLE + 1, label)
            self.list_widget.addItem(item)


class SettingsDialog(QDialog):
    def __init__(self, store: SettingsStore, parent=None):
        super().__init__(parent)
        self.store = store
        self.setWindowTitle("API Settings")
        self.setMinimumWidth(540)
        self._setup_ui()
        self._load()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        info = QLabel(
            "Configure your Meta Marketing API credentials.\n"
            "These are stored locally on your machine and never transmitted elsewhere."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(info)

        # Access Token
        token_group = QGroupBox("API Credentials")
        token_form = QFormLayout(token_group)
        token_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.token_edit = QLineEdit()
        self.token_edit.setPlaceholderText("EAA...")
        self.token_edit.setEchoMode(QLineEdit.EchoMode.Password)
        token_form.addRow("Access Token *", self.token_edit)

        show_token_btn = QPushButton("Show/Hide")
        show_token_btn.setFixedWidth(80)
        show_token_btn.clicked.connect(self._toggle_token_visibility)
        token_form.addRow("", show_token_btn)

        self.api_version_combo = QComboBox()
        self.api_version_combo.addItems(_API_VERSIONS)
        self.api_version_combo.setEditable(True)
        token_form.addRow("API Version", self.api_version_combo)

        layout.addWidget(token_group)

        # Ad Accounts
        self.accounts_list = _EntryListWidget(
            title="Ad Accounts *",
            id_placeholder="Account ID (without act_ prefix)",
            label_placeholder="Label (optional, e.g. Client Name)",
        )
        layout.addWidget(self.accounts_list)

        # Pages
        self.pages_list = _EntryListWidget(
            title="Pages *",
            id_placeholder="Page ID",
            label_placeholder="Label (optional, e.g. Page Name)",
        )
        layout.addWidget(self.pages_list)

        # Instagram Accounts
        self.instagram_list = _EntryListWidget(
            title="Instagram Accounts (required for Instagram placements)",
            id_placeholder="Instagram User ID",
            label_placeholder="Label (optional, e.g. @handle)",
        )
        layout.addWidget(self.instagram_list)

        hint = QLabel(
            "Tip: Use a System User token with ads_management and"
            " pages_read_engagement permissions.\n"
            "You can add multiple Ad Accounts and Pages, then select"
            " which to use from the main window."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: gray; font-size: 10px;")
        layout.addWidget(hint)

        # Test connection
        test_row = QHBoxLayout()
        test_btn = QPushButton("Test Connection")
        test_btn.clicked.connect(self._test_connection)
        test_row.addWidget(test_btn)
        self.test_label = QLabel("")
        self.test_label.setStyleSheet("font-size: 11px;")
        test_row.addWidget(self.test_label, stretch=1)
        layout.addLayout(test_row)

        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        btn_box.accepted.connect(self._save)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def _toggle_token_visibility(self) -> None:
        if self.token_edit.echoMode() == QLineEdit.EchoMode.Password:
            self.token_edit.setEchoMode(QLineEdit.EchoMode.Normal)
        else:
            self.token_edit.setEchoMode(QLineEdit.EchoMode.Password)

    def _load(self) -> None:
        settings = self.store.load()
        self.token_edit.setText(settings.get("access_token", ""))

        version = settings.get("api_version", "v25.0")
        idx = self.api_version_combo.findText(version)
        if idx >= 0:
            self.api_version_combo.setCurrentIndex(idx)
        else:
            self.api_version_combo.setCurrentText(version)

        self.accounts_list.set_entries(settings.get("ad_accounts", []))
        self.pages_list.set_entries(settings.get("pages", []))
        self.instagram_list.set_entries(settings.get("instagram_accounts", []))

    def _test_connection(self) -> None:
        """Quick API call to verify the access token is valid."""
        token = self.token_edit.text().strip()
        if not token:
            self.test_label.setText("Enter an access token first.")
            self.test_label.setStyleSheet("font-size: 11px; color: #f44336;")
            return

        version = self.api_version_combo.currentText().strip() or "v25.0"
        self.test_label.setText("Testing...")
        self.test_label.setStyleSheet("font-size: 11px; color: #d4d4d4;")
        # Force repaint so the user sees "Testing..."
        self.test_label.repaint()

        try:
            import requests  # pylint: disable=import-outside-toplevel

            url = f"https://graph.facebook.com/{version}/me"
            resp = requests.get(url, params={"access_token": token}, timeout=10)
            data = resp.json()
            if "error" in data:
                err = data["error"]
                self.test_label.setText(
                    f"Failed: {err.get('message', 'Unknown error')}"
                )
                self.test_label.setStyleSheet("font-size: 11px; color: #f44336;")
            else:
                name = data.get("name", data.get("id", "OK"))
                self.test_label.setText(f"Connected as: {name}")
                self.test_label.setStyleSheet("font-size: 11px; color: #4caf50;")
        except (requests.exceptions.RequestException, ValueError, OSError) as e:
            self.test_label.setText(f"Error: {e}")
            self.test_label.setStyleSheet("font-size: 11px; color: #f44336;")

    def _save(self) -> None:
        ad_accounts = self.accounts_list.get_entries()
        pages = self.pages_list.get_entries()

        if not ad_accounts:
            QMessageBox.warning(
                self, "Missing Data", "Please add at least one Ad Account."
            )
            return
        if not pages:
            QMessageBox.warning(self, "Missing Data", "Please add at least one Page.")
            return

        instagram_accounts = self.instagram_list.get_entries()
        settings = {
            "access_token": self.token_edit.text().strip(),
            "api_version": self.api_version_combo.currentText().strip(),
            "ad_accounts": ad_accounts,
            "pages": pages,
            "instagram_accounts": instagram_accounts,
            # Keep legacy fields in sync (first entry)
            "ad_account_id": ad_accounts[0]["id"] if ad_accounts else "",
            "page_id": pages[0]["id"] if pages else "",
        }
        self.store.save(settings)
        self.accept()
