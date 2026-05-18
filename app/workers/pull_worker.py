"""Pull worker — fetches the full campaign hierarchy from Meta API in a background thread."""

from __future__ import annotations

from PyQt6.QtCore import QThread, pyqtSignal

from app.api.client import MetaApiClient, MetaApiError
from app.api.campaign_reader import pull_full_hierarchy


class PullWorker(QThread):
    """
    Signals:
      log_message(str)                — append a line to the log
      progress_updated(int)           — overall progress 0-100
      finished(bool, str, list)       — (success, summary, list[CampaignData])
    """

    log_message = pyqtSignal(str)
    progress_updated = pyqtSignal(int)
    finished = pyqtSignal(bool, str, list)

    def __init__(
        self,
        client: MetaApiClient,
        parent=None,
        campaign_ids: list[str] | None = None,
        status_filter: list[str] | None = None,
    ):
        super().__init__(parent)
        self.client = client
        self.campaign_ids = campaign_ids
        self.status_filter = status_filter

    def run(self) -> None:
        try:
            self.progress_updated.emit(10)
            campaigns = pull_full_hierarchy(
                self.client,
                log=self.log_message.emit,
                campaign_ids=self.campaign_ids,
                status_filter=self.status_filter,
            )
            self.progress_updated.emit(100)
            total_adsets = sum(len(c.ad_sets) for c in campaigns)
            total_ads = sum(len(a.ads) for s in campaigns for a in s.ad_sets)
            summary = (
                f"Pulled {len(campaigns)} campaign(s), "
                f"{total_adsets} ad set(s), {total_ads} ad(s)."
            )
            self.finished.emit(True, summary, campaigns)
        except MetaApiError as e:
            self.log_message.emit(f"[ERROR] API Error (code {e.code}): {e}")
            self.finished.emit(False, f"API Error: {e}", [])
        except Exception as e:  # pylint: disable=broad-exception-caught
            # Worker thread — must not propagate; surface all failures via signal
            self.log_message.emit(f"[ERROR] {e}")
            self.finished.emit(False, str(e), [])
