"""Audience worker — fetches custom, lookalike, and saved audiences in a background thread."""

from __future__ import annotations

from PyQt6.QtCore import QThread, pyqtSignal

from app.api.client import MetaApiClient, MetaApiError
from app.api.campaign_reader import (
    _fetch_all_custom_audiences,
    list_saved_audiences,
    list_dsa_entities,
)


class AudienceWorker(QThread):
    """
    Signals:
      finished(list, list, list, list, list)
        — (custom, lookalike, saved, dsa_payors, dsa_beneficiaries)
      error(str)                              — human-readable error message
    """

    finished = pyqtSignal(list, list, list, list, list)
    error = pyqtSignal(str)

    def __init__(self, client: MetaApiClient, parent=None):
        super().__init__(parent)
        self.client = client

    def run(self) -> None:
        try:
            all_custom = _fetch_all_custom_audiences(self.client)
            custom = [a for a in all_custom if a.get("subtype") != "LOOKALIKE"]
            lookalike = [a for a in all_custom if a.get("subtype") == "LOOKALIKE"]
            saved = list_saved_audiences(self.client)
            dsa_payors, dsa_beneficiaries = list_dsa_entities(self.client)
            self.finished.emit(custom, lookalike, saved, dsa_payors, dsa_beneficiaries)
        except MetaApiError as e:
            self.error.emit(str(e))
        except Exception as e:  # pylint: disable=broad-exception-caught
            # Worker thread — must not propagate; surface all failures via signal
            self.error.emit(f"Failed to load audiences: {e}")
