"""Update existing campaigns, ad sets, ads, and creatives via Meta API."""

from __future__ import annotations
import json

from app.api.client import MetaApiClient
from app.api.campaign_api import create_ad_creative, _build_campaign_budget_payload
from app.models.campaign_data import CampaignData, AdSetData, AdData, CreativeData


def update_campaign(
    client: MetaApiClient,
    campaign: CampaignData,
    validate_only: bool = False,
) -> None:
    """Update an existing campaign (POST /{campaign_id})."""
    payload: dict = {
        "name": campaign.name,
        "status": campaign.status.value,
        "special_ad_categories": json.dumps(campaign.special_ad_categories),
    }
    payload.update(_build_campaign_budget_payload(campaign))
    if validate_only:
        payload["execution_options"] = '["validate_only"]'
    client.post(campaign.fb_campaign_id, data=payload)


def update_adset(
    client: MetaApiClient,
    adset: AdSetData,
    validate_only: bool = False,
) -> None:
    """Update an existing ad set (POST /{adset_id})."""
    payload: dict = {
        "name": adset.name,
        "status": adset.status.value,
        "optimization_goal": adset.optimization_goal.value,
        "billing_event": adset.billing_event.value,
        "bid_strategy": adset.bid_strategy.value,
    }

    if adset.daily_budget is not None:
        payload["daily_budget"] = str(adset.daily_budget)
    if adset.lifetime_budget is not None:
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

    payload["use_dynamic_creative"] = "true" if adset.use_dynamic_creative else "false"

    if adset.promoted_object:
        payload["promoted_object"] = json.dumps(adset.promoted_object)

    if validate_only:
        payload["execution_options"] = '["validate_only"]'
    client.post(adset.fb_adset_id, data=payload)


def update_ad(
    client: MetaApiClient,
    ad: AdData,
    _page_id: str,
    new_creative_id: str | None = None,
    validate_only: bool = False,
) -> None:
    """Update an existing ad (POST /{ad_id}).

    If *new_creative_id* is provided, the ad's creative reference is swapped.
    Creative content itself is immutable — callers must create a new creative
    first and pass its ID here.
    """
    payload: dict = {
        "name": ad.name,
        "status": ad.status.value,
    }
    if new_creative_id:
        payload["creative"] = json.dumps({"creative_id": new_creative_id})
    if validate_only:
        payload["execution_options"] = '["validate_only"]'
    client.post(ad.fb_ad_id, data=payload)


def recreate_creative(
    client: MetaApiClient,
    creative: CreativeData,
    page_id: str,
    instagram_user_id: str = "",
    use_dynamic_creative: bool = False,
    validate_only: bool = False,
) -> str:
    """Create a new creative (content is immutable) and return the new ID."""
    new_id = create_ad_creative(
        client, creative, page_id,
        instagram_user_id=instagram_user_id,
        use_dynamic_creative=use_dynamic_creative,
        validate_only=validate_only,
    )
    if not validate_only:
        creative.fb_creative_id = new_id
    return new_id
