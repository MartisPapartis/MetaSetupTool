"""Form validation for campaign hierarchy before upload."""

from __future__ import annotations
from app.models.campaign_data import CampaignData, AdSetData, AdData, CreativeData
from app.models.enums import AdFormat


def validate_campaign(campaign: CampaignData) -> list[str]:
    errors = []
    prefix = f"[Campaign '{campaign.name or '(unnamed)'}']"

    if not campaign.name.strip():
        errors.append(f"{prefix} Name is required.")
    if not campaign.objective:
        errors.append(f"{prefix} Objective is required.")
    if not campaign.special_ad_categories:
        errors.append(f"{prefix} Special ad categories must be specified.")

    if not campaign.ad_sets:
        errors.append(f"{prefix} At least one Ad Set is required.")

    for adset in campaign.ad_sets:
        errors.extend(validate_adset(adset, campaign_prefix=prefix))

    return errors


def validate_adset(adset: AdSetData, campaign_prefix: str = "") -> list[str]:
    errors = []
    prefix = f"{campaign_prefix}[Ad Set '{adset.name or '(unnamed)'}']"

    if not adset.name.strip():
        errors.append(f"{prefix} Name is required.")
    if not adset.optimization_goal:
        errors.append(f"{prefix} Optimization goal is required.")
    if not adset.billing_event:
        errors.append(f"{prefix} Billing event is required.")
    if adset.daily_budget is not None and adset.lifetime_budget is not None:
        errors.append(f"{prefix} Cannot set both daily budget and lifetime budget.")

    targeting = adset.targeting
    if not targeting or not targeting.get("geo_locations", {}).get("countries"):
        errors.append(f"{prefix} Targeting must include at least one country.")

    if not adset.ads:
        errors.append(f"{prefix} At least one Ad is required.")

    for ad in adset.ads:
        errors.extend(validate_ad(ad, adset_prefix=prefix))

    return errors


def validate_ad(ad: AdData, adset_prefix: str = "") -> list[str]:
    errors = []
    prefix = f"{adset_prefix}[Ad '{ad.name or '(unnamed)'}']"

    if not ad.name.strip():
        errors.append(f"{prefix} Name is required.")

    errors.extend(validate_creative(ad.creative, ad_prefix=prefix))
    return errors


def validate_creative(creative: CreativeData, ad_prefix: str = "") -> list[str]:
    errors = []
    prefix = f"{ad_prefix}[Creative]"

    if creative.ad_format == AdFormat.SINGLE_IMAGE:
        if not creative.media_path and not creative.fb_image_hash:
            errors.append(f"{prefix} An image must be selected.")
        if not creative.link_url.strip():
            errors.append(f"{prefix} Link URL is required.")

    elif creative.ad_format == AdFormat.SINGLE_VIDEO:
        if not creative.media_path and not creative.fb_video_id:
            errors.append(f"{prefix} A video must be selected.")
        if not creative.link_url.strip():
            errors.append(f"{prefix} Link URL is required.")

    elif creative.ad_format == AdFormat.CAROUSEL:
        if len(creative.carousel_cards) < 2:
            errors.append(f"{prefix} Carousel requires at least 2 cards.")
        for i, card in enumerate(creative.carousel_cards, 1):
            if not card.media_path and not card.fb_image_hash and not card.fb_video_id:
                errors.append(f"{prefix} Card {i}: Media is required.")
            if not card.link_url.strip():
                errors.append(f"{prefix} Card {i}: Link URL is required.")

    return errors
