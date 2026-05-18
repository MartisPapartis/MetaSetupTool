"""Excel import — reads campaign data from a spreadsheet template.

The expected sheet layout (row 1 = headers):
  Campaign Name | Campaign Objective | Ad Set Name | Daily Budget (EUR) |
  Start Date | End Date | Ad Name | Headline | Body | Link URL

Returns a list of CampaignData objects with nested AdSetData and AdData.
Creative media must be assigned manually after import.
"""

from __future__ import annotations

import datetime

from app.models.campaign_data import CampaignData, AdSetData, AdData, CreativeData, default_ad_name
from app.models.enums import AdFormat, AdObjective, AdStatus, OptimizationGoal, BillingEvent


def _date_only(val) -> str:
    """Extract a YYYY-MM-DD string from a cell value (datetime or string)."""
    if val is None:
        return ""
    if isinstance(val, datetime.datetime):
        return val.strftime("%Y-%m-%d")
    if isinstance(val, datetime.date):
        return val.strftime("%Y-%m-%d")
    # String — strip any existing time portion
    return str(val).strip().split(" ", maxsplit=1)[0].split("T", maxsplit=1)[0]


def _raw_cell(row, headers, col_name: str):
    """Return the raw cell value (preserving datetime type)."""
    try:
        idx = headers.index(col_name)
        return row[idx]
    except (ValueError, IndexError):
        return None


def _cell(row, headers, col_name: str) -> str:
    try:
        idx = headers.index(col_name)
        val = row[idx]
        return str(val).strip() if val is not None else ""
    except ValueError:
        return ""


def _format_start(row, headers) -> str:
    val = _raw_cell(row, headers, "start date")
    date_str = _date_only(val)
    return f"{date_str} 00:00:00" if date_str else ""


def _format_end(row, headers) -> str:
    val = _raw_cell(row, headers, "end date")
    date_str = _date_only(val)
    return f"{date_str} 23:59:59" if date_str else ""


def _get_or_create_campaign(campaigns: dict, row, headers) -> CampaignData | None:
    campaign_name = _cell(row, headers, "campaign name")
    if not campaign_name:
        return None
    if campaign_name not in campaigns:
        obj_str = _cell(row, headers, "campaign objective").upper()
        try:
            objective = AdObjective(obj_str)  # pylint: disable=no-value-for-parameter
        except ValueError:
            objective = AdObjective.OUTCOME_TRAFFIC
        campaigns[campaign_name] = CampaignData(
            name=campaign_name,
            objective=objective,
            status=AdStatus.PAUSED,
        )
    return campaigns[campaign_name]


def _get_or_create_adset(campaign: CampaignData, row, headers) -> AdSetData | None:
    adset_name = _cell(row, headers, "ad set name")
    if not adset_name:
        return None
    adset = next((a for a in campaign.ad_sets if a.name == adset_name), None)
    if adset is None:
        budget_str = _cell(row, headers, "daily budget (eur)")
        try:
            budget_cents = int(float(budget_str) * 100)
        except (ValueError, TypeError):
            budget_cents = None
        adset = AdSetData(
            name=adset_name,
            status=AdStatus.PAUSED,
            optimization_goal=OptimizationGoal.LINK_CLICKS,
            billing_event=BillingEvent.IMPRESSIONS,
            daily_budget=budget_cents,
            start_time=_format_start(row, headers),
            end_time=_format_end(row, headers),
        )
        campaign.ad_sets.append(adset)
    return adset


def _process_excel_row(row, headers, campaigns: dict) -> None:
    if not any(row):
        return
    campaign = _get_or_create_campaign(campaigns, row, headers)
    if campaign is None:
        return
    adset = _get_or_create_adset(campaign, row, headers)
    if adset is None:
        return
    if _cell(row, headers, "ad name"):
        creative = CreativeData(
            headline=_cell(row, headers, "headline"),
            body=_cell(row, headers, "body"),
            link_url=_cell(row, headers, "link url"),
            link_utm=_cell(row, headers, "link utm"),
        )
        adset.ads.append(AdData(
            name=default_ad_name(AdFormat.SINGLE_IMAGE),
            status=AdStatus.PAUSED,
            creative=creative,
        ))


def read_campaigns_from_excel(path: str) -> list[CampaignData]:
    """Parse an Excel file and return a list of CampaignData objects."""
    try:
        import openpyxl
    except ImportError as exc:
        raise RuntimeError("openpyxl is not installed. Run: pip install openpyxl") from exc

    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return []

    headers = [str(h).strip().lower() if h else "" for h in rows[0]]
    campaigns: dict[str, CampaignData] = {}
    for row in rows[1:]:
        _process_excel_row(row, headers, campaigns)
    return list(campaigns.values())
