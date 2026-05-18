"""Plan import dialog — imports campaigns from a Plan .xlsx file (Planas sheet)."""

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

from app.utils.plan_reader import read_campaigns_from_plan


class PlanImportDialog(QDialog):
    """Import campaigns from a Plan spreadsheet (sheet: Planas)."""

    imported_campaigns = None

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Import from Plan")
        self.setMinimumSize(580, 400)
        self.imported_campaigns = []
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        info = QLabel(
            "Select a Plan (.xlsx or .xlsm) file.\n"
            'Only rows where column AD = "Meta" will be imported.\n'
            "Campaigns, ad sets, and ads will be created from the Planas sheet."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        file_row = QHBoxLayout()
        self.file_edit = QLineEdit()
        self.file_edit.setPlaceholderText("Path to Plan .xlsx / .xlsm file…")
        self.file_edit.setReadOnly(True)
        file_row.addWidget(self.file_edit)
        browse_btn = QPushButton("Browse…")
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
            self, "Select Plan File", "", "Excel Files (*.xlsx *.xlsm *.xls)"
        )
        if path:
            self.file_edit.setText(path)
            self.log_edit.clear()
            self.imported_campaigns = []

    def _import(self) -> None:
        path = self.file_edit.text().strip()
        if not path:
            self.log_edit.append("Please select a file first.")
            return

        if self.imported_campaigns:
            self.accept()
            return

        try:
            campaigns = read_campaigns_from_plan(path)
            self.imported_campaigns = campaigns
            self.log_edit.clear()
            self.log_edit.append(f"Parsed {len(campaigns)} campaign(s):\n")
            for c in campaigns:
                budget_str = ""
                if c.lifetime_budget is not None:
                    budget_str = f"  €{c.lifetime_budget / 100:.2f} lifetime"
                elif c.daily_budget is not None:
                    budget_str = f"  €{c.daily_budget / 100:.2f}/day"
                self.log_edit.append(f"  Campaign: {c.name}{budget_str}")
                for adset in c.ad_sets:
                    self.log_edit.append(f"    Ad Set: {adset.name}")
                    if adset.start_time:
                        self.log_edit.append(
                            f"      Schedule: {adset.start_time} → {adset.end_time}"
                        )
                    for ad in adset.ads:
                        self.log_edit.append(f"      Ad: {ad.name}")
                self.log_edit.append("")
            self.log_edit.append("Review the data above, then click Import again to confirm.")
        except (OSError, ValueError, RuntimeError, KeyError) as e:
            self.log_edit.append(f"Error: {e}")
