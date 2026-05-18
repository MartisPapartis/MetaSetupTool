"""Pull progress dialog — shown while fetching campaigns from the API."""

from __future__ import annotations

from app.api.client import MetaApiClient
from app.models.campaign_data import CampaignData
from app.ui.base_progress_dialog import BaseProgressDialog
from app.workers.pull_worker import PullWorker


class PullProgressDialog(BaseProgressDialog):
    """Modal dialog that runs PullWorker and exposes the result."""

    def __init__(
        self,
        client: MetaApiClient,
        parent=None,
        campaign_ids: list[str] | None = None,
        status_filter: list[str] | None = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Pulling Campaigns from API")
        self.setMinimumSize(720, 500)
        self.setModal(True)

        self.pulled_campaigns: list[CampaignData] = []
        self._success = False
        self._setup_progress_ui(initial_status="Pulling campaigns...", show_cancel=False)

        self.worker = PullWorker(
            client,
            parent=self,
            campaign_ids=campaign_ids,
            status_filter=status_filter,
        )
        self.worker.log_message.connect(self._on_log)
        self.worker.progress_updated.connect(self.progress_bar.setValue)
        self.worker.finished.connect(self._on_finished)

        self.close_btn.clicked.connect(self.accept)
        self.worker.start()

    def _on_finished(self, success: bool, message: str, campaigns: list) -> None:
        self._success = success
        if success:
            self.pulled_campaigns = campaigns
            self.status_label.setText("Pull complete!")
            self.status_label.setStyleSheet("font-weight: bold; color: #4caf50;")
            self.progress_bar.setValue(100)
        else:
            self.status_label.setText("Pull finished with errors.")
            self.status_label.setStyleSheet("font-weight: bold; color: #f44336;")

        self._on_log(f"\n{'SUCCESS' if success else 'ERROR'}: {message}")
        self.close_btn.setEnabled(True)

    @property
    def success(self) -> bool:
        return self._success

    def closeEvent(self, event) -> None:  # pylint: disable=invalid-name
        if self.worker.isRunning():
            self.worker.wait(5000)
        super().closeEvent(event)
