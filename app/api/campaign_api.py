"""High-level API calls for campaign, ad set, ad creative, and ad creation."""

from __future__ import annotations
import json

from app.api.client import MetaApiClient
from app.models.campaign_data import CampaignData, AdSetData, AdData, CreativeData
from app.models.enums import AdFormat


def _build_campaign_budget_payload(campaign: CampaignData) -> dict:
    """Return the budget/CBO/promoted-object portion shared by create and update calls."""
    payload: dict = {}
    # Campaign budget (CBO) — daily or lifetime, mutually exclusive
    if campaign.daily_budget is not None:
        payload["daily_budget"] = str(campaign.daily_budget)
    elif campaign.lifetime_budget is not None:
        payload["lifetime_budget"] = str(campaign.lifetime_budget)
    if campaign.spend_cap is not None:
        payload["spend_cap"] = str(campaign.spend_cap)
    # bid_strategy and budget sharing require a campaign-level budget
    if campaign.has_campaign_budget:
        payload["bid_strategy"] = campaign.bid_strategy.value
        payload["is_adset_budget_sharing_enabled"] = str(
            campaign.is_budget_sharing_enabled
        ).lower()
    if campaign.promoted_object:
        payload["promoted_object"] = json.dumps(campaign.promoted_object)
    return payload


def create_campaign(
    client: MetaApiClient,
    campaign: CampaignData,
    validate_only: bool = False,
) -> str:
    """Create a campaign and return the Facebook campaign ID."""
    payload: dict = {
        "name": campaign.name,
        "objective": campaign.objective.value,
        "status": campaign.status.value,
        "special_ad_categories": json.dumps(campaign.special_ad_categories),
    }
    payload.update(_build_campaign_budget_payload(campaign))
    if validate_only:
        payload["execution_options"] = '["validate_only"]'

    result = client.post(f"{client.account_path}/campaigns", data=payload)
    return result.get("id", "")


def create_adset(
    client: MetaApiClient,
    adset: AdSetData,
    campaign_id: str,
    validate_only: bool = False,
) -> str:
    """Create an ad set under the given campaign and return its Facebook ID."""
    payload: dict = {
        "name": adset.name,
        "campaign_id": campaign_id,
        "status": adset.status.value,
        "optimization_goal": adset.optimization_goal.value,
        "billing_event": adset.billing_event.value,
        "bid_strategy": adset.bid_strategy.value,
    }

    if adset.daily_budget is not None:
        payload["daily_budget"] = str(adset.daily_budget)
    elif adset.lifetime_budget is not None:
        payload["lifetime_budget"] = str(adset.lifetime_budget)

    if adset.bid_amount is not None:
        payload["bid_amount"] = str(adset.bid_amount)

    if adset.start_time:
        payload["start_time"] = adset.start_time
    if adset.end_time:
        payload["end_time"] = adset.end_time

    if adset.dsa_payor:
        payload["dsa_payor"] = adset.dsa_payor
    if adset.dsa_beneficiary:
        payload["dsa_beneficiary"] = adset.dsa_beneficiary

    if adset.targeting:
        payload["targeting"] = json.dumps(adset.targeting)

    if adset.use_dynamic_creative:
        payload["use_dynamic_creative"] = "true"

    if adset.promoted_object:
        payload["promoted_object"] = json.dumps(adset.promoted_object)

    if validate_only:
        payload["execution_options"] = '["validate_only"]'

    result = client.post(f"{client.account_path}/adsets", data=payload)
    return result.get("id", "")


def create_ad_creative(
    client: MetaApiClient,
    creative: CreativeData,
    page_id: str,
    instagram_user_id: str = "",
    use_dynamic_creative: bool = False,
    validate_only: bool = False,
) -> str:
    """Create an ad creative and return its Facebook ID."""
    name = creative.name or "Creative"

    payload: dict = {"name": name}

    is_dynamic = (
        use_dynamic_creative and creative.has_multiple_assets
        and creative.ad_format != AdFormat.CAROUSEL
    )

    has_placement_assignments = bool(creative.placement_assignments)

    if has_placement_assignments:
        # Placement asset customization — requires both object_story_spec and asset_feed_spec
        story_spec: dict = {"page_id": page_id}
        if instagram_user_id:
            story_spec["instagram_user_id"] = instagram_user_id
        payload["object_story_spec"] = json.dumps(story_spec)
        payload["asset_feed_spec"] = json.dumps(
            _build_placement_asset_feed_spec(creative, page_id)
        )
    elif is_dynamic:
        # asset_feed_spec requires the ad set to have use_dynamic_creative=True
        payload["asset_feed_spec"] = json.dumps(_build_asset_feed_spec(creative))
        payload["page_id"] = page_id
    else:
        # Standard single-asset creative — uses only the primary media
        payload["object_story_spec"] = json.dumps(_build_story_spec(creative, page_id))

    # Advantage+ creative enhancements
    dof_spec = _build_degrees_of_freedom_spec(creative)
    if dof_spec:
        payload["degrees_of_freedom_spec"] = json.dumps(dof_spec)

    if creative.link_utm:
        payload["url_tags"] = _utm_tags(creative.link_utm)

    if validate_only:
        payload["execution_options"] = '["validate_only"]'

    result = client.post(f"{client.account_path}/adcreatives", data=payload)
    return result.get("id", "")


def _utm_tags(utm: str) -> str:
    """Strip leading '?' from UTM string for use in url_tags field."""
    return utm.lstrip("?") if utm else ""


def _build_story_spec(creative: CreativeData, page_id: str) -> dict:
    if creative.ad_format == AdFormat.SINGLE_IMAGE:
        link_data: dict = {
            "image_hash": creative.fb_image_hash,
            "link": creative.link_url,
            "message": creative.body,
            "name": creative.headline,
            "description": creative.description,
            "call_to_action": {
                "type": creative.call_to_action.value,
                "value": {"link": creative.link_url},
            },
        }
        if creative.display_url:
            link_data["caption"] = creative.display_url
        return {"page_id": page_id, "link_data": link_data}

    if creative.ad_format == AdFormat.SINGLE_VIDEO:
        video_data: dict = {
            "video_id": creative.fb_video_id,
            "title": creative.headline,
            "message": creative.body,
            "call_to_action": {
                "type": creative.call_to_action.value,
                "value": {"link": creative.link_url},
            },
        }
        if creative.fb_video_thumbnail_url:
            video_data["image_url"] = creative.fb_video_thumbnail_url
        return {"page_id": page_id, "video_data": video_data}

    if creative.ad_format == AdFormat.CAROUSEL:
        child_attachments = []
        for card in creative.carousel_cards:
            attachment: dict = {
                "link": card.link_url,
                "name": card.headline,
                "description": card.description,
                "call_to_action": {"type": card.call_to_action.value},
            }
            if card.is_video():
                attachment["video_id"] = card.fb_video_id
            else:
                attachment["image_hash"] = card.fb_image_hash
            child_attachments.append(attachment)

        return {
            "page_id": page_id,
            "link_data": {
                "link": creative.link_url or child_attachments[0].get("link", ""),
                "message": creative.body,
                "child_attachments": child_attachments,
            },
        }

    raise ValueError(f"Unknown ad format: {creative.ad_format}")


_ASSET_FORMAT_NAMES = {
    AdFormat.SINGLE_IMAGE: "SINGLE_IMAGE",
    AdFormat.SINGLE_VIDEO: "SINGLE_VIDEO",
}


def _collect_media_assets(spec: dict, creative: CreativeData) -> None:
    if creative.ad_format == AdFormat.SINGLE_IMAGE:
        images = [{"hash": h} for h in [creative.fb_image_hash] + creative.fb_extra_image_hashes if h]
        if images:
            spec["images"] = images
    elif creative.ad_format == AdFormat.SINGLE_VIDEO:
        videos = [{"video_id": v} for v in [creative.fb_video_id] + creative.fb_extra_video_ids if v]
        if videos:
            spec["videos"] = videos


def _build_asset_feed_spec(creative: CreativeData) -> dict:
    """Build an asset_feed_spec for creatives with multiple variations."""

    spec: dict = {}

    _collect_media_assets(spec, creative)

    titles = [{"text": h} for h in creative.all_headlines if h]
    if titles:
        spec["titles"] = titles

    bodies = [{"text": b} for b in creative.all_bodies if b]
    if bodies:
        spec["bodies"] = bodies

    if creative.description:
        spec["descriptions"] = [{"text": creative.description}]

    if creative.link_url:
        link_url_entry: dict = {"website_url": creative.link_url}
        if creative.display_url:
            link_url_entry["display_url"] = creative.display_url
        spec["link_urls"] = [link_url_entry]

    spec["call_to_action_types"] = [creative.call_to_action.value]

    if creative.ad_format in _ASSET_FORMAT_NAMES:
        spec["ad_formats"] = [_ASSET_FORMAT_NAMES[creative.ad_format]]

    return spec


def create_ad_creative_for_placement(
    client: MetaApiClient,
    creative: CreativeData,
    page_id: str,
    assignment: dict,
) -> str:
    """Create a single-asset creative for one placement assignment.

    Temporarily swaps the primary fb_image_hash / fb_video_id to the
    assignment's fb_id so _build_story_spec picks it up, then restores.
    """
    import os as _os
    fb_id = assignment["fb_id"]
    media_path = assignment.get("media_path", "")
    ext = media_path.rsplit(".", 1)[-1].lower() if "." in media_path else ""
    is_video = ext in {"mp4", "mov", "avi", "mkv", "m4v", "wmv", "flv"}

    # Swap primary media ID so _build_story_spec uses the assignment asset
    orig_hash = creative.fb_image_hash
    orig_video_id = creative.fb_video_id
    orig_thumb = creative.fb_video_thumbnail_url
    try:
        if is_video:
            creative.fb_video_id = fb_id
            creative.fb_video_thumbnail_url = assignment.get("thumbnail_url", "")
        else:
            creative.fb_image_hash = fb_id

        label = assignment.get("label", media_path)
        name = f"{creative.name or 'Creative'} [{label}]"
        story_spec = _build_story_spec(creative, page_id)
    finally:
        creative.fb_image_hash = orig_hash
        creative.fb_video_id = orig_video_id
        creative.fb_video_thumbnail_url = orig_thumb

    payload: dict = {
        "name": name,
        "object_story_spec": json.dumps(story_spec),
    }
    dof_spec = _build_degrees_of_freedom_spec(creative)
    if dof_spec:
        payload["degrees_of_freedom_spec"] = json.dumps(dof_spec)

    if creative.link_utm:
        payload["url_tags"] = _utm_tags(creative.link_utm)

    result = client.post(f"{client.account_path}/adcreatives", data=payload)
    return result.get("id", "")


def _build_placement_asset_feed_spec(creative: CreativeData, _page_id: str) -> dict:
    """Build an asset_feed_spec with asset_customization_rules.

    Meta requires assets to carry named adlabels, and customization rules
    reference those labels by name.  Each assignment gets a unique label
    name (e.g. "media_0", "media_1") that ties the asset entry to its rule.

    The first assignment is also marked is_default so Meta always has a
    fallback when no rule matches at serve time.
    """
    assignments = creative.placement_assignments  # list[dict]

    images: list[dict] = []
    videos: list[dict] = []

    for idx, entry in enumerate(assignments):
        fb_id = entry["fb_id"]
        media_path = entry.get("media_path", "")
        ext = media_path.rsplit(".", 1)[-1].lower() if "." in media_path else ""
        label_name = f"media_{idx}"
        adlabels = [{"name": label_name}]

        if ext in {"mp4", "mov", "avi", "mkv", "m4v", "wmv", "flv"}:
            videos.append({"video_id": fb_id, "adlabels": adlabels})
        else:
            images.append({"hash": fb_id, "adlabels": adlabels})

    spec: dict = {}
    if images:
        spec["images"] = images
    if videos:
        spec["videos"] = videos

    titles = [{"text": h} for h in creative.all_headlines if h]
    if titles:
        spec["titles"] = titles

    bodies = [{"text": b} for b in creative.all_bodies if b]
    if bodies:
        spec["bodies"] = bodies

    if creative.description:
        spec["descriptions"] = [{"text": creative.description}]

    if creative.link_url:
        link_url_entry: dict = {"website_url": creative.link_url}
        if creative.display_url:
            link_url_entry["display_url"] = creative.display_url
        spec["link_urls"] = [link_url_entry]

    spec["call_to_action_types"] = [creative.call_to_action.value]

    if creative.ad_format in _ASSET_FORMAT_NAMES:
        spec["ad_formats"] = [_ASSET_FORMAT_NAMES[creative.ad_format]]

    spec["optimization_type"] = "PLACEMENT"

    # One customization rule per assignment, referencing its label by name.
    # A final fallback rule with empty customization_spec catches any placements
    # not covered by the explicit rules (required by Meta).
    rules: list[dict] = []
    first_label: str = ""
    first_is_video: bool = False

    for idx, entry in enumerate(assignments):
        media_path = entry.get("media_path", "")
        ext = media_path.rsplit(".", 1)[-1].lower() if "." in media_path else ""
        is_video = ext in {"mp4", "mov", "avi", "mkv", "m4v", "wmv", "flv"}
        label_name = f"media_{idx}"

        if idx == 0:
            first_label = label_name
            first_is_video = is_video

        rule: dict = {"customization_spec": entry["customization_spec"]}
        if is_video:
            rule["video_label"] = {"name": label_name}
        else:
            rule["image_label"] = {"name": label_name}

        rules.append(rule)

    # Fallback rule — empty customization_spec, points to first (primary) asset
    if first_label:
        fallback: dict = {"customization_spec": {}}
        if first_is_video:
            fallback["video_label"] = {"name": first_label}
        else:
            fallback["image_label"] = {"name": first_label}
        rules.append(fallback)

    if rules:
        spec["asset_customization_rules"] = rules

    return spec


def _build_degrees_of_freedom_spec(creative: CreativeData) -> dict:
    """Build the degrees_of_freedom_spec from creative_enhancements.

    Returns an empty dict when no enhancements are configured, so the
    caller can skip sending the field entirely.
    """
    enhancements = creative.creative_enhancements
    if not enhancements:
        return {}

    features_spec: dict = {}
    for feature, status in enhancements.items():
        if status in ("OPT_IN", "OPT_OUT"):
            features_spec[feature] = {"enroll_status": status}

    if not features_spec:
        return {}

    return {"creative_features_spec": features_spec}


def create_ad(
    client: MetaApiClient,
    ad: AdData,
    adset_id: str,
    creative_id: str,
    validate_only: bool = False,
) -> str:
    """Create an ad and return its Facebook ID."""
    payload: dict = {
        "name": ad.name,
        "adset_id": adset_id,
        "creative": json.dumps({"creative_id": creative_id}),
        "status": ad.status.value,
    }
    if validate_only:
        payload["execution_options"] = '["validate_only"]'

    result = client.post(f"{client.account_path}/ads", data=payload)
    return result.get("id", "")
