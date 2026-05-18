"""Excel import dialog — stub implementation."""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QFileDialog,
    QDialogButtonBox,
    QTextEdit,
)

from app.utils.excel_reader import read_campaigns_from_excel


class ExcelImportDialog(QDialog):
    """Import campaigns from an Excel spreadsheet template."""

    imported_campaigns = None  # set after successful import

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Import from Excel")
        self.setMinimumSize(560, 380)
        self.imported_campaigns = []
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        info = QLabel(
            "Select an Excel (.xlsx) file with campaign data.\n"
            "Required columns: Campaign Name, Campaign Objective, Ad Set Name,\n"
            "Daily Budget (EUR), Start Date, End Date, Ad Name, Headline, Body, Link URL.\n\n"
            "After import, assign media to each ad in the editor."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        file_row = QHBoxLayout()
        self.file_edit = QLineEdit()
        self.file_edit.setPlaceholderText("Path to .xlsx file...")
        self.file_edit.setReadOnly(True)
        file_row.addWidget(self.file_edit)
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse)
        file_row.addWidget(browse_btn)
        layout.addLayout(file_row)

        layout.addWidget(QLabel("Preview / Log:"))
        self.log_edit = QTextEdit()
        self.log_edit.setReadOnly(True)
        layout.addWidget(self.log_edit)

        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btn_box.button(QDialogButtonBox.StandardButton.Ok).setText("Import")
        btn_box.accepted.connect(self._import)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def _browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Excel File", "", "Excel Files (*.xlsx *.xls)"
        )
        if path:
            self.file_edit.setText(path)
            self.log_edit.clear()

    def _import(self) -> None:
        path = self.file_edit.text().strip()
        if not path:
            self.log_edit.append("Please select a file first.")
            return

        # If we already parsed successfully, accept on second click
        if self.imported_campaigns:
            self.accept()
            return

        try:
            campaigns = read_campaigns_from_excel(path)
            self.imported_campaigns = campaigns
            self.log_edit.clear()
            self.log_edit.append(f"Parsed {len(campaigns)} campaign(s):\n")
            for c in campaigns:
                self.log_edit.append(f"  Campaign: {c.name}  ({c.objective.value})")
                for adset in c.ad_sets:
                    budget = ""
                    if adset.daily_budget is not None:
                        budget = f"  €{adset.daily_budget / 100:.2f}/day"
                    self.log_edit.append(f"    Ad Set: {adset.name}{budget}")
                    if adset.start_time:
                        self.log_edit.append(
                            f"      Schedule: {adset.start_time} → {adset.end_time}"
                        )
                    for ad in adset.ads:
                        self.log_edit.append(f"      Ad: {ad.name}")
                        cr = ad.creative
                        if cr.headline:
                            self.log_edit.append(f"        Headline: {cr.headline}")
                        if cr.link_url:
                            self.log_edit.append(f"        Link: {cr.link_url}")
                self.log_edit.append("")
            self.log_edit.append(
                "Review the data above, then click Import again to confirm."
            )
        except (OSError, ValueError, RuntimeError, KeyError) as e:
            self.log_edit.append(f"Error: {e}")
