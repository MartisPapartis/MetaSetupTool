"""Command pattern for undo/redo support."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.models.campaign_data import SessionData, CampaignData, AdSetData, AdData


@dataclass
class AdSetMoveContext:
    """Captures source/destination for a MoveAdSetCommand."""
    from_campaign: CampaignData
    to_campaign: CampaignData
    from_index: int
    to_index: int


@dataclass
class AdMoveContext:
    """Captures source/destination for a MoveAdCommand."""
    from_adset: AdSetData
    to_adset: AdSetData
    from_index: int
    to_index: int


class Command(ABC):
    select_id: str = ""
    undo_select_id: str = ""

    @abstractmethod
    def execute(self) -> None: ...

    @abstractmethod
    def undo(self) -> None: ...

    @property
    @abstractmethod
    def description(self) -> str: ...


class CommandHistory:
    def __init__(self, max_size: int = 100):
        self._undo_stack: list[Command] = []
        self._redo_stack: list[Command] = []
        self._max_size = max_size

    def push(self, command: Command) -> None:
        """Execute and record a command."""
        command.execute()
        self._undo_stack.append(command)
        self._redo_stack.clear()
        if len(self._undo_stack) > self._max_size:
            self._undo_stack.pop(0)

    def record(self, command: Command) -> None:
        """Record a command that was already executed externally."""
        self._undo_stack.append(command)
        self._redo_stack.clear()
        if len(self._undo_stack) > self._max_size:
            self._undo_stack.pop(0)

    def undo(self) -> Command | None:
        if not self._undo_stack:
            return None
        cmd = self._undo_stack.pop()
        cmd.undo()
        self._redo_stack.append(cmd)
        return cmd

    def redo(self) -> Command | None:
        if not self._redo_stack:
            return None
        cmd = self._redo_stack.pop()
        cmd.execute()
        self._undo_stack.append(cmd)
        return cmd

    def clear(self) -> None:
        self._undo_stack.clear()
        self._redo_stack.clear()

    @property
    def can_undo(self) -> bool:
        return bool(self._undo_stack)

    @property
    def can_redo(self) -> bool:
        return bool(self._redo_stack)

    @property
    def undo_description(self) -> str:
        return self._undo_stack[-1].description if self._undo_stack else ""

    @property
    def redo_description(self) -> str:
        return self._redo_stack[-1].description if self._redo_stack else ""


# ── Structural add commands ────────────────────────────────────────────────────

class AddCampaignCommand(Command):
    def __init__(self, session: SessionData, campaign: CampaignData):
        self._session = session
        self._campaign = campaign
        self.select_id = campaign.id
        self.undo_select_id = ""

    def execute(self) -> None:
        if self._campaign not in self._session.campaigns:
            self._session.campaigns.append(self._campaign)

    def undo(self) -> None:
        self._session.campaigns = [c for c in self._session.campaigns if c.id != self._campaign.id]

    @property
    def description(self) -> str:
        return f'Add Campaign "{self._campaign.name}"'


class AddAdSetCommand(Command):
    def __init__(self, campaign: CampaignData, adset: AdSetData):
        self._campaign = campaign
        self._adset = adset
        self.select_id = adset.id
        self.undo_select_id = campaign.id

    def execute(self) -> None:
        if self._adset not in self._campaign.ad_sets:
            self._campaign.ad_sets.append(self._adset)

    def undo(self) -> None:
        self._campaign.ad_sets = [a for a in self._campaign.ad_sets if a.id != self._adset.id]

    @property
    def description(self) -> str:
        return f'Add Ad Set "{self._adset.name}"'


class AddAdCommand(Command):
    def __init__(self, adset: AdSetData, ad: AdData):
        self._adset = adset
        self._ad = ad
        self.select_id = ad.id
        self.undo_select_id = adset.id

    def execute(self) -> None:
        if self._ad not in self._adset.ads:
            self._adset.ads.append(self._ad)

    def undo(self) -> None:
        self._adset.ads = [a for a in self._adset.ads if a.id != self._ad.id]

    @property
    def description(self) -> str:
        return f'Add Ad "{self._ad.name}"'


# ── Remove commands ────────────────────────────────────────────────────────────

class RemoveCampaignCommand(Command):
    def __init__(self, session: SessionData, campaign: CampaignData):
        self._session = session
        self._campaign = campaign
        self._index = session.campaigns.index(campaign)
        self.select_id = ""
        self.undo_select_id = campaign.id

    def execute(self) -> None:
        self._session.campaigns = [c for c in self._session.campaigns if c.id != self._campaign.id]

    def undo(self) -> None:
        idx = min(self._index, len(self._session.campaigns))
        self._session.campaigns.insert(idx, self._campaign)

    @property
    def description(self) -> str:
        return f'Remove Campaign "{self._campaign.name}"'


class RemoveAdSetCommand(Command):
    def __init__(self, campaign: CampaignData, adset: AdSetData):
        self._campaign = campaign
        self._adset = adset
        self._index = campaign.ad_sets.index(adset)
        self.select_id = ""
        self.undo_select_id = adset.id

    def execute(self) -> None:
        self._campaign.ad_sets = [a for a in self._campaign.ad_sets if a.id != self._adset.id]

    def undo(self) -> None:
        idx = min(self._index, len(self._campaign.ad_sets))
        self._campaign.ad_sets.insert(idx, self._adset)

    @property
    def description(self) -> str:
        return f'Remove Ad Set "{self._adset.name}"'


class RemoveAdCommand(Command):
    def __init__(self, adset: AdSetData, ad: AdData):
        self._adset = adset
        self._ad = ad
        self._index = adset.ads.index(ad)
        self.select_id = ""
        self.undo_select_id = ad.id

    def execute(self) -> None:
        self._adset.ads = [a for a in self._adset.ads if a.id != self._ad.id]

    def undo(self) -> None:
        idx = min(self._index, len(self._adset.ads))
        self._adset.ads.insert(idx, self._ad)

    @property
    def description(self) -> str:
        return f'Remove Ad "{self._ad.name}"'


class BatchRemoveCommand(Command):
    """Wraps multiple remove commands into one undoable unit."""

    def __init__(self, commands: list[Command]):
        self._commands = commands
        self.select_id = ""
        self.undo_select_id = commands[0].undo_select_id if commands else ""

    def execute(self) -> None:
        for cmd in self._commands:
            cmd.execute()

    def undo(self) -> None:
        for cmd in reversed(self._commands):
            cmd.undo()

    @property
    def description(self) -> str:
        return f"Remove {len(self._commands)} items"


# ── Duplicate commands ─────────────────────────────────────────────────────────

class DuplicateCampaignCommand(Command):
    def __init__(self, session: SessionData, duplicate: CampaignData):
        self._session = session
        self._duplicate = duplicate
        self.select_id = duplicate.id
        self.undo_select_id = ""

    def execute(self) -> None:
        if self._duplicate not in self._session.campaigns:
            self._session.campaigns.append(self._duplicate)

    def undo(self) -> None:
        self._session.campaigns = [c for c in self._session.campaigns if c.id != self._duplicate.id]

    @property
    def description(self) -> str:
        return f'Duplicate Campaign "{self._duplicate.name}"'


class DuplicateAdSetCommand(Command):
    def __init__(self, campaign: CampaignData, duplicate: AdSetData):
        self._campaign = campaign
        self._duplicate = duplicate
        self.select_id = duplicate.id
        self.undo_select_id = campaign.id

    def execute(self) -> None:
        if self._duplicate not in self._campaign.ad_sets:
            self._campaign.ad_sets.append(self._duplicate)

    def undo(self) -> None:
        self._campaign.ad_sets = [a for a in self._campaign.ad_sets if a.id != self._duplicate.id]

    @property
    def description(self) -> str:
        return f'Duplicate Ad Set "{self._duplicate.name}"'


class DuplicateAdCommand(Command):
    def __init__(self, adset: AdSetData, duplicate: AdData):
        self._adset = adset
        self._duplicate = duplicate
        self.select_id = duplicate.id
        self.undo_select_id = adset.id

    def execute(self) -> None:
        if self._duplicate not in self._adset.ads:
            self._adset.ads.append(self._duplicate)

    def undo(self) -> None:
        self._adset.ads = [a for a in self._adset.ads if a.id != self._duplicate.id]

    @property
    def description(self) -> str:
        return f'Duplicate Ad "{self._duplicate.name}"'


# ── Move commands ─────────────────────────────────────────────────────────────

class MoveAdSetCommand(Command):
    def __init__(self, adset: AdSetData, ctx: AdSetMoveContext):
        self._adset = adset
        self._ctx = ctx
        self.select_id = adset.id
        self.undo_select_id = adset.id

    def execute(self) -> None:
        if self._adset in self._ctx.from_campaign.ad_sets:
            self._ctx.from_campaign.ad_sets.remove(self._adset)
        idx = min(self._ctx.to_index, len(self._ctx.to_campaign.ad_sets))
        self._ctx.to_campaign.ad_sets.insert(idx, self._adset)

    def undo(self) -> None:
        if self._adset in self._ctx.to_campaign.ad_sets:
            self._ctx.to_campaign.ad_sets.remove(self._adset)
        idx = min(self._ctx.from_index, len(self._ctx.from_campaign.ad_sets))
        self._ctx.from_campaign.ad_sets.insert(idx, self._adset)

    @property
    def description(self) -> str:
        return f'Move Ad Set "{self._adset.name}"'


class MoveAdCommand(Command):
    def __init__(self, ad: AdData, ctx: AdMoveContext):
        self._ad = ad
        self._ctx = ctx
        self.select_id = ad.id
        self.undo_select_id = ad.id

    def execute(self) -> None:
        if self._ad in self._ctx.from_adset.ads:
            self._ctx.from_adset.ads.remove(self._ad)
        idx = min(self._ctx.to_index, len(self._ctx.to_adset.ads))
        self._ctx.to_adset.ads.insert(idx, self._ad)

    def undo(self) -> None:
        if self._ad in self._ctx.to_adset.ads:
            self._ctx.to_adset.ads.remove(self._ad)
        idx = min(self._ctx.from_index, len(self._ctx.from_adset.ads))
        self._ctx.from_adset.ads.insert(idx, self._ad)

    @property
    def description(self) -> str:
        return f'Move Ad "{self._ad.name}"'


# ── Rename command ─────────────────────────────────────────────────────────────

class RenameNodeCommand(Command):
    def __init__(self, obj, old_name: str, new_name: str):
        self._obj = obj
        self._old_name = old_name
        self._new_name = new_name
        self.select_id = obj.id
        self.undo_select_id = obj.id

    def execute(self) -> None:
        self._obj.name = self._new_name

    def undo(self) -> None:
        self._obj.name = self._old_name

    @property
    def description(self) -> str:
        return f'Rename to "{self._new_name}"'
