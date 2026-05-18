"""Read existing campaigns, ad sets, ads, and creatives from Meta API."""

from __future__ import annotations
import json
import urllib.request
from pathlib import Path
from typing import Callable

from app.api.client import MetaApiClient
from app.models.campaign_data import (
    CampaignData,
    AdSetData,
    AdData,
    CreativeData,
    CarouselCard,
)
from app.models.enums import (
    AdObjective,
    AdStatus,
    BidStrategy,
    OptimizationGoal,
    BillingEvent,
    CallToAction,
    AdFormat,
)

_THUMB_CACHE = Path.home() / ".metasetuptool" / "thumbnails"


def _download_preview(url: str, name: str) -> str:
    """Download a preview image URL to the local thumbnail cache.

    Returns the local path on success, or '' on failure.
    """
    if not url:
        return ""
    try:
        _THUMB_CACHE.mkdir(parents=True, exist_ok=True)
        ext = url.split("?")[0].rsplit(".", 1)[-1].lower()
        if ext not in {"jpg", "jpeg", "png", "gif", "webp"}:
            ext = "jpg"
        dest = _THUMB_CACHE / f"{name}.{ext}"
        if not dest.exists():
            urllib.request.urlretrieve(url, str(dest))
        return str(dest)
    except (OSError, ValueError):
        return ""


# Fields to request from each endpoint
_CAMPAIGN_FIELDS = ",".join(
    [
        "id",
        "name",
        "objective",
        "status",
        "bid_strategy",
        "spend_cap",
        "special_ad_categories",
        "daily_budget",
        "lifetime_budget",
        "is_adset_budget_sharing_enabled",
    ]
)

_ADSET_FIELDS = ",".join(
    [
        "id",
        "name",
        "status",
        "optimization_goal",
        "billing_event",
        "bid_strategy",
        "bid_amount",
        "daily_budget",
        "lifetime_budget",
        "targeting",
        "start_time",
        "end_time",
        "dsa_payor",
        "dsa_beneficiary",
        "use_dynamic_creative",
        "promoted_object",
    ]
)

_AD_FIELDS = ",".join(
    [
        "id",
        "name",
        "status",
        "creative{id}",
    ]
)

_CREATIVE_FIELDS = ",".join(
    [
        "id",
        "name",
        "title",
        "body",
        "image_url",
        "image_hash",
        "link_url",
        "call_to_action_type",
        "object_story_spec",
        "asset_feed_spec",
        "degrees_of_freedom_spec",
        "thumbnail_url",
        "effective_object_story_id",
    ]
)


def _paginate(client: MetaApiClient, path: str, params: dict) -> list[dict]:
    """Fetch all pages of a paginated endpoint."""
    results: list[dict] = []
    resp = client.get(path, params=params)
    results.extend(resp.get("data", []))
    while True:
        paging = resp.get("paging", {})
        next_url = paging.get("next")
        if not next_url:
            break
        after = paging.get("cursors", {}).get("after")
        if not after:
            break
        params["after"] = after
        resp = client.get(path, params=params)
        results.extend(resp.get("data", []))
    return results


def list_campaigns(
    client: MetaApiClient,
    status_filter: list[str] | None = None,
) -> list[dict]:
    """List all non-deleted campaigns for the ad account.

    status_filter: if given, only return campaigns whose effective_status is in the list
    (e.g. ["ACTIVE", "PAUSED"]).
    """
    filters: list[dict] = [
        {"field": "effective_status", "operator": "NOT_IN", "value": ["DELETED"]}
    ]
    if status_filter:
        filters.append(
            {"field": "effective_status", "operator": "IN", "value": status_filter}
        )
    return _paginate(
        client,
        f"{client.account_path}/campaigns",
        {
            "fields": _CAMPAIGN_FIELDS,
            "limit": "100",
            "filtering": json.dumps(filters),
        },
    )


def list_adsets(client: MetaApiClient, campaign_id: str) -> list[dict]:
    """List all non-deleted ad sets for a campaign."""
    return _paginate(
        client,
        f"{campaign_id}/adsets",
        {
            "fields": _ADSET_FIELDS,
            "limit": "100",
            "filtering": json.dumps(
                [
                    {
                        "field": "effective_status",
                        "operator": "NOT_IN",
                        "value": ["DELETED"],
                    }
                ]
            ),
        },
    )


def list_ads(client: MetaApiClient, adset_id: str) -> list[dict]:
    """List all non-deleted ads for an ad set."""
    return _paginate(
        client,
        f"{adset_id}/ads",
        {
            "fields": _AD_FIELDS,
            "limit": "100",
            "filtering": json.dumps(
                [
                    {
                        "field": "effective_status",
                        "operator": "NOT_IN",
                        "value": ["DELETED"],
                    }
                ]
            ),
        },
    )


def read_creative(client: MetaApiClient, creative_id: str) -> dict:
    """Read a single ad creative."""
    return client.get(creative_id, {"fields": _CREATIVE_FIELDS})


def _fetch_all_custom_audiences(client: MetaApiClient) -> list[dict]:
    """Fetch all custom audiences (including lookalikes) for the ad account."""
    return _paginate(
        client,
        f"{client.account_path}/customaudiences",
        {"fields": "id,name,subtype", "limit": "200"},
    )


def list_custom_audiences(client: MetaApiClient) -> list[dict]:
    """Return non-lookalike custom audiences for the ad account."""
    return [a for a in _fetch_all_custom_audiences(client) if a.get("subtype") != "LOOKALIKE"]


def list_lookalike_audiences(client: MetaApiClient) -> list[dict]:
    """Return lookalike audiences for the ad account."""
    return [a for a in _fetch_all_custom_audiences(client) if a.get("subtype") == "LOOKALIKE"]


def list_saved_audiences(client: MetaApiClient) -> list[dict]:
    """Return saved audience presets for the ad account."""
    return _paginate(
        client,
        f"{client.account_path}/saved_audiences",
        {"fields": "id,name,targeting", "limit": "200"},
    )


# ──────────────────────────────────────────────────────────────────
# Conversion helpers: API response dicts → app data models
# ──────────────────────────────────────────────────────────────────


def _safe_enum(enum_cls, value, default):
    try:
        return enum_cls(value)
    except (ValueError, KeyError):
        return default


def _parse_campaign(raw: dict) -> CampaignData:
    c = CampaignData()
    c.fb_campaign_id = raw.get("id", "")
    c.name = raw.get("name", "")
    c.objective = _safe_enum(
        AdObjective, raw.get("objective"), AdObjective.OUTCOME_TRAFFIC
    )
    c.status = _safe_enum(AdStatus, raw.get("status"), AdStatus.PAUSED)
    c.bid_strategy = _safe_enum(
        BidStrategy, raw.get("bid_strategy"), BidStrategy.LOWEST_COST_WITHOUT_CAP
    )
    daily = raw.get("daily_budget")
    c.daily_budget = int(daily) if daily else None
    lifetime = raw.get("lifetime_budget")
    c.lifetime_budget = int(lifetime) if lifetime else None
    cap = raw.get("spend_cap")
    c.spend_cap = int(cap) if cap else None
    c.is_budget_sharing_enabled = raw.get("is_adset_budget_sharing_enabled", True)
    c.special_ad_categories = raw.get("special_ad_categories", ["NONE"])
    return c


def _parse_adset(raw: dict) -> AdSetData:
    a = AdSetData()
    a.fb_adset_id = raw.get("id", "")
    a.name = raw.get("name", "")
    a.status = _safe_enum(AdStatus, raw.get("status"), AdStatus.PAUSED)
    a.optimization_goal = _safe_enum(
        OptimizationGoal, raw.get("optimization_goal"), OptimizationGoal.LINK_CLICKS
    )
    a.billing_event = _safe_enum(
        BillingEvent, raw.get("billing_event"), BillingEvent.IMPRESSIONS
    )
    a.bid_strategy = _safe_enum(
        BidStrategy, raw.get("bid_strategy"), BidStrategy.LOWEST_COST_WITHOUT_CAP
    )
    bid = raw.get("bid_amount")
    a.bid_amount = int(bid) if bid else None
    daily = raw.get("daily_budget")
    a.daily_budget = int(daily) if daily else None
    lifetime = raw.get("lifetime_budget")
    a.lifetime_budget = int(lifetime) if lifetime else None
    a.start_time = raw.get("start_time", "")
    a.end_time = raw.get("end_time", "")
    a.use_dynamic_creative = bool(raw.get("use_dynamic_creative", False))
    a.dsa_payor = raw.get("dsa_payor", "")
    a.dsa_beneficiary = raw.get("dsa_beneficiary", "")
    a.promoted_object = raw.get("promoted_object", {})
    a.targeting = raw.get("targeting", {})
    return a


def _parse_creative(raw: dict) -> CreativeData:
    """Parse creative from API response, handling object_story_spec or asset_feed_spec."""
    cr = CreativeData()
    cr.fb_creative_id = raw.get("id", "")
    cr.name = raw.get("name", "")

    story = raw.get("object_story_spec", {})
    feed = raw.get("asset_feed_spec")

    if feed:
        # Multi-asset creative
        _parse_asset_feed(cr, feed)
    elif "link_data" in story:
        _parse_link_data(cr, story["link_data"])
    elif "video_data" in story:
        _parse_video_data(cr, story["video_data"])

    # Parse Advantage+ creative enhancements
    dof = raw.get("degrees_of_freedom_spec", {})
    features = dof.get("creative_features_spec", {})
    for feature_name, detail in features.items():
        if isinstance(detail, dict):
            status = detail.get("enroll_status", "")
            if status in ("OPT_IN", "OPT_OUT"):
                cr.creative_enhancements[feature_name] = status

    return cr


def _parse_link_data(cr: CreativeData, ld: dict) -> None:
    children = ld.get("child_attachments")
    if children and len(children) >= 2:
        # Carousel
        cr.ad_format = AdFormat.CAROUSEL
        cr.body = ld.get("message", "")
        cr.link_url = ld.get("link", "")
        if ld.get("url_tags"):
            cr.link_utm = "?" + ld["url_tags"].lstrip("?")
        for child in children:
            card = CarouselCard()
            card.headline = child.get("name", "")
            card.description = child.get("description", "")
            card.link_url = child.get("link", "")
            card.fb_image_hash = child.get("image_hash", "")
            card.fb_video_id = child.get("video_id", "")
            cta = child.get("call_to_action", {})
            card.call_to_action = _safe_enum(
                CallToAction, cta.get("type"), CallToAction.LEARN_MORE
            )
            cr.carousel_cards.append(card)
    else:
        # Single image
        cr.ad_format = AdFormat.SINGLE_IMAGE
        cr.fb_image_hash = ld.get("image_hash", "")
        cr.headline = ld.get("name", "")
        cr.body = ld.get("message", "")
        cr.description = ld.get("description", "")
        cr.link_url = ld.get("link", "")
        cr.display_url = ld.get("caption", "")
        if ld.get("url_tags"):
            cr.link_utm = "?" + ld["url_tags"].lstrip("?")
        cta = ld.get("call_to_action", {})
        cr.call_to_action = _safe_enum(
            CallToAction, cta.get("type"), CallToAction.LEARN_MORE
        )


def _parse_video_data(cr: CreativeData, vd: dict) -> None:
    cr.ad_format = AdFormat.SINGLE_VIDEO
    cr.fb_video_id = vd.get("video_id", "")
    cr.headline = vd.get("title", "")
    cr.body = vd.get("message", "")
    cta = vd.get("call_to_action", {})
    cr.call_to_action = _safe_enum(
        CallToAction, cta.get("type"), CallToAction.LEARN_MORE
    )
    link_val = cta.get("value", {})
    cr.link_url = link_val.get("link", "")
    if vd.get("url_tags"):
        cr.link_utm = "?" + vd["url_tags"].lstrip("?")


def _parse_asset_feed(cr: CreativeData, feed: dict) -> None:
    """Parse asset_feed_spec into CreativeData with multi-asset support."""
    images = feed.get("images", [])
    videos = feed.get("videos", [])
    titles = feed.get("titles", [])
    bodies = feed.get("bodies", [])
    links = feed.get("link_urls", [])
    descriptions = feed.get("descriptions", [])
    ctas = feed.get("call_to_action_types", [])

    if videos:
        cr.ad_format = AdFormat.SINGLE_VIDEO
        if len(videos) > 0:
            cr.fb_video_id = videos[0].get("video_id", "")
        cr.fb_extra_video_ids = [v.get("video_id", "") for v in videos[1:]]
    elif images:
        cr.ad_format = AdFormat.SINGLE_IMAGE
        if len(images) > 0:
            cr.fb_image_hash = images[0].get("hash", "")
        cr.fb_extra_image_hashes = [im.get("hash", "") for im in images[1:]]

    if titles:
        cr.headline = titles[0].get("text", "")
        cr.extra_headlines = [t.get("text", "") for t in titles[1:]]
    if bodies:
        cr.body = bodies[0].get("text", "")
        cr.extra_bodies = [b.get("text", "") for b in bodies[1:]]
    if descriptions:
        cr.description = descriptions[0].get("text", "")
    if links:
        cr.link_url = links[0].get("website_url", "")
        cr.display_url = links[0].get("display_url", "")
        if links[0].get("url_tags"):
            cr.link_utm = "?" + links[0]["url_tags"].lstrip("?")
    if ctas:
        cr.call_to_action = _safe_enum(CallToAction, ctas[0], CallToAction.LEARN_MORE)


def _parse_ad(raw: dict, creative: CreativeData | None = None) -> AdData:
    ad = AdData()
    ad.fb_ad_id = raw.get("id", "")
    ad.name = raw.get("name", "")
    ad.status = _safe_enum(AdStatus, raw.get("status"), AdStatus.PAUSED)
    if creative:
        ad.creative = creative
    return ad


def _fetch_image_info(client: MetaApiClient, hashes: list[str]) -> dict[str, dict]:
    """Batch-fetch URL and dimensions for image hashes via the adimages endpoint.

    Returns {hash: {"url": str, "width": int, "height": int}}.
    """
    resp = client.get(
        f"{client.account_path}/adimages",
        {"hashes": json.dumps(hashes), "fields": "hash,url,width,height"},
    )
    result: dict[str, dict] = {}
    for item in resp.get("data", []):
        h = item.get("hash", "")
        if h:
            result[h] = {
                "url": item.get("url", ""),
                "width": item.get("width", 0),
                "height": item.get("height", 0),
            }
    return result


def _fetch_video_thumbnail_info(client: MetaApiClient, video_id: str) -> tuple[str, int, int]:
    """Fetch thumbnail URL and dimensions for a video ID.

    Returns (thumbnail_url, width, height).
    """
    resp = client.get(video_id, {"fields": "picture,format"})
    url = resp.get("picture", "")
    formats = resp.get("format", [])
    w, h = 0, 0
    if formats:
        first = formats[0]
        w = int(first.get("width", 0))
        h = int(first.get("height", 0))
    return url, w, h


def _fetch_image_media_info(
    client: MetaApiClient,
    creative: "CreativeData",
    raw_creative: dict,
    log: Callable[[str], None],
) -> None:
    """Download preview thumbnails and store dimensions for all image slots."""
    all_hashes = [h for h in ([creative.fb_image_hash] + list(creative.fb_extra_image_hashes)) if h]

    info_by_hash: dict[str, dict] = {}
    if all_hashes:
        try:
            info_by_hash = _fetch_image_info(client, all_hashes)
        except Exception as e:  # pylint: disable=broad-exception-caught
            log(f"        [WARN] Could not fetch image info: {e}")

    # Primary slot
    primary_info = info_by_hash.get(creative.fb_image_hash, {})
    primary_url = primary_info.get("url") or raw_creative.get("image_url", "")
    w, h = primary_info.get("width", 0), primary_info.get("height", 0)

    name = creative.fb_creative_id or creative.id
    creative.cached_preview_path = _download_preview(primary_url, name)
    if creative.cached_preview_path:
        log("        Preview cached.")
    if w and h and creative.fb_image_hash:
        creative.pulled_media_dimensions[creative.fb_image_hash] = [w, h]

    # Extra slots
    for i, fb_hash in enumerate(creative.fb_extra_image_hashes):
        if not fb_hash:
            creative.extra_cached_preview_paths.append("")
            continue
        info = info_by_hash.get(fb_hash, {})
        url = info.get("url", "")
        w, h = info.get("width", 0), info.get("height", 0)
        cached = _download_preview(url, f"{name}_extra_{i}")
        creative.extra_cached_preview_paths.append(cached)
        if w and h:
            creative.pulled_media_dimensions[fb_hash] = [w, h]
        if cached:
            log(f"        Extra image {i + 1} preview cached.")


def _fetch_video_media_info(
    client: MetaApiClient,
    creative: "CreativeData",
    raw_creative: dict,
    log: Callable[[str], None],
) -> None:
    """Download preview thumbnails and store dimensions for all video slots."""
    name = creative.fb_creative_id or creative.id

    # Primary slot
    primary_url = raw_creative.get("thumbnail_url", "")
    pw, ph = 0, 0
    if creative.fb_video_id:
        try:
            url, pw, ph = _fetch_video_thumbnail_info(client, creative.fb_video_id)
            if url:
                primary_url = url
        except Exception as e:  # pylint: disable=broad-exception-caught
            log(f"        [WARN] Could not fetch video thumbnail: {e}")

    creative.cached_preview_path = _download_preview(primary_url, name)
    if creative.cached_preview_path:
        log("        Preview cached.")
    if pw and ph and creative.fb_video_id:
        creative.pulled_media_dimensions[creative.fb_video_id] = [pw, ph]

    # Extra slots
    for i, video_id in enumerate(creative.fb_extra_video_ids):
        if not video_id:
            creative.extra_cached_preview_paths.append("")
            continue
        url, w, h = "", 0, 0
        try:
            url, w, h = _fetch_video_thumbnail_info(client, video_id)
        except Exception as e:  # pylint: disable=broad-exception-caught
            log(f"        [WARN] Could not fetch extra video {i + 1} thumbnail: {e}")
        cached = _download_preview(url, f"{name}_extra_{i}")
        creative.extra_cached_preview_paths.append(cached)
        if w and h:
            creative.pulled_media_dimensions[video_id] = [w, h]
        if cached:
            log(f"        Extra video {i + 1} preview cached.")


def _fetch_pulled_media_info(
    client: MetaApiClient,
    creative: "CreativeData",
    raw_creative: dict,
    log: Callable[[str], None],
) -> None:
    """Populate cached previews and stored dimensions for all pulled media slots."""
    if creative.ad_format == AdFormat.CAROUSEL:
        return
    if creative.ad_format == AdFormat.SINGLE_IMAGE:
        _fetch_image_media_info(client, creative, raw_creative, log)
    elif creative.ad_format == _AdFormat.SINGLE_VIDEO:
        _fetch_video_media_info(client, creative, raw_creative, log)


def _fetch_creative_for_ad(
    client: MetaApiClient,
    raw_ad: dict,
    log: Callable[[str], None],
) -> CreativeData:
    creative_id = raw_ad.get("creative", {}).get("id", "")
    if not creative_id:
        return CreativeData()
    try:
        log(f"      Reading creative {creative_id}...")
        raw_creative = read_creative(client, creative_id)
        creative = _parse_creative(raw_creative)
        if not creative.media_path:
            _fetch_pulled_media_info(client, creative, raw_creative, log)
        return creative
    except (KeyError, ValueError, TypeError, AttributeError) as e:
        log(f"      [WARN] Could not read creative: {e}")
        return CreativeData()


def pull_full_hierarchy(
    client: MetaApiClient,
    log: Callable[[str], None] | None = None,
    campaign_ids: list[str] | None = None,
    status_filter: list[str] | None = None,
) -> list[CampaignData]:
    """Pull complete campaign hierarchy for the ad account.

    campaign_ids: if given, only pull campaigns whose fb_campaign_id is in this list.
    status_filter: if given, filter by effective_status (e.g. ["ACTIVE"]).
    """

    def _log(msg: str) -> None:
        if log:
            log(msg)

    _log("Fetching campaigns...")
    raw_campaigns = list_campaigns(client, status_filter=status_filter)
    if campaign_ids is not None:
        id_set = set(campaign_ids)
        raw_campaigns = [rc for rc in raw_campaigns if rc.get("id") in id_set]
    _log(f"  Found {len(raw_campaigns)} campaign(s)")

    campaigns: list[CampaignData] = []
    for rc in raw_campaigns:
        campaign = _parse_campaign(rc)
        _log(f"\nCampaign: {campaign.name} ({campaign.fb_campaign_id})")

        _log("  Fetching ad sets...")
        raw_adsets = list_adsets(client, campaign.fb_campaign_id)
        _log(f"  Found {len(raw_adsets)} ad set(s)")

        for ra in raw_adsets:
            adset = _parse_adset(ra)
            _log(f"    Ad Set: {adset.name} ({adset.fb_adset_id})")

            _log("    Fetching ads...")
            raw_ads = list_ads(client, adset.fb_adset_id)
            _log(f"    Found {len(raw_ads)} ad(s)")

            for rad in raw_ads:
                creative = _fetch_creative_for_ad(client, rad, _log)
                ad = _parse_ad(rad, creative)
                _log(f"      Ad: {ad.name} ({ad.fb_ad_id})")
                adset.ads.append(ad)

            campaign.ad_sets.append(adset)
        campaigns.append(campaign)

    # Snapshot all pulled objects so push can detect local edits
    for c in campaigns:
        c.take_snapshot()

    _log(f"\nDone — pulled {len(campaigns)} campaign(s)")
    return campaigns


def list_dsa_entities(client: MetaApiClient) -> tuple[list[str], list[str]]:
    """Return (payors, beneficiaries) — unique non-empty values from existing ad sets."""
    result = client.get(
        f"{client.account_path}/adsets",
        params={"fields": "dsa_payor,dsa_beneficiary", "limit": "200"},
    )
    payors: list[str] = []
    beneficiaries: list[str] = []
    seen_p: set[str] = set()
    seen_b: set[str] = set()
    for adset in result.get("data", []):
        p = adset.get("dsa_payor", "").strip()
        b = adset.get("dsa_beneficiary", "").strip()
        if p and p not in seen_p:
            payors.append(p)
            seen_p.add(p)
        if b and b not in seen_b:
            beneficiaries.append(b)
            seen_b.add(b)
    return payors, beneficiaries


def list_pixels(client: MetaApiClient) -> list[dict]:
    """Return pixels linked to the ad account as [{"id": ..., "name": ...}]."""
    result = client.get(f"{client.account_path}/adspixels", params={"fields": "id,name"})
    return result.get("data", [])


def list_apps(client: MetaApiClient) -> list[dict]:
    """Return advertisable apps linked to the ad account as [{"id": ..., "name": ...}]."""
    result = client.get(
        f"{client.account_path}/advertisable_applications", params={"fields": "id,name"}
    )
    return result.get("data", [])
