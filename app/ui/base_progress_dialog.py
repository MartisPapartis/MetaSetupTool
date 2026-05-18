"""Shared base class for push/upload/pull progress dialogs."""
from __future__ import annotations

from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QTextEdit,
    QProgressBar,
    QPushButton,
)


class BaseProgressDialog(QDialog):
    """QDialog base providing status label, progress bar, log area, and buttons.

    Subclasses call ``_setup_progress_ui`` once from their constructor, then
    connect signals and start the worker.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.status_label: QLabel | None = None
        self.progress_bar: QProgressBar | None = None
        self.log_edit: QTextEdit | None = None
        self.cancel_btn: QPushButton | None = None
        self.close_btn: QPushButton | None = None

    def _setup_progress_ui(
        self, *, initial_status: str, show_cancel: bool = True
    ) -> None:
        """Build the shared UI layout."""
        layout = QVBoxLayout(self)

        self.status_label = QLabel(initial_status)
        self.status_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(self.status_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        layout.addWidget(QLabel("Log:"))
        self.log_edit = QTextEdit()
        self.log_edit.setReadOnly(True)
        self.log_edit.setFont(QFont("Courier New", 9))
        self.log_edit.setStyleSheet("background: #1e1e1e; color: #d4d4d4;")
        layout.addWidget(self.log_edit)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        if show_cancel:
            self.cancel_btn = QPushButton("Cancel")
            btn_row.addWidget(self.cancel_btn)
        self.close_btn = QPushButton("Close")
        self.close_btn.setEnabled(False)
        btn_row.addWidget(self.close_btn)
        layout.addLayout(btn_row)

    def _on_log(self, message: str) -> None:
        self.log_edit.append(message)
