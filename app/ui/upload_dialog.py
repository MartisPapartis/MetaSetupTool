"""Upload progress dialog — shown while the upload worker runs."""

from __future__ import annotations

from app.ui.base_progress_dialog import BaseProgressDialog
from app.workers.upload_worker import UploadWorker
from app.workers.worker_config import WorkerConfig


class UploadProgressDialog(BaseProgressDialog):
    def __init__(self, config: WorkerConfig, parent=None):
        super().__init__(parent)
        self._validate_only = config.validate_only
        title = (
            "Test Upload — Validating Campaigns" if config.validate_only else "Uploading Campaigns"
        )
        self.setWindowTitle(title)
        self.setMinimumSize(720, 500)
        self.setModal(True)
        initial_status = "Testing upload…" if config.validate_only else "Uploading…"
        self._setup_progress_ui(initial_status=initial_status)

        self.worker = UploadWorker(config, parent=self)
        self.worker.log_message.connect(self._on_log)
        self.worker.progress_updated.connect(self.progress_bar.setValue)
        self.worker.finished.connect(self._on_finished)

        self.cancel_btn.clicked.connect(self._cancel)
        self.close_btn.clicked.connect(self.accept)

        self.worker.start()

    def _on_finished(self, success: bool, message: str) -> None:
        if success:
            ok_text = (
                "Test upload passed!" if self._validate_only else "Upload complete!"
            )
            self.status_label.setText(ok_text)
            self.status_label.setStyleSheet("font-weight: bold; color: #4caf50;")
            self.progress_bar.setValue(100)
        else:
            err_text = (
                "Test upload finished with errors."
                if self._validate_only
                else "Upload finished with errors."
            )
            self.status_label.setText(err_text)
            self.status_label.setStyleSheet("font-weight: bold; color: #f44336;")

        self._on_log(f"\n{'SUCCESS' if success else 'ERRORS'}: {message}")
        self.cancel_btn.setEnabled(False)
        self.close_btn.setEnabled(True)

    def _cancel(self) -> None:
        self.worker.cancel()
        self.cancel_btn.setEnabled(False)
        self.status_label.setText("Cancelling…")

    def closeEvent(self, event) -> None:  # pylint: disable=invalid-name
        if self.worker.isRunning():
            self.worker.cancel()
            self.worker.wait(5000)
        super().closeEvent(event)
