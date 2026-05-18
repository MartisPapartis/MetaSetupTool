"""WorkerConfig dataclass — bundles shared worker constructor arguments."""
from __future__ import annotations

from dataclasses import dataclass, field

from app.api.client import MetaApiClient
from app.models.campaign_data import CampaignData


@dataclass
class WorkerConfig:
    """Arguments shared by UploadWorker and PushWorker.

    Pass this as the first positional argument instead of the individual fields
    to keep both worker and dialog constructors under the R0913 threshold.
    """

    campaigns: list[CampaignData]
    client: MetaApiClient
    page_id: str
    instagram_user_id: str = ""
    validate_only: bool = False
    selected_ids: set[str] | None = field(default=None)
