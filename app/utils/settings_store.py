"""Stores API credentials in a JSON file in the user's home directory."""

from __future__ import annotations
import json
from pathlib import Path

_SETTINGS_DIR = Path.home() / ".metasetuptool"
_SETTINGS_FILE = _SETTINGS_DIR / "settings.json"

_DEFAULTS = {
    "access_token": "",
    "api_version": "v25.0",
    # Legacy single-value fields (kept for backward compat on load)
    "ad_account_id": "",
    "page_id": "",
    # New list fields: each entry is {"id": "...", "label": "..."}
    "ad_accounts": [],
    "pages": [],
    "instagram_accounts": [],
}


class SettingsStore:
    def load(self) -> dict:
        if not _SETTINGS_FILE.exists():
            return dict(_DEFAULTS)
        try:
            with open(_SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            merged = {**_DEFAULTS, **data}
            # Migrate legacy single values into lists if lists are empty
            if not merged.get("ad_accounts") and merged.get("ad_account_id"):
                merged["ad_accounts"] = [
                    {"id": merged["ad_account_id"], "label": merged["ad_account_id"]}
                ]
            if not merged.get("pages") and merged.get("page_id"):
                merged["pages"] = [
                    {"id": merged["page_id"], "label": merged["page_id"]}
                ]
            return merged
        except (OSError, ValueError):
            return dict(_DEFAULTS)

    def save(self, settings: dict) -> None:
        _SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
        with open(_SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2)

    def get(self, key: str, default=None):
        return self.load().get(key, default)
