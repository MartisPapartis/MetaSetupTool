"""Push worker — updates existing campaigns/ad sets/ads via Meta API.

Only sends API calls for objects whose content has actually changed since
the last pull or upload (snapshot-based change detection).
"""

from __future__ import annotations
import os

from PyQt6.QtCore import QThread, pyqtSignal

from app.api.client import MetaApiError
from app.api.campaign_updater import (
    update_campaign,
    update_adset,
    update_ad,
    recreate_creative,
)
from app.api.media_uploader import upload_image, upload_video
from app.models.campaign_data import CampaignData, CreativeData
from app.models.enums import AdFormat
from app.models.placement_rules import PLACEMENT_RULES
from app.utils.media_utils import get_media_dimensions
from app.workers.worker_config import WorkerConfig


class PushWorker(QThread):
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
        self.instagram_user_id = config.instagram_user_id
        self.validate_only = config.validate_only
        # None means push everything; a set means only push objects whose local id is in it
        self.selected_ids = config.selected_ids
        self._cancelled = False
        self._media_cache: dict[str, str] = {}
        self._thumbnail_cache: dict[str, str] = {}
        self._updated = 0
        self._skipped = 0

    def cancel(self) -> None:
        self._cancelled = True
        self.log_message.emit(
            "[!] Cancellation requested — stopping after current step."
        )

    def run(self) -> None:
        total = len(self.campaigns)
        if total == 0:
            self.finished.emit(False, "No campaigns to push.")
            return

        errors: list[str] = []

        if self.validate_only:
            self._log("[PREVIEW PUSH] Validate-only mode — no changes will be made.\n")

        for idx, campaign in enumerate(self.campaigns):
            if self._cancelled:
                break
            self._log(f"\n{'=' * 60}")
            self._log(f"Campaign {idx + 1}/{total}: {campaign.name}")
            self._log(f"{'=' * 60}")

            try:
                self._push_campaign(campaign)
                self.progress_updated.emit(int((idx + 1) / total * 100))
            except MetaApiError as e:
                msg = f"API Error (code {e.code}): {e}"
                self._log(f"[ERROR] {msg}")
                errors.append(f"{campaign.name}: {msg}")
                if e.code in (190, 200, 273):
                    self._log("[FATAL] Authentication/permission error — stopping.")
                    break
            except Exception as e:  # pylint: disable=broad-exception-caught
                # Worker thread — must not propagate; surface all failures via signal
                msg = str(e)
                self._log(f"[ERROR] {msg}")
                errors.append(f"{campaign.name}: {msg}")

        if self.validate_only:
            summary_parts = [
                f"{self._updated} object(s) would be updated",
                f"{self._skipped} unchanged (would be skipped)",
            ]
        else:
            summary_parts = [
                f"{self._updated} update(s) sent",
                f"{self._skipped} unchanged (skipped)",
            ]
        if self._cancelled:
            verb = "Preview" if self.validate_only else "Push"
            self.finished.emit(False, f"{verb} cancelled by user.")
        elif errors:
            self.finished.emit(
                False,
                f"Completed with {len(errors)} error(s), "
                + ", ".join(summary_parts)
                + ":\n"
                + "\n".join(errors),
            )
        else:
            verb = "Preview complete" if self.validate_only else "Push complete"
            self.finished.emit(True, f"{verb} — {', '.join(summary_parts)}.")

    def _is_selected(self, obj_id: str) -> bool:
        return self.selected_ids is None or obj_id in self.selected_ids

    def _push_campaign(self, campaign: CampaignData) -> None:
        if not campaign.fb_campaign_id:
            self._log(
                f"  [SKIP] Campaign '{campaign.name}' has no FB ID — not yet uploaded."
            )
            return

        if not self._is_selected(campaign.id):
            self._log(f"  [SKIP] Campaign '{campaign.name}' not selected for push.")
            for adset in campaign.ad_sets:
                if self._cancelled:
                    return
                self._push_adset(adset)
            return

        if campaign.has_changes():
            action = "Previewing update to" if self.validate_only else "Updating"
            self._log(f"  {action} campaign '{campaign.name}' ({campaign.fb_campaign_id})...")
            update_campaign(self.client, campaign, validate_only=self.validate_only)
            if not self.validate_only:
                campaign.take_snapshot()
            self._updated += 1
            self._log("  Campaign validated OK." if self.validate_only else "  Campaign updated.")
        else:
            self._log(f"  [NO CHANGE] Campaign '{campaign.name}' — skipping.")
            self._skipped += 1

        for adset in campaign.ad_sets:
            if self._cancelled:
                return
            self._push_adset(adset)

    def _push_adset(self, adset) -> None:
        if not adset.fb_adset_id:
            self._log(
                f"    [SKIP] Ad set '{adset.name}' has no FB ID — not yet uploaded."
            )
            return

        if not self._is_selected(adset.id):
            self._log(f"    [SKIP] Ad set '{adset.name}' not selected for push.")
            for ad in adset.ads:
                if self._cancelled:
                    return
                self._push_ad(ad, adset.use_dynamic_creative)
            return

        if adset.has_changes():
            action = "Previewing update to" if self.validate_only else "Updating"
            self._log(f"    {action} ad set '{adset.name}' ({adset.fb_adset_id})...")
            update_adset(self.client, adset, validate_only=self.validate_only)
            if not self.validate_only:
                adset.take_snapshot()
            self._updated += 1
            self._log("    Ad set validated OK." if self.validate_only else "    Ad set updated.")
        else:
            self._log(f"    [NO CHANGE] Ad set '{adset.name}' — skipping.")
            self._skipped += 1

        for ad in adset.ads:
            if self._cancelled:
                return
            self._push_ad(ad, adset.use_dynamic_creative)

    def _push_ad(self, ad, use_dynamic_creative: bool = False) -> None:
        if not ad.fb_ad_id:
            self._log(f"      [SKIP] Ad '{ad.name}' has no FB ID — not yet uploaded.")
            return

        if not self._is_selected(ad.id):
            self._log(f"      [SKIP] Ad '{ad.name}' not selected for push.")
            return

        ad_changed = ad.has_changes()
        creative_changed = ad.creative.has_changes()

        if not ad_changed and not creative_changed:
            self._log(f"      [NO CHANGE] Ad '{ad.name}' — skipping.")
            self._skipped += 1
            return

        action = "Previewing update to" if self.validate_only else "Updating"
        self._log(f"      {action} ad '{ad.name}' ({ad.fb_ad_id})...")

        # Only recreate / validate creative if creative content actually changed
        new_creative_id = None
        if creative_changed:
            if self.validate_only:
                self._validate_creative_media(ad.creative)
                if self._cancelled:
                    return
                ad.creative.placement_assignments = []
                self._log("      Creative changed — validating new creative payload...")
                recreate_creative(
                    self.client, ad.creative, self.page_id,
                    instagram_user_id=self.instagram_user_id,
                    use_dynamic_creative=use_dynamic_creative,
                    validate_only=True,
                )
                self._log("      Creative validated OK.")
                # No real creative ID — validate ad payload without creative swap.
                update_ad(self.client, ad, self.page_id, validate_only=True)
            else:
                self._upload_creative_media(ad.creative)
                if self._cancelled:
                    return
                has_instagram = any(
                    "instagram" in entry.get("customization_spec", {}).get("publisher_platforms", [])
                    for entry in ad.creative.placement_assignments
                )
                if has_instagram and not self.instagram_user_id:
                    raise ValueError(
                        "This ad targets Instagram placements but no Instagram account is selected. "
                        "Select an Instagram account in the toolbar before pushing."
                    )
                self._log(f"      Instagram account: {self.instagram_user_id or '(none — Facebook Page only)'}")
                self._log("      Creative changed — recreating (content is immutable)...")
                new_creative_id = recreate_creative(
                    self.client, ad.creative, self.page_id,
                    instagram_user_id=self.instagram_user_id,
                    use_dynamic_creative=use_dynamic_creative,
                )
                self._log(f"      New creative: {new_creative_id}")
                update_ad(self.client, ad, self.page_id, new_creative_id=new_creative_id)
        else:
            self._log("      Creative unchanged — keeping existing.")
            update_ad(
                self.client, ad, self.page_id,
                validate_only=self.validate_only,
            )

        if not self.validate_only:
            ad.take_snapshot()
        self._updated += 1
        self._log("      Ad validated OK." if self.validate_only else "      Ad updated.")

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
                self._log(f"        Media OK: {os.path.basename(path)} ({w}×{h})")
            except Exception as exc:
                raise ValueError(
                    f"Cannot read media '{os.path.basename(path)}': {exc}"
                ) from exc

    def _upload_image_creative(self, creative: CreativeData) -> None:
        dim_map, fb_id_map = self._build_image_dim_map(creative) if PLACEMENT_RULES else ({}, {})

        # Primary: upload if local file without a hash; keep existing hash if pulled
        if creative.media_path and not creative.fb_image_hash:
            creative.fb_image_hash = self._ensure_image(creative.media_path)

        # Extras: start with kept pulled hashes, then upload any new local files
        new_hashes = list(creative.fb_extra_image_hashes)
        for path in creative.extra_media_paths:
            if path and not self._cancelled:
                new_hashes.append(self._ensure_image(path))
        creative.fb_extra_image_hashes = new_hashes

        creative.placement_assignments = []
        if dim_map:
            try:
                self._resolve_placement_assignments(creative, dim_map, fb_id_map)
            except ValueError as e:
                self._log(f"      [WARN] Placement assignment skipped: {e}")

    def _upload_video_creative(self, creative: CreativeData) -> None:
        dim_map, fb_id_map = self._build_video_dim_map(creative) if PLACEMENT_RULES else ({}, {})

        # Primary: upload if local file without a video ID; keep existing ID if pulled
        if creative.media_path and not creative.fb_video_id:
            creative.fb_video_id = self._ensure_video(creative.media_path)
            creative.fb_video_thumbnail_url = self._thumbnail_cache.get(creative.media_path, "")

        # Extras: start with kept pulled IDs, then upload any new local files
        new_video_ids = list(creative.fb_extra_video_ids)
        new_thumb_urls = list(creative.fb_extra_video_thumbnail_urls)
        for path in creative.extra_media_paths:
            if path and not self._cancelled:
                new_video_ids.append(self._ensure_video(path))
                new_thumb_urls.append(self._thumbnail_cache.get(path, ""))
        creative.fb_extra_video_ids = new_video_ids
        creative.fb_extra_video_thumbnail_urls = new_thumb_urls

        creative.placement_assignments = []
        if dim_map:
            try:
                self._resolve_placement_assignments(creative, dim_map, fb_id_map)
            except ValueError as e:
                self._log(f"      [WARN] Placement assignment skipped: {e}")

    def _upload_carousel_creative(self, creative: CreativeData) -> None:
        for card in creative.carousel_cards:
            if not card.media_path or self._cancelled:
                continue
            if card.is_video() and not card.fb_video_id:
                card.fb_video_id = self._ensure_video(card.media_path)
            elif not card.is_video() and not card.fb_image_hash:
                card.fb_image_hash = self._ensure_image(card.media_path)

    def _upload_creative_media(self, creative: CreativeData) -> None:
        """Upload any local media files that haven't been uploaded yet."""
        if creative.ad_format == AdFormat.SINGLE_IMAGE:
            self._upload_image_creative(creative)
        elif creative.ad_format == AdFormat.SINGLE_VIDEO:
            self._upload_video_creative(creative)
        elif creative.ad_format == AdFormat.CAROUSEL:
            self._upload_carousel_creative(creative)

    def _ensure_image(self, path: str) -> str:
        if path in self._media_cache:
            self._log(
                f"        (reusing cached image hash for {os.path.basename(path)})"
            )
            return self._media_cache[path]
        self._log(f"        Uploading image: {os.path.basename(path)}")
        image_hash = upload_image(self.client, path)
        self._media_cache[path] = image_hash
        self._log(f"        Image hash: {image_hash}")
        return image_hash

    def _ensure_video(self, path: str) -> str:
        if path in self._media_cache:
            self._log(f"        (reusing cached video ID for {os.path.basename(path)})")
            return self._media_cache[path]
        self._log(f"        Uploading video: {os.path.basename(path)}")

        def on_progress(pct: int) -> None:
            self._log(f"          Upload progress: {pct}%")

        video_id, thumbnail_url = upload_video(self.client, path, progress_callback=on_progress)
        self._media_cache[path] = video_id
        self._thumbnail_cache[path] = thumbnail_url
        self._log(f"        Video ID: {video_id}")
        return video_id

    def _build_image_dim_map(
        self, creative: CreativeData
    ) -> tuple[dict[str, tuple[int, int]], dict[str, str]]:
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
        creative.placement_assignments = []

        rule_by_dim = {(r.width, r.height): r for r in PLACEMENT_RULES}

        for path, (w, h) in dim_map.items():
            if (w, h) not in rule_by_dim:
                configured = ", ".join(f"{r.width}x{r.height}" for r in PLACEMENT_RULES)
                display = path if not path.startswith("__pulled__") else f"[Meta] {path[10:18]}…"
                raise ValueError(
                    f"No placement rule for '{display}' ({w}x{h}). "
                    f"Configured: {configured}"
                )

        present_dims = set(dim_map.values())
        has_square    = _SQUARE    in present_dims
        has_story     = _STORY     in present_dims
        has_landscape = _LANDSCAPE in present_dims

        path_by_dim: dict[tuple[int, int], str] = {}
        for path, dims in dim_map.items():
            path_by_dim.setdefault(dims, path)

        def make_assignment(media_dim: tuple[int, int], *spec_dims: tuple[int, int]) -> dict:
            path = path_by_dim[media_dim]
            fb_id = (fb_id_map or {}).get(path) or self._media_cache.get(path, "")
            if not fb_id:
                display = path if not path.startswith("__pulled__") else f"[Meta] {path[10:18]}…"
                raise ValueError(
                    f"Media '{display}' was not uploaded before placement assignment."
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
