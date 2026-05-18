"""Upload worker — runs the full campaign upload sequence in a background thread."""

from __future__ import annotations
import os

from PyQt6.QtCore import QThread, pyqtSignal

from app.api.client import MetaApiError
from app.api.campaign_api import (
    create_campaign,
    create_adset,
    create_ad_creative,
    create_ad_creative_for_placement,
    create_ad,
)
from app.api.media_uploader import upload_image, upload_video
from app.models.campaign_data import CampaignData, AdSetData, CreativeData, CarouselCard
from app.models.enums import AdFormat
from app.models.placement_rules import PLACEMENT_RULES
from app.utils.media_utils import get_media_dimensions
from app.workers.worker_config import WorkerConfig


class UploadWorker(QThread):
    """
    Signals:
      log_message(str)        — append a line to the log
      progress_updated(int)   — overall progress 0-100
      finished(bool, str)     — (success, summary_message)
    """

    log_message = pyqtSignal(str)
    progress_updated = pyqtSignal(int)
    finished = pyqtSignal(bool, str)

    def __init__(self, config: WorkerConfig, parent=None):
        super().__init__(parent)
        self.campaigns = config.campaigns
        self.client = config.client
        self.page_id = config.page_id
        self.validate_only = config.validate_only
        self.instagram_user_id = config.instagram_user_id
        self._cancelled = False
        # Cache: local_path -> fb_id (hash or video_id)
        self._media_cache: dict[str, str] = {}
        self._thumbnail_cache: dict[str, str] = {}
        self._current_campaign_id: str = ""

    def cancel(self) -> None:
        self._cancelled = True
        self.log_message.emit(
            "[!] Cancellation requested — stopping after current step."
        )

    def run(self) -> None:
        total = len(self.campaigns)
        if total == 0:
            self.finished.emit(False, "No campaigns to upload.")
            return

        errors: list[str] = []

        if self.validate_only:
            self._log("[DRY RUN] Validate-only mode — nothing will be created.\n")

        for idx, campaign in enumerate(self.campaigns):
            if self._cancelled:
                break
            self._log(f"\n{'=' * 60}")
            self._log(f"Campaign {idx + 1}/{total}: {campaign.name}")
            self._log(f"{'=' * 60}")

            try:
                self._upload_campaign(campaign)
                if not self.validate_only:
                    campaign.take_snapshot()
                base_pct = int((idx + 1) / total * 100)
                self.progress_updated.emit(base_pct)
            except MetaApiError as e:
                msg = f"API Error (code {e.code}): {e}"
                self._log(f"[ERROR] {msg}")
                errors.append(f"{campaign.name}: {msg}")
                # Auth errors are fatal — stop all uploads
                if e.code in (190, 200, 273):
                    self._log(
                        "[FATAL] Authentication/permission error — stopping upload."
                    )
                    break
            except Exception as e:  # pylint: disable=broad-exception-caught
                # Worker thread — must not propagate; surface all failures via signal
                msg = str(e)
                self._log(f"[ERROR] {msg}")
                errors.append(f"{campaign.name}: {msg}")

        if self._cancelled:
            self.finished.emit(False, "Upload cancelled by user.")
        elif errors:
            self.finished.emit(
                False, f"Completed with {len(errors)} error(s):\n" + "\n".join(errors)
            )
        else:
            self.finished.emit(True, f"All {total} campaign(s) uploaded successfully.")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _clear_fb_ids(self, campaign: CampaignData) -> None:
        """Reset Facebook object IDs so the campaign is treated as brand-new.

        Media hashes/video IDs are intentionally preserved: they are content
        identifiers valid for the account indefinitely and can be reused in new
        creatives.  Clearing them would break re-upload of pulled campaigns that
        have no local source files.
        """
        campaign.fb_campaign_id = ""
        for adset in campaign.ad_sets:
            adset.fb_adset_id = ""
            for ad in adset.ads:
                ad.fb_ad_id = ""
                ad.creative.fb_creative_id = ""
                ad.creative.placement_assignments = []

    def _upload_campaign(self, campaign: CampaignData) -> None:
        # Clear any stale Facebook IDs from previous failed attempts
        if not self.validate_only:
            self._clear_fb_ids(campaign)

        # Step 1: Create / validate campaign
        self._log(
            f"{'Validating' if self.validate_only else 'Creating'} campaign '{campaign.name}'..."
        )
        campaign_id = create_campaign(
            self.client, campaign, validate_only=self.validate_only
        )
        if not self.validate_only:
            campaign.fb_campaign_id = campaign_id
            self._current_campaign_id = campaign_id
            self._log(f"  Campaign created: {campaign_id}")
            parent_id = campaign_id
        else:
            self._log("  Campaign validated OK")
            # validate_only returns no ID — use the existing FB ID if the campaign was
            # previously uploaded, so ad set / ad validation can still run.
            parent_id = campaign.fb_campaign_id
            if not parent_id:
                self._log(
                    "  [TEST UPLOAD] Ad set / ad API validation skipped — "
                    "campaign has no FB ID yet. Media files will still be checked."
                )
            else:
                self._log(
                    f"  [TEST UPLOAD] Validating ad sets against existing campaign {parent_id}..."
                )

        for adset in campaign.ad_sets:
            if self._cancelled:
                return
            self._upload_adset(adset, parent_id)

    def _upload_adset(self, adset, campaign_id: str) -> None:
        if self.validate_only and not campaign_id:
            # No campaign ID available — skip adset API validation, still check media.
            self._log(f"  [TEST UPLOAD] Ad set '{adset.name}' — API validation skipped (no campaign ID).")
            for ad in adset.ads:
                if self._cancelled:
                    return
                self._upload_ad(ad, "", adset)
            return

        self._log(
            f"  {'Validating' if self.validate_only else 'Creating'} ad set '{adset.name}'..."
        )
        adset_id = create_adset(
            self.client, adset, campaign_id, validate_only=self.validate_only
        )
        if not self.validate_only:
            adset.fb_adset_id = adset_id
            self._log(f"    Ad set created: {adset_id}")
        else:
            self._log("    Ad set validated OK")

        for ad in adset.ads:
            if self._cancelled:
                return
            self._upload_ad(ad, adset_id, adset)

    def _upload_ad(self, ad, adset_id: str, adset: AdSetData) -> None:
        self._log(f"    Processing ad '{ad.name}'...")

        if self.validate_only:
            # In test-upload mode: validate media files locally; skip creative/ad API
            # validation because image hashes and adset IDs aren't real at this stage.
            self._validate_creative_media(ad.creative)
            if self._cancelled:
                return
            self._log(f"      [TEST UPLOAD] Media checked OK for '{ad.name}'.")
            return

        # Step 2: Upload media
        self._upload_creative_media(ad.creative)
        if self._cancelled:
            return

        ad.creative.name = ad.creative.name or ad.name

        # Step 3: Create creative
        self._log(f"    Creating creative for '{ad.name}'...")
        creative_id = create_ad_creative(
            self.client, ad.creative, self.page_id,
            instagram_user_id=self.instagram_user_id,
            use_dynamic_creative=adset.use_dynamic_creative,
        )
        ad.creative.fb_creative_id = creative_id
        self._log(f"      Creative created: {creative_id}")

        # Step 4: Create ad
        self._log(f"    Creating ad '{ad.name}'...")
        ad_id = create_ad(self.client, ad, adset_id, creative_id)
        ad.fb_ad_id = ad_id
        self._log(f"      Ad created: {ad_id}")

    def _validate_creative_media(self, creative: CreativeData) -> None:
        """Check that all media files exist and are readable. No uploads."""
        if creative.ad_format == AdFormat.CAROUSEL:
            paths = [card.media_path for card in creative.carousel_cards if card.media_path]
        else:
            paths = [p for p in [creative.media_path] + creative.extra_media_paths if p]
        for path in paths:
            if not os.path.isfile(path):
                raise ValueError(f"Media file not found: {path}")
            try:
                w, h = get_media_dimensions(path)
                self._log(f"      Media OK: {os.path.basename(path)} ({w}×{h})")
            except Exception as exc:
                raise ValueError(
                    f"Cannot read media '{os.path.basename(path)}': {exc}"
                ) from exc

    def _upload_creative_media(self, creative: CreativeData) -> None:
        if creative.ad_format == AdFormat.SINGLE_IMAGE:
            dim_map, fb_id_map = self._build_image_dim_map(creative) if PLACEMENT_RULES else ({}, {})

            if dim_map and _SQUARE not in set(dim_map.values()):
                self._log(
                    "[!] Media will not be uploaded — 1080x1080 (square) media is required "
                    "but was not provided. Skipping media upload for this creative."
                )
                return

            if creative.media_path:
                creative.fb_image_hash = self._ensure_image(creative.media_path)

            # Extras: upload new local files and append to kept pulled hashes
            new_hashes = list(creative.fb_extra_image_hashes)
            for path in creative.extra_media_paths:
                if path and not self._cancelled:
                    new_hashes.append(self._ensure_image(path))
            creative.fb_extra_image_hashes = new_hashes

            if dim_map:
                self._resolve_placement_assignments(creative, dim_map, fb_id_map)

        elif creative.ad_format == AdFormat.SINGLE_VIDEO:
            dim_map, fb_id_map = self._build_video_dim_map(creative) if PLACEMENT_RULES else ({}, {})

            if dim_map and _SQUARE not in set(dim_map.values()):
                self._log(
                    "[!] Media will not be uploaded — 1080x1080 (square) media is required "
                    "but was not provided. Skipping media upload for this creative."
                )
                return

            if creative.media_path:
                creative.fb_video_id = self._ensure_video(creative.media_path)
                creative.fb_video_thumbnail_url = self._thumbnail_cache.get(creative.media_path, "")

            new_video_ids = list(creative.fb_extra_video_ids)
            new_thumb_urls = list(creative.fb_extra_video_thumbnail_urls)
            for path in creative.extra_media_paths:
                if path and not self._cancelled:
                    new_video_ids.append(self._ensure_video(path))
                    new_thumb_urls.append(self._thumbnail_cache.get(path, ""))
            creative.fb_extra_video_ids = new_video_ids
            creative.fb_extra_video_thumbnail_urls = new_thumb_urls

            if dim_map:
                self._resolve_placement_assignments(creative, dim_map, fb_id_map)

        elif creative.ad_format == AdFormat.CAROUSEL:
            for card in creative.carousel_cards:
                self._upload_card_media(card)

    def _build_image_dim_map(
        self, creative: CreativeData
    ) -> tuple[dict[str, tuple[int, int]], dict[str, str]]:
        """Return (dim_map, fb_id_map) for all image slots (local + pulled)."""
        dim_map: dict[str, tuple[int, int]] = {}
        fb_id_map: dict[str, str] = {}

        if creative.media_path:
            dim_map[creative.media_path] = get_media_dimensions(creative.media_path)
        elif creative.fb_image_hash:
            dims = creative.pulled_media_dimensions.get(creative.fb_image_hash)
            if dims:
                key = f"__pulled__{creative.fb_image_hash}"
                dim_map[key] = (dims[0], dims[1])
                fb_id_map[key] = creative.fb_image_hash

        for path in creative.extra_media_paths:
            if path:
                dim_map[path] = get_media_dimensions(path)

        for fb_hash in creative.fb_extra_image_hashes:
            if fb_hash:
                dims = creative.pulled_media_dimensions.get(fb_hash)
                if dims:
                    key = f"__pulled__{fb_hash}"
                    dim_map[key] = (dims[0], dims[1])
                    fb_id_map[key] = fb_hash

        return dim_map, fb_id_map

    def _build_video_dim_map(
        self, creative: CreativeData
    ) -> tuple[dict[str, tuple[int, int]], dict[str, str]]:
        """Return (dim_map, fb_id_map) for all video slots (local + pulled)."""
        dim_map: dict[str, tuple[int, int]] = {}
        fb_id_map: dict[str, str] = {}

        if creative.media_path:
            dim_map[creative.media_path] = get_media_dimensions(creative.media_path)
        elif creative.fb_video_id:
            dims = creative.pulled_media_dimensions.get(creative.fb_video_id)
            if dims:
                key = f"__pulled__{creative.fb_video_id}"
                dim_map[key] = (dims[0], dims[1])
                fb_id_map[key] = creative.fb_video_id

        for path in creative.extra_media_paths:
            if path:
                dim_map[path] = get_media_dimensions(path)

        for video_id in creative.fb_extra_video_ids:
            if video_id:
                dims = creative.pulled_media_dimensions.get(video_id)
                if dims:
                    key = f"__pulled__{video_id}"
                    dim_map[key] = (dims[0], dims[1])
                    fb_id_map[key] = video_id

        return dim_map, fb_id_map

    def _resolve_placement_assignments(
        self,
        creative: CreativeData,
        dim_map: dict[str, tuple[int, int]],
        fb_id_map: dict[str, str] | None = None,
    ) -> None:
        """Build creative.placement_assignments from pre-read dimension map.

        fb_id_map provides fb_id overrides for pulled-media keys (keys that have
        no local file and therefore no entry in _media_cache).
        """
        creative.placement_assignments = []

        rule_by_dim = {(r.width, r.height): r for r in PLACEMENT_RULES}

        for path, (w, h) in dim_map.items():
            if (w, h) not in rule_by_dim:
                configured = ", ".join(f"{r.width}x{r.height}" for r in PLACEMENT_RULES)
                display = path if not path.startswith("__pulled__") else f"[Meta] {path[10:18]}…"
                raise ValueError(
                    f"No placement rule found for '{display}' "
                    f"({w}x{h} px). Configured dimensions: {configured}"
                )

        present_dims = set(dim_map.values())
        has_square    = _SQUARE    in present_dims
        has_story     = _STORY     in present_dims
        has_landscape = _LANDSCAPE in present_dims

        # First occurrence of each dimension is the representative media entry.
        path_by_dim: dict[tuple[int, int], str] = {}
        for path, dims in dim_map.items():
            path_by_dim.setdefault(dims, path)

        def make_assignment(media_dim: tuple[int, int], *spec_dims: tuple[int, int]) -> dict:
            path = path_by_dim[media_dim]
            fb_id = (fb_id_map or {}).get(path) or self._media_cache.get(path, "")
            if not fb_id:
                display = path if not path.startswith("__pulled__") else f"[Meta] {path[10:18]}…"
                raise ValueError(
                    f"Media '{display}' was not uploaded before "
                    "placement assignment — internal ordering error."
                )
            merged_spec = _merge_customization_specs(
                *(rule_by_dim[d].customization_spec() for d in spec_dims)
            )
            label = " + ".join(rule_by_dim[d].label for d in spec_dims)
            display = os.path.basename(path) if not path.startswith("__pulled__") else f"[Meta] {path[10:18]}…"
            self._log(f"      Placement: {display} → {label}")
            return {"media_path": path, "fb_id": fb_id, "customization_spec": merged_spec, "label": label}

        if has_square and has_story and has_landscape:
            creative.placement_assignments.append(make_assignment(_SQUARE, _SQUARE))
            creative.placement_assignments.append(make_assignment(_STORY, _STORY))
            creative.placement_assignments.append(make_assignment(_LANDSCAPE, _LANDSCAPE))

        elif has_square and has_story:
            creative.placement_assignments.append(make_assignment(_SQUARE, _SQUARE, _LANDSCAPE))
            creative.placement_assignments.append(make_assignment(_STORY, _STORY))

        elif has_square and has_landscape:
            creative.placement_assignments.append(make_assignment(_SQUARE, _SQUARE, _STORY))
            creative.placement_assignments.append(make_assignment(_LANDSCAPE, _LANDSCAPE))

        elif has_square:
            creative.placement_assignments.append(
                make_assignment(_SQUARE, _SQUARE, _STORY, _LANDSCAPE)
            )

    def _upload_placement_split_ads(self, ad, parent_adset: AdSetData) -> None:
        """Create one ad set + creative + ad per placement assignment.

        Each child ad set is a copy of the parent with its targeting restricted
        to the placements for that assignment.  The creative uses a standard
        object_story_spec with the single media matched to that placement.
        """
        import copy

        assignments = ad.creative.placement_assignments
        self._log(
            f"    Splitting '{ad.name}' into {len(assignments)} placement ad set(s)..."
        )

        for assignment in assignments:
            if self._cancelled:
                return

            label = assignment.get("label", assignment.get("media_path", ""))
            child_adset_name = f"{parent_adset.name} — {label}"
            self._log(f"    Creating placement ad set '{child_adset_name}'...")

            # Build placement-restricted targeting
            base_targeting = copy.deepcopy(parent_adset.targeting) if parent_adset.targeting else {}
            spec = assignment["customization_spec"]
            placement_targeting = _merge_placement_targeting(base_targeting, spec)

            # Create a temporary AdSetData copy with restricted targeting
            child_adset = AdSetData(
                name=child_adset_name,
                status=parent_adset.status,
                optimization_goal=parent_adset.optimization_goal,
                billing_event=parent_adset.billing_event,
                bid_strategy=parent_adset.bid_strategy,
                daily_budget=parent_adset.daily_budget,
                lifetime_budget=parent_adset.lifetime_budget,
                bid_amount=parent_adset.bid_amount,
                start_time=parent_adset.start_time,
                end_time=parent_adset.end_time,
                use_dynamic_creative=False,
                dsa_payor=parent_adset.dsa_payor,
                dsa_beneficiary=parent_adset.dsa_beneficiary,
                promoted_object=parent_adset.promoted_object,
                targeting=placement_targeting,
            )

            child_adset_id = create_adset(
                self.client, child_adset, self._current_campaign_id,
                validate_only=False,
            )
            self._log(f"      Ad set created: {child_adset_id}")

            # Create placement-specific creative
            self._log(f"      Creating creative for placement '{label}'...")
            creative_id = create_ad_creative_for_placement(
                self.client, ad.creative, self.page_id, assignment
            )
            self._log(f"      Creative created: {creative_id}")

            # Create the ad
            self._log(f"      Creating ad '{ad.name}'...")
            ad_id = create_ad(self.client, ad, child_adset_id, creative_id)
            self._log(f"      Ad created: {ad_id}")

    def _upload_card_media(self, card: CarouselCard) -> None:
        if not card.media_path:
            return
        if card.is_video():
            card.fb_video_id = self._ensure_video(card.media_path)
        else:
            card.fb_image_hash = self._ensure_image(card.media_path)

    def _read_dimensions_map(self, paths: list[str]) -> dict[str, tuple[int, int]]:
        """Read pixel dimensions for each path. Raises ValueError on read failure."""
        result: dict[str, tuple[int, int]] = {}
        for path in paths:
            try:
                result[path] = get_media_dimensions(path)
            except Exception as exc:
                raise ValueError(
                    f"Could not read dimensions for '{os.path.basename(path)}': {exc}"
                ) from exc
        return result

    def _ensure_image(self, path: str) -> str:
        if path in self._media_cache:
            self._log(f"      (reusing cached image hash for {os.path.basename(path)})")
            return self._media_cache[path]
        self._log(f"      Uploading image: {os.path.basename(path)}")
        image_hash = upload_image(self.client, path)
        self._media_cache[path] = image_hash
        self._log(f"      Image hash: {image_hash}")
        return image_hash

    def _ensure_video(self, path: str) -> str:
        if path in self._media_cache:
            self._log(f"      (reusing cached video ID for {os.path.basename(path)})")
            return self._media_cache[path]
        self._log(f"      Uploading video: {os.path.basename(path)}")

        def on_progress(pct: int) -> None:
            self._log(f"        Upload progress: {pct}%")

        video_id, thumbnail_url = upload_video(self.client, path, progress_callback=on_progress)
        self._media_cache[path] = video_id
        self._thumbnail_cache[path] = thumbnail_url
        self._log(f"      Video ID: {video_id}")
        return video_id

    def _log(self, message: str) -> None:
        self.log_message.emit(message)


# Known placement dimensions — must match PLACEMENT_RULES entries.
_SQUARE    = (1080, 1080)
_STORY     = (1080, 1920)
_LANDSCAPE = (1200, 628)


def _merge_customization_specs(*specs: dict) -> dict:
    """Union multiple customization_spec dicts into one."""
    platforms: list[str] = []
    positions: dict[str, list[str]] = {}
    for spec in specs:
        for p in spec.get("publisher_platforms", []):
            if p not in platforms:
                platforms.append(p)
        for key in ("facebook_positions", "instagram_positions",
                    "audience_network_positions", "messenger_positions"):
            if key in spec:
                bucket = positions.setdefault(key, [])
                for pos in spec[key]:
                    if pos not in bucket:
                        bucket.append(pos)
    result: dict = {"publisher_platforms": platforms}
    result.update(positions)
    return result


def _merge_placement_targeting(base: dict, customization_spec: dict) -> dict:
    """Return a copy of base targeting with placements restricted to customization_spec.

    Overwrites publisher_platforms and all *_positions keys from the spec,
    preserving all other targeting fields (geo, age, interests, etc.).
    """
    result = dict(base)
    position_keys = {
        "facebook_positions",
        "instagram_positions",
        "audience_network_positions",
        "messenger_positions",
    }
    # Remove any existing placement keys so we start clean
    for key in position_keys:
        result.pop(key, None)
    result.pop("publisher_platforms", None)

    # Apply placement fields from the customization spec
    for key, value in customization_spec.items():
        result[key] = value

    return result
