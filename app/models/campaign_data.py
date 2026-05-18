from __future__ import annotations
import os
import uuid
from dataclasses import dataclass, field
from typing import Optional

from .enums import (
    AdFormat,
    AdObjective,
    AdStatus,
    BidStrategy,
    OptimizationGoal,
    BillingEvent,
    CallToAction,
)

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".m4v", ".wmv", ".flv"}

_DEFAULT_AD_NAMES = {
    AdFormat.SINGLE_IMAGE: "IMG_Concept_Version",
    AdFormat.SINGLE_VIDEO: "VID_Concept_Version",
    AdFormat.CAROUSEL: "CAR_Concept_Version",
}


def default_ad_name(ad_format: AdFormat) -> str:
    return _DEFAULT_AD_NAMES.get(ad_format, "IMG_Concept_Version")


def is_default_ad_name(name: str) -> bool:
    return name in _DEFAULT_AD_NAMES.values()


def _new_id() -> str:
    return str(uuid.uuid4())


@dataclass
class CarouselCard:
    id: str = field(default_factory=_new_id)
    media_path: str = ""
    headline: str = ""
    description: str = ""
    link_url: str = ""
    call_to_action: CallToAction = CallToAction.LEARN_MORE
    # Populated after upload
    fb_image_hash: str = ""
    fb_video_id: str = ""
    # Cached preview downloaded during pull (not a local source file)
    cached_preview_path: str = ""

    def is_video(self) -> bool:
        return os.path.splitext(self.media_path)[1].lower() in VIDEO_EXTENSIONS

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "media_path": self.media_path,
            "headline": self.headline,
            "description": self.description,
            "link_url": self.link_url,
            "call_to_action": self.call_to_action.value,
            "fb_image_hash": self.fb_image_hash,
            "fb_video_id": self.fb_video_id,
            "cached_preview_path": self.cached_preview_path,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "CarouselCard":
        obj = cls()
        obj.id = d.get("id", _new_id())
        obj.media_path = d.get("media_path", "")
        obj.headline = d.get("headline", "")
        obj.description = d.get("description", "")
        obj.link_url = d.get("link_url", "")
        obj.call_to_action = CallToAction(
            d.get("call_to_action", CallToAction.LEARN_MORE.value)
        )
        obj.fb_image_hash = d.get("fb_image_hash", "")
        obj.fb_video_id = d.get("fb_video_id", "")
        obj.cached_preview_path = d.get("cached_preview_path", "")
        return obj

    def duplicate(self) -> "CarouselCard":
        obj = CarouselCard.from_dict(self.to_dict())
        obj.id = _new_id()
        obj.fb_image_hash = ""
        obj.fb_video_id = ""
        return obj


@dataclass
class CreativeData:
    id: str = field(default_factory=_new_id)
    name: str = ""
    ad_format: AdFormat = AdFormat.SINGLE_IMAGE
    # Single image / video
    media_path: str = ""
    headline: str = ""
    body: str = ""
    description: str = ""
    link_url: str = ""
    link_utm: str = "?utm_source=facebook&utm_medium=ads&utm_campaign={{campaign.name}}&utm_content={{ad.name}}"
    display_url: str = ""
    call_to_action: CallToAction = CallToAction.LEARN_MORE
    # Multiple variations (Meta asset_feed_spec)
    extra_media_paths: list = field(default_factory=list)  # list[str]
    extra_headlines: list = field(default_factory=list)  # list[str]
    extra_bodies: list = field(default_factory=list)  # list[str]
    # Carousel
    carousel_cards: list = field(default_factory=list)  # list[CarouselCard]
    # Advantage+ creative enhancements — {feature_name: "OPT_IN" | "OPT_OUT"}
    creative_enhancements: dict = field(default_factory=dict)
    # Placement asset customization — populated by upload worker after dimension matching.
    # Each entry: {"media_path": str, "fb_id": str, "customization_spec": dict, "label": str}
    # fb_id is the image hash or video ID uploaded to Meta.
    placement_assignments: list = field(default_factory=list)  # list[dict]
    # Populated after upload
    fb_creative_id: str = ""
    fb_image_hash: str = ""
    fb_video_id: str = ""
    fb_extra_image_hashes: list = field(default_factory=list)  # list[str]
    fb_extra_video_ids: list = field(default_factory=list)  # list[str]
    fb_video_thumbnail_url: str = ""
    fb_extra_video_thumbnail_urls: list = field(default_factory=list)  # list[str]
    # Cached preview downloaded during pull (not a local source file)
    cached_preview_path: str = ""
    # Parallel to fb_extra_image_hashes / fb_extra_video_ids — cached thumbnail per extra slot
    extra_cached_preview_paths: list = field(default_factory=list)  # list[str]
    # Maps fb_image_hash or fb_video_id → [width, height] for pulled media (no local file)
    pulled_media_dimensions: dict = field(default_factory=dict)  # dict[str, list[int]]
    # Change detection — snapshot of pushable fields at last sync
    _synced_snapshot: dict = field(default_factory=dict)

    def is_video(self) -> bool:
        return os.path.splitext(self.media_path)[1].lower() in VIDEO_EXTENSIONS

    @property
    def has_multiple_assets(self) -> bool:
        """True when the creative uses multiple variations (asset_feed_spec)."""
        return bool(
            self.extra_media_paths
            or self.fb_extra_image_hashes
            or self.fb_extra_video_ids
            or self.extra_headlines
            or self.extra_bodies
        )

    @property
    def all_media_paths(self) -> list:
        """Primary media + extras, deduplicated, preserving order."""
        paths = []
        if self.media_path:
            paths.append(self.media_path)
        for p in self.extra_media_paths:
            if p and p not in paths:
                paths.append(p)
        return paths

    @property
    def all_headlines(self) -> list:
        items = []
        if self.headline:
            items.append(self.headline)
        for h in self.extra_headlines:
            if h and h not in items:
                items.append(h)
        return items

    @property
    def all_bodies(self) -> list:
        items = []
        if self.body:
            items.append(self.body)
        for b in self.extra_bodies:
            if b and b not in items:
                items.append(b)
        return items

    def _pushable_fields(self) -> dict:
        """Content fields that matter for change detection (excludes IDs and snapshot)."""
        return {
            "name": self.name,
            "ad_format": self.ad_format.value,
            "media_path": self.media_path,
            "headline": self.headline,
            "body": self.body,
            "description": self.description,
            "link_url": self.link_url,
            "link_utm": self.link_utm,
            "display_url": self.display_url,
            "call_to_action": self.call_to_action.value,
            "extra_media_paths": list(self.extra_media_paths),
            "extra_headlines": list(self.extra_headlines),
            "extra_bodies": list(self.extra_bodies),
            "carousel_cards": [
                {k: v for k, v in c.to_dict().items() if k != "cached_preview_path"}
                for c in self.carousel_cards
            ],
            "creative_enhancements": dict(self.creative_enhancements),
        }

    def take_snapshot(self) -> None:
        """Capture current content as the 'last synced' baseline."""
        self._synced_snapshot = self._pushable_fields()

    def has_changes(self) -> bool:
        """True if content differs from last snapshot (or never snapshotted)."""
        if not self._synced_snapshot:
            return True
        return self._pushable_fields() != self._synced_snapshot

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "ad_format": self.ad_format.value,
            "media_path": self.media_path,
            "headline": self.headline,
            "body": self.body,
            "description": self.description,
            "link_url": self.link_url,
            "link_utm": self.link_utm,
            "display_url": self.display_url,
            "call_to_action": self.call_to_action.value,
            "extra_media_paths": self.extra_media_paths,
            "extra_headlines": self.extra_headlines,
            "extra_bodies": self.extra_bodies,
            "carousel_cards": [c.to_dict() for c in self.carousel_cards],
            "creative_enhancements": self.creative_enhancements,
            "placement_assignments": self.placement_assignments,
            "fb_creative_id": self.fb_creative_id,
            "fb_image_hash": self.fb_image_hash,
            "fb_video_id": self.fb_video_id,
            "fb_extra_image_hashes": self.fb_extra_image_hashes,
            "fb_extra_video_ids": self.fb_extra_video_ids,
            "cached_preview_path": self.cached_preview_path,
            "extra_cached_preview_paths": self.extra_cached_preview_paths,
            "pulled_media_dimensions": self.pulled_media_dimensions,
            "_synced_snapshot": self._synced_snapshot,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "CreativeData":
        obj = cls()
        obj.id = d.get("id", _new_id())
        obj.name = d.get("name", "")
        obj.ad_format = AdFormat(d.get("ad_format", AdFormat.SINGLE_IMAGE.value))
        obj.media_path = d.get("media_path", "")
        obj.headline = d.get("headline", "")
        obj.body = d.get("body", "")
        obj.description = d.get("description", "")
        obj.link_url = d.get("link_url", "")
        obj.link_utm = d.get("link_utm", "")
        obj.display_url = d.get("display_url", "")
        obj.call_to_action = CallToAction(
            d.get("call_to_action", CallToAction.LEARN_MORE.value)
        )
        obj.extra_media_paths = d.get("extra_media_paths", [])
        obj.extra_headlines = d.get("extra_headlines", [])
        obj.extra_bodies = d.get("extra_bodies", [])
        obj.carousel_cards = [
            CarouselCard.from_dict(c) for c in d.get("carousel_cards", [])
        ]
        obj.creative_enhancements = d.get("creative_enhancements", {})
        obj.placement_assignments = d.get("placement_assignments", [])
        obj.fb_creative_id = d.get("fb_creative_id", "")
        obj.fb_image_hash = d.get("fb_image_hash", "")
        obj.fb_video_id = d.get("fb_video_id", "")
        obj.fb_extra_image_hashes = d.get("fb_extra_image_hashes", [])
        obj.fb_extra_video_ids = d.get("fb_extra_video_ids", [])
        obj.cached_preview_path = d.get("cached_preview_path", "")
        obj.extra_cached_preview_paths = d.get("extra_cached_preview_paths", [])
        obj.pulled_media_dimensions = d.get("pulled_media_dimensions", {})
        obj._synced_snapshot = d.get("_synced_snapshot", {})
        return obj

    def duplicate(self) -> "CreativeData":
        obj = CreativeData.from_dict(self.to_dict())
        obj.id = _new_id()
        obj.fb_creative_id = ""
        obj.fb_image_hash = ""
        obj.fb_video_id = ""
        obj.fb_extra_image_hashes = []
        obj.fb_extra_video_ids = []
        obj.placement_assignments = []
        obj.cached_preview_path = ""
        obj.extra_cached_preview_paths = []
        obj.pulled_media_dimensions = {}
        obj.carousel_cards = [c.duplicate() for c in self.carousel_cards]
        return obj


@dataclass
class AdData:
    id: str = field(default_factory=_new_id)
    name: str = field(default_factory=lambda: default_ad_name(AdFormat.SINGLE_IMAGE))
    status: AdStatus = AdStatus.PAUSED
    creative: CreativeData = field(default_factory=CreativeData)
    # Populated after upload
    fb_ad_id: str = ""
    # Change detection
    _synced_snapshot: dict = field(default_factory=dict)

    def _pushable_fields(self) -> dict:
        """Ad-level fields only (creative tracked separately)."""
        return {"name": self.name, "status": self.status.value}

    def take_snapshot(self) -> None:
        self._synced_snapshot = self._pushable_fields()
        self.creative.take_snapshot()

    def has_changes(self) -> bool:
        if not self._synced_snapshot:
            return True
        return self._pushable_fields() != self._synced_snapshot

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "status": self.status.value,
            "creative": self.creative.to_dict(),
            "fb_ad_id": self.fb_ad_id,
            "_synced_snapshot": self._synced_snapshot,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "AdData":
        obj = cls()
        obj.id = d.get("id", _new_id())
        obj.name = d.get("name", "")
        obj.status = AdStatus(d.get("status", AdStatus.PAUSED.value))
        obj.creative = CreativeData.from_dict(d.get("creative", {}))
        obj.fb_ad_id = d.get("fb_ad_id", "")
        obj._synced_snapshot = d.get("_synced_snapshot", {})
        return obj

    def duplicate(self) -> "AdData":
        obj = AdData.from_dict(self.to_dict())
        obj.id = _new_id()
        obj.fb_ad_id = ""
        obj.name = f"{self.name} (copy)"
        obj.creative = self.creative.duplicate()
        return obj


@dataclass
class AdSetData:
    id: str = field(default_factory=_new_id)
    name: str = ""
    status: AdStatus = AdStatus.PAUSED
    optimization_goal: OptimizationGoal = OptimizationGoal.LINK_CLICKS
    billing_event: BillingEvent = BillingEvent.IMPRESSIONS
    bid_strategy: BidStrategy = BidStrategy.LOWEST_COST_WITHOUT_CAP
    # Budget stored in cents (int). Mutually exclusive.
    daily_budget: Optional[int] = None
    lifetime_budget: Optional[int] = None
    bid_amount: Optional[int] = None
    start_time: str = ""
    end_time: str = ""
    use_dynamic_creative: bool = False
    # DSA compliance (required for EU)
    dsa_payor: str = ""
    dsa_beneficiary: str = ""
    # Promoted object — required by some objectives at ad set level
    promoted_object: dict = field(default_factory=dict)
    # Targeting dict (raw Meta targeting spec)
    targeting: dict = field(default_factory=dict)
    ads: list = field(default_factory=list)  # list[AdData]
    # Populated after upload
    fb_adset_id: str = ""
    # Change detection
    _synced_snapshot: dict = field(default_factory=dict)

    def _pushable_fields(self) -> dict:
        """AdSet-level fields only (excludes children and IDs)."""
        return {
            "name": self.name,
            "status": self.status.value,
            "optimization_goal": self.optimization_goal.value,
            "billing_event": self.billing_event.value,
            "bid_strategy": self.bid_strategy.value,
            "daily_budget": self.daily_budget,
            "lifetime_budget": self.lifetime_budget,
            "bid_amount": self.bid_amount,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "use_dynamic_creative": self.use_dynamic_creative,
            "dsa_payor": self.dsa_payor,
            "dsa_beneficiary": self.dsa_beneficiary,
            "promoted_object": dict(self.promoted_object) if self.promoted_object else {},
            "targeting": dict(self.targeting) if self.targeting else {},
        }

    def take_snapshot(self) -> None:
        self._synced_snapshot = self._pushable_fields()
        for ad in self.ads:
            ad.take_snapshot()

    def has_changes(self) -> bool:
        if not self._synced_snapshot:
            return True
        return self._pushable_fields() != self._synced_snapshot

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "status": self.status.value,
            "optimization_goal": self.optimization_goal.value,
            "billing_event": self.billing_event.value,
            "bid_strategy": self.bid_strategy.value,
            "daily_budget": self.daily_budget,
            "lifetime_budget": self.lifetime_budget,
            "bid_amount": self.bid_amount,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "use_dynamic_creative": self.use_dynamic_creative,
            "dsa_payor": self.dsa_payor,
            "dsa_beneficiary": self.dsa_beneficiary,
            "promoted_object": self.promoted_object,
            "targeting": self.targeting,
            "ads": [a.to_dict() for a in self.ads],
            "fb_adset_id": self.fb_adset_id,
            "_synced_snapshot": self._synced_snapshot,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "AdSetData":
        obj = cls()
        obj.id = d.get("id", _new_id())
        obj.name = d.get("name", "")
        obj.status = AdStatus(d.get("status", AdStatus.PAUSED.value))
        obj.optimization_goal = OptimizationGoal(
            d.get("optimization_goal", OptimizationGoal.LINK_CLICKS.value)
        )
        obj.billing_event = BillingEvent(
            d.get("billing_event", BillingEvent.IMPRESSIONS.value)
        )
        obj.bid_strategy = BidStrategy(  # pylint: disable=no-value-for-parameter
            d.get("bid_strategy", BidStrategy.LOWEST_COST_WITHOUT_CAP.value)
        )
        obj.daily_budget = d.get("daily_budget")
        obj.lifetime_budget = d.get("lifetime_budget")
        obj.bid_amount = d.get("bid_amount")
        obj.start_time = d.get("start_time", "")
        obj.end_time = d.get("end_time", "")
        obj.use_dynamic_creative = d.get("use_dynamic_creative", False)
        obj.dsa_payor = d.get("dsa_payor", "")
        obj.dsa_beneficiary = d.get("dsa_beneficiary", "")
        obj.promoted_object = d.get("promoted_object", {})
        obj.targeting = d.get("targeting", {})
        obj.ads = [AdData.from_dict(a) for a in d.get("ads", [])]
        obj.fb_adset_id = d.get("fb_adset_id", "")
        obj._synced_snapshot = d.get("_synced_snapshot", {})
        return obj

    def duplicate(self) -> "AdSetData":
        obj = AdSetData.from_dict(self.to_dict())
        obj.id = _new_id()
        obj.fb_adset_id = ""
        obj.name = f"{self.name} (copy)"
        obj.ads = [a.duplicate() for a in self.ads]
        return obj


@dataclass
class CampaignData:
    id: str = field(default_factory=_new_id)
    name: str = ""
    objective: AdObjective = AdObjective.OUTCOME_TRAFFIC
    status: AdStatus = AdStatus.PAUSED
    special_ad_categories: list = field(default_factory=lambda: ["NONE"])
    bid_strategy: BidStrategy = BidStrategy.LOWEST_COST_WITHOUT_CAP
    # Campaign budget (CBO) — stored in cents. Mutually exclusive.
    daily_budget: Optional[int] = None
    lifetime_budget: Optional[int] = None
    spend_cap: Optional[int] = None  # in cents
    is_budget_sharing_enabled: bool = False
    promoted_object: dict = field(
        default_factory=dict
    )  # e.g. {"pixel_id": "...", "custom_event_type": "..."}
    ad_sets: list = field(default_factory=list)  # list[AdSetData]
    # Populated after upload
    fb_campaign_id: str = ""
    # Change detection
    _synced_snapshot: dict = field(default_factory=dict)

    @property
    def has_campaign_budget(self) -> bool:
        """True when budget is at the campaign level (CBO)."""
        return bool(self.daily_budget or self.lifetime_budget or self.spend_cap)

    def _pushable_fields(self) -> dict:
        """Campaign-level fields only (excludes children and IDs)."""
        return {
            "name": self.name,
            "objective": self.objective.value,
            "status": self.status.value,
            "special_ad_categories": list(self.special_ad_categories),
            "bid_strategy": self.bid_strategy.value,
            "daily_budget": self.daily_budget,
            "lifetime_budget": self.lifetime_budget,
            "spend_cap": self.spend_cap,
            "is_budget_sharing_enabled": self.is_budget_sharing_enabled,
            "promoted_object": dict(self.promoted_object)
            if self.promoted_object
            else {},
        }

    def take_snapshot(self) -> None:
        self._synced_snapshot = self._pushable_fields()
        for adset in self.ad_sets:
            adset.take_snapshot()

    def has_changes(self) -> bool:
        if not self._synced_snapshot:
            return True
        return self._pushable_fields() != self._synced_snapshot

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "objective": self.objective.value,
            "status": self.status.value,
            "special_ad_categories": self.special_ad_categories,
            "bid_strategy": self.bid_strategy.value,
            "daily_budget": self.daily_budget,
            "lifetime_budget": self.lifetime_budget,
            "spend_cap": self.spend_cap,
            "is_budget_sharing_enabled": self.is_budget_sharing_enabled,
            "promoted_object": self.promoted_object,
            "ad_sets": [a.to_dict() for a in self.ad_sets],
            "fb_campaign_id": self.fb_campaign_id,
            "_synced_snapshot": self._synced_snapshot,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "CampaignData":
        obj = cls()
        obj.id = d.get("id", _new_id())
        obj.name = d.get("name", "")
        obj.objective = AdObjective(  # pylint: disable=no-value-for-parameter
            d.get("objective", AdObjective.OUTCOME_TRAFFIC.value)
        )
        obj.status = AdStatus(d.get("status", AdStatus.PAUSED.value))
        obj.special_ad_categories = d.get("special_ad_categories", ["NONE"])
        obj.bid_strategy = BidStrategy(  # pylint: disable=no-value-for-parameter
            d.get("bid_strategy", BidStrategy.LOWEST_COST_WITHOUT_CAP.value)
        )
        obj.daily_budget = d.get("daily_budget")
        obj.lifetime_budget = d.get("lifetime_budget")
        obj.spend_cap = d.get("spend_cap")
        obj.is_budget_sharing_enabled = d.get("is_budget_sharing_enabled", True)
        obj.promoted_object = d.get("promoted_object", {})
        obj.ad_sets = [AdSetData.from_dict(a) for a in d.get("ad_sets", [])]
        obj.fb_campaign_id = d.get("fb_campaign_id", "")
        obj._synced_snapshot = d.get("_synced_snapshot", {})
        return obj

    def duplicate(self) -> "CampaignData":
        obj = CampaignData.from_dict(self.to_dict())
        obj.id = _new_id()
        obj.fb_campaign_id = ""
        obj.name = f"{self.name} (copy)"
        obj.ad_sets = [a.duplicate() for a in self.ad_sets]
        return obj


@dataclass
class SessionData:
    campaigns: list = field(default_factory=list)  # list[CampaignData]
    media_library_folder: str = ""

    def to_dict(self) -> dict:
        return {
            "campaigns": [c.to_dict() for c in self.campaigns],
            "media_library_folder": self.media_library_folder,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "SessionData":
        obj = cls()
        obj.campaigns = [CampaignData.from_dict(c) for c in d.get("campaigns", [])]
        obj.media_library_folder = d.get("media_library_folder", "")
        return obj
