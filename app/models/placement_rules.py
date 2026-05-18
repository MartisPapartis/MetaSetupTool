"""Placement asset customization rules.

Each rule maps a media dimension (width x height in pixels) to the Meta
placement positions that should receive that creative.  The upload worker
reads PLACEMENT_RULES at runtime to build asset_customization_rules inside
asset_feed_spec.

Edit PLACEMENT_RULES to match your actual creative specifications.
"""

from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class PlacementRule:
    width: int
    height: int
    # Keys: Meta publisher platform names ("facebook", "instagram", "audience_network")
    # Values: list of position names valid for that platform
    positions: dict[str, list[str]]
    label: str = ""  # Human-readable description, used in log messages

    def matches(self, width: int, height: int) -> bool:
        return self.width == width and self.height == height

    def customization_spec(self) -> dict:
        """Return the customization_spec fragment expected by the Meta API."""
        spec: dict = {}
        platform_position_keys = {
            "facebook": "facebook_positions",
            "instagram": "instagram_positions",
            "audience_network": "audience_network_positions",
            "messenger": "messenger_positions",
        }
        publisher_platforms = []
        for platform, positions in self.positions.items():
            if positions:
                publisher_platforms.append(platform)
                key = platform_position_keys.get(platform, f"{platform}_positions")
                spec[key] = positions
        spec["publisher_platforms"] = publisher_platforms
        return spec


# ---------------------------------------------------------------------------
# Edit this list to define your dimension → placement rules.
# Rules are evaluated in order; the first match wins for each media file.
# ---------------------------------------------------------------------------

PLACEMENT_RULES: list[PlacementRule] = [
    PlacementRule(
        width=1080,
        height=1080,
        positions={
            "facebook": ["feed", "instream_video", "marketplace", "profile_feed", "notification"],
            "instagram": ["stream", "explore_home", "profile_feed"],
        },
        label="1080x1080 — Facebook Feed + Instagram Feed",
    ),
    PlacementRule(
        width=1080,
        height=1920,
        positions={
            "facebook": ["story", "facebook_reels"],
            "instagram": ["story", "reels", "ig_search"],
            "audience_network": ["classic", "rewarded_video"],
            "messenger": ["story"],
        },
        label="1080x1920 — Facebook Stories + Instagram Stories/Reels",
    ),
    PlacementRule(
        width=1200,
        height=628,
        positions={
            "facebook": ["search", "right_hand_column"],
        },
        label="1200x628 — Facebook Search + Right Column",
    ),
]


def match_rule(width: int, height: int) -> PlacementRule | None:
    """Return the first rule whose dimensions match, or None."""
    for rule in PLACEMENT_RULES:
        if rule.matches(width, height):
            return rule
    return None
